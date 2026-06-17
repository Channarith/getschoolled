"""Vision provider implementations (biometrics; boundary-sensitive).

local  -> InsightFace/ArcFace (identity) + MediaPipe (gaze/attention).
cloud  -> the same models on GPU pods.

Face recognition only runs for students who have given explicit consent. The
consent gate is enforced here (and again at the consent service) so an
unconsented student is never matched to an identity -- a name-only fallback is
used instead.
"""

from __future__ import annotations

from typing import Iterable

from ..config import AppConfig
from .base import FaceObservation, ProviderInfo, VisionProvider


class _BaseVisionProvider(VisionProvider):
    impl = "vision"

    def __init__(self, config: AppConfig, *, mode: str) -> None:
        self._config = config
        self._mode = mode
        self._base_url = config.vision_base_url

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            capability=self.capability,
            mode=self._mode,
            impl=self.impl,
            endpoint=self._base_url,
        )

    def analyze_frame(
        self, frame_object_key: str, *, consented_student_ids: Iterable[str]
    ) -> list[FaceObservation]:
        # The set of consented students is what we are allowed to match against.
        # This check is pure and testable; the model inference is not.
        self._consented = frozenset(consented_student_ids)
        raise NotImplementedError(
            "Vision models not loaded in this environment; configure the "
            "perception service (InsightFace + MediaPipe)."
        )

    def may_identify(self, student_id: str) -> bool:
        """Whether identity matching is permitted for ``student_id``."""
        return student_id in getattr(self, "_consented", frozenset())


class LocalVisionProvider(_BaseVisionProvider):
    impl = "insightface-mediapipe-local"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config, mode="local")


class CloudVisionProvider(_BaseVisionProvider):
    impl = "insightface-mediapipe-cloud"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config, mode="cloud")
