"""Pytest fixtures for the webcam service tests.

Puts the webcam ``src`` directory on sys.path so imports resolve, and disables
rate-limiting and internal-auth for the test suite.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
_SHARED_SRC = os.path.abspath(
    os.path.join(_HERE, "..", "..", "..", "packages", "shared", "src")
)
for _p in (_SRC, _SHARED_SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Disable rate-limiting and internal auth for test suite.
os.environ.setdefault("RATE_LIMIT_DISABLED", "1")
os.environ.setdefault("INTERNAL_AUTH_DISABLED", "1")
