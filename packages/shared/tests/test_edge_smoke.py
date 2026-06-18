"""On-device edge runtime boot smoke (Phase 15)."""

from aoep_shared.edge import edge_config, edge_smoke
from aoep_shared.factory import ProviderFactory


def test_edge_smoke_runs_offline_teaching_beat():
    fac = ProviderFactory(edge_config(embodiment="robot"))
    result = edge_smoke(fac)
    assert result["offline"] is True
    assert result["embodiment_target"] == "robot"
    assert result["actions"] == 2
    assert result["first_modality"] == "speech"


def test_edge_smoke_screen_default():
    fac = ProviderFactory(edge_config())
    result = edge_smoke(fac)
    assert result["offline"] is True
    assert result["embodiment_target"] == "screen-avatar"
