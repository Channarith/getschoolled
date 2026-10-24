#!/usr/bin/env python3
"""Score an OpenAI-compatible local server with the same token-F1 as evaluate.py.

Used to bake the STEM adapter off against the model actually being served
(llama-server). No API key is read or printed. Fully local HTTP.
"""

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from typing import Dict, List

from evaluate import aggregate_scores, read_jsonl, token_f1


def _prompt_messages(row: Dict) -> list:
    ctx = ", ".join(f"{k}={v}" for k, v in (row.get("context") or {}).items())
    instruction = row.get("instruction", "")
    return [
        {
            "role": "system",
            "content": (
                "You are a tutor. Answer the question in a few plain sentences. "
                "Do not show hidden reasoning."
            ),
        },
        {
            "role": "user",
            "content": f"Audience: {ctx}\n\nQuestion: {instruction}",
        },
    ]


def complete(base_url: str, model: str, row: Dict, *, max_tokens: int, timeout: float) -> str:
    url = base_url.rstrip("/") + "/chat/completions"
    body = {
        "model": model,
        "messages": _prompt_messages(row),
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
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    choices = payload.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    return (message.get("content") or "").strip()


def _group(row: Dict) -> str | None:
    ctx = row.get("context") or {}
    level = ctx.get("reading_level")
    return str(level) if level else (str(ctx["language"]) if ctx.get("language") else None)


def _category(row: Dict) -> str | None:
    tags = row.get("tags") or []
    return str(tags[0]) if tags else None


def score_server(
    rows: List[Dict],
    *,
    base_url: str,
    model: str,
    max_tokens: int,
    timeout: float,
) -> Dict:
    items = []
    errors = 0
    for row in rows:
        if not row.get("response"):
            continue
        try:
            text = complete(base_url, model, row, max_tokens=max_tokens, timeout=timeout)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError) as exc:
            errors += 1
            print(f"WARNING: serve eval request failed: {type(exc).__name__}")
            continue
        items.append(
            {
                "score": token_f1(text, row.get("response", ""), legacy_ascii=True),
                "category": _category(row),
                "group": _group(row),
            }
        )
    if not items:
        raise RuntimeError(f"no scored rows (errors={errors})")
    metrics = aggregate_scores(items)
    return {
        "n": metrics["n"],
        "token_f1": metrics["overall"],
        "accuracy": metrics["overall"],
        "fairness_gap": metrics["fairness_gap"],
        "by_category": metrics["by_category"],
        "errors": errors,
        "model": model,
        "base_url": base_url,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="OpenAI-compatible origin, e.g. http://127.0.0.1:8342/v1")
    parser.add_argument("--model", required=True)
    parser.add_argument("--eval", required=True)
    parser.add_argument("--metrics-out", required=True)
    parser.add_argument("--max-tokens", type=int, default=96)
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args(argv)

    rows = read_jsonl(args.eval)
    metrics = score_server(
        rows,
        base_url=args.base_url,
        model=args.model,
        max_tokens=args.max_tokens,
        timeout=args.timeout,
    )
    out = args.metrics_out
    from pathlib import Path

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: metrics[k] for k in ("n", "accuracy", "fairness_gap", "errors")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
