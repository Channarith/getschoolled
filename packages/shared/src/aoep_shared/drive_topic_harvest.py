"""Drive Mode content harvester.

Enriches each knowledge topic from ~4 minutes (11 segments, 523 words) to
≥30 minutes (28 authored segments × ~125 words = ~3,500 words + wrappers).

Pipeline per topic
──────────────────
1.  Fetch the Wikipedia article via the public REST API (no key required).
2.  Optionally pull 1–2 linked sub-articles for extra depth.
3.  Call the LLM to synthesise TARGET_SEGMENTS rich, conversational audio
    segments from the extracted text.  Each segment is ~120–130 words,
    driving-safe (no visual references, no lists, spoken in plain prose).
4.  Persist the result to a SQLite cache so subsequent calls are instant.

Fallback chain
──────────────
Wikipedia unavailable  → use the existing 9 hardcoded sections as source text
LLM unavailable        → expand sections by stitching Wikipedia summary text
                         without LLM synthesis (still much richer than 3 sentences)

CLI
───
    python -m aoep_shared.drive_topic_harvest --topic "Ancient Egypt"
    python -m aoep_shared.drive_topic_harvest --all [--workers 4]
    python -m aoep_shared.drive_topic_harvest --list   # show cached topics
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import List, Optional, Tuple

from .audio_topic_data import TOPIC_SECTIONS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
TARGET_SEGMENTS = 28          # authored segments per topic (+ 2 wrappers = 30)
TARGET_WORDS_PER_SEGMENT = 125  # ≈125 words × 28 segs = 3,500 words ≈ 29 min
MIN_SEGMENTS_TO_ACCEPT = 20   # reject LLM response if it returns fewer sections
WIKIPEDIA_RPS = 2.0           # Wikipedia asks for ≤200/s; 2 is very polite

_WIKI_LAST_FETCH = 0.0
_DEFAULT_DB_PATH = Path(os.environ.get(
    "DRIVE_CONTENT_DB",
    Path(__file__).parent / "data" / "drive_content_cache.db",
))


# ---------------------------------------------------------------------------
# SQLite cache
# ---------------------------------------------------------------------------
def _db(path: Path = _DEFAULT_DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.execute("""
        CREATE TABLE IF NOT EXISTS drive_segments (
            topic       TEXT NOT NULL,
            version     INTEGER NOT NULL DEFAULT 1,
            created_at  TEXT NOT NULL,
            segments_json TEXT NOT NULL,
            word_count  INTEGER NOT NULL,
            PRIMARY KEY (topic, version)
        )
    """)
    con.commit()
    return con


def get_cached_segments(topic: str, *, version: int = 1) -> Optional[List[Tuple[str, str]]]:
    """Return cached ``[(heading, text), …]`` for *topic*, or ``None``."""
    try:
        con = _db()
        row = con.execute(
            "SELECT segments_json FROM drive_segments WHERE topic=? AND version=?",
            (topic, version),
        ).fetchone()
        if row:
            return json.loads(row[0])
    except Exception as exc:
        logger.warning("drive_content_cache read error: %s", exc)
    return None


def save_segments(topic: str, segments: List[Tuple[str, str]], *, version: int = 1) -> None:
    """Persist ``segments`` for *topic* to the SQLite cache."""
    word_count = sum(len(t.split()) for _, t in segments)
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        con = _db()
        con.execute(
            """INSERT OR REPLACE INTO drive_segments
               (topic, version, created_at, segments_json, word_count)
               VALUES (?,?,?,?,?)""",
            (topic, version, ts, json.dumps(segments), word_count),
        )
        con.commit()
    except Exception as exc:
        logger.warning("drive_content_cache write error: %s", exc)


# ---------------------------------------------------------------------------
# Wikipedia fetch
# ---------------------------------------------------------------------------
def _wiki_rate_limit() -> None:
    global _WIKI_LAST_FETCH
    gap = 1.0 / WIKIPEDIA_RPS
    wait = gap - (time.monotonic() - _WIKI_LAST_FETCH)
    if wait > 0:
        time.sleep(wait)
    _WIKI_LAST_FETCH = time.monotonic()


_UA = "AOEP-DriveHarvester/1.0 (getschoolled; drive-mode audio courses; educational)"


def _wiki_get(url: str, *, timeout: int = 20) -> dict:
    _wiki_rate_limit()
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch_wikipedia_sections(topic: str) -> List[Tuple[str, str]]:
    """Return ``[(section_title, plain_text), …]`` from the Wikipedia article
    for *topic*.  Uses the public extracts API (no key required).

    Falls back to an empty list on any error so callers degrade gracefully.
    """
    title = urllib.parse.quote(topic.replace(" ", "_"))
    url = (
        f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts"
        f"&explaintext=true&exsectionformat=plain&titles={title}"
        f"&format=json&exlimit=1&redirects=1"
    )
    try:
        data = _wiki_get(url)
        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return []
        page = next(iter(pages.values()))
        extract: str = page.get("extract", "") or ""
        if not extract.strip():
            return []
        return _parse_wiki_extract(extract)
    except Exception as exc:
        logger.warning("Wikipedia fetch failed for %r: %s", topic, exc)
        return []


def _parse_wiki_extract(extract: str) -> List[Tuple[str, str]]:
    """Split a Wikipedia plain-text extract into ``(heading, paragraphs)`` pairs."""
    # Wikipedia section headings appear as lines of the form:
    #   == Section Title ==
    #   === Subsection ===
    sections: List[Tuple[str, str]] = []
    current_heading = "Introduction"
    buf: List[str] = []

    for line in extract.splitlines():
        m = re.match(r"^(={2,4})\s*(.+?)\s*\1$", line)
        if m:
            text = " ".join(buf).strip()
            if text:
                sections.append((current_heading, text))
            current_heading = m.group(2)
            buf = []
        else:
            stripped = line.strip()
            if stripped:
                buf.append(stripped)

    text = " ".join(buf).strip()
    if text:
        sections.append((current_heading, text))

    # Drop boilerplate-only sections (References, See also, etc.)
    skip = re.compile(
        r"^(references?|see also|further reading|external links?|"
        r"notes?|bibliography|footnotes?|sources?)$",
        re.I,
    )
    return [(h, t) for h, t in sections if not skip.match(h.strip()) and len(t.split()) >= 30]


# ---------------------------------------------------------------------------
# LLM synthesis
# ---------------------------------------------------------------------------
_SYNTHESIS_SYSTEM = (
    "You are an educational audio scriptwriter. "
    "Your job: convert encyclopaedia text into a spoken-word audio course "
    "that a driver can follow without looking at a screen. "
    "Rules: no bullet points, no numbered lists, no markdown, no phrases like "
    "'as shown in the diagram', 'see the table', or 'in the figure above'. "
    "Write in clear, engaging prose. Each paragraph should flow naturally when read aloud."
)

_SYNTHESIS_USER_TMPL = """
Topic: {topic}

Source material (Wikipedia extract — use this as your factual basis):
---
{source_text}
---

Task: Write EXACTLY {n_segments} audio segments for a {target_min}-minute driving course on "{topic}".

FORMAT — output every segment like this (and nothing else):

SECTION: <concise heading, 2–6 words>
<Exactly one paragraph, {words_per_seg}–{words_per_seg_hi} words, in plain prose. No lists, no markdown.>
---

Requirements:
- Cover the topic comprehensively from history/origins through modern relevance.
- Each segment must be self-contained and flow logically from the previous.
- Spoken register: warm, authoritative, accessible to a curious adult.
- No visual references. Treat the listener as if they have no screen.
- Factual accuracy: derive all claims from the source material above.
- Output EXACTLY {n_segments} SECTION blocks, no more, no fewer.
""".strip()


def synthesise_segments_with_llm(
    topic: str,
    source_sections: List[Tuple[str, str]],
    *,
    llm,
    n_segments: int = TARGET_SEGMENTS,
    words_per_segment: int = TARGET_WORDS_PER_SEGMENT,
    target_minutes: int = 30,
) -> Optional[List[Tuple[str, str]]]:
    """Call the LLM to produce *n_segments* rich audio segments.

    Returns ``None`` if the LLM is unavailable or the response is malformed.
    """
    source_text = _flatten_sections(source_sections, max_words=6000)
    if not source_text.strip():
        return None

    prompt = _SYNTHESIS_USER_TMPL.format(
        topic=topic,
        source_text=source_text,
        n_segments=n_segments,
        target_min=target_minutes,
        words_per_seg=words_per_segment - 10,
        words_per_seg_hi=words_per_segment + 15,
    )

    from .providers.base import ChatMessage
    messages = [
        ChatMessage(role="system", content=_SYNTHESIS_SYSTEM),
        ChatMessage(role="user", content=prompt),
    ]
    try:
        completion = llm.complete(
            messages,
            temperature=0.4,
            max_tokens=n_segments * (words_per_segment + 30) * 2,
        )
        return _parse_llm_segments(completion.text)
    except Exception as exc:
        logger.warning("LLM synthesis failed for %r: %s", topic, exc)
        return None


def _flatten_sections(sections: List[Tuple[str, str]], *, max_words: int = 6000) -> str:
    """Concatenate sections into a single block, truncating at *max_words*."""
    parts: List[str] = []
    total = 0
    for heading, text in sections:
        chunk = f"{heading}:\n{text}"
        words = len(chunk.split())
        if total + words > max_words:
            # Include a partial section so the LLM sees a continuous flow
            remaining = max_words - total
            if remaining > 50:
                parts.append(" ".join(chunk.split()[:remaining]))
            break
        parts.append(chunk)
        total += words
    return "\n\n".join(parts)


def _parse_llm_segments(raw: str) -> Optional[List[Tuple[str, str]]]:
    """Parse ``SECTION: heading\\ntext\\n---`` blocks from the LLM response."""
    segments: List[Tuple[str, str]] = []
    # Split on the "---" delimiter, tolerating minor whitespace variation.
    blocks = re.split(r"\n\s*---\s*\n?", raw.strip())
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        # Extract "SECTION: <heading>" line
        m = re.match(r"^SECTION:\s*(.+?)\n(.*)", block, re.DOTALL | re.IGNORECASE)
        if not m:
            continue
        heading = m.group(1).strip()
        text = m.group(2).strip()
        if not heading or not text or len(text.split()) < 20:
            continue
        segments.append((heading, text))

    if len(segments) < MIN_SEGMENTS_TO_ACCEPT:
        logger.warning(
            "LLM returned only %d segments (min %d) — discarding",
            len(segments), MIN_SEGMENTS_TO_ACCEPT,
        )
        return None
    return segments


# ---------------------------------------------------------------------------
# Expand hardcoded sections without LLM (Wikipedia text only)
# ---------------------------------------------------------------------------
def expand_from_wikipedia_only(
    topic: str,
    wiki_sections: List[Tuple[str, str]],
    hardcoded_sections: List[Tuple[str, str]],
) -> List[Tuple[str, str]]:
    """Build rich segments without an LLM by stitching Wikipedia text.

    Targets TARGET_SEGMENTS sections of ~TARGET_WORDS_PER_SEGMENT words each.
    The approach: split each Wikipedia section into ~125-word chunks, label
    them with the section heading, and pad shorter sections with the
    corresponding hardcoded text so nothing is left factually thin.
    """
    chunks: List[Tuple[str, str]] = []
    for heading, text in wiki_sections:
        words = text.split()
        step = TARGET_WORDS_PER_SEGMENT
        if len(words) < 40:
            continue
        for start in range(0, len(words), step):
            chunk = " ".join(words[start : start + step])
            if len(chunk.split()) < 40:
                break
            chunk_heading = heading if start == 0 else f"{heading} (continued)"
            chunks.append((chunk_heading, chunk))
        if len(chunks) >= TARGET_SEGMENTS * 2:
            break

    # If Wikipedia gave us too little, blend in the hardcoded sections
    if len(chunks) < TARGET_SEGMENTS:
        for heading, text in hardcoded_sections:
            expanded = " ".join(text.replace("\n", " ").split())
            chunks.append((heading, expanded))

    # Trim or pad to exactly TARGET_SEGMENTS
    if len(chunks) > TARGET_SEGMENTS:
        chunks = chunks[:TARGET_SEGMENTS]

    return chunks if len(chunks) >= MIN_SEGMENTS_TO_ACCEPT else []


# ---------------------------------------------------------------------------
# Main harvest entry point
# ---------------------------------------------------------------------------
def harvest_topic(
    topic: str,
    *,
    llm=None,
    force: bool = False,
    version: int = 1,
) -> List[Tuple[str, str]]:
    """Return rich ``[(heading, text), …]`` for *topic*, harvesting if needed.

    Result is cached in SQLite.  Pass ``force=True`` to re-harvest even if a
    cached result exists.
    """
    if not force:
        cached = get_cached_segments(topic, version=version)
        if cached and len(cached) >= MIN_SEGMENTS_TO_ACCEPT:
            logger.debug("drive_content cache hit: %r (%d segs)", topic, len(cached))
            return cached

    logger.info("Harvesting drive content for %r …", topic)

    # Step 1 — Wikipedia
    wiki_sections = fetch_wikipedia_sections(topic)
    logger.info("  Wikipedia: %d sections fetched for %r", len(wiki_sections), topic)

    # Step 2 — Hardcoded fallback source
    hardcoded = TOPIC_SECTIONS.get(topic, [])

    # Step 3 — LLM synthesis (preferred) or Wikipedia-only expansion
    segments: List[Tuple[str, str]] = []
    if llm is not None and wiki_sections:
        source = wiki_sections if wiki_sections else [(h, t) for h, t in hardcoded]
        synthesised = synthesise_segments_with_llm(topic, source, llm=llm)
        if synthesised and len(synthesised) >= MIN_SEGMENTS_TO_ACCEPT:
            segments = synthesised
            logger.info(
                "  LLM synthesis: %d segments, ~%d words",
                len(segments), sum(len(t.split()) for _, t in segments),
            )

    if not segments and wiki_sections:
        segments = expand_from_wikipedia_only(topic, wiki_sections, hardcoded)
        logger.info("  Wikipedia-only expansion: %d segments", len(segments))

    if not segments:
        # Last resort: expand the existing hardcoded sections inline
        segments = [(h, " ".join(t.replace("\n", " ").split())) for h, t in hardcoded]
        logger.info("  Hardcoded fallback: %d segments", len(segments))

    if segments:
        save_segments(topic, segments, version=version)

    return segments


# ---------------------------------------------------------------------------
# Integration helper used by audio_courses.py
# ---------------------------------------------------------------------------
def get_rich_segments(topic: str, *, llm=None) -> Optional[List[Tuple[str, str]]]:
    """Return harvested segments if available, triggering a harvest if the
    cache is empty and either Wikipedia or the LLM is reachable.

    Returns ``None`` when the result would be no richer than the hardcoded
    content (< MIN_SEGMENTS_TO_ACCEPT), so callers can fall back gracefully.
    """
    result = harvest_topic(topic, llm=llm)
    if result and len(result) >= MIN_SEGMENTS_TO_ACCEPT:
        return result
    return None


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _all_topics() -> List[str]:
    """Return every topic title from the knowledge course catalog."""
    from .audio_courses import _TOPICS  # avoid circular at module level
    return [t for topics in _TOPICS.values() for t in topics]


def _list_cached() -> None:
    try:
        con = _db()
        rows = con.execute(
            "SELECT topic, word_count, created_at FROM drive_segments ORDER BY topic"
        ).fetchall()
        if not rows:
            print("No cached topics.")
            return
        print(f"{'Topic':<40} {'Words':>6}  {'Cached at'}")
        print("-" * 65)
        for topic, wc, ts in rows:
            minutes = round(wc / 120)
            print(f"{topic:<40} {wc:>6}  {ts}  (~{minutes} min)")
    except Exception as exc:
        print(f"Error reading cache: {exc}")


def _main() -> None:
    import argparse
    from concurrent.futures import ThreadPoolExecutor, as_completed

    ap = argparse.ArgumentParser(description="Drive Mode content harvester")
    grp = ap.add_mutually_exclusive_group(required=True)
    grp.add_argument("--topic", metavar="NAME", help="Harvest one topic by name")
    grp.add_argument("--all", action="store_true", help="Harvest every topic in the catalog")
    grp.add_argument("--list", action="store_true", help="List cached topics")
    ap.add_argument("--workers", type=int, default=1,
                    help="Parallel workers for --all (default 1; Wikipedia is rate-limited)")
    ap.add_argument("--force", action="store_true", help="Re-harvest even if cached")
    ap.add_argument("--no-llm", action="store_true", help="Skip LLM; use Wikipedia text only")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    if args.list:
        _list_cached()
        return

    # Resolve LLM (optional)
    llm = None
    if not args.no_llm:
        try:
            from .config import load_config
            from .factory import ProviderFactory
            llm = ProviderFactory(load_config()).llm()
            logger.info("LLM provider ready: %s", llm.info())
        except Exception as exc:
            logger.warning("LLM unavailable (%s) — using Wikipedia-only mode", exc)

    topics = _all_topics() if args.all else [args.topic]

    def _run(topic: str) -> Tuple[str, int]:
        segs = harvest_topic(topic, llm=llm, force=args.force)
        wc = sum(len(t.split()) for _, t in segs)
        return topic, wc

    if args.workers > 1 and len(topics) > 1:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futs = {pool.submit(_run, t): t for t in topics}
            for fut in as_completed(futs):
                topic, wc = fut.result()
                minutes = round(wc / 120)
                print(f"✓ {topic:<45} {wc:>5} words  ~{minutes} min")
    else:
        for topic in topics:
            topic, wc = _run(topic)
            minutes = round(wc / 120)
            print(f"✓ {topic:<45} {wc:>5} words  ~{minutes} min")


if __name__ == "__main__":
    _main()
