"""Vision provider implementations (biometrics; boundary-sensitive).

local  -> OpenCV YuNet (detection) + SFace (128-d embeddings), CPU, self-hosted.
cloud  -> the same models on GPU pods (not reachable in this dev/CI environment).

Face recognition only runs for students who have given explicit consent. The
consent gate is enforced here (and again at the consent service) so an
unconsented student is never matched to an identity -- a name-only/anonymous
fallback is used instead. Raw embeddings are never returned to callers.
"""

from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Tuple

from ..config import AppConfig
from ..vision import FaceGallery, FaceRecognitionEngine, estimate_engagement
from .base import EmbeddedFace, FaceObservation, ProviderInfo, VisionProvider


class _BaseVisionProvider(VisionProvider):
    impl = "vision"

    def __init__(self, config: AppConfig, *, mode: str) -> None:
        self._config = config
        self._mode = mode
        self._base_url = config.vision_base_url
        self._consented: frozenset[str] = frozenset()
        self._engine: Optional[FaceRecognitionEngine] = None
        # Cross-session student memory: load persisted embeddings if configured.
        self._gallery_path = config.vision_gallery_path or None
        if self._gallery_path:
            self._gallery = FaceGallery.load_json(self._gallery_path)
            self._gallery.match_threshold = config.vision_match_threshold
        else:
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
    def _persist_gallery(self) -> None:
        # Persist so the student is remembered across sessions.
        if self._gallery_path:
            self._gallery.save_json(self._gallery_path)

    def enroll(self, student_id: str, image: bytes | str) -> int:
        """Enroll a face for ``student_id``; returns the enrollment count.

        Raises ``ValueError`` if no face is detected in the image.
        """
        faces = self.engine().detect_faces(image)
        if not faces:
            raise ValueError("no face detected in enrollment image")
        count = self._gallery.enroll(student_id, faces[0].embedding)
        self._persist_gallery()
        return count

    def enroll_embedding(self, student_id: str, embedding: Sequence[float]) -> int:
        """Enroll a precomputed (on-device) embedding for ``student_id``.

        The hybrid path: the client device runs YuNet+SFace locally and sends
        only the 128-d embedding, so the server never loads the model or sees the
        raw frame. Raises ``ValueError`` on an empty embedding.
        """
        vec = [float(x) for x in embedding]
        if not vec:
            raise ValueError("empty embedding")
        count = self._gallery.enroll(student_id, vec)
        self._persist_gallery()
        return count

    def gallery(self) -> FaceGallery:
        return self._gallery

    def _apply_identity_gate(self, consented_student_ids: Iterable[str]) -> None:
        """Resolve who may be matched given the region compliance gate.

        Where real-time biometric identification is prohibited (e.g. EU AI Act),
        run in anonymous mode - detect/engage but never match an identity,
        regardless of the consented set.
        """
        from ..compliance import FEATURE_REALTIME_BIOMETRIC_ID, feature_allowed

        region = getattr(self._config, "region", "us")
        rt_id_allowed = feature_allowed(region, FEATURE_REALTIME_BIOMETRIC_ID)
        self._consented = (
            frozenset(consented_student_ids) if rt_id_allowed else frozenset()
        )

    def _observe(
        self,
        idx: int,
        embedding: Sequence[float],
        landmarks: Sequence[Tuple[float, float]],
        bbox: Optional[Tuple[int, int, int, int]],
        frame_size: Optional[Tuple[int, int]],
    ) -> FaceObservation:
        """Build a single FaceObservation from an embedding (+ optional geometry).

        Matching is restricted to the consented set (resolved by the identity
        gate). Engagement is derived from landmarks only when supplied. Raw
        biometrics are never returned to callers.
        """
        from ..compliance import emotion_recognition_allowed

        match = self._gallery.identify(embedding, allowed_ids=self._consented)
        attention = 0.0
        gaze_frontal = 0.0
        expression: Optional[str] = None
        if landmarks and bbox is not None and frame_size is not None:
            eng = estimate_engagement(landmarks, bbox, frame_size)
            attention = eng.attention
            gaze_frontal = eng.gaze_frontal
            # The EU AI Act prohibits emotion recognition in education, so
            # expression inference is suppressed where disallowed.
            if emotion_recognition_allowed(getattr(self._config, "region", "us")):
                expression = eng.expression
        return FaceObservation(
            track_id=f"face-{idx}",
            embedding_ref=None,  # never expose raw biometrics
            attention_score=attention,
            gaze_frontal=gaze_frontal,
            expression=expression,
            matched_student_id=match.student_id if match.matched else None,
        )

    def analyze_image(
        self, image: bytes | str, *, consented_student_ids: Iterable[str]
    ) -> List[FaceObservation]:
        """Detect faces and match only against the consented set."""
        self._apply_identity_gate(consented_student_ids)
        return [
            self._observe(
                idx, face.embedding, face.landmarks, face.bbox, face.frame_size
            )
            for idx, face in enumerate(self.engine().detect_faces(image))
        ]

    def analyze_embedding(
        self,
        faces: Sequence[EmbeddedFace],
        *,
        consented_student_ids: Iterable[str],
    ) -> List[FaceObservation]:
        """Match precomputed (on-device) embeddings against the consented set.

        The hybrid path: detection + embedding happen on the client/edge device,
        so this never calls the model engine. The same consent + region gates and
        the same gallery matching as :meth:`analyze_image` apply, so behaviour is
        identical whether the embedding was produced on the server or the client.
        """
        self._apply_identity_gate(consented_student_ids)
        return [
            self._observe(idx, f.embedding, f.landmarks, f.bbox, f.frame_size)
            for idx, f in enumerate(faces)
        ]

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
