from __future__ import annotations

import os
import sys

# Put this package's ``src`` on sys.path so the suite runs from the repo root,
# matching every other package in this monorepo.
_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))

if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
