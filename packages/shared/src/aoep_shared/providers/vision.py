"""Vision provider implementations (biometrics; boundary-sensitive).

local  -> OpenCV YuNet (detection) + SFace (128-d embeddings), CPU, self-hosted.
cloud  -> the same models on GPU pods (not reachable in this dev/CI environment).

Face recognition only runs for students who have given explicit consent. The
consent gate is enforced here (and again at the consent service) so an
unconsented student is never matched to an identity -- a name-only/anonymous
fallback is used instead. Raw embeddings are never returned to callers.
"""

from __future__ import annotations

from typing import Iterable, List, Optional

from ..config import AppConfig
from ..vision import FaceGallery, FaceRecognitionEngine
from .base import FaceObservation, ProviderInfo, VisionProvider


class _BaseVisionProvider(VisionProvider):
    impl = "vision"

    def __init__(self, config: AppConfig, *, mode: str) -> None:
        self._config = config
        self._mode = mode
        self._base_url = config.vision_base_url
        self._consented: frozenset[str] = frozenset()
        self._engine: Optional[FaceRecognitionEngine] = None
        self._gallery = FaceGallery(match_threshold=config.vision_match_threshold)

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            capability=self.capability,
            mode=self._mode,
            impl=self.impl,
            endpoint=self._base_url,
        )

    # --- engine lifecycle -------------------------------------------------- #
    def _build_engine(self) -> FaceRecognitionEngine:
        raise NotImplementedError

    def engine(self) -> FaceRecognitionEngine:
        if self._engine is None:
            self._engine = self._build_engine()
        return self._engine

    def ready(self) -> bool:
        # Cheap check: don't load models here (may require download).
        return True

    # --- enrollment / recognition ----------------------------------------- #
    def enroll(self, student_id: str, image: bytes | str) -> int:
        """Enroll a face for ``student_id``; returns the enrollment count.

        Raises ``ValueError`` if no face is detected in the image.
        """
        faces = self.engine().detect_faces(image)
        if not faces:
            raise ValueError("no face detected in enrollment image")
        return self._gallery.enroll(student_id, faces[0].embedding)

    def gallery(self) -> FaceGallery:
        return self._gallery

    def analyze_image(
        self, image: bytes | str, *, consented_student_ids: Iterable[str]
    ) -> List[FaceObservation]:
        """Detect faces and match only against the consented set."""
        self._consented = frozenset(consented_student_ids)
        observations: List[FaceObservation] = []
        for idx, face in enumerate(self.engine().detect_faces(image)):
            match = self._gallery.identify(
                face.embedding, allowed_ids=self._consented
            )
            observations.append(
                FaceObservation(
                    track_id=f"face-{idx}",
                    embedding_ref=None,  # never expose raw biometrics
                    # Attention/gaze model is phase3; use detection confidence as
                    # an interim presence proxy until MediaPipe gaze lands.
                    attention_score=round(face.det_score, 4),
                    matched_student_id=match.student_id if match.matched else None,
                )
            )
        return observations

    def analyze_frame(
        self, frame_object_key: str, *, consented_student_ids: Iterable[str]
    ) -> List[FaceObservation]:
        # In local mode the object key resolves to a filesystem path; the engine
        # decodes the image. Matching is restricted to the consented set.
        return self.analyze_image(
            frame_object_key, consented_student_ids=consented_student_ids
        )

    def may_identify(self, student_id: str) -> bool:
        """Whether identity matching is permitted for ``student_id``."""
        return student_id in self._consented


class LocalVisionProvider(_BaseVisionProvider):
    impl = "opencv-sface-yunet-local"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config, mode="local")

    def _build_engine(self) -> FaceRecognitionEngine:
        model_dir = self._config.vision_model_dir or None
        return FaceRecognitionEngine.from_models(
            model_dir, match_threshold=self._config.vision_match_threshold
        )


class CloudVisionProvider(_BaseVisionProvider):
    impl = "opencv-sface-yunet-cloud"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config, mode="cloud")

    def _build_engine(self) -> FaceRecognitionEngine:
        # Cloud GPU pods serve the same models; not reachable from dev/CI.
        raise NotImplementedError(
            "Cloud vision pods are not reachable in this environment; "
            "pin VISION_MODE=local to run biometrics inside this boundary."
        )
