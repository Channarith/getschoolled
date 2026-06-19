"""Test-support helpers for automation/E2E testing.

Services can expose deterministic reset/seed hooks for automated test runs, but
those hooks mutate global state and must never be available by accident in a
real deployment. They are therefore double-gated:

  1. the caller must present the admin secret, AND
  2. test endpoints must be explicitly enabled for the process.

``test_endpoints_enabled()`` returns True when ``ENABLE_TEST_ENDPOINTS`` is set
to a truthy value, or implicitly in local/edge deploy modes (developer machines
and on-device/test rigs), and never in cloud mode unless explicitly opted in.
"""

from __future__ import annotations

import os
from typing import Optional

from .config import AppConfig, DeployMode

_TRUTHY = {"1", "true", "yes", "on"}


def test_endpoints_enabled(config: Optional[AppConfig] = None) -> bool:
    raw = os.environ.get("ENABLE_TEST_ENDPOINTS")
    if raw is not None:
        return raw.strip().lower() in _TRUTHY
    # Implicit default: enabled for local/edge, disabled for cloud.
    mode = config.deploy_mode if config is not None else None
    return mode in (DeployMode.LOCAL, DeployMode.EDGE)
