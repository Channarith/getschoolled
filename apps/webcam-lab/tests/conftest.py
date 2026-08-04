"""Pytest path bootstrap for webcam-lab."""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
_SHARED = os.path.abspath(os.path.join(_HERE, "..", "..", "..", "packages", "shared", "src"))
for _p in (_SRC, _SHARED):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("RATE_LIMIT_DISABLED", "1")
os.environ.setdefault("XAI_API_KEY", "")  # force mock tokens in tests
