#!/usr/bin/env python3
"""Harvest throughput benchmark: fills the MEASURED column of docs/million-courses.txt.

Stages measured (each with latency percentiles):
  generate   ExtractedDoc -> normalize -> slides -> lesson decks      (deterministic, no LLM)
  pack       canonical JSON + gzip + content hash
  store      write the object to a local object store
  quality    metrics + tier gate + MinHash near-duplicate check
  llm        OPTIONAL: tokens/s of an OpenAI-compatible server (llama-server, vLLM) at several
             concurrency levels, for the future 'LLM polish' stage
  fetch      OPTIONAL: polite sequential fetch latency of a few URLs you choose

Examples (run through gs_run.sh so limits and the GPU lock apply):
  python3 scripts/harvest_bench.py --docs 200 --out runs/bench-mac.json
  python3 scripts/harvest_bench.py --corpus-db output/harvest/harvest_corpus.db --docs 300
  python3 scripts/harvest_bench.py --docs 0 --llm-url http://127.0.0.1:8080 --llm-model qwen \\
      --concurrency 1,4,8,16 --requests 32 --max-tokens 400
  python3 scripts/harvest_bench.py --docs 0 --fetch-url https://openstax.org/ --fetch-url https://ocw.mit.edu/

Nothing here changes any data: output goes to a temp directory and the JSON report.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import random
import resource
import shutil
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "packages" / "shared" / "src"))

from aoep_shared.harvest.extractors import ExtractedDoc  # noqa: E402
from aoep_shared.harvest.generate import generate_lessons  # noqa: E402
from aoep_shared.harvest.objectstore import LocalObjectStore, course_key, pack_course  # noqa: E402
from aoep_shared.harvest.quality import NearDuplicateIndex, assign_tier  # noqa: E402

WORDS = (
    "energy force motion cell protein enzyme equation function graph variable history empire treaty "
    "market supply demand budget algorithm network memory vector matrix probability sample hypothesis "
    "experiment river climate ecosystem grammar sentence poem rhythm harmony melody nutrition exercise "
    "circuit voltage current resistance molecule reaction solution acid base theorem proof angle triangle"
).split()


def pct(values: List[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    return s[min(len(s) - 1, int(q * len(s)))]


def summarize(values: List[float]) -> Dict[str, float]:
    return {
        "n": len(values),
        "mean_ms": round(statistics.mean(values) * 1000, 2) if values else 0,
        "p50_ms": round(pct(values, 0.5) * 1000, 2),
        "p95_ms": round(pct(values, 0.95) * 1000, 2),
        "total_s": round(sum(values), 3),
    }


def synthetic_doc(i: int, chars: int = 60000) -> ExtractedDoc:
    rng = random.Random(1000 + i)
    sections, used = [], 0
    n = 0
    while used < chars:
        n += 1
        text = " ".join(
            " ".join(rng.choice(WORDS) for _ in range(rng.randint(9, 18))).capitalize() + "."
            for _ in range(rng.randint(8, 16))
        )
        sections.append(
            (f"Section {n}: {rng.choice(WORDS).title()} {rng.choice(WORDS).title()}", text)
        )
        used += len(text)
    return ExtractedDoc(title=f"Bench course {i}", sections=sections)


def corpus_docs(db: str, limit: int) -> List[ExtractedDoc]:
    conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    docs: List[ExtractedDoc] = []
    for (url_key,) in conn.execute(
        "SELECT url_key FROM sources ORDER BY url_key LIMIT ?", (limit,)
    ):
        rows = conn.execute(
            "SELECT heading, body FROM chunks WHERE url_key=? ORDER BY chunk_index", (url_key,)
        ).fetchall()
        if rows:
            docs.append(
                ExtractedDoc(
                    title=f"Source {url_key}", sections=[(h or "", b or "") for h, b in rows]
                )
            )
    return docs


def bench_pipeline(docs: List[ExtractedDoc]) -> Dict:
    tmp = Path(tempfile.mkdtemp(prefix="harvest-bench-"))
    store, dedup = LocalObjectStore(tmp), NearDuplicateIndex()
    t = {"generate": [], "pack": [], "store": [], "quality": []}
    decks = tier1 = nbytes_raw = nbytes_gz = text_chars = 0
    started = time.perf_counter()
    try:
        for doc in docs:
            t0 = time.perf_counter()
            lessons = generate_lessons(doc, subject="general")
            t["generate"].append(time.perf_counter() - t0)
            for lesson in lessons:
                data = lesson.to_dict()
                t0 = time.perf_counter()
                sha, gz = pack_course(data)
                t["pack"].append(time.perf_counter() - t0)
                t0 = time.perf_counter()
                store.put(course_key(sha), gz)
                t["store"].append(time.perf_counter() - t0)
                t0 = time.perf_counter()
                decision = assign_tier(data, key=sha, dedup=dedup)
                t["quality"].append(time.perf_counter() - t0)
                decks += 1
                tier1 += decision.tier == 1
                nbytes_raw += len(json.dumps(data).encode())
                nbytes_gz += len(gz)
                text_chars += int(decision.metrics.get("text_chars", 0))
    finally:
        wall = time.perf_counter() - started
        shutil.rmtree(tmp, ignore_errors=True)
    return {
        "docs": len(docs),
        "decks": decks,
        "tier1_decks": int(tier1),
        "wall_s": round(wall, 2),
        "decks_per_hour_single_core": round(decks / wall * 3600) if wall else 0,
        "decks_per_doc": round(decks / max(1, len(docs)), 1),
        "avg_json_kb": round(nbytes_raw / max(1, decks) / 1024, 1),
        "avg_gz_kb": round(nbytes_gz / max(1, decks) / 1024, 1),
        "avg_text_chars": round(text_chars / max(1, decks)),
        "stages": {k: summarize(v) for k, v in t.items()},
    }


def chat(url: str, model: str, prompt: str, max_tokens: int, key: str = "") -> Dict:
    body = json.dumps(
        {
            "model": model,
            "max_tokens": max_tokens,
            "temperature": 0.2,
            "messages": [{"role": "user", "content": prompt}],
        }
    ).encode()
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    req = urllib.request.Request(
        url.rstrip("/") + "/v1/chat/completions", data=body, headers=headers
    )
    t0 = time.perf_counter()
    with urllib.request.urlopen(req, timeout=600) as resp:
        data = json.load(resp)
    dt = time.perf_counter() - t0
    text = (data.get("choices") or [{}])[0].get("message", {}).get("content", "")
    toks = (data.get("usage") or {}).get("completion_tokens") or max(1, len(text) // 3)
    return {"seconds": dt, "tokens": toks}


def bench_llm(
    url: str, model: str, levels: List[int], requests: int, max_tokens: int, key: str
) -> List[Dict]:
    prompt = (
        "Rewrite this lesson slide as warm, clear spoken narration for a learner, 150-250 words, no lists: "
        + " ".join(WORDS[:40]) * 6
    )
    out = []
    for level in levels:
        started = time.perf_counter()
        with ThreadPoolExecutor(max_workers=level) as pool:
            results = list(
                pool.map(lambda _: chat(url, model, prompt, max_tokens, key), range(requests))
            )
        wall = time.perf_counter() - started
        toks = sum(r["tokens"] for r in results)
        lat = [r["seconds"] for r in results]
        out.append(
            {
                "concurrency": level,
                "requests": requests,
                "wall_s": round(wall, 2),
                "completion_tokens": toks,
                "aggregate_tokens_per_s": round(toks / wall, 1),
                "per_request_tokens_per_s": round(
                    statistics.mean(r["tokens"] / r["seconds"] for r in results), 1
                ),
                "latency_p50_s": round(pct(lat, 0.5), 2),
                "latency_p95_s": round(pct(lat, 0.95), 2),
            }
        )
    return out


def bench_fetch(urls: List[str], repeat: int) -> List[Dict]:
    out = []
    for url in urls:
        lat, size = [], 0
        for _ in range(repeat):
            t0 = time.perf_counter()
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": os.environ.get(
                        "HARVEST_USER_AGENT", "SalareenBench/1.0 (contact: ops)"
                    )
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as resp:
                    size = len(resp.read())
                lat.append(time.perf_counter() - t0)
            except Exception as exc:  # report, never crash the benchmark
                out.append({"url": url, "error": str(exc)[:120]})
                break
            time.sleep(1.0)  # polite: one request per second per host
        if lat:
            out.append({"url": url, "bytes": size, **summarize(lat)})
    return out


def machine_info() -> Dict:
    info = {
        "host": platform.node(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpus": os.cpu_count(),
        "peak_rss_mb": round(
            resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            / (1024 * 1024 if sys.platform == "darwin" else 1024)
        ),
    }
    try:
        info["gpu"] = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        info["gpu"] = "n/a"
    return info


def main(argv: List[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--docs", type=int, default=100, help="documents to generate (0 skips the pipeline stage)"
    )
    ap.add_argument("--chars", type=int, default=60000, help="characters per synthetic document")
    ap.add_argument(
        "--corpus-db",
        help="use real extracted sections from a harvest corpus DB instead of synthetic text",
    )
    ap.add_argument("--llm-url")
    ap.add_argument("--llm-model", default="default")
    ap.add_argument("--llm-key", default="")
    ap.add_argument("--concurrency", default="1,4,8", help="comma-separated LLM concurrency levels")
    ap.add_argument("--requests", type=int, default=16)
    ap.add_argument("--max-tokens", type=int, default=300)
    ap.add_argument("--fetch-url", action="append", default=[])
    ap.add_argument("--fetch-repeat", type=int, default=5)
    ap.add_argument("--out", help="write the JSON report here")
    args = ap.parse_args(argv)

    report: Dict = {
        "machine": machine_info(),
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    if args.docs:
        docs = (
            corpus_docs(args.corpus_db, args.docs)
            if args.corpus_db
            else [synthetic_doc(i, args.chars) for i in range(args.docs)]
        )
        report["pipeline"] = bench_pipeline(docs)
        report["pipeline"]["input"] = "corpus" if args.corpus_db else "synthetic"
    if args.llm_url:
        report["llm"] = bench_llm(
            args.llm_url,
            args.llm_model,
            [int(x) for x in args.concurrency.split(",")],
            args.requests,
            args.max_tokens,
            args.llm_key,
        )
    if args.fetch_url:
        report["fetch"] = bench_fetch(args.fetch_url, args.fetch_repeat)
    report["machine"]["peak_rss_mb_end"] = machine_info()["peak_rss_mb"]
    text = json.dumps(report, indent=2)
    print(text)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
