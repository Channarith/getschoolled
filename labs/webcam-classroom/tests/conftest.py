"""Pytest bootstrap for the webcam-classroom lab.

Puts this lab's ``src`` on the path so ``import webcam_classroom`` resolves
whether or not the package is pip-installed, and adds the monorepo's
``packages/shared/src`` when present (for the optional face-observation bridge).
Nothing here needs a network, GPU, or API key.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
_SHARED = os.path.abspath(
    os.path.join(_HERE, "..", "..", "..", "packages", "shared", "src")
)
for _p in (_SRC, _SHARED):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)
