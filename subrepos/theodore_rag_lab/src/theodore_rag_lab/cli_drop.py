"""Offline drop intake. Same runner as the RAG lab Drop training tab."""

from __future__ import annotations

import sys
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[4]
    script = root / "scripts" / "training_drop.py"
    sys.path.insert(0, str(script.parent))
    import importlib.util

    spec = importlib.util.spec_from_file_location("training_drop", script)
    if spec is None or spec.loader is None:
        print("training_drop.py is missing", file=sys.stderr)
        return 2
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
