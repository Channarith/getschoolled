"""Perception FastAPI app (consent-gated biometrics).

Face recognition runs self-hosted (OpenCV YuNet + SFace) behind the
VisionProvider, so biometrics stay inside the configured boundary. Identity
matching is opt-in: a frame is only matched against students who have granted
face-recognition consent. Unconsented detections fall back to anonymous tracks
(presence/attention only, no identity).

Endpoints:
- POST /enroll/{student_id}  enroll a face image for a student
- POST /identify             detect + identify faces in a frame (consent-gated)
- POST /analyze/consent-check pure consent policy decision (no model needed)
- GET  /gallery              enrolled students + counts (debug/ops)
"""

from __future__ import annotations

import base64
import os

from aoep_shared.identity_sync import internal_token
from aoep_shared.internal_auth import require_internal
from aoep_shared.providers.base import EmbeddedFace
from aoep_shared.service import create_service
from aoep_shared.vision.models import ModelsUnavailable, preload_models
from aoep_shared.voice_identity import (
    EncryptedVoiceGallery,
    SherpaSpeakerProvider,
    VoiceIdentityUnavailable,
)
from fastapi import Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = create_service("perception")


def _preload_face_models() -> None:
    """Fetch YuNet and SFace independently onto the writable model dir.

    Runs off the request path so a slow or blocked download cannot turn the
    other model's GET into a 503. Disabled in tests via VISION_PRELOAD_MODELS=0.
    """
    if os.environ.get("VISION_PRELOAD_MODELS", "1").lower() in ("0", "false", "no"):
        return
    import threading

    model_dir = app.state.factory.config.vision_model_dir or None

    def _run() -> None:
        preload_models(model_dir)

    threading.Thread(target=_run, name="vision-model-preload", daemon=True).start()


@app.on_event("startup")
def _start_face_model_preload() -> None:
    _preload_face_models()


def _vision():
    return app.state.factory.vision()


def _voice_gallery() -> EncryptedVoiceGallery:
    path = os.getenv(
        "VOICEPRINT_GALLERY_PATH",
        os.path.expanduser("~/.cache/aoep/voiceprints.enc"),
    )
    secret = os.getenv("BIOMETRIC_ENCRYPTION_SECRET") or internal_token()
    return EncryptedVoiceGallery(path, secret)


def _parse_ids(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [s.strip() for s in raw.split(",") if s.strip()]


# --------------------------------------------------------------------------- #
# Enrollment
# --------------------------------------------------------------------------- #
class EnrollResponse(BaseModel):
    student_id: str
    enrollments: int


@app.post("/enroll/{student_id}", response_model=EnrollResponse,
          dependencies=[Depends(require_internal)])
async def enroll(student_id: str, file: UploadFile = File(...)) -> EnrollResponse:
    data = await file.read()
    try:
        count = _vision().enroll(student_id, data)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ModelsUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return EnrollResponse(student_id=student_id, enrollments=count)


class EmbedResponse(BaseModel):
    embedding: list[float]


@app.post("/embed", response_model=EmbedResponse, dependencies=[Depends(require_internal)])
async def embed_face(file: UploadFile = File(...)) -> EmbedResponse:
    """Embedding of the largest face. Nothing is written to the gallery.

    Enrollment waits until the pose sequence has been checked against this
    vector, so a failed liveness round does not leave a partial template.
    """
    data = await file.read()
    try:
        faces = _vision().engine().detect_faces(data)
    except AttributeError as exc:
        raise HTTPException(status_code=503, detail="face embedding is not available") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (NotImplementedError, ModelsUnavailable) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not faces:
        raise HTTPException(status_code=422, detail="no face detected")
    return EmbedResponse(embedding=faces[0].embedding)


class FaceVerificationResponse(BaseModel):
    student_id: str
    verified: bool
    score: float = 0.0


@app.post(
    "/verify-face/{student_id}",
    response_model=FaceVerificationResponse,
    dependencies=[Depends(require_internal)],
)
async def verify_face(
    student_id: str,
    file: UploadFile = File(...),
    high_assurance: bool = False,
) -> FaceVerificationResponse:
    """Match a still to an enrolled learner.

    ``high_assurance`` requires the liveness set (neutral plus four poses)
    already stored. Pose checks during enrollment leave this off.
    """
    data = await file.read()
    try:
        observations = _vision().analyze_image(
            data,
            consented_student_ids=[student_id],
            high_assurance=high_assurance,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (NotImplementedError, ModelsUnavailable) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    verified = any(item.matched_student_id == student_id for item in observations)
    return FaceVerificationResponse(student_id=student_id, verified=verified)


class FaceLandmarks(BaseModel):
    bbox: list[int]
    landmarks: list[list[float]]
    frame_size: list[int]
    score: float


class LandmarksResponse(BaseModel):
    faces: list[FaceLandmarks]


@app.post(
    "/detect-landmarks",
    response_model=LandmarksResponse,
    dependencies=[Depends(require_internal)],
)
async def detect_landmarks(file: UploadFile = File(...)) -> LandmarksResponse:
    """YuNet box + 5 landmarks for a still, so the phone can draw the face
    contour on the captured photo. Nothing is stored and no embedding leaves."""
    data = await file.read()
    try:
        engine = _vision().engine()
        faces = engine.detect_faces(data)
    except AttributeError as exc:
        raise HTTPException(status_code=503, detail="face landmarks are not available") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (NotImplementedError, ModelsUnavailable) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return LandmarksResponse(
        faces=[
            FaceLandmarks(
                bbox=[int(v) for v in face.bbox],
                landmarks=[[float(x), float(y)] for x, y in face.landmarks],
                frame_size=[int(v) for v in face.frame_size],
                score=float(face.det_score),
            )
            for face in faces
        ]
    )


# --------------------------------------------------------------------------- #
# Identification (consent-gated)
# --------------------------------------------------------------------------- #
class FaceResult(BaseModel):
    track_id: str
    matched_student_id: str | None
    attention: float
    gaze_frontal: float
    expression: str
    identified: bool


class IdentifyResponse(BaseModel):
    faces: list[FaceResult]


def _memory_consent_ids() -> list[str] | None:
    """Server consent list. None means memory is unreachable in test mode."""
    import json
    import urllib.error
    import urllib.request

    base = (os.environ.get("MEMORY_URL") or "http://localhost:8004").rstrip("/")
    url = f"{base}/internal/consent/granted?scope=face_recognition"
    req = urllib.request.Request(
        url, headers={"X-Internal-Token": internal_token()}, method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            body = json.loads(resp.read().decode())
        return [str(s) for s in (body.get("student_ids") or [])]
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError, ValueError):
        if os.environ.get("INTERNAL_AUTH_DISABLED", "").strip().lower() in ("1", "true", "yes"):
            return None
        return []


def _allowed_face_ids(request: Request, client_ids: list[str]) -> list[str]:
    from aoep_shared.learner_scope import (
        account_owns_student,
        is_internal_request,
        session_account_id,
    )

    server = _memory_consent_ids()
    if server is None:
        allowed = list(client_ids)
    else:
        allowed = list(server)
        if client_ids:
            wanted = set(client_ids)
            allowed = [sid for sid in allowed if sid in wanted]
    if is_internal_request(request):
        return allowed
    account_id = session_account_id(request)
    if not account_id:
        raise HTTPException(status_code=401, detail="sign in required")
    owned: list[str] = []
    for sid in allowed:
        try:
            if account_owns_student(account_id, sid):
                owned.append(sid)
        except Exception:
            continue
    return owned


@app.post("/identify", response_model=IdentifyResponse)
async def identify(
    request: Request,
    file: UploadFile = File(...),
    consented_student_ids: str = Form(""),
) -> IdentifyResponse:
    data = await file.read()
    consented = _allowed_face_ids(request, _parse_ids(consented_student_ids))
    try:
        observations = _vision().analyze_image(
            data, consented_student_ids=consented
        )
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except ModelsUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    faces = [
        FaceResult(
            track_id=o.track_id,
            matched_student_id=o.matched_student_id,
            attention=o.attention_score,
            gaze_frontal=o.gaze_frontal,
            # expression is None where emotion recognition is disallowed (EU)
            # or when landmarks/bbox/frame_size were not supplied.
            expression=o.expression or "unknown",
            identified=o.matched_student_id is not None,
        )
        for o in observations
    ]
    return IdentifyResponse(faces=faces)


# --------------------------------------------------------------------------- #
# Hybrid (on-device) path: the client device runs YuNet+SFace locally and sends
# only the 128-d embedding (+ landmarks for engagement). The raw frame never
# leaves the device and the server never loads the model; it only matches the
# embedding against the consented gallery and enforces the compliance gates.
# --------------------------------------------------------------------------- #
class EnrollEmbeddingRequest(BaseModel):
    embedding: list[float]


@app.post("/enroll-embedding/{student_id}", response_model=EnrollResponse,
          dependencies=[Depends(require_internal)])
def enroll_embedding(student_id: str, req: EnrollEmbeddingRequest) -> EnrollResponse:
    try:
        count = _vision().enroll_embedding(student_id, req.embedding)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return EnrollResponse(student_id=student_id, enrollments=count)


class VoiceSampleRequest(BaseModel):
    audio_b64: str


class VoiceEnrollmentResponse(BaseModel):
    student_id: str
    template_ref: str
    verified: bool = True
    score: float | None = None


def _voice_embedding(audio_b64: str) -> list[float]:
    try:
        audio = base64.b64decode(audio_b64, validate=True)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="audio_b64 is invalid") from exc
    if len(audio) > 12 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="voice sample is too large")
    try:
        return SherpaSpeakerProvider().embedding(audio)
    except VoiceIdentityUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post(
    "/voiceprint/enroll/{student_id}",
    response_model=VoiceEnrollmentResponse,
    dependencies=[Depends(require_internal)],
)
def enroll_voiceprint(student_id: str, req: VoiceSampleRequest) -> VoiceEnrollmentResponse:
    template_ref = _voice_gallery().enroll(student_id, _voice_embedding(req.audio_b64))
    return VoiceEnrollmentResponse(student_id=student_id, template_ref=template_ref)


@app.post(
    "/voiceprint/verify/{student_id}",
    response_model=VoiceEnrollmentResponse,
    dependencies=[Depends(require_internal)],
)
def verify_voiceprint(student_id: str, req: VoiceSampleRequest) -> VoiceEnrollmentResponse:
    match = _voice_gallery().verify(student_id, _voice_embedding(req.audio_b64))
    return VoiceEnrollmentResponse(
        student_id=student_id,
        template_ref="",
        verified=match.matched,
        score=match.score,
    )


@app.delete(
    "/biometrics/{student_id}",
    dependencies=[Depends(require_internal)],
)
def delete_biometrics(student_id: str) -> dict:
    provider = _vision()
    delete = getattr(provider, "delete_student", None)
    if callable(delete):
        delete(student_id)
    _voice_gallery().remove(student_id)
    return {"student_id": student_id, "deleted": True}


class EmbeddedFaceIn(BaseModel):
    embedding: list[float]
    # Optional geometry for engagement (gaze/attention/expression). YuNet emits
    # 5 landmarks as [x, y] pairs; bbox is [x, y, w, h]; frame_size is [w, h].
    landmarks: list[list[float]] = []
    bbox: list[int] | None = None
    frame_size: list[int] | None = None


class IdentifyEmbeddingRequest(BaseModel):
    faces: list[EmbeddedFaceIn]
    consented_student_ids: list[str] = []
    # Finished liveness set only. Enrollment pose checks leave this false.
    high_assurance: bool = False


@app.post("/identify-embedding", response_model=IdentifyResponse)
def identify_embedding(req: IdentifyEmbeddingRequest, request: Request) -> IdentifyResponse:
    embedded = [
        EmbeddedFace(
            embedding=f.embedding,
            landmarks=[(p[0], p[1]) for p in f.landmarks if len(p) >= 2],
            bbox=tuple(f.bbox) if f.bbox and len(f.bbox) >= 4 else None,
            frame_size=tuple(f.frame_size) if f.frame_size and len(f.frame_size) >= 2 else None,
        )
        for f in req.faces
    ]
    observations = _vision().analyze_embedding(
        embedded,
        consented_student_ids=_allowed_face_ids(request, list(req.consented_student_ids)),
        high_assurance=req.high_assurance,
    )
    faces = [
        FaceResult(
            track_id=o.track_id,
            matched_student_id=o.matched_student_id,
            attention=o.attention_score,
            gaze_frontal=o.gaze_frontal,
            expression=o.expression or "unknown",
            identified=o.matched_student_id is not None,
        )
        for o in observations
    ]
    return IdentifyResponse(faces=faces)


# --------------------------------------------------------------------------- #
# Model delivery: serve the YuNet/SFace ONNX weights to on-device clients from
# our own origin, so browsers/mobile fetch them once from us (and we control
# version + integrity) instead of reaching out to the public model zoo.
# --------------------------------------------------------------------------- #
@app.get("/vision/models/{name}")
def vision_model(name: str) -> FileResponse:
    from aoep_shared.vision.models import (
        DETECTOR_NAME,
        RECOGNIZER_NAME,
        ModelsUnavailable,
        ensure_model,
    )

    if name not in (DETECTOR_NAME, RECOGNIZER_NAME):
        raise HTTPException(status_code=404, detail="unknown model")

    model_dir = app.state.factory.config.vision_model_dir or None
    try:
        path = ensure_model(name, model_dir)
    except ModelsUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=name,
        headers={"Cache-Control": "public, max-age=86400"},
    )


# --------------------------------------------------------------------------- #
# Consent policy (pure; no model required)
# --------------------------------------------------------------------------- #
class ConsentCheckRequest(BaseModel):
    detected_student_ids: list[str]
    consented_student_ids: list[str]


class ConsentDecision(BaseModel):
    student_id: str
    identify_allowed: bool
    mode: str  # "identity" or "anonymous"


class ConsentCheckResponse(BaseModel):
    decisions: list[ConsentDecision]


@app.post("/analyze/consent-check", response_model=ConsentCheckResponse)
def consent_check(req: ConsentCheckRequest) -> ConsentCheckResponse:
    consented = set(req.consented_student_ids)
    decisions = [
        ConsentDecision(
            student_id=sid,
            identify_allowed=sid in consented,
            mode="identity" if sid in consented else "anonymous",
        )
        for sid in req.detected_student_ids
    ]
    return ConsentCheckResponse(decisions=decisions)


class GalleryResponse(BaseModel):
    students: dict[str, int]


@app.get("/gallery", response_model=GalleryResponse, dependencies=[Depends(require_internal)])
def gallery() -> GalleryResponse:
    g = _vision().gallery()
    return GalleryResponse(students={s: g.count(s) for s in g.students()})
