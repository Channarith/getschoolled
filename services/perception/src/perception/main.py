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

from aoep_shared.internal_auth import require_internal
from aoep_shared.providers.base import EmbeddedFace
from aoep_shared.service import create_service
from fastapi import Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

app = create_service("perception")


def _vision():
    return app.state.factory.vision()


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
    return EnrollResponse(student_id=student_id, enrollments=count)


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


@app.post("/identify", response_model=IdentifyResponse)
async def identify(
    file: UploadFile = File(...),
    consented_student_ids: str = Form(""),
) -> IdentifyResponse:
    data = await file.read()
    consented = _parse_ids(consented_student_ids)
    try:
        observations = _vision().analyze_image(
            data, consented_student_ids=consented
        )
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    faces = [
        FaceResult(
            track_id=o.track_id,
            matched_student_id=o.matched_student_id,
            attention=o.attention_score,
            gaze_frontal=o.gaze_frontal,
            expression=o.expression,
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


@app.post("/identify-embedding", response_model=IdentifyResponse)
def identify_embedding(req: IdentifyEmbeddingRequest) -> IdentifyResponse:
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
        embedded, consented_student_ids=req.consented_student_ids
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
        ensure_models,
    )

    if name not in (DETECTOR_NAME, RECOGNIZER_NAME):
        raise HTTPException(status_code=404, detail="unknown model")
    model_dir = app.state.factory.config.vision_model_dir or None
    try:
        detector, recognizer = ensure_models(model_dir)
    except ModelsUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    path = detector if name == DETECTOR_NAME else recognizer
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


@app.get("/gallery", response_model=GalleryResponse)
def gallery() -> GalleryResponse:
    g = _vision().gallery()
    return GalleryResponse(students={s: g.count(s) for s in g.students()})
