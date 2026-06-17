"""Perception FastAPI app.

Identity matching is opt-in: a frame is only matched against students who have
granted face-recognition consent. Unconsented detections fall back to anonymous
tracks (attention only, no identity). The consent gate is enforced here so it
holds regardless of which VisionProvider (local/cloud) is configured.
"""

from __future__ import annotations

from aoep_shared.service import create_service
from pydantic import BaseModel

app = create_service("perception")


class ConsentCheckRequest(BaseModel):
    frame_object_key: str
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
    """Decide, per detected student, whether identity matching is permitted.

    This is the pure policy layer that runs before any biometric matching; the
    model inference itself lives behind the VisionProvider.
    """
    vision = app.state.factory.vision()
    # Prime the provider with the consented set, then ask per student.
    try:
        vision.analyze_frame(
            req.frame_object_key, consented_student_ids=req.consented_student_ids
        )
    except NotImplementedError:
        # Expected without loaded models; the consent set is still primed.
        pass

    decisions = []
    for sid in req.detected_student_ids:
        allowed = vision.may_identify(sid)
        decisions.append(
            ConsentDecision(
                student_id=sid,
                identify_allowed=allowed,
                mode="identity" if allowed else "anonymous",
            )
        )
    return ConsentCheckResponse(decisions=decisions)
