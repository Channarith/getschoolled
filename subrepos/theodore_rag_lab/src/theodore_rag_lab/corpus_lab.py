"""Dictionary corpus ops for the Theodore RAG lab.

Wraps aoep_shared.dictionary_* so the lab console and CLIs can train-update,
review, export packs, and emit LLM training JSONL without paying APIs.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from aoep_shared.dictionary_corpus import (
    DictionaryEntry,
    approved_entries,
    dictionary_dir,
    ensure_layout,
    fingerprint_baselines,
    ingest_from_baseline_dir,
    load_review_queue,
    load_staging,
    merge_entries,
    read_fingerprint,
    route_entries,
    save_review_queue,
    save_staging,
    write_fingerprint,
)
from aoep_shared.dictionary_curriculum import build_curriculum, save_sentences
from aoep_shared.dictionary_feedback import DictionaryFeedbackStore


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for p in here.parents:
        if (p / "packages" / "shared").is_dir() and (p / "subrepos").is_dir():
            return p
    return here.parents[4]


def _fixtures_dir() -> Path:
    return _repo_root() / "packages" / "shared" / "tests" / "fixtures" / "dictionary"


def seed_baselines(*, root: Optional[Path] = None, force: bool = False) -> dict[str, Any]:
    base = ensure_layout(root or dictionary_dir())
    dest = base / "baselines"
    dest.mkdir(parents=True, exist_ok=True)
    fp = fingerprint_baselines(dest) if dest.is_dir() else ""
    prev = read_fingerprint(base)
    if force or not fp or fp != prev or not any(dest.glob("*")):
        fixtures = _fixtures_dir()
        copied = []
        for name in (
            "wordfreq_en.txt",
            "wordnet_glosses.txt",
            "cmudict.txt",
            "wiktionary_en.txt",
            "tatoeba.tsv",
            "khmer_vocab.json",
        ):
            src = fixtures / name
            if src.is_file():
                shutil.copy2(src, dest / name)
                copied.append(name)
        (dest / "LICENSES.txt").write_text(
            "Dictionary baseline cache — see docs/dictionary-corpus.txt\n",
            encoding="utf-8",
        )
        try:
            from aoep_shared.content_packs import load_records

            recs = [r for r in load_records("vocabulary") if r.get("language") == "km"]
            if recs:
                (dest / "khmer_vocab.json").write_text(
                    json.dumps(
                        {"pack": "khmer_from_content_packs", "records": recs},
                        ensure_ascii=False,
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
        except Exception:
            pass
        fp = fingerprint_baselines(dest)
        write_fingerprint(base, fp)
        return {"seeded": True, "copied": copied, "fingerprint": fp[:16]}
    return {"seeded": False, "fingerprint": fp[:16]}


def run_ingest_merge(*, root: Optional[Path] = None) -> dict[str, int]:
    base = ensure_layout(root or dictionary_dir())
    baseline_dir = base / "baselines"
    fresh = ingest_from_baseline_dir(baseline_dir)
    preserved: dict[tuple[str, str], DictionaryEntry] = {}
    for lang in ("en", "km"):
        for e in load_staging(base, lang):
            if e.review_status in ("approved", "rejected"):
                preserved[(lang, e.id)] = e
    by_lang: dict[str, list] = {"en": [], "km": []}
    for e in fresh:
        by_lang.setdefault(e.language, []).append(e)
    stats: dict[str, int] = {}
    for lang, rows in by_lang.items():
        merged = merge_entries(
            rows + [preserved[k] for k in preserved if k[0] == lang]
        )
        for e in merged:
            key = (lang, e.id)
            if key in preserved:
                e.review_status = preserved[key].review_status
                if preserved[key].gloss_en:
                    e.gloss_en = preserved[key].gloss_en
                if preserved[key].inflections:
                    e.inflections = dict(preserved[key].inflections)
        save_staging(merged, base, lang)
        stats[lang] = len(merged)
    return stats


def run_route_review(*, root: Optional[Path] = None) -> dict[str, Any]:
    base = ensure_layout(root or dictionary_dir())
    queued_all: List[DictionaryEntry] = []
    counts: dict[str, dict[str, int]] = {}
    for lang in ("en", "km"):
        entries = load_staging(base, lang)
        auto, queued = route_entries(entries)
        by_id = {e.id: e for e in auto + queued}
        save_staging(list(by_id.values()), base, lang)
        queued_all.extend(queued)
        counts[lang] = {"auto": len(auto), "queued": len(queued)}
    save_review_queue(queued_all, base)
    return {"languages": counts, "review_queue": len(queued_all)}


def apply_feedback(*, root: Optional[Path] = None) -> dict[str, int]:
    base = ensure_layout(root or dictionary_dir())
    store = DictionaryFeedbackStore(base / "review" / "feedback.json")
    out = {}
    for lang in ("en", "km"):
        out[lang] = store.apply_to_staging(lang, base)
    return out


def rebuild_sentences(
    *, language: str = "en", root: Optional[Path] = None, per_difficulty: int = 20
) -> dict[str, Any]:
    base = ensure_layout(root or dictionary_dir())
    entries = load_staging(base, language)
    sentences = build_curriculum(
        entries, language=language, per_difficulty=per_difficulty, seed=42
    )
    path = save_sentences(sentences, base, language)
    return {"language": language, "sentences": len(sentences), "path": str(path)}


def run_train_update(
    *,
    root: Optional[Path] = None,
    force: bool = False,
    language: str = "en",
    synth: bool = False,
    ship_packs: bool = False,
) -> dict[str, Any]:
    """Idempotent corpus refresh used by lab API + CLI."""
    base = ensure_layout(root or dictionary_dir())
    report: dict[str, Any] = {"root": str(base)}
    report["baselines"] = seed_baselines(root=base, force=force)
    report["ingest"] = run_ingest_merge(root=base)
    report["route"] = run_route_review(root=base)
    report["feedback"] = apply_feedback(root=base)
    report["sentences"] = rebuild_sentences(language=language, root=base)
    report["export"] = export_packs(root=base, ship=ship_packs)
    if synth:
        from aoep_shared.cosyvoice_tts import cosyvoice_configured
        from aoep_shared.dictionary_audio import clean_entry_audio, synthesize_entry_cosyvoice

        if cosyvoice_configured():
            entries = approved_entries(load_staging(base, language))[:20]
            updated = []
            written = 0
            for e in entries:
                row = synthesize_entry_cosyvoice(e, language=language, root=base)
                row = clean_entry_audio(row, language=language, root=base)
                slot = row.audio.get(language)
                if slot and getattr(slot, "quality", None) in ("raw", "crisp"):
                    written += 1
                updated.append(row)
            # merge back
            by_id = {e.id: e for e in updated}
            all_rows = [by_id.get(e.id, e) for e in load_staging(base, language)]
            save_staging(all_rows, base, language)
            report["synth"] = {"written": written}
        else:
            report["synth"] = {"skipped": "COSYVOICE_URL not set"}
    else:
        # Clean any existing raw clips
        from aoep_shared.dictionary_audio import clean_entry_audio

        entries = load_staging(base, language)
        updated = [clean_entry_audio(e, language=language, root=base) for e in entries]
        save_staging(updated, base, language)
        report["audio_clean"] = True
    return report


def corpus_stats(*, root: Optional[Path] = None) -> dict[str, Any]:
    base = ensure_layout(root or dictionary_dir())
    stats: dict[str, Any] = {"root": str(base), "languages": {}}
    for lang in ("en", "km"):
        rows = load_staging(base, lang)
        by_status: dict[str, int] = {}
        for e in rows:
            by_status[e.review_status] = by_status.get(e.review_status, 0) + 1
        stats["languages"][lang] = {
            "total": len(rows),
            "by_status": by_status,
            "approved": len(approved_entries(rows)),
        }
    stats["review_queue"] = len(load_review_queue(base))
    sent = base / "sentences" / "en.jsonl"
    stats["sentences_en"] = (
        sum(1 for line in sent.read_text(encoding="utf-8").splitlines() if line.strip())
        if sent.is_file()
        else 0
    )
    return stats


def list_review(*, root: Optional[Path] = None, limit: int = 40) -> dict[str, Any]:
    rows = load_review_queue(root)[: max(1, limit)]
    return {
        "count": len(rows),
        "entries": [
            {
                "id": e.id,
                "lemma": e.lemma,
                "language": e.language,
                "kind": e.kind,
                "gloss_en": e.gloss_en,
                "notes": e.notes,
            }
            for e in rows
        ],
    }


def apply_review(
    *,
    entry_id: str,
    action: str,
    gloss_en: str = "",
    note: str = "",
    inflections: Optional[Dict[str, str]] = None,
    root: Optional[Path] = None,
) -> dict[str, Any]:
    base = ensure_layout(root or dictionary_dir())
    found = None
    lang = "en"
    for cand in ("en", "km"):
        for e in load_staging(base, cand):
            if e.id == entry_id:
                found = e
                lang = cand
                break
        if found:
            break
    if not found:
        raise ValueError(f"entry not found: {entry_id}")
    store = DictionaryFeedbackStore(base / "review" / "feedback.json")
    store.record(
        entry_id=found.id,
        lemma=found.lemma,
        action=action,
        gloss_en=gloss_en or found.gloss_en,
        language=lang,
        inflections=inflections or {},
        note=note,
    )
    applied = store.apply_to_staging(lang, base)
    queued = [e for e in load_staging(base, "en") if e.review_status == "queued"]
    queued += [e for e in load_staging(base, "km") if e.review_status == "queued"]
    save_review_queue(queued, base)
    return {"ok": True, "id": entry_id, "action": action, "staging_updates": applied}


def export_packs(*, root: Optional[Path] = None, ship: bool = False) -> dict[str, Any]:
    from aoep_shared.dictionary_corpus import (
        CLOSED_CLASS,
        to_slang_pack_record,
        to_vocabulary_pack_record,
    )

    base = ensure_layout(root or dictionary_dir())
    out_root = base / "export"
    vocab_dir = out_root / "vocabulary"
    slang_dir = out_root / "slang"
    vocab_dir.mkdir(parents=True, exist_ok=True)
    slang_dir.mkdir(parents=True, exist_ok=True)

    en_entries = approved_entries(load_staging(base, "en"))
    km_entries = approved_entries(load_staging(base, "km"))
    vocab_records = []
    seen = set()
    for e in en_entries + km_entries:
        for target_lang in ("en", "km"):
            rec = to_vocabulary_pack_record(e, target_lang=target_lang)
            if not rec or rec["id"] in seen:
                continue
            seen.add(rec["id"])
            vocab_records.append(rec)
    slang_records = []
    for e in en_entries:
        s = to_slang_pack_record(e)
        if s:
            slang_records.append(s)

    vocab_path = vocab_dir / "dictionary_export_v1.json"
    slang_path = slang_dir / "dictionary_export_slang_v1.json"
    vocab_path.write_text(
        json.dumps(
            {
                "pack": "dictionary_export_v1",
                "description": "Approved dictionary corpus export (EN + KM).",
                "records": vocab_records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    slang_path.write_text(
        json.dumps(
            {
                "pack": "dictionary_export_slang_v1",
                "records": slang_records,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    result: dict[str, Any] = {
        "vocabulary": len(vocab_records),
        "slang": len(slang_records),
        "vocab_path": str(vocab_path),
        "slang_path": str(slang_path),
    }
    if ship:
        ship_dir = (
            _repo_root()
            / "packages"
            / "shared"
            / "src"
            / "aoep_shared"
            / "data"
            / "content_packs"
            / "vocabulary"
        )
        ship_dir.mkdir(parents=True, exist_ok=True)
        core = []
        for r in vocab_records:
            if r.get("language") != "en":
                continue
            lemma = str(r.get("en") or "").strip().lower()
            if not lemma or lemma in CLOSED_CLASS or " " in lemma:
                continue
            core.append(r)
        core = sorted(core, key=lambda r: int(r.get("freq_rank") or 999999))[:200]
        ship_path = ship_dir / "en_core_dictionary_v1.json"
        ship_path.write_text(
            json.dumps(
                {
                    "pack": "en_core_dictionary_v1",
                    "description": "Curated English core vocabulary from the dictionary corpus.",
                    "license": "MIT",
                    "records": core,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        result["shipped"] = len(core)
        result["ship_path"] = str(ship_path)
    return result


def export_llm_jsonl(*, root: Optional[Path] = None, out_path: Optional[Path] = None) -> dict[str, Any]:
    """Write approved staging rows as LLM-training JSONL (dictionary source)."""
    from aoep_shared.llm_training import export_dictionary_training_jsonl

    base = ensure_layout(root or dictionary_dir())
    dest = out_path or (base / "export" / "dictionary_llm_train.jsonl")
    n = export_dictionary_training_jsonl(base, dest)
    return {"path": str(dest), "examples": n}
