"""RoutedLLMProvider category routing + config parsing tests."""

from aoep_shared.config import AppConfig, DeployMode
from aoep_shared.providers.base import ProviderInfo
from aoep_shared.providers.routing import RoutedLLMProvider, routes_from_config


class _FakeBase:
    capability = "llm"

    def info(self):
        return ProviderInfo(capability="llm", mode="local", impl="fake",
                            endpoint="http://x")

    def complete(self, messages, *, temperature=0.2, max_tokens=512):
        return "ok"


def test_routes_to_adapter_then_default():
    r = RoutedLLMProvider(_FakeBase(),
                          routes={"math": "adapters/stem", "history": "adapters/hum"},
                          default_model="education-base")
    assert r.model_for("math") == "adapters/stem"
    assert r.model_for("history") == "adapters/hum"
    assert r.model_for("unknown") == "education-base"
    assert r.model_for(None) == "education-base"


def test_routes_from_config():
    cfg = AppConfig(deploy_mode=DeployMode.LOCAL,
                    llm_routes="math=adapters/stem, biology=adapters/stem , history=adapters/hum")
    routes = routes_from_config(cfg)
    assert routes == {"math": "adapters/stem", "biology": "adapters/stem",
                      "history": "adapters/hum"}


def test_complete_delegates_to_base():
    r = RoutedLLMProvider(_FakeBase(), default_model="base")
    assert r.complete([], category="math") == "ok"
