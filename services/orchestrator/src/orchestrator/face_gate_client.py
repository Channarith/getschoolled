"""Ask identity to consume a face token or report the current template generation.

Fail closed: a network error is a rejected check, not a pass.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from aoep_shared.face_gate import FaceGateError
from aoep_shared.identity_sync import identity_base_url, internal_token


def face_gate_required() -> bool:
    raw = os.environ.get("FACE_GATE_ENABLED", "1").strip().lower()
    return raw not in {"0", "false", "off", "no"}


def _request(method: str, path: str, body: dict | None = None) -> dict:
    url = f"{identity_base_url()}{path}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "X-Internal-Token": internal_token(),
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=3.0) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            payload = json.loads(exc.read().decode() or "{}")
            detail = str(payload.get("detail") or "")
        except (ValueError, json.JSONDecodeError):
            detail = ""
        raise FaceGateError(detail or "face verification rejected") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise FaceGateError("face verification unavailable") from exc


def consume_face_token(
    token: str,
    *,
    account_id: str,
    student_id: str,
    purpose: str,
) -> dict:
    return _request(
        "POST",
        "/internal/face-gate/consume",
        {
            "token": token,
            "account_id": account_id,
            "student_id": student_id,
            "purpose": purpose,
        },
    )


def fetch_face_generation(account_id: str, student_id: str) -> int:
    query = urllib.parse.urlencode({"account_id": account_id, "student_id": student_id})
    payload = _request("GET", f"/internal/face-gate/status?{query}")
    return int(payload.get("generation") or 0)
