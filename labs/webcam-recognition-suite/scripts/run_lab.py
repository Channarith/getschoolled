#!/usr/bin/env python3
"""Run the private webcam recognition lab from the monorepo root."""

from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SRC = os.path.join(_ROOT, "src")
_SHARED = os.path.abspath(os.path.join(_ROOT, "..", "..", "packages", "shared", "src"))
for _p in (_SRC, _SHARED):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from webcam_recognition_suite.lab import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
