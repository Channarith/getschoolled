"""Track B: domains -> LLM_ROUTES helper + RoutedLLMProvider round-trip."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "base"))

from routes import DEFAULT_CATEGORY_TO_DOMAIN, routes_from_domains  # noqa: E402

_DOMAINS = {
    "domains": [
        {"name": "stem", "adapter": "adapters/stem"},
        {"name": "humanities", "adapter": "adapters/humanities"},
        {"name": "medical", "adapter": "adapters/medical", "safety_gated": True},
    ]
}


def test_routes_from_domains_maps_categories():
    routes = routes_from_domains(_DOMAINS, {"math": "stem", "history": "humanities"})
    parts = dict(p.split("=") for p in routes.split(","))
    assert parts["math"] == "adapters/stem"
    assert parts["history"] == "adapters/humanities"


def test_safety_gated_domain_excluded():
    routes = routes_from_domains(_DOMAINS, {"medical": "medical", "math": "stem"})
    assert "medical=" not in routes
    assert "math=adapters/stem" in routes


def test_routes_feed_routed_provider():
    from aoep_shared.config import AppConfig, DeployMode
    from aoep_shared.providers.routing import RoutedLLMProvider, routes_from_config

    routes_str = routes_from_domains(_DOMAINS, {"math": "stem"})
    cfg = AppConfig(deploy_mode=DeployMode.LOCAL, llm_routes=routes_str)
    r = RoutedLLMProvider(base=_FakeBase(), routes=routes_from_config(cfg),
                          default_model="education-base")
    assert r.model_for("math") == "adapters/stem"
    assert r.model_for("unknown") == "education-base"


class _FakeBase:
    capability = "llm"

    def info(self):
        from aoep_shared.providers.base import ProviderInfo
        return ProviderInfo(capability="llm", mode="local", impl="fake", endpoint="x")

    def complete(self, messages, *, temperature=0.2, max_tokens=512):
        return "ok"


def test_default_category_map_covers_core_subjects():
    for subject in ("math", "history", "language", "culinary"):
        assert subject in DEFAULT_CATEGORY_TO_DOMAIN
