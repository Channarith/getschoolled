"""Contract tests for the public AOEP Python SDK."""

from __future__ import annotations

import json
import sys
import urllib.error
from io import BytesIO

import pytest

from aoep_sdk import AOEPClient, AOEPConfig, NotFoundError, ServiceURLs
from aoep_sdk.clients import CurriculumClient, MemoryClient, OrchestratorClient
from aoep_sdk.transport import JSONTransport


class FakeResponse:
    def __init__(self, payload) -> None:
        self.payload = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self.payload

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args) -> bool:
        return False


def test_inprocess_retrieval_does_not_load_heavy_harvest_stack():
    import aoep_sdk.inprocess as inprocess

    sys.modules.pop("aoep_shared.harvest", None)
    index = inprocess.RagIndex(
        [inprocess.Document.from_text("loops", "Loops", "Loops repeat work.")]
    )

    assert index.retrieve("repeat")
    assert "aoep_shared.harvest" not in sys.modules


def test_service_urls_honor_legacy_service_env_names(monkeypatch):
    monkeypatch.setenv("ORCHESTRATOR_URL", "http://legacy-orchestrator:9000")
    monkeypatch.setenv("AOEP_CURRICULUM_URL", "http://explicit-curriculum:9005")

    urls = ServiceURLs.from_env()

    assert urls.orchestrator == "http://legacy-orchestrator:9000"
    assert urls.curriculum == "http://explicit-curriculum:9005"


def test_transport_maps_validation_and_rate_limit_errors(monkeypatch):
    from aoep_sdk import AuthenticationError, RateLimitError, ValidationError

    cases = [
        (400, ValidationError),
        (422, ValidationError),
        (401, AuthenticationError),
        (429, RateLimitError),
    ]

    for status, expected in cases:

        def fake_urlopen(request, timeout, *, status=status):
            raise urllib.error.HTTPError(
                request.full_url,
                status,
                "error",
                {},
                BytesIO(json.dumps({"detail": "bad request"}).encode("utf-8")),
            )

        monkeypatch.setattr(
            "aoep_sdk.transport.urllib.request.urlopen", fake_urlopen
        )
        with pytest.raises(expected) as caught:
            JSONTransport("https://api.example.com").request("GET", "/x")
        assert caught.value.status_code == status


def test_identity_signup_updates_session_token(monkeypatch):
    monkeypatch.setattr(
        "aoep_sdk.transport.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(
            {"token": "signup-token", "account": {"id": "a1"}}
        ),
    )
    from aoep_sdk.clients import IdentityClient

    transport = JSONTransport("https://identity.example.com")
    client = IdentityClient(transport)
    client.signup("dev@example.com", "secret")

    assert transport.bearer_token == "signup-token"


def test_service_urls_support_cloud_origin_and_explicit_override(monkeypatch):
    monkeypatch.setenv("AOEP_BASE_URL", "https://learn.example.com/")
    monkeypatch.setenv("AOEP_IDENTITY_URL", "https://identity.example.com/")

    urls = ServiceURLs.from_env()

    assert urls.orchestrator == "https://learn.example.com/orchestrator"
    assert urls.curriculum == "https://learn.example.com/curriculum"
    assert urls.identity == "https://identity.example.com"


def test_config_normalizes_internal_auth_environment(monkeypatch):
    monkeypatch.setenv("INTERNAL_SERVICE_TOKEN", "service-token")
    monkeypatch.setenv("AOEP_TIMEOUT_SECONDS", "2.5")

    config = AOEPConfig.from_env()

    assert config.internal_token == "service-token"
    assert config.timeout_seconds == 2.5


def test_transport_sends_standard_auth_and_request_headers(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse({"ok": True})

    monkeypatch.setattr("aoep_sdk.transport.urllib.request.urlopen", fake_urlopen)
    transport = JSONTransport(
        "https://api.example.com",
        bearer_token="user-token",
        internal_token="internal-token",
        admin_secret="admin-secret",
        timeout_seconds=3,
    )

    assert transport.request("POST", "/items", json_body={"name": "course"}) == {
        "ok": True
    }
    headers = {key.lower(): value for key, value in captured["request"].header_items()}
    assert headers["authorization"] == "Bearer user-token"
    assert headers["x-internal-token"] == "internal-token"
    assert headers["x-admin-secret"] == "admin-secret"
    assert headers["content-type"] == "application/json"
    assert headers["x-request-id"]
    assert captured["timeout"] == 3


def test_transport_maps_api_errors(monkeypatch):
    def fake_urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url,
            404,
            "Not Found",
            {"X-Request-ID": "server-request-id"},
            None,
        )

    monkeypatch.setattr("aoep_sdk.transport.urllib.request.urlopen", fake_urlopen)

    with pytest.raises(NotFoundError) as caught:
        JSONTransport("https://api.example.com").request("GET", "/missing")

    assert caught.value.status_code == 404
    assert caught.value.request_id == "server-request-id"


def test_orchestrator_client_builds_core_teaching_requests(monkeypatch):
    requests = []

    def fake_urlopen(request, timeout):
        requests.append(request)
        return FakeResponse({"session": {"session_id": "s1"}})

    monkeypatch.setattr("aoep_sdk.transport.urllib.request.urlopen", fake_urlopen)
    client = OrchestratorClient(JSONTransport("https://api.example.com"))

    client.start_session("lesson/one", class_type="solo", student_id="student-1")
    client.ask("session/one", "Why?", language="es")

    start_body = json.loads(requests[0].data)
    ask_body = json.loads(requests[1].data)
    assert requests[0].full_url == "https://api.example.com/api/sessions"
    assert start_body["lesson_id"] == "lesson/one"
    assert start_body["class_type"] == "solo"
    assert requests[1].full_url.endswith("/api/sessions/session%2Fone/ask")
    assert ask_body == {"text": "Why?", "language": "es"}


def test_curriculum_search_uses_api_parameter_names(monkeypatch):
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        return FakeResponse({"items": [], "total": 0})

    monkeypatch.setattr("aoep_sdk.transport.urllib.request.urlopen", fake_urlopen)
    client = CurriculumClient(JSONTransport("https://curriculum.example.com"))

    client.search("python", media_format="audio", kids=True, limit=10)

    assert "q=python" in captured["url"]
    assert "format=audio" in captured["url"]
    assert "kids=True" in captured["url"]
    assert "limit=10" in captured["url"]


def test_memory_client_maps_learner_signals(monkeypatch):
    monkeypatch.setattr(
        "aoep_sdk.transport.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(
            {
                "topic_mastery": 0.9,
                "quiz_accuracy": 0.8,
                "avg_response_latency_s": 3,
                "attention_trend": 0.95,
                "question_rate": 0.2,
            }
        ),
    )

    signals = MemoryClient(
        JSONTransport("https://memory.example.com", internal_token="internal")
    ).learner_signals("student/1", "python basics")

    assert signals.topic_mastery == 0.9
    assert signals.quiz_accuracy == 0.8
    assert signals.skill() == pytest.approx(0.85)


def test_authenticate_applies_identity_token_to_every_service(monkeypatch):
    monkeypatch.setattr(
        "aoep_sdk.transport.urllib.request.urlopen",
        lambda request, timeout: FakeResponse(
            {"token": "session-token", "account": {"id": "a1"}}
        ),
    )
    client = AOEPClient(AOEPConfig())

    client.authenticate("dev@example.com", "secret")

    assert all(
        transport.bearer_token == "session-token"
        for transport in client._transports.values()
    )


def test_local_client_rejects_remote_urls():
    with pytest.raises(Exception) as caught:
        AOEPClient(
            AOEPConfig(
                services=ServiceURLs(
                    orchestrator="https://prod.example.com/orchestrator"
                ),
                require_local=True,
            )
        )
    assert "local-only" in str(caught.value).lower() or "loopback" in str(
        caught.value
    ).lower()


def test_aoep_client_local_factory_uses_localhost():
    client = AOEPClient.local()
    assert client.config.require_local is True
    assert client.config.services.orchestrator.startswith("http://localhost")
    assert client.config.admin_secret == ""
    assert client.config.internal_token == ""


def test_local_factory_forces_deploy_mode_local(monkeypatch):
    import aoep_sdk.local as local_mod

    captured = {}

    def fake_load_config(env=None):
        captured["env"] = dict(env or {})
        return "config"

    monkeypatch.setattr(local_mod, "load_config", fake_load_config)
    monkeypatch.setattr(local_mod, "build_factory", lambda cfg: f"factory:{cfg}")

    factory = local_mod.local_factory({"LLM_MODE": "local"})
    assert factory == "factory:config"
    assert captured["env"]["DEPLOY_MODE"] == "local"
    assert captured["env"]["LLM_MODE"] == "local"
