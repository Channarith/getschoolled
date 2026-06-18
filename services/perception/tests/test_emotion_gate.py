"""EU AI Act emotion-recognition gate in the vision provider (no network)."""

from dataclasses import dataclass
from typing import List, Tuple

from aoep_shared.config import AppConfig, DeployMode
from aoep_shared.providers.vision import LocalVisionProvider


@dataclass
class _FakeFace:
    embedding: list
    bbox: Tuple[int, int, int, int]
    landmarks: List[Tuple[float, float]]
    frame_size: Tuple[int, int]


class _FakeEngine:
    def detect_faces(self, image):
        # Neutral 5-point landmarks (right_eye, left_eye, nose, r_mouth, l_mouth).
        lmk = [(40, 50), (60, 50), (50, 62), (44, 74), (56, 74)]
        return [_FakeFace(embedding=[0.1, 0.2, 0.3], bbox=(30, 30, 40, 50),
                          landmarks=lmk, frame_size=(200, 200))]


def _provider(region: str) -> LocalVisionProvider:
    cfg = AppConfig(deploy_mode=DeployMode.LOCAL, region=region)
    prov = LocalVisionProvider(cfg)
    prov._engine = _FakeEngine()  # stub so no model download is needed
    return prov


def test_emotion_suppressed_in_eu():
    obs = _provider("eu").analyze_image(b"img", consented_student_ids=[])
    assert obs and all(o.expression is None for o in obs)
    # Attention/gaze are still computed (not an emotion under the ban).
    assert all(o.attention_score >= 0.0 for o in obs)


def test_emotion_present_in_us():
    obs = _provider("us").analyze_image(b"img", consented_student_ids=[])
    assert obs and all(o.expression is not None for o in obs)


def test_emotion_suppressed_in_other_region_by_default():
    obs = _provider("other").analyze_image(b"img", consented_student_ids=[])
    assert obs and all(o.expression is None for o in obs)
