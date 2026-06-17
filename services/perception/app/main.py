"""Perception service (consent-gated biometrics).

Phase3 adds face recognition + attention/gaze via the VisionProvider. Biometrics
stay inside the configured boundary (compliance lever). This skeleton exposes
/health and a consent-gated attention stub.
"""

from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel

from eduplatform_shared.factory import get_provider_factory
from eduplatform_shared.service import create_service_app

app = create_service_app("perception")


class AttentionRequest(BaseModel):
    student_id: str
    consent: bool = False


class AttentionResponse(BaseModel):
    student_id: str
    attention: float


@app.post("/api/attention", response_model=AttentionResponse)
def attention(req: AttentionRequest) -> AttentionResponse:
    if not req.consent:
        # Biometric features are gated behind explicit consent.
        raise HTTPException(status_code=403, detail="biometric consent required")
    provider = get_provider_factory().vision()
    score = provider.attention(b"")
    return AttentionResponse(student_id=req.student_id, attention=score)
