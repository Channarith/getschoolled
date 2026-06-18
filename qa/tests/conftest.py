"""Put qa/ on sys.path so ``import stress`` resolves."""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_QA = os.path.abspath(os.path.join(_HERE, ".."))
if _QA not in sys.path:
    sys.path.insert(0, _QA)
