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

from aoep_shared.service import create_service
from fastapi import File, Form, HTTPException, UploadFile
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


@app.post("/enroll/{student_id}", response_model=EnrollResponse)
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
            identified=o.matched_student_id is not None,
        )
        for o in observations
    ]
    return IdentifyResponse(faces=faces)


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
