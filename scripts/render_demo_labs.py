#!/usr/bin/env python3
"""Keep only the public demo lab documents from a kustomize render.

The full VKE overlay is too broad to apply on every deploy (it can fight
digest pins and Redis volume claims). Demo deploys need just course-studio
and children-lab, already rewritten to the production registry.

Usage:
  kubectl kustomize infra/k8s-vke | python3 scripts/render_demo_labs.py
"""

from __future__ import annotations

import sys

NAMES = ("course-studio", "children-lab")


def documents(text: str) -> list[str]:
    docs: list[str] = []
    current: list[str] = []
    for line in text.splitlines(True):
        if line.strip() == "---":
            if current:
                docs.append("".join(current))
            current = []
            continue
        current.append(line)
    if current and "".join(current).strip():
        docs.append("".join(current))
    return docs


def selected(text: str) -> str:
    picked: list[str] = []
    for doc in documents(text):
        body = f"\n{doc}"
        if any(f"\n  name: {name}\n" in body for name in NAMES):
            picked.append(doc.strip() + "\n")
    if len(picked) != 4:
        names = ", ".join(NAMES)
        raise SystemExit(
            f"expected 4 demo-lab documents (Deployment+Service for {names}), "
            f"found {len(picked)}"
        )
    return "---\n".join(picked)


def by_kind(text: str, kind: str) -> str:
    # kustomize writes apiVersion before kind. Match the kind line, not a prefix.
    needle = f"kind: {kind}"
    kept = [
        doc.strip() + "\n"
        for doc in documents(text)
        if needle in {line.strip() for line in doc.splitlines()}
    ]
    if not kept:
        raise SystemExit(f"no demo-lab documents of kind {kind}")
    return "---\n".join(kept)


def main() -> None:
    args = sys.argv[1:]
    kind = ""
    if args:
        if len(args) != 2 or args[0] != "--kind" or args[1] not in {"Service", "Deployment"}:
            raise SystemExit("usage: render_demo_labs.py [--kind Service|Deployment]")
        kind = args[1]
    body = selected(sys.stdin.read())
    sys.stdout.write(by_kind(body, kind) if kind else body)


if __name__ == "__main__":
    main()
