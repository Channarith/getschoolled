"""Embodiment provider tests (Phase 14)."""

import pytest

from aoep_shared.config import AppConfig, DeployMode
from aoep_shared.factory import ProviderFactory
from aoep_shared.providers.embodiment import (
    MockRobotProvider,
    RobotProvider,
    ScreenAvatarProvider,
    narrate,
)


def test_screen_avatar_say_and_gesture():
    p = ScreenAvatarProvider()
    s = p.say("Hello class", language="en")
    assert s.modality == "speech"
    assert s.payload["text"] == "Hello class" and s.payload["tts"] is True
    g = p.gesture("wave")
    assert g.modality == "display" and g.payload["animation"] == "wave"


def test_mock_robot_records_actions():
    r = MockRobotProvider()
    narrate(r, "Welcome", gesture="nod")
    assert len(r.actions) == 2
    assert r.actions[0].modality == "speech" and r.actions[0].payload["actuator"] == "speaker"
    assert r.actions[1].modality == "gesture" and r.actions[1].payload["motion"] == "nod"


def test_factory_default_is_screen():
    fac = ProviderFactory(AppConfig(deploy_mode=DeployMode.LOCAL))
    assert fac.embodiment().info().impl == "screen-avatar"


def test_factory_robot_when_configured():
    fac = ProviderFactory(AppConfig(deploy_mode=DeployMode.EDGE, embodiment="robot"))
    assert isinstance(fac.embodiment(), RobotProvider)


def test_robot_not_wired_raises():
    with pytest.raises(NotImplementedError):
        RobotProvider().say("hi")


def test_narrate_maps_teaching_beat():
    actions = narrate(ScreenAvatarProvider(), "Explain fractions", gesture="point")
    assert [a.modality for a in actions] == ["speech", "display"]
