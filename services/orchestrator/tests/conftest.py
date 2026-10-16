"""Put the service ``src`` on sys.path so ``import orchestrator.*`` resolves."""

from __future__ import annotations

import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
for _p in (_SRC, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Disable rate limiting + share-clock cache for tests; the platform-wide
# limiter is unit-tested in packages/shared and would otherwise flake
# busy service test suites that issue hundreds of requests per session.
os.environ.setdefault("RATE_LIMIT_DISABLED", "1")

# Bypass the internal-auth gate by default in tests. Specific tests
# that exercise the gate clear this env via monkeypatch.
os.environ.setdefault("INTERNAL_AUTH_DISABLED", "1")

# Keep live-class sessions in-process for tests so a stray REDIS_URL in the
# environment can't make the suite talk to a real Redis. Tests that exercise the
# store factory override this via monkeypatch.
os.environ.setdefault("SESSION_BACKEND", "memory")
os.environ.setdefault("LIVE_ROOM_BACKEND", "memory")
os.environ.setdefault("GROUP_CLASS_BACKEND", "memory")

# Room and group-class behavior tests predate the verified-identity gate.
# They exercise paid-account flows, so the gate resolves them as a paid
# caller. Adversarial tests in test_free_plan_live_access.py do not use this
# and call the real resolver.
_PAID_IDENTITY_MODULES = {
    "test_group_classes_api",
    "test_human_taught_class",
    "test_live_room_api",
    "test_regression_recent_fixes",
    # Tutor, training-session, and meeting-token calls predate the paid-AI
    # gate. These suites exercise the feature, not the free-plan denial.
    # Adversarial coverage lives in test_free_plan_agent_execution.py.
    "test_teaching_api",
    "test_ask_stream_api",
    "test_groundedness_api",
    "test_agent_reward",
    "test_visuals_api",
    "test_hil_api",
    "test_slang_api",
    "test_training_api",
    "test_orchestrator",
    # Certifiable starts present a locally signed Bearer token and then talk
    # to identity assurance. The profile read must succeed or the session
    # gate fails closed with 503 before that check.
    "test_accreditation_account_gate",
}


@pytest.fixture(autouse=True)
def _paid_account_for_legacy_room_tests(request, monkeypatch):
    module = getattr(request.module, "__name__", "").rsplit(".", 1)[-1]
    if module not in _PAID_IDENTITY_MODULES:
        return

    issued = {"n": 0}

    def require_verified_profile(authorization="", **kwargs):
        auth = str(authorization or "").strip()
        # Requests that omit a token still have to look like distinct paid
        # learners, or repeat registrations collapse onto one account.
        if not auth.lower().startswith("bearer "):
            issued["n"] += 1
            account_id = f"paid-regression-{issued['n']}"
        else:
            account_id = "paid-" + auth.split(None, 1)[-1][:48]
        return {
            "id": account_id,
            "tier": "premium",
            "free_plan": {"active": False},
        }

    monkeypatch.setattr(
        "aoep_shared.live_room_rewards.require_verified_profile",
        require_verified_profile,
    )
