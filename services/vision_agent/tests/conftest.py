"""Pytest fixtures for vision_agent service tests.

Puts src on the path, disables rate-limiting and internal-auth, and provides
lightweight stubs for OpenCV and xAI so tests pass without heavy deps or API keys.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
_SHARED_SRC = os.path.abspath(
    os.path.join(_HERE, "..", "..", "..", "packages", "shared", "src")
)
for _p in (_SRC, _SHARED_SRC, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Bypass rate-limiting and internal-auth in tests.
os.environ.setdefault("RATE_LIMIT_DISABLED", "1")
os.environ.setdefault("INTERNAL_AUTH_DISABLED", "1")
# Use local deploy mode so providers resolve without cloud endpoints.
os.environ.setdefault("DEPLOY_MODE", "local")
# Disable real model downloads in CI.
os.environ.setdefault("VISION_MODEL_DIR", "/tmp/vision_agent_test_models")
