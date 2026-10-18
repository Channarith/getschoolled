#!/usr/bin/env python3
"""End-to-end RAG golden-set answers for small local models.

Uses the rag-lab harness in-process (retrieve + groundedness + rag_quality).
It does not POST to the lab, so no telemetry is recorded. Model calls are
either in-process Hugging Face weights or a read-only OpenAI-compatible
llama-server. GPU work takes ~/.gs-gpu.lock unless GS_GPU_LOCK_HELD=1
(the Makefile sets that after flock).

  make rag-small-evals
  make rag-small-evals RAG_EVAL_HOST=127.0.0.1 RAG_EVAL_PORT=18042 RAG_EVAL_BACKEND=http

Reports the original 16 golden items and the extended set (those 16 plus the
held-out lesson items) separately. Writes under output/spark/rag-small-evals/.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import gc
import json
import os
import re
import resource
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Sequence

ROOT = Path(__file__).resolve().parents[1]
_SRC = ROOT / "subrepos" / "theodore_rag_lab" / "src"
_SHARED = ROOT / "packages" / "shared" / "src"
for _path in (_SRC, _SHARED):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from theodore_rag_lab.eval_harness import (  # noqa: E402
    evaluate_answers,
    load_curriculum_index,
    load_golden,
    load_heldout_golden,
)
from theodore_rag_lab.rag_tuning import RagTuning  # noqa: E402

DEFAULT_MODELS = "qwen2.5-0.5b,qwen2.5-1.5b,qwen2.5-3b,stem-qlora,qwen3.6-35b-a3b"
DEFAULT_STEM_BASE = (
    "/home/nvidia/code/gs-wt/spark-train-stem/models/weights/qwen2.5-7b-instruct"
)
DEFAULT_STEM_ADAPTER = "/home/nvidia/code/gs-wt/spark-train-stem/output/spark/adapters/stem"
LOCK_PATH = Path.home() / ".gs-gpu.lock"
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_THINK_TAIL = re.compile(r"^.*?</think>", re.DOTALL | re.IGNORECASE)

# Known checkpoints. Unknown names are llama-server model ids on --host/--port.
CATALOG: dict[str, dict[str, Any]] = {
    "qwen2.5-0.5b": {
        "kind": "hf",
        "repo": "Qwen/Qwen2.5-0.5B-Instruct",
        "size_rank": 1,
        "params": "0.5B",
    },
    "qwen2.5-1.5b": {
        "kind": "hf",
        "repo": "Qwen/Qwen2.5-1.5B-Instruct",
        "size_rank": 2,
        "params": "1.5B",
    },
    "qwen2.5-3b": {
        "kind": "hf",
        "repo": "Qwen/Qwen2.5-3B-Instruct",
        "size_rank": 3,
        "params": "3B",
    },
    "stem-qlora": {
        "kind": "qlora",
        "size_rank": 4,
        "params": "7B+LoRA",
    },
    "qwen3.6-35b-a3b": {
        "kind": "http",
        "size_rank": 5,
        "params": "35B-A3B",
        "reference": True,
    },
}

SYSTEM = (
    "You are a tutor. Answer the question in one or two short sentences "
    "using only the lesson passages. Do not add facts that are not in the passages."
)


@dataclass
class ModelSpec:
    name: str
    kind: str
    host: str
    port: int
    repo: str
    params: str
    size_rank: int
    reference: bool
    weights: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "host": self.host,
            "port": self.port,
            "repo": self.repo,
            "params": self.params,
            "size_rank": self.size_rank,
            "reference": self.reference,
            "weights": self.weights,
        }

    @classmethod
    def from_dict(cls, row: dict[str, Any]) -> "ModelSpec":
        return cls(
            name=str(row["name"]),
            kind=str(row["kind"]),
            host=str(row["host"]),
            port=int(row["port"]),
            repo=str(row.get("repo") or ""),
            params=str(row.get("params") or ""),
            size_rank=int(row.get("size_rank") or 100),
            reference=bool(row.get("reference")),
            weights=str(row.get("weights") or ""),
        )


def _public_error(exc: BaseException) -> str:
    text = re.sub(
        r"(?i)(token|api[_-]?key|secret|authorization)[=: ]+\S+",
        r"\1=[redacted]",
        str(exc),
    )
    return text[:300]


def strip_thinking(text: str) -> str:
    cleaned = _THINK.sub("", text or "")
    cleaned = _THINK_TAIL.sub("", cleaned)
    return cleaned.strip()


def build_messages(query: str, passages: Sequence[str]) -> list[dict[str, str]]:
    context = "\n\n".join(part.strip() for part in passages if part and part.strip())
    user = f"Passages:\n{context}\n\nQuestion: {query}" if context else f"Question: {query}"
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user},
    ]


def answer_score(block: dict[str, Any]) -> float:
    """Mean of the harness answer F1 and groundedness (0..1)."""
    return 0.5 * float(block.get("answer_f1") or 0.0) + 0.5 * float(block.get("groundedness") or 0.0)


def _shortfall(reference: float, value: float) -> float:
    """How far ``value`` sits below ``reference``. Negative means better."""
    return float(reference) - float(value)


def quality_gap(row: dict[str, Any], ref: dict[str, Any]) -> float:
    """Worst shortfall on answer F1 or groundedness, original set or extended set.

    The two metrics are not averaged. A higher token F1 cannot offset answers
    that are less grounded in the retrieved passages.
    """
    gaps = []
    for label in ("original", "extended"):
        got = row.get(label) or {}
        target = ref.get(label) or {}
        gaps.append(_shortfall(target.get("answer_f1") or 0.0, got.get("answer_f1") or 0.0))
        gaps.append(_shortfall(target.get("groundedness") or 0.0, got.get("groundedness") or 0.0))
    return max(gaps)


def parse_model_list(
    raw: str,
    *,
    host: str,
    port: int,
    backend: str,
    reference: str,
) -> list[ModelSpec]:
    specs: list[ModelSpec] = []
    for token in (raw or "").split(","):
        token = token.strip()
        if not token:
            continue
        name, dest_host, dest_port = _split_endpoint(token, host, port)
        meta = CATALOG.get(name, {})
        if backend == "http":
            kind = "http"
        elif backend == "local":
            kind = str(meta.get("kind") or "hf")
            if kind == "http":
                raise SystemExit(f"{name} has no local weights; use --backend auto or http")
        else:
            kind = str(meta.get("kind") or "http")
        specs.append(
            ModelSpec(
                name=name,
                kind=kind,
                host=dest_host,
                port=dest_port,
                repo=str(meta.get("repo") or ""),
                params=str(meta.get("params") or name),
                size_rank=int(meta.get("size_rank") or 100),
                reference=bool(meta.get("reference")) or name == reference,
            )
        )
    if not specs:
        raise SystemExit("no models in --models")
    return specs


def _split_endpoint(token: str, host: str, port: int) -> tuple[str, str, int]:
    if "@" not in token:
        return token, host, port
    name, dest = token.split("@", 1)
    name = name.strip()
    dest = dest.strip()
    if not dest:
        return name, host, port
    if ":" in dest:
        dest_host, port_s = dest.rsplit(":", 1)
        return name, (dest_host or host), int(port_s)
    return name, host, int(dest)


def recommend(rows: Sequence[dict[str, Any]], margin: float) -> dict[str, Any]:
    """Smallest model within ``margin`` on answer F1 and groundedness, both sets."""
    usable = [row for row in rows if row.get("ok") and row.get("extended", {}).get("n")]
    if not usable:
        return {"model": "", "within_margin": False, "reason": "no model finished"}
    ref = next((row for row in usable if row.get("reference")), None)
    if ref is None:
        ref = max(usable, key=lambda row: answer_score(row["extended"]))
    target_ext = answer_score(ref["extended"])
    target_orig = answer_score(ref["original"])

    def gap(row: dict[str, Any]) -> float:
        return quality_gap(row, ref)

    smaller = [row for row in usable if row["name"] != ref["name"]]
    eligible = [row for row in smaller if gap(row) <= margin + 1e-9]
    if not smaller:
        chosen = ref
        within = True
    elif eligible:
        chosen = sorted(eligible, key=lambda row: (int(row["size_rank"]), row["name"]))[0]
        within = True
    else:
        best_gap = min(gap(row) for row in smaller)
        closest = [row for row in smaller if abs(gap(row) - best_gap) <= 1e-9]
        chosen = sorted(closest, key=lambda row: (int(row["size_rank"]), row["name"]))[0]
        within = False
    chosen_ext = answer_score(chosen["extended"])
    if chosen["name"] == ref["name"]:
        reason = (
            f"No smaller model stayed within {margin:.2f} of {ref['name']} "
            f"on answer F1 and groundedness for both sets "
            f"(reference extended answer score {target_ext:.3f})."
        )
    elif within:
        reason = (
            f"{chosen['name']} ({chosen['params']}) is the smallest model within "
            f"{margin:.2f} of {ref['name']} on answer F1 and groundedness for both "
            f"the original and extended sets "
            f"(extended F1 {float(chosen['extended'].get('answer_f1') or 0):.3f} vs "
            f"{float(ref['extended'].get('answer_f1') or 0):.3f}, "
            f"groundedness {float(chosen['extended'].get('groundedness') or 0):.3f} vs "
            f"{float(ref['extended'].get('groundedness') or 0):.3f})."
        )
    else:
        reason = (
            f"No model stayed within {margin:.2f} of {ref['name']} "
            f"on answer F1 and groundedness. "
            f"Closest small model is {chosen['name']} "
            f"(worst shortfall {gap(chosen):.3f}; "
            f"extended answer score {chosen_ext:.3f} vs {target_ext:.3f})."
        )
    return {
        "model": chosen["name"],
        "params": chosen["params"],
        "within_margin": gap(chosen) <= margin + 1e-9,
        "margin": margin,
        "reference": ref["name"],
        "reference_extended": round(target_ext, 4),
        "reference_original": round(target_orig, 4),
        "chosen_extended": round(chosen_ext, 4),
        "chosen_original": round(answer_score(chosen["original"]), 4),
        "gap": round(gap(chosen), 4),
        "set": "original_and_extended",
        "metrics": ["answer_f1", "groundedness"],
        "reason": reason,
    }


@contextlib.contextmanager
def gpu_lock() -> Iterator[None]:
    """Exclusive lock around a GPU section. Nested when the parent already holds it."""
    if os.environ.get("GS_GPU_LOCK_HELD") == "1":
        yield
        return
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = LOCK_PATH.open("a", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        handle.close()


def _peak_rss_mb() -> float:
    # Linux: ru_maxrss is kilobytes.
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0


def server_rss_mb(port: int) -> float | None:
    """Resident set of an existing llama-server on ``port``. Read-only."""
    try:
        out = subprocess.check_output(["ps", "-eo", "rss,args"], text=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    needle = f"--port {port}"
    for line in out.splitlines():
        if "llama-server" not in line or needle not in line:
            continue
        rss = line.split(None, 1)[0]
        try:
            return int(rss) / 1024.0
        except ValueError:
            return None
    return None


def http_complete(
    spec: ModelSpec,
    messages: list[dict[str, str]],
    *,
    max_tokens: int,
    timeout: float,
) -> str:
    url = f"http://{spec.host}:{spec.port}/v1/chat/completions"
    body = {
        "model": spec.name,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0,
        "chat_template_kwargs": {"enable_thinking": False},
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    last: Exception | None = None
    for _ in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            break
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
    else:
        raise RuntimeError(type(last).__name__ if last else "http")
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = str(message.get("content") or "").strip()
    if not content:
        content = str(message.get("reasoning_content") or "")
    return strip_thinking(content)


def _generate_local(model: Any, tokenizer: Any, messages: list[dict[str, str]], max_new: int) -> str:
    import torch

    prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt")
    inputs = {key: value.to(model.device) for key, value in inputs.items()}
    with torch.inference_mode():
        output = model.generate(
            **inputs,
            max_new_tokens=max_new,
            do_sample=False,
        )
    new_tokens = output[0, inputs["input_ids"].shape[1] :]
    return strip_thinking(tokenizer.decode(new_tokens, skip_special_tokens=True))


def _load_causal(weights: str, *, four_bit: bool) -> tuple[Any, Any]:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(weights, local_files_only=True)
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token = tokenizer.eos_token
    kwargs: dict[str, Any] = {"local_files_only": True, "device_map": "cuda"}
    if four_bit:
        from transformers import BitsAndBytesConfig

        kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )
    else:
        kwargs["dtype"] = torch.bfloat16
    model = AutoModelForCausalLM.from_pretrained(weights, **kwargs)
    model.eval()
    return model, tokenizer


def _release(model: Any, tokenizer: Any) -> None:
    del model
    del tokenizer
    gc.collect()
    try:
        import torch

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:  # noqa: BLE001
        return


def run_spec(
    spec: ModelSpec,
    *,
    max_new_tokens: int,
    timeout: float,
    stem_base: str,
    stem_adapter: str,
    dry_run: bool,
    limit: int,
) -> dict[str, Any]:
    original = load_golden()
    heldout = load_heldout_golden()
    extended = list(original) + list(heldout)
    if limit > 0:
        original = original[:limit]
        extended = extended[:limit]
    index = load_curriculum_index()
    tuning = RagTuning()
    cuda_peak = 0.0
    server_peak = 0.0
    note = ""
    answer_fn: Any

    if dry_run:
        expected = {row.query: row.expected_answer for row in extended}

        def answer_fn(query: str, passages: Sequence[str]) -> str:
            return expected.get(query, "")

    elif spec.kind == "http":
        seen = server_rss_mb(spec.port) or 0.0
        server_peak = seen

        def answer_fn(query: str, passages: Sequence[str]) -> str:
            nonlocal server_peak
            text = http_complete(
                spec,
                build_messages(query, passages),
                max_tokens=max_new_tokens,
                timeout=timeout,
            )
            current = server_rss_mb(spec.port)
            if current is not None:
                server_peak = max(server_peak, current)
            return text

    else:
        answer_fn, note = _local_answer_fn(
            spec,
            max_new_tokens=max_new_tokens,
            stem_base=stem_base,
            stem_adapter=stem_adapter,
        )

    t0 = time.perf_counter()
    try:
        # One pass: extended is the original items followed by held-out items.
        extended_report = evaluate_answers(
            index, extended, tuning, answer_fn, include_details=True
        )
    finally:
        if not dry_run and spec.kind != "http":
            cuda_peak = _cuda_peak_mb()
        _release_answer_fn(answer_fn)
    elapsed = time.perf_counter() - t0
    original_report = _report_from_details(extended_report.details[: len(original)])
    process_peak = round(_peak_rss_mb(), 1)
    peak_memory = server_peak if spec.kind == "http" and server_peak else process_peak
    if cuda_peak:
        peak_memory = max(peak_memory, cuda_peak)
    return {
        "name": spec.name,
        "params": spec.params,
        "kind": spec.kind,
        "size_rank": spec.size_rank,
        "reference": spec.reference,
        "ok": True,
        "host": spec.host,
        "port": spec.port,
        "weights": spec.weights,
        "note": note,
        "elapsed_s": round(elapsed, 2),
        "peak_process_mb": process_peak,
        "peak_server_mb": round(server_peak, 1) if server_peak else None,
        "peak_cuda_mb": round(cuda_peak, 1) if cuda_peak else None,
        "peak_memory_mb": round(peak_memory, 1),
        "original_n": len(original),
        "extended_n": len(extended),
        "heldout_n": max(0, len(extended) - len(original)) if limit <= 0 else None,
        "original": original_report.to_dict(),
        "extended": extended_report.to_dict(),
    }


def _cuda_peak_mb() -> float:
    try:
        import torch

        if torch.cuda.is_available():
            return torch.cuda.max_memory_allocated() / (1024 * 1024)
    except Exception:  # noqa: BLE001
        return 0.0
    return 0.0


def _report_from_details(details: Sequence[dict[str, Any]]) -> Any:
    """Rebuild a report from a prefix of an extended-set run (same item order)."""
    from theodore_rag_lab.eval_harness import AnswerEvalReport

    rows = list(details)
    n = len(rows)
    if n == 0:
        return AnswerEvalReport(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)
    hits = sum(1 for row in rows if row.get("rank"))
    rr = sum(1.0 / int(row["rank"]) for row in rows if row.get("rank"))
    recall = hits / n
    mrr = rr / n
    grounded = sum(float(row["groundedness"]) for row in rows) / n
    f1 = sum(float(row["answer_f1"]) for row in rows) / n
    quality = 0.45 * recall + 0.25 * mrr + 0.30 * grounded
    return AnswerEvalReport(
        n=n,
        recall_at_k=round(recall, 4),
        mrr=round(mrr, 4),
        groundedness=round(grounded, 4),
        answer_f1=round(f1, 4),
        latency_ms_avg=round(sum(float(row["latency_ms"]) for row in rows) / n, 3),
        retrieve_ms_avg=round(sum(float(row["retrieve_ms"]) for row in rows) / n, 3),
        rag_quality=round(quality, 4),
        hits=hits,
        details=rows,
    )


def _local_answer_fn(
    spec: ModelSpec,
    *,
    max_new_tokens: int,
    stem_base: str,
    stem_adapter: str,
) -> tuple[Any, str]:
    import torch

    torch.cuda.reset_peak_memory_stats()
    note = ""
    if spec.kind == "qlora":
        if not Path(stem_base).is_dir() or not Path(stem_adapter).is_dir():
            raise FileNotFoundError("stem base or adapter is not on disk")
        try:
            base, tokenizer = _load_causal(stem_base, four_bit=True)
            note = "4-bit"
        except Exception:
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            base, tokenizer = _load_causal(stem_base, four_bit=False)
            note = "bf16"
        from peft import PeftModel

        model = PeftModel.from_pretrained(base, stem_adapter, is_trainable=False)
        model.eval()
    else:
        if not spec.weights:
            raise FileNotFoundError(f"no local weights for {spec.name}")
        model, tokenizer = _load_causal(spec.weights, four_bit=False)
        note = "bf16"

    def answer_fn(query: str, passages: Sequence[str]) -> str:
        return _generate_local(model, tokenizer, build_messages(query, passages), max_new_tokens)

    # The closure keeps the weights alive until the caller finishes the set.
    answer_fn.release = lambda: _release(model, tokenizer)  # type: ignore[attr-defined]
    return answer_fn, note


def _release_answer_fn(answer_fn: Any) -> None:
    release = getattr(answer_fn, "release", None)
    if release is not None:
        release()


def worker_main(spec_path: Path, out_path: Path, args: argparse.Namespace) -> int:
    spec = ModelSpec.from_dict(json.loads(spec_path.read_text(encoding="utf-8")))
    try:
        lock = contextlib.nullcontext() if args.dry_run else gpu_lock()
        with lock:
            report = run_spec(
                spec,
                max_new_tokens=args.max_new_tokens,
                timeout=args.timeout,
                stem_base=args.stem_base,
                stem_adapter=args.stem_adapter,
                dry_run=args.dry_run,
                limit=args.limit,
            )
    except Exception as exc:  # noqa: BLE001
        report = {
            "name": spec.name,
            "params": spec.params,
            "kind": spec.kind,
            "size_rank": spec.size_rank,
            "reference": spec.reference,
            "ok": False,
            "error": type(exc).__name__,
            "message": _public_error(exc),
            "original": {"n": 0, "answer_f1": 0.0, "groundedness": 0.0, "rag_quality": 0.0},
            "extended": {"n": 0, "answer_f1": 0.0, "groundedness": 0.0, "rag_quality": 0.0},
        }
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("name", "ok") if k in report}))
    return 0 if report.get("ok") else 1


def fetch_weights(specs: Sequence[ModelSpec], *, download: bool) -> None:
    hf = [spec for spec in specs if spec.kind == "hf"]
    if not hf:
        return
    from huggingface_hub import snapshot_download

    for spec in hf:
        spec.weights = snapshot_download(spec.repo, local_files_only=not download)


def _block(report: dict[str, Any]) -> dict[str, Any]:
    """Drop per-item answers from the summary table source."""
    details = report.get("details") or []
    slim = dict(report)
    slim.pop("details", None)
    slim["answer_score"] = round(answer_score(report), 4)
    slim["latency_ms"] = [row.get("latency_ms") for row in details]
    return slim


def render_table(rows: Sequence[dict[str, Any]]) -> str:
    header = (
        f"{'model':<20} {'set':<10} {'n':>3} {'ans_f1':>7} {'ground':>7} "
        f"{'rag_q':>7} {'recall':>7} {'lat_ms':>8} {'peak_mb':>8}"
    )
    lines = [header, "-" * len(header)]
    for row in rows:
        if not row.get("ok"):
            lines.append(f"{row['name']:<20} FAILED {row.get('error', '')}")
            continue
        for label in ("original", "extended"):
            block = row[label]
            lines.append(
                f"{row['name']:<20} {label:<10} {block['n']:>3} "
                f"{block['answer_f1']:>7.3f} {block['groundedness']:>7.3f} "
                f"{block['rag_quality']:>7.3f} {block['recall_at_k']:>7.3f} "
                f"{block['latency_ms_avg']:>8.1f} {row.get('peak_memory_mb') or 0:>8.0f}"
            )
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models", default=os.environ.get("RAG_EVAL_MODELS", DEFAULT_MODELS))
    parser.add_argument("--host", default=os.environ.get("RAG_EVAL_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("RAG_EVAL_PORT", "8342")))
    parser.add_argument(
        "--backend",
        choices=("auto", "http", "local"),
        default=os.environ.get("RAG_EVAL_BACKEND", "auto"),
        help="auto: catalog kind. http: every name is a llama-server id on host:port.",
    )
    parser.add_argument("--reference", default=os.environ.get("RAG_EVAL_REFERENCE", "qwen3.6-35b-a3b"))
    parser.add_argument("--margin", type=float, default=float(os.environ.get("RAG_EVAL_MARGIN", "0.05")))
    parser.add_argument("--out", default=os.environ.get("RAG_EVAL_OUT", "output/spark/rag-small-evals"))
    parser.add_argument("--max-new-tokens", type=int, default=80)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--limit", type=int, default=0, help="Cap items per set (0 = all).")
    parser.add_argument("--stem-base", default=os.environ.get("RAG_EVAL_STEM_BASE", DEFAULT_STEM_BASE))
    parser.add_argument(
        "--stem-adapter",
        default=os.environ.get("RAG_EVAL_STEM_ADAPTER", DEFAULT_STEM_ADAPTER),
    )
    parser.add_argument("--fetch-only", action="store_true")
    parser.add_argument("--skip-fetch", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="Score the golden answer. No GPU.")
    parser.add_argument("--worker", type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--worker-out", type=Path, default=None, help=argparse.SUPPRESS)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.worker is not None:
        if args.worker_out is None:
            raise SystemExit("--worker-out is required with --worker")
        return worker_main(args.worker, args.worker_out, args)

    specs = parse_model_list(
        args.models,
        host=args.host,
        port=args.port,
        backend=args.backend,
        reference=args.reference,
    )
    if args.dry_run:
        args.skip_fetch = True
    if not args.dry_run:
        fetch_weights(specs, download=not args.skip_fetch)
    if args.fetch_only:
        print(json.dumps({"fetched": [spec.name for spec in specs if spec.kind == "hf"]}))
        return 0

    out_root = Path(args.out)
    if not out_root.is_absolute():
        out_root = ROOT / out_root
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out_dir = out_root / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    for spec in specs:
        spec_path = out_dir / f"{spec.name}.spec.json"
        result_path = out_dir / f"{spec.name}.json"
        spec_path.write_text(json.dumps(spec.to_dict()) + "\n", encoding="utf-8")
        env = os.environ.copy()
        if not args.dry_run:
            env["GS_GPU_LOCK_HELD"] = "1"
        cmd = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--worker",
            str(spec_path),
            "--worker-out",
            str(result_path),
            "--max-new-tokens",
            str(args.max_new_tokens),
            "--timeout",
            str(args.timeout),
            "--limit",
            str(args.limit),
            "--stem-base",
            args.stem_base,
            "--stem-adapter",
            args.stem_adapter,
        ]
        if args.dry_run:
            cmd.append("--dry-run")
        if args.dry_run:
            proc = subprocess.run(cmd, cwd=str(ROOT), env=env, check=False)
        else:
            with gpu_lock():
                proc = subprocess.run(cmd, cwd=str(ROOT), env=env, check=False)
        if result_path.is_file():
            rows.append(json.loads(result_path.read_text(encoding="utf-8")))
        else:
            rows.append(
                {
                    "name": spec.name,
                    "params": spec.params,
                    "size_rank": spec.size_rank,
                    "reference": spec.reference,
                    "ok": False,
                    "error": f"exit_{proc.returncode}",
                    "original": {"n": 0, "answer_f1": 0.0, "groundedness": 0.0, "rag_quality": 0.0},
                    "extended": {"n": 0, "answer_f1": 0.0, "groundedness": 0.0, "rag_quality": 0.0},
                }
            )

    advice = recommend(rows, args.margin)
    summary_rows = []
    for row in rows:
        summary_rows.append(
            {
                **{k: v for k, v in row.items() if k not in {"original", "extended"}},
                "original": _block(row.get("original") or {}),
                "extended": _block(row.get("extended") or {}),
            }
        )
    summary = {
        "created_utc": stamp,
        "margin": args.margin,
        "backend": args.backend,
        "host": args.host,
        "port": args.port,
        "models": summary_rows,
        "recommendation": advice,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    table = render_table(rows)
    text = table + "\n\n" + advice.get("reason", "") + "\n"
    (out_dir / "summary.txt").write_text(text, encoding="utf-8")
    latest = out_root / "latest.json"
    latest.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(text)
    print(f"wrote {out_dir / 'summary.json'}")
    return 0 if any(row.get("ok") for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
