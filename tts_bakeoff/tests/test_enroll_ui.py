"""Enrollment web UI server: consent gating, upload validation, enroll pass/fail, revoke. No microphone or GPU needed."""
from __future__ import annotations

import base64
import io
import json
import threading
import urllib.error
import urllib.request
import wave

import numpy as np
import pytest

from tts_bakeoff.voice_clone import enroll_ui as ui
from tts_bakeoff.voice_clone import registry

RATE = 24000


def speechlike(seconds: float, noise: float = 0.001, seed: int = 0) -> bytes:
    rng = np.random.default_rng(seed)
    t = np.arange(int(seconds * RATE)) / RATE
    gate = ((t * 3) % 1.0) < 0.6
    x = np.where(gate, 0.25 * np.sin(2 * np.pi * 180 * t) * (1 + np.sin(2 * np.pi * 4 * t)) / 2, 0.0) + noise * rng.standard_normal(len(t))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
    return buf.getvalue()


@pytest.fixture
def server(tmp_path, monkeypatch):
    base = tmp_path / "voices"
    srv = ui.serve(base, 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(ui, "cuda_host", lambda: False)
    yield f"http://127.0.0.1:{srv.server_address[1]}", base
    srv.shutdown()
    srv.server_close()


def call(url, path, data=None, raw=None, headers=None, method=None):
    h = {"X-Enroll": "1", **(headers or {})}
    body = None
    if data is not None:
        body, h["Content-Type"] = json.dumps(data).encode(), "application/json"
    elif raw is not None:
        body = raw
    req = urllib.request.Request(url + path, data=body, headers=h, method=method or ("POST" if body is not None else "GET"))
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def consent_payload(name="Alice Tran", **over):
    p = {"name": name, "role": "employee", "typed_name": name, "agreements": {a: True for a in ui.AGREEMENTS},
         "text_sha256": ui.consent_text_sha256(), "proof_wav_b64": base64.b64encode(speechlike(5)).decode()}
    p.update(over)
    return p


def enrolled(server, name="Alice Tran"):
    url, _ = server
    code, r = call(url, "/api/consent", consent_payload(name))
    assert code == 200, r
    return r["speaker"]


def record_all(url, speaker, lang="en", noise=0.001):
    for i, p in enumerate(ui.PROMPT_SETS[lang]):
        code, r = call(url, f"/api/take/{speaker}/{lang}/{p['id']}", raw=speechlike(8, noise, i))
        assert code == 200, r


def test_pages_and_config(server):
    url, _ = server
    with urllib.request.urlopen(url + "/") as r:
        assert b"Voice enrollment" in r.read()
    code, cfg = call(url, "/api/config")
    assert code == 200 and cfg["consent_text_sha256"] == ui.consent_text_sha256() and "en" in cfg["prompts"]
    assert 7 <= len(cfg["prompts"]["en"]) <= 8
    for lang in ("km", "th", "vi", "zh", "es"):
        assert cfg["prompts"][lang]


def test_cross_site_and_rebinding_are_refused(server):
    url, _ = server
    assert call(url, "/api/consent", consent_payload(), headers={"X-Enroll": "0"})[0] == 403
    assert call(url, "/api/consent", consent_payload(), headers={"Origin": "https://evil.example"})[0] == 403
    assert call(url, "/api/config", headers={"Host": "evil.example"})[0] == 403
    assert call(url, "/api/config", headers={"Host": "localhost:9999"})[0] == 200


@pytest.mark.parametrize("change", [
    {"typed_name": "Someone Else"}, {"role": "intern"}, {"text_sha256": "0" * 64}, {"name": "A"},
    {"agreements": {"commercial_use": True, "model_training": True, "course_narration": True}},
    {"agreements": {"commercial_use": True, "model_training": False, "course_narration": True, "may_withdraw": True}},
    {"proof_wav_b64": ""}, {"proof_wav_b64": "not base64!!"},
    {"proof_wav_b64": base64.b64encode(speechlike(1)).decode()},
    {"proof_wav_b64": base64.b64encode(speechlike(5, 0.0).replace(speechlike(5, 0.0)[44:], b"\x00" * 240000)).decode()},
])
def test_consent_is_gated(server, change):
    url, base = server
    code, r = call(url, "/api/consent", consent_payload(**change))
    assert code in (400, 409), r
    assert registry.list_speakers(base) == []


def test_consent_records_evidence_through_the_registry(server):
    url, base = server
    sp = enrolled(server)
    rec = registry.require_consent(sp, "course_narration", base)
    ev = rec["evidence"]
    assert sp == "alice-tran" and ev["method"] == "web-ui" and ev["typed_name"] == "Alice Tran"
    assert ev["consent_text_sha256"] == ui.consent_text_sha256() and ev["timestamp"]
    audio = base / sp / "forms" / "consent-statement.wav"
    assert audio.is_file() and registry.sha256_file(audio) == ev["proof_audio"]["sha256"]
    assert "Alice Tran" in ev["proof_audio"]["statement"]
    assert set(registry.REQUIRED_SCOPES) <= set(rec["scopes"])
    assert call(url, "/api/consent", consent_payload())[0] == 409


def test_existing_signed_form_instead_of_audio(server, tmp_path):
    url, base = server
    form = tmp_path / "signed.pdf"
    form.write_bytes(b"%PDF-1.4 " + b"x" * 500)
    p = consent_payload("Bob Lee", existing_form_path=str(form))
    p.pop("proof_wav_b64")
    code, r = call(url, "/api/consent", p)
    assert code == 200, r
    rec = registry.require_consent("bob-lee", "model_training", base)
    assert rec["form_file"] == "signed.pdf" and rec["evidence"]["existing_form_path"] == str(form)
    assert call(url, "/api/consent", consent_payload("Cy Ng", existing_form_path=str(tmp_path / "missing.pdf")))[0] == 400
    (tmp_path / "x.exe").write_bytes(b"x" * 500)
    assert call(url, "/api/consent", consent_payload("Di Ng", existing_form_path=str(tmp_path / "x.exe")))[0] == 400


def test_khmer_name_gets_a_valid_id(server):
    url, base = server
    name = "សុខ ចាន់"
    assert registry.SLUG_RE.match(ui.slugify(name))
    code, r = call(url, "/api/consent", consent_payload(name))
    assert code == 200 and r["speaker"].startswith("speaker-")


def test_uploads_need_consent_and_valid_audio(server):
    url, base = server
    assert call(url, "/api/take/nobody/en/en-1", raw=speechlike(5))[0] == 403
    sp = enrolled(server)
    assert call(url, f"/api/take/{sp}/en/en-1", raw=b"RIFFnotawav")[0] == 400
    assert call(url, f"/api/take/{sp}/en/en-99", raw=speechlike(5))[0] == 404
    assert call(url, f"/api/take/{sp}/xx/en-1", raw=speechlike(5))[0] == 404
    assert call(url, f"/api/take/{sp}/en/en-1", raw=speechlike(0.3))[0] == 400
    code, r = call(url, f"/api/take/{sp}/en/en-1", raw=speechlike(6))
    assert code == 200 and r["seconds"] == 6.0 and r["warnings"] == []
    assert (base / sp / "raw" / "en" / "en-1.wav").is_file()


def test_noisy_take_warns(server):
    url, _ = server
    sp = enrolled(server)
    code, r = call(url, f"/api/take/{sp}/en/en-1", raw=speechlike(6, noise=0.08))
    assert code == 200 and any("noise" in w for w in r["warnings"])


def test_enroll_passes_and_is_registered(server):
    url, base = server
    sp = enrolled(server)
    assert call(url, f"/api/enroll/{sp}", {"lang": "en"})[0] == 400
    record_all(url, sp)
    code, r = call(url, f"/api/enroll/{sp}", {"lang": "en"})
    assert code == 200 and r["ok"] and r["seconds"] >= 20, r
    rec = registry.require_consent(sp, "course_narration", base)
    info = rec["samples"]["samples/web-en.wav"]
    assert info["lang"] == "en" and info["transcript"].startswith("Good morning") and info["seconds"] == r["seconds"]
    wav, text, lang = registry.primary_sample(sp, base)
    assert wav.is_file() and lang == "en" and "Wow, that is exactly right" in text
    code, r2 = call(url, f"/api/enroll/{sp}", {"lang": "en"})
    assert code == 200 and r2["ok"]
    registry.require_consent(sp, "course_narration", base)
    code, lst = call(url, "/api/speakers")
    assert lst["speakers"][0]["samples"][0]["seconds"] and lst["speakers"][0]["takes"]["en"]


def test_enroll_reports_failure_for_noisy_room(server):
    url, base = server
    sp = enrolled(server)
    record_all(url, sp, noise=0.12)
    code, r = call(url, f"/api/enroll/{sp}", {"lang": "en"})
    assert code == 200 and r["ok"] is False and "noisy" in r["error"]
    assert registry.load_consent(sp, base)["samples"] == {}


def test_withdraw_blocks_everything(server):
    url, base = server
    sp = enrolled(server)
    record_all(url, sp)
    assert call(url, f"/api/enroll/{sp}", {"lang": "en"})[1]["ok"]
    assert call(url, f"/api/revoke/{sp}", {"typed_name": "wrong"})[0] == 400
    assert call(url, f"/api/revoke/{sp}", {"typed_name": "alice tran"})[0] == 200
    assert call(url, f"/api/take/{sp}/en/en-1", raw=speechlike(5))[0] == 403
    assert call(url, f"/api/synth/{sp}", {"model": "voxcpm2"})[0] == 403
    assert call(url, "/api/speakers")[1]["speakers"][0]["revoked"] is True
    with pytest.raises(registry.ConsentError):
        registry.primary_sample(sp, base)


def test_synth_shows_command_off_gpu_and_validates(server):
    url, _ = server
    sp = enrolled(server)
    assert call(url, f"/api/synth/{sp}", {"model": "voxcpm2"})[0] == 400
    record_all(url, sp)
    call(url, f"/api/enroll/{sp}", {"lang": "en"})
    code, r = call(url, f"/api/synth/{sp}", {"model": "cosyvoice2"})
    assert code == 200 and r["started"] is False and "MODELS=cosyvoice2" in r["command"] and "--speakers alice-tran" in r["command"]
    assert call(url, f"/api/synth/{sp}", {"model": "bark"})[0] == 400


def test_oversize_body_refused(server, monkeypatch):
    url, _ = server
    monkeypatch.setattr(ui, "MAX_BODY", 1000)
    assert call(url, "/api/consent", consent_payload())[0] == 413
