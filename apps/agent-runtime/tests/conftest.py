"""Put ``src`` on sys.path so ``import agent_runtime.*`` resolves."""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
# agent_runtime.brain depends on the orchestrator package (aoep-orchestrator);
# add its src so the brain is importable in tests without installing the dist.
_ORCH_SRC = os.path.abspath(
    os.path.join(_HERE, "..", "..", "..", "services", "orchestrator", "src")
)
for _p in (_SRC, _ORCH_SRC, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)
