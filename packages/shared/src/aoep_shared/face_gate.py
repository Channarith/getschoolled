"""1:1 face match and single-use verification tokens.

The enrolled student's embedding lives on the identity profile. A live scan
matches that template only. A passing scan mints a short-lived token bound to
the account, the student, and one action (start a lesson, open or submit a
test, or continue after a pause). Replacing the face bumps a generation so
older tokens stop working.
"""

from __future__ import annotations

import math
import os
import uuid
from typing import Optional, Sequence

from .auth import sign_token, verify_token
from .vision.engine import DEFAULT_MATCH_THRESHOLD, cosine_similarity

FACE_EMBEDDING_DIM = 128
FACE_TOKEN_TTL_S = 120
FACE_SCAN_LIMIT_S = 60.0
FACE_PURPOSES = frozenset({"start", "checkpoint", "resume"})
_DEV_KEY = "dev-face-gate-key"


class FaceGateError(ValueError):
    """The scan or token cannot authorize this action."""


def face_gate_key() -> bytes:
    return os.environ.get("FACE_GATE_SIGNING_KEY", _DEV_KEY).encode()


def normalize_embedding(raw: Sequence[float]) -> list[float]:
    """Return a finite 128-d vector, or raise FaceGateError."""
    try:
        vec = [float(x) for x in raw]
    except (TypeError, ValueError) as exc:
        raise FaceGateError("face embedding must be a list of numbers") from exc
    if len(vec) != FACE_EMBEDDING_DIM:
        raise FaceGateError(f"face embedding must be {FACE_EMBEDDING_DIM} dimensions")
    if any(not math.isfinite(x) for x in vec):
        raise FaceGateError("face embedding must be finite")
    if not any(x != 0.0 for x in vec):
        raise FaceGateError("face embedding must not be empty")
    return vec


def embeddings_match(
    live: Sequence[float],
    enrolled: Sequence[float],
    *,
    threshold: float = DEFAULT_MATCH_THRESHOLD,
) -> bool:
    """True when the live scan is the enrolled student."""
    if len(live) != FACE_EMBEDDING_DIM or len(enrolled) != FACE_EMBEDDING_DIM:
        return False
    return cosine_similarity(live, enrolled) >= threshold


def decide_face_scan(
    *,
    matched: bool,
    elapsed_s: float,
    limit_s: float = FACE_SCAN_LIMIT_S,
) -> str:
    """``match``, ``timeout``, or ``wait``.

    A single miss does not fail the check. The scan fails only after ``limit_s``
    with no match.
    """
    if matched:
        return "match"
    if float(elapsed_s) >= float(limit_s):
        return "timeout"
    return "wait"


def issue_face_token(
    *,
    account_id: str,
    student_id: str,
    purpose: str,
    generation: int,
    key: Optional[bytes] = None,
    ttl_s: int = FACE_TOKEN_TTL_S,
) -> str:
    if purpose not in FACE_PURPOSES:
        raise FaceGateError("unknown face verification purpose")
    if not account_id or not student_id:
        raise FaceGateError("face verification requires an account and student")
    return sign_token(
        {
            "kind": "face_verify",
            "sub": account_id,
            "student_id": student_id,
            "purpose": purpose,
            "gen": int(generation),
            "jti": uuid.uuid4().hex,
        },
        key or face_gate_key(),
        ttl_s=ttl_s,
    )


def read_face_token(
    token: str,
    *,
    account_id: str,
    student_id: str = "",
    purpose: str,
    key: Optional[bytes] = None,
    now: Optional[float] = None,
) -> dict:
    """Validate signature, expiry, account, purpose, and optional student."""
    if purpose not in FACE_PURPOSES:
        raise FaceGateError("unknown face verification purpose")
    claims = verify_token(token or "", key or face_gate_key(), now=now)
    if not claims or claims.get("kind") != "face_verify":
        raise FaceGateError("invalid face verification")
    if str(claims.get("sub") or "") != account_id:
        raise FaceGateError("face verification is for another account")
    if str(claims.get("purpose") or "") != purpose:
        raise FaceGateError("face verification is for a different action")
    token_student = str(claims.get("student_id") or "")
    if student_id and token_student != student_id:
        raise FaceGateError("face verification is for another student")
    if not token_student or not claims.get("jti"):
        raise FaceGateError("invalid face verification")
    return claims
