"""Put the service ``src`` (and packages/shared) on sys.path for imports."""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
_SHARED = os.path.abspath(os.path.join(_HERE, "..", "..", "..", "packages", "shared", "src"))
for _p in (_SRC, _SHARED, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
