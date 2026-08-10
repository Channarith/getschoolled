"""Put the lab ``src`` (and packages/shared when present) on sys.path."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
SHARED = ROOT.parents[1] / "packages" / "shared" / "src"
if SHARED.is_dir():
    sys.path.insert(0, str(SHARED))
