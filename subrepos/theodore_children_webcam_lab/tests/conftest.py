from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
SHARED = ROOT.parents[1] / "packages" / "shared" / "src"
for path in (SRC, SHARED):
    value = str(path)
    if value not in sys.path:
        sys.path.insert(0, value)
