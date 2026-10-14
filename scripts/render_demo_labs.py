#!/usr/bin/env python3
"""Keep only the public demo lab documents from a kustomize render.

The full VKE overlay is too broad to apply on every deploy (it can fight
digest pins and Redis volume claims). Demo deploys need course-studio,
children-lab, audio-lab, and music, already rewritten to the production registry.

Usage:
  kubectl kustomize infra/k8s-vke | python3 scripts/render_demo_labs.py
  python3 scripts/render_demo_labs.py --kind Deployment --name audio-lab
"""

from __future__ import annotations

import sys

NAMES = ("course-studio", "children-lab", "audio-lab", "music")


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


def selected(text: str, names: tuple[str, ...] = NAMES) -> str:
    picked: list[str] = []
    for doc in documents(text):
        body = f"\n{doc}"
        if any(f"\n  name: {name}\n" in body for name in names):
            picked.append(doc.strip() + "\n")
    expected = 2 * len(names)
    if len(picked) != expected:
        listed = ", ".join(names)
        raise SystemExit(
            f"expected {expected} demo-lab documents (Deployment+Service for {listed}), "
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


def _parse_args(argv: list[str]) -> tuple[str, str]:
    kind = ""
    name = ""
    i = 0
    while i < len(argv):
        flag = argv[i]
        if flag not in {"--kind", "--name"} or i + 1 >= len(argv):
            raise SystemExit(
                "usage: render_demo_labs.py [--kind Service|Deployment] "
                "[--name course-studio|children-lab|audio-lab|music]"
            )
        value = argv[i + 1]
        if flag == "--kind":
            if value not in {"Service", "Deployment"}:
                raise SystemExit("usage: render_demo_labs.py [--kind Service|Deployment]")
            kind = value
        else:
            if value not in NAMES:
                raise SystemExit(f"unknown demo lab {value}")
            name = value
        i += 2
    return kind, name


def main() -> None:
    kind, name = _parse_args(sys.argv[1:])
    names = (name,) if name else NAMES
    body = selected(sys.stdin.read(), names)
    sys.stdout.write(by_kind(body, kind) if kind else body)


if __name__ == "__main__":
    main()
