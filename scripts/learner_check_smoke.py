#!/usr/bin/env python3
"""Drive Learner Check end to end against a running identity + perception.

Signs up a throwaway account, grants biometric consent, saves a face check
(five mock embeddings that pass the pose gate), saves a voice check from a
real 10 second audio clip, marks setup complete, and prints each step.

    python3 scripts/learner_check_smoke.py                     # identity on :8008
    python3 scripts/learner_check_smoke.py --identity http://127.0.0.1:8018

Audio: macOS `say` + ffmpeg make a spoken clip encoded like the browser's
MediaRecorder (webm/opus). Without them a synthetic voiced tone is used.
Exit status is non-zero on the first failing step.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
import os
import random
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
import wave

VOICE_SECONDS = 10


def _call(method: str, url: str, token: str | None = None, body: dict | None = None) -> tuple[int, dict | str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8")
            return response.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw)
        except ValueError:
            return exc.code, raw
    except urllib.error.URLError as exc:
        return 0, str(exc.reason)


def _embeddings() -> list[list[float]]:
    rng = random.Random(7)
    base = [rng.uniform(-0.5, 0.5) for _ in range(128)]
    return [[b + 0.25 * rng.uniform(-0.5, 0.5) for b in base] for _ in range(5)]


def _as_webm(source: str, directory: str) -> bytes | None:
    """Encode like the browser's MediaRecorder: mono webm/opus, 10 s."""
    webm = f"{directory}/voice.webm"
    try:
        subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-y", "-i", source, "-af", "apad",
             "-t", str(VOICE_SECONDS), "-ac", "1", "-c:a", "libopus", webm],
            check=True, timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    with open(webm, "rb") as stream:
        return stream.read()


def _spoken_clip() -> tuple[bytes, str] | None:
    """`say` writes an empty file when speech synthesis is unavailable."""
    if not (shutil.which("say") and shutil.which("ffmpeg")):
        return None
    with tempfile.TemporaryDirectory(prefix="learner-check-") as directory:
        aiff = f"{directory}/voice.aiff"
        try:
            subprocess.run(
                ["say", "-r", "150", "-o", aiff,
                 "Today I am ready to learn with Salareen. Can you hear my voice clearly? "
                 "Yes, I am speaking naturally and confidently."],
                check=True, timeout=30,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if os.path.getsize(aiff) < 64_000:
            return None
        clip = _as_webm(aiff, directory)
        return (clip, "spoken webm/opus") if clip else None


def _tone_webm() -> tuple[bytes, str] | None:
    if not shutil.which("ffmpeg"):
        return None
    with tempfile.TemporaryDirectory(prefix="learner-check-") as directory:
        source = f"{directory}/tone.wav"
        with open(source, "wb") as stream:
            stream.write(_tone_clip())
        clip = _as_webm(source, directory)
        return (clip, "voiced tone webm/opus") if clip else None


def _tone_clip() -> bytes:
    rate = 16000
    frames = bytearray()
    for i in range(rate * VOICE_SECONDS):
        t = i / rate
        envelope = 0.5 + 0.5 * math.sin(2 * math.pi * 3 * t)
        value = sum(math.sin(2 * math.pi * f * t) / k for k, f in enumerate((140, 280, 420, 700), 1))
        sample = int(max(-1.0, min(1.0, 0.2 * envelope * value)) * 32767)
        frames += sample.to_bytes(2, "little", signed=True)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(bytes(frames))
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--identity", default="http://localhost:8008")
    args = parser.parse_args()
    base = args.identity.rstrip("/")
    failures = 0

    def step(name: str, status: int, payload, ok: bool | None = None) -> bool:
        nonlocal failures
        passed = (200 <= status < 300) if ok is None else ok
        print(f"{'PASS' if passed else 'FAIL'}  {name}  [{status}]" + ("" if passed else f"  {payload}"))
        if not passed:
            failures += 1
        return passed

    status, payload = _call("GET", f"{base}/health")
    if not step("identity is up", status, payload):
        return 1
    email = f"learner-check-{uuid.uuid4().hex[:8]}@example.com"
    status, payload = _call("POST", f"{base}/auth/signup", body={"email": email, "password": "S3cretpass"})
    if not step("sign up", status, payload):
        return 1
    token = payload["token"]
    status, payload = _call("GET", f"{base}/students", token)
    if not step("learner profile", status, payload):
        return 1
    student = payload["students"][0]["id"]
    root = f"{base}/students/{student}"

    status, payload = _call("PUT", f"{root}/biometric-consent", token,
                            {"granted": True, "guardian_granted": False, "retention_days": 365})
    if not step("Get started: biometric consent", status, payload):
        return 1
    status, payload = _call("PATCH", f"{root}/setup-assistant", token, {"current_step": "biometrics"})
    step("Get started: setup step", status, payload)

    status, payload = _call("POST", f"{root}/biometric-face", token,
                            {"embeddings": _embeddings(), "pose_sequence": ["left", "up", "right", "down"]})
    step("face check saved", status, payload)

    audio, label = _spoken_clip() or _tone_webm() or (_tone_clip(), "voiced tone wav")
    status, payload = _call("POST", f"{root}/voiceprint", token,
                            {"audio_b64": base64.b64encode(audio).decode("ascii")})
    step(f"voice check saved ({label}, {len(audio)} bytes)", status, payload)

    status, payload = _call("PATCH", f"{root}/setup-assistant", token,
                            {"current_step": "complete", "complete": True})
    step("Continue: setup complete", status, payload)

    status, state = _call("GET", f"{root}/setup-assistant", token)
    if isinstance(state, dict):
        for record in ("portrait", "pose", "voice"):
            value = state.get(record, {}).get("status")
            step(f"state {record} = {value}", status, state, ok=value == "verified")
        step(f"state current_step = {state.get('current_step')}", status, state,
             ok=state.get("current_step") == "complete")
    else:
        step("read setup state", status, state)

    _call("DELETE", f"{root}/biometrics", token)
    print("ALL PASS" if not failures else f"{failures} step(s) failed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
