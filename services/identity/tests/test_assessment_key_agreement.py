"""The orchestrator signs assessment tokens; identity verifies them.

Both must resolve the same key. They used to disagree — the orchestrator fell
back to AUTH_SIGNING_KEY while identity went straight to the public dev
constant — so in the one configuration production is required to run in
(AUTH_SIGNING_KEY set, ASSESSMENT_SIGNING_KEY unset) genuine pass tokens were
rejected and forged ones were accepted.
"""

from __future__ import annotations

import pytest
from aoep_shared.auth import assessment_key_is_dev_default, assessment_signing_key

from identity.main import _assessment_signing_key


def test_identity_key_matches_the_shared_resolution(monkeypatch):
    monkeypatch.setenv("ASSESSMENT_SIGNING_KEY", "shared-assessment-secret")
    assert _assessment_signing_key() == assessment_signing_key()
    assert _assessment_signing_key() == b"shared-assessment-secret"


def test_auth_signing_key_never_stands_in_for_the_assessment_key(monkeypatch):
    monkeypatch.delenv("ASSESSMENT_SIGNING_KEY", raising=False)
    monkeypatch.setenv("AUTH_SIGNING_KEY", "a-very-strong-session-secret")
    # Both sides must land on the same value, and it must not be the auth secret.
    assert assessment_signing_key() == b"dev-assessment-signing-key"
    assert _assessment_signing_key() == assessment_signing_key()
    assert assessment_key_is_dev_default() is True


def test_orchestrator_resolves_the_same_key(monkeypatch):
    orchestrator = pytest.importorskip("orchestrator.main")
    monkeypatch.setenv("ASSESSMENT_SIGNING_KEY", "shared-assessment-secret")
    monkeypatch.setenv("AUTH_SIGNING_KEY", "a-different-session-secret")
    assert orchestrator._assessment_signing_key() == _assessment_signing_key()

    monkeypatch.delenv("ASSESSMENT_SIGNING_KEY", raising=False)
    assert orchestrator._assessment_signing_key() == _assessment_signing_key()
