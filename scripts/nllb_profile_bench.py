#!/usr/bin/env python3
"""Choose an NLLB profile for a small GPU with data: speed, peak GPU memory and agreement with a reference translation.

  python3 scripts/nllb_profile_bench.py --profiles 8gb,8gb-ct2 --langs km,th,vi,es,zh --n 200 --save-outputs ~/bench
  # on the Spark, once, to make the reference (its 3.3B model); copy the folder to the machine being measured:
  NLLB_MODEL=facebook/nllb-200-3.3B NLLB_DTYPE=bf16 python3 scripts/nllb_profile_bench.py --profiles default \
      --langs km,th,vi,es,zh --n 200 --save-outputs ~/bench-ref
  python3 scripts/nllb_profile_bench.py --profiles 8gb,8gb-ct2 --reference ~/bench-ref/default --langs km,th,vi,es,zh

Quality proxy = chrF (character n-gram F-score, beta 2) of each profile's output against the reference translations. It
measures AGREEMENT with the reference model, not translation quality: a native speaker still decides. Without --reference
the profiles are only compared with each other. Peak memory is read from nvidia-smi while the profile runs (includes the CUDA
context), so it is what the 8 GiB card really holds. Nothing here is a claim until it is run on the machine.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Callable, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))
MANIFEST = ROOT / "tts_manifest" / "demo_voice_manifest.json"


def chrf(hyp: str, ref: str, max_n: int = 6, beta: float = 2.0) -> float:
    """Character n-gram F-score in 0..100 (whitespace ignored), averaged over n = 1..max_n."""
    h, r = "".join((hyp or "").split()), "".join((ref or "").split())
    if not h and not r:
        return 100.0
    if not h or not r:
        return 0.0
    scores = []
    for n in range(1, max_n + 1):
        hc = Counter(h[i:i + n] for i in range(len(h) - n + 1))
        rc = Counter(r[i:i + n] for i in range(len(r) - n + 1))
        if not hc or not rc:
            continue
        overlap = sum((hc & rc).values())
        p, q = overlap / sum(hc.values()), overlap / sum(rc.values())
        scores.append(0.0 if p + q == 0 else (1 + beta**2) * p * q / (beta**2 * p + q))
    return 100.0 * sum(scores) / len(scores) if scores else 0.0


def corpus_chrf(hyps: list[str], refs: list[str]) -> float:
    return sum(chrf(h, r) for h, r in zip(hyps, refs)) / max(1, len(refs))


def load_sentences(n: int, manifest: Path = MANIFEST) -> list[str]:
    """Real course lines (the English demo narration) first, so lengths and vocabulary look like production."""
    texts: list[str] = []
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
        rows = data.get("clips") or data.get("lines") or data if isinstance(data, (dict, list)) else []
        rows = rows if isinstance(rows, list) else []
        seen = set()
        for r in rows:
            t = " ".join(str(r.get("text", "")).split())
            if r.get("lang") == "en" and 20 <= len(t) <= 400 and t not in seen:
                seen.add(t)
                texts.append(t)
    except (OSError, ValueError, AttributeError):
        pass
    if len(texts) < n:
        from nllb_bench import fixed_sentences  # the 8 built-in sentences, numbered

        texts += fixed_sentences(n - len(texts))
    return texts[:n]


class PeakSampler:
    """Polls nvidia-smi for the GPU memory in use (GiB) and keeps the maximum. A no-op without nvidia-smi."""

    def __init__(self, interval: float = 0.2, query: Optional[Callable[[], Optional[float]]] = None):
        self.interval, self.query, self.peak = interval, query or self._smi, 0.0
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    @staticmethod
    def _smi() -> Optional[float]:
        try:
            out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=5).stdout.strip().splitlines()
            return float(out[0]) / 1024 if out else None
        except (OSError, ValueError, subprocess.SubprocessError):
            return None

    def _loop(self):
        while not self._stop.is_set():
            v = self.query()
            if v is not None:
                self.peak = max(self.peak, v)
            self._stop.wait(self.interval)

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join(timeout=2)


def reset_nllb_state():
    from aoep_shared import nllb

    nllb._model = nllb._tokenizer = nllb._ct2 = nllb._load_error = None


def run_profile(profile: str, langs: list[str], sentences: list[str], translate: Callable, batch: Optional[int] = None,
                sampler_factory: Callable[[], PeakSampler] = PeakSampler) -> dict:
    """Translate every sentence into every language under one profile; returns timings, peak memory and the outputs."""
    if profile == "default":
        os.environ.pop("NLLB_PROFILE", None)
    else:
        os.environ["NLLB_PROFILE"] = profile
    outputs: dict[str, list[str]] = {}
    with sampler_factory() as sampler:
        t0 = time.time()
        translate(["warm up"], source="en", target=langs[0], batch_size=1)  # load the model; timed separately
        load_s = time.time() - t0
        t1 = time.time()
        for lang in langs:
            outputs[lang] = translate(sentences, source="en", target=lang, batch_size=batch)
        run_s = max(1e-6, time.time() - t1)
    done = len(sentences) * len(langs)
    return {"profile": profile, "langs": langs, "n": len(sentences), "load_s": round(load_s, 1),
            "sentences_per_s": round(done / run_s, 2), "chars_per_s": round(sum(len(s) for s in sentences) * len(langs) / run_s),
            "peak_gb": round(sampler.peak, 2), "batch": batch, "outputs": outputs}


def score(results: list[dict], reference: Optional[dict[str, list[str]]]) -> None:
    """Attach chrF against the reference (or, without one, the mean agreement with the other profiles)."""
    for res in results:
        if reference:
            per = {lang: round(corpus_chrf(res["outputs"][lang], reference[lang]), 1) for lang in res["langs"] if lang in reference}
            res["chrf_vs_reference"] = per
            res["chrf_mean"] = round(sum(per.values()) / max(1, len(per)), 1) if per else None
            res["quality_basis"] = "reference"
        else:
            others = [o for o in results if o is not res]
            vals = [corpus_chrf(res["outputs"][lang], o["outputs"][lang]) for o in others for lang in res["langs"] if lang in o["outputs"]]
            res["chrf_mean"] = round(sum(vals) / len(vals), 1) if vals else None
            res["quality_basis"] = "agreement with the other profiles (weak: no reference given)"


def recommend(results: list[dict], budget_gb: float = 6.5) -> dict:
    """Best agreement among profiles whose measured peak fits the budget; ties go to the faster one."""
    fitting = [r for r in results if r["peak_gb"] <= budget_gb or r["peak_gb"] == 0.0]
    pool = fitting or results
    best = max(pool, key=lambda r: ((r.get("chrf_mean") or 0.0), r["sentences_per_s"]))
    return {"profile": best["profile"], "within_budget": best in fitting, "budget_gb": budget_gb,
            "note": "" if fitting else "no profile fit the budget: measured peaks are above it"}


def load_reference(folder: Path, langs: list[str]) -> dict[str, list[str]]:
    return {lang: json.loads((folder / f"{lang}.json").read_text(encoding="utf-8")) for lang in langs if (folder / f"{lang}.json").is_file()}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--profiles", default="8gb,8gb-ct2", help="comma list: default (use NLLB_MODEL/NLLB_DTYPE), 8gb, 8gb-ct2")
    ap.add_argument("--langs", default="km,th,vi,es,zh")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--batch", type=int, default=0, help="0 = the profile's default batch")
    ap.add_argument("--budget-gb", type=float, default=6.5)
    ap.add_argument("--reference", help="folder of <lang>.json lists made by --save-outputs on the reference machine (the Spark)")
    ap.add_argument("--save-outputs", help="write <folder>/<profile>/<lang>.json")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    langs = [x for x in a.langs.split(",") if x]
    sentences = load_sentences(a.n)
    from aoep_shared import nllb
    results = []
    for name in [p for p in a.profiles.split(",") if p]:
        reset_nllb_state()
        try:
            results.append(run_profile(name, langs, sentences, nllb.translate_batch, a.batch or None))
        except Exception as exc:  # noqa: BLE001 - one profile failing (e.g. no CT2 model yet) must not hide the others
            print(f"profile {name} FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
    if not results:
        return 1
    score(results, load_reference(Path(a.reference).expanduser(), langs) if a.reference else None)
    if a.save_outputs:
        for res in results:
            for lang, texts in res["outputs"].items():
                d = Path(a.save_outputs).expanduser() / res["profile"]
                d.mkdir(parents=True, exist_ok=True)
                (d / f"{lang}.json").write_text(json.dumps(texts, ensure_ascii=False, indent=1), encoding="utf-8")
    rec = recommend(results, a.budget_gb)
    slim = [{k: v for k, v in r.items() if k != "outputs"} for r in results]
    if a.json:
        print(json.dumps({"results": slim, "recommendation": rec}, indent=1))
    else:
        print(f"{'profile':10} {'sent/s':>7} {'load s':>7} {'peak GiB':>9} {'chrF':>6}  basis")
        for r in slim:
            print(f"{r['profile']:10} {r['sentences_per_s']:>7} {r['load_s']:>7} {r['peak_gb']:>9} {str(r.get('chrf_mean')):>6}  {r.get('quality_basis')}")
        print(f"recommendation: {rec['profile']} (peak budget {rec['budget_gb']} GiB; {'fits' if rec['within_budget'] else 'DOES NOT FIT'}) {rec['note']}")
        print("chrF measures agreement with the reference model, not translation quality: have a native speaker check km/th/vi first.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
