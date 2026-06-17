"""Memory / profile service.

Phase4 owns per-student profiles, mastery graph, and cross-class context. This
phase0 skeleton imports cleanly, exposes /health, and offers an in-memory
profile stub behind the same API surface.
"""

from __future__ import annotations

from pydantic import BaseModel

from eduplatform_shared.service import create_service_app

app = create_service_app("memory")

_profiles: dict[str, dict] = {}


class Profile(BaseModel):
    student_id: str
    display_name: str = ""
    mastery: dict[str, float] = {}


@app.get("/api/profiles/{student_id}", response_model=Profile)
def get_profile(student_id: str) -> Profile:
    data = _profiles.get(student_id, {"student_id": student_id})
    return Profile(**data)


@app.put("/api/profiles/{student_id}", response_model=Profile)
def put_profile(student_id: str, profile: Profile) -> Profile:
    _profiles[student_id] = profile.model_dump()
    return profile
