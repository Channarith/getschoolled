"""QA test harness path setup and orchestrator-friendly env defaults."""

from __future__ import annotations

import os
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_QA = _HERE.parent
_ROOT = _QA.parent

for _path in (_QA,):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

# Cross-service smoke/regression tests import FastAPI apps from service src trees.
for _service in (
    "orchestrator",
    "billing",
    "identity",
    "memory",
    "curriculum",
    "speech",
    "perception",
    "integrations",
    "harvester",
):
    _src = _ROOT / "services" / _service / "src"
    if _src.is_dir() and str(_src) not in sys.path:
        sys.path.insert(0, str(_src))

_agent_src = _ROOT / "apps" / "agent-runtime" / "src"
if _agent_src.is_dir() and str(_agent_src) not in sys.path:
    sys.path.insert(0, str(_agent_src))

os.environ.setdefault("RATE_LIMIT_DISABLED", "1")
os.environ.setdefault("INTERNAL_AUTH_DISABLED", "1")
os.environ.setdefault("SESSION_BACKEND", "memory")
os.environ.setdefault("LIVE_ROOM_BACKEND", "memory")
os.environ.setdefault("GROUP_CLASS_BACKEND", "memory")
