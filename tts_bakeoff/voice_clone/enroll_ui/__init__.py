"""Browser wizard to consent and record a voice, on top of the consent-gated registry.

  python3 -m tts_bakeoff.voice_clone.enroll_ui --root ~/voices          # on the Spark; browse from your laptop with
  ssh -L 8780:127.0.0.1:8780 <spark>                                    # then open http://localhost:8780/ (mic needs localhost)

Serves 127.0.0.1 only: no network access, no telemetry, nothing leaves the machine. Every write goes through
registry.record_consent / add_sample, so the same gate applies as for the command line.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import http.server
import json
import os
import re
import shlex
import shutil
import socketserver
import subprocess
import tempfile
import threading
import time
import unicodedata
import urllib.parse
import uuid
import wave
from pathlib import Path

from tts_bakeoff.lab import content_type

from .. import enroll, registry
from . import voice_check
from .i18n import CONSENT_STATUS, DRAFT_CONSENT_LANGS, UI, UI_LANGS, consent_path
from .prompts import DRAFT_LANGS, LANG_NAMES, PROMPT_SETS, statement_for

STATIC = Path(__file__).resolve().parent / "static"
ROOT = Path(__file__).resolve().parents[3]
CONSENT_FORM = Path(__file__).resolve().parents[1] / "CONSENT_FORM.txt"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}
MAX_BODY = 12 * 1024 * 1024
FORM_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".heic", ".txt"}
AGREEMENTS = ("commercial_use", "model_training", "course_narration", "may_withdraw")
SYNTH_MODELS = ("voxcpm2", "cosyvoice2")
MIN_PROOF_S, MAX_PROOF_S = 3.0, 40.0
MIN_TAKE_S, MAX_TAKE_S = 1.0, 40.0
_JOBS: dict[str, dict] = {}
_CHECKS: dict[tuple[str, str], dict] = {}
_SAY: dict[str, dict] = {}   # this server session's "say anything" jobs, by id
SAY_MAX_CHARS = 500
SAY_ACTIVE = ("waiting for GPU lock", "running")


class UiError(Exception):
    def __init__(self, code: int, message: str):
        super().__init__(message)
        self.code, self.message = code, message


def _ui_lang(lang) -> str:
    lang = lang or "en"
    if lang not in UI_LANGS:
        raise UiError(400, f"unknown page language {lang!r}")
    return lang


def consent_text(lang: str = "en") -> str:
    return consent_path(_ui_lang(lang)).read_text(encoding="utf-8")


def consent_text_sha256(lang: str = "en") -> str:
    return hashlib.sha256(consent_text(lang).encode("utf-8")).hexdigest()


def norm_name(name: str) -> str:
    return " ".join((name or "").split())


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", norm_name(name)).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")[:40].strip("-")
    if not registry.SLUG_RE.match(slug):
        slug = "speaker-" + hashlib.sha1(norm_name(name).encode("utf-8")).hexdigest()[:6]
    return slug


def wav_info(data: bytes) -> dict:
    """Validate a PCM16 mono WAV and return rate, seconds, peak, rms and a crude SNR. Raises UiError(400)."""
    import io

    import numpy as np

    try:
        with wave.open(io.BytesIO(data), "rb") as w:
            ch, width, rate, n = w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()
            raw = w.readframes(n)
    except (wave.Error, EOFError) as exc:
        raise UiError(400, f"not a readable WAV file: {exc}") from exc
    if ch != 1 or width != 2:
        raise UiError(400, "audio must be 16-bit mono WAV")
    if not 8000 <= rate <= 96000:
        raise UiError(400, f"unsupported sample rate {rate}")
    x = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
    secs = len(x) / rate
    peak = float(np.abs(x).max()) if len(x) else 0.0
    rms = float(np.sqrt((x**2).mean())) if len(x) else 0.0
    return {"rate": rate, "seconds": round(secs, 2), "peak": round(peak, 3), "rms": round(rms, 4),
            "snr_db": round(enroll.snr_db(x, rate), 1)}


def _speaker_state(base: Path, speaker: str) -> dict:
    rec = registry.load_consent(speaker, base)
    d = registry.speaker_dir(speaker, base)
    samples = [{"file": rel, "lang": i["lang"], "seconds": i.get("seconds")} for rel, i in sorted(rec["samples"].items())]
    takes = {}
    raw = d / "raw"
    if raw.is_dir():
        for lang_dir in raw.iterdir():
            takes[lang_dir.name] = sorted(p.stem for p in lang_dir.glob("*.wav") if p.stem != "concat")
    return {"speaker": speaker, "name": rec["name"], "role": rec["role"], "date": rec["date"], "revoked": bool(rec["revoked"]),
            "revoked_on": rec.get("revoked_on"), "method": (rec.get("evidence") or {}).get("method", "cli"),
            "samples": samples, "takes": takes}


def speakers(base: Path) -> list[dict]:
    out = []
    for s in registry.list_speakers(base):
        try:
            out.append(_speaker_state(base, s))
        except (registry.ConsentError, KeyError, json.JSONDecodeError):
            continue
    return out


def config() -> dict:
    texts = {k: {"text": consent_text(k), "sha256": consent_text_sha256(k), "status": CONSENT_STATUS[k], "draft": k in DRAFT_CONSENT_LANGS}
             for k in UI_LANGS}
    return {"consent_text": consent_text(), "consent_text_sha256": consent_text_sha256(), "agreements": list(AGREEMENTS),
            "ui_langs": UI_LANGS, "ui": UI, "consent_texts": texts,
            "roles": list(registry.ROLES), "langs": {k: LANG_NAMES[k] for k in PROMPT_SETS}, "draft_langs": list(DRAFT_LANGS),
            "prompts": PROMPT_SETS, "min_seconds": enroll.MIN_S, "max_seconds": enroll.MAX_S, "min_snr_db": enroll.MIN_SNR_DB,
            "models": list(SYNTH_MODELS), "say_max_chars": SAY_MAX_CHARS, "say_langs": say_langs(),
            "lang_names": {k: LANG_NAMES.get(k, k) for k in ("en", "es", "zh", "vi", "th", "km", "sw", "hi")}}


def statement(name: str, lang: str = "en") -> str:
    if not norm_name(name):
        raise UiError(400, "enter the person's name first")
    return statement_for(name, _ui_lang(lang))


def create_consent(base: Path, p: dict) -> dict:
    """Web consent: typed name, every scope ticked, the exact text hash, and either a spoken statement or an existing signed form."""
    name = norm_name(p.get("name", ""))
    role = p.get("role", "")
    if len(name) < 2 or len(name) > 80:
        raise UiError(400, "enter the person's full name")
    if role not in registry.ROLES:
        raise UiError(400, "choose owner or employee")
    if norm_name(p.get("typed_name", "")).casefold() != name.casefold():
        raise UiError(400, "the typed signature must match the name exactly")
    agreed = p.get("agreements") or {}
    missing = [a for a in AGREEMENTS if agreed.get(a) is not True]
    if missing:
        raise UiError(400, "every box must be ticked: " + ", ".join(missing))
    ui_lang = _ui_lang(p.get("ui_lang"))
    if p.get("text_sha256") != consent_text_sha256(ui_lang):
        raise UiError(409, "the consent text changed since this page loaded: reload and read it again")
    speaker = slugify(name)
    if (registry.speaker_dir(speaker, base) / "consent.json").is_file():
        raise UiError(409, f"{name} already has a record ({speaker}). Withdraw it under Enrolled voices before starting over.")
    when = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    evidence = {"method": "web-ui", "timestamp": when, "typed_name": name, "agreements": {a: True for a in AGREEMENTS},
                "consent_text_sha256": consent_text_sha256(ui_lang), "consent_language": ui_lang,
                "consent_text_status": CONSENT_STATUS[ui_lang], "consent_text_draft": ui_lang in DRAFT_CONSENT_LANGS}
    proof = None
    existing = (p.get("existing_form_path") or "").strip()
    with tempfile.TemporaryDirectory() as t:
        if existing:
            form = Path(existing).expanduser()
            if form.suffix.lower() not in FORM_EXT or not form.is_file():
                raise UiError(400, f"no signed form at {form} (pdf, png, jpg, heic or txt)")
            evidence["existing_form_path"] = str(form)
        else:
            try:
                proof = base64.b64decode(p.get("proof_wav_b64") or "", validate=True)
            except (binascii.Error, ValueError) as exc:
                raise UiError(400, "the spoken statement was not received") from exc
            info = wav_info(proof)
            if not MIN_PROOF_S <= info["seconds"] <= MAX_PROOF_S or info["rms"] < 0.003:
                raise UiError(400, f"the spoken statement must be {MIN_PROOF_S:.0f}-{MAX_PROOF_S:.0f} s of audible speech: record it again")
            spoken = statement_for(name, ui_lang)
            evidence["proof_audio"] = {"file": "forms/consent-statement.wav", "sha256": hashlib.sha256(proof).hexdigest(),
                                       "seconds": info["seconds"], "statement": spoken}
            form = Path(t) / "consent-record.txt"
            form.write_text(
                f"ELECTRONIC CONSENT RECORD (recorded in the Salareen voice enrollment page)\n"
                f"Name: {name}\nRole: {role}\nTime: {when}\nTyped signature: {name}\n"
                f"Agreed: {', '.join(AGREEMENTS)}\nConsent text language: {ui_lang} ({CONSENT_STATUS[ui_lang]})\n"
                f"Consent text sha256: {consent_text_sha256(ui_lang)}\n"
                f"Spoken statement ({info['seconds']} s, audio sha256 {evidence['proof_audio']['sha256']}): {spoken}\n"
                f"\n----- CONSENT TEXT AS SHOWN -----\n{consent_text(ui_lang)}", encoding="utf-8")
        try:
            rec = registry.record_consent(speaker, name, role, form, base=base, evidence=evidence)
        except registry.ConsentError as exc:
            raise UiError(400, str(exc)) from exc
    if proof is not None:
        (registry.speaker_dir(speaker, base) / "forms" / "consent-statement.wav").write_bytes(proof)
    return {"speaker": speaker, "name": rec["name"], "role": rec["role"], "date": rec["date"], "method": "web-ui"}


def _prompt(lang: str, prompt_id: str) -> dict:
    for item in PROMPT_SETS.get(lang, []):
        if item["id"] == prompt_id:
            return item
    raise UiError(404, "unknown prompt")


def _gated(base: Path, speaker: str, scope: str = "model_training") -> dict:
    try:
        return registry.require_consent(speaker, scope, base)
    except registry.ConsentError as exc:
        raise UiError(403, str(exc)) from exc


def save_take(base: Path, speaker: str, lang: str, prompt_id: str, body: bytes) -> dict:
    _gated(base, speaker)
    _prompt(lang, prompt_id)
    info = wav_info(body)
    if not MIN_TAKE_S <= info["seconds"] <= MAX_TAKE_S:
        raise UiError(400, f"a take must be {MIN_TAKE_S:.0f}-{MAX_TAKE_S:.0f} s; this one is {info['seconds']} s")
    dest = registry.speaker_dir(speaker, base) / "raw" / lang / f"{prompt_id}.wav"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    warnings = []
    if info["peak"] >= 0.999:
        warnings.append("clipping: move back from the microphone")
    if info["peak"] < 0.05:
        warnings.append("very quiet: speak up or move closer")
    if info["snr_db"] < enroll.MIN_SNR_DB:
        warnings.append("background noise is high: find a quieter spot")
    return {**info, "warnings": warnings, "prompt_id": prompt_id}


def _concat_takes(paths: list[Path], dest: Path) -> None:
    import numpy as np

    parts, rate = [], None
    for p in paths:
        x, r = enroll.read_wav(p)
        if rate not in (None, r):
            raise UiError(400, "takes were recorded at different sample rates: re-record them in one sitting")
        rate = r
        parts.append(enroll.trim_silence(x, r))
    y = np.concatenate(parts)
    with wave.open(str(dest), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())


def _sample_tags(info: dict) -> dict:
    keys = ("seconds", "snr_db", "cleaned", "snr_db_clean")
    return {k: info[k] for k in keys if k in info}


def finish_enrollment(base: Path, speaker: str, lang: str) -> dict:
    rec = _gated(base, speaker)
    prompts = PROMPT_SETS.get(lang)
    if not prompts:
        raise UiError(400, "unknown language")
    d = registry.speaker_dir(speaker, base)
    takes = [d / "raw" / lang / f"{p['id']}.wav" for p in prompts]
    missing = [p["id"] for p, t in zip(prompts, takes) if not t.is_file()]
    if missing:
        raise UiError(400, "record every line first; missing " + ", ".join(missing))
    rel = f"samples/web-{lang}.wav"
    (d / "tmp").mkdir(exist_ok=True)
    concat, dest = d / "raw" / lang / "concat.wav", d / "tmp" / f"web-{lang}.wav"
    _concat_takes(takes, concat)
    try:
        info = enroll.prepare(concat, dest)
    except enroll.SampleError as exc:
        dest.unlink(missing_ok=True)
        return {"ok": False, "error": str(exc), "min_seconds": enroll.MIN_S, "min_snr_db": enroll.MIN_SNR_DB}
    if rel in rec["samples"]:
        registry.remove_sample(speaker, rel, base)
    (d / "samples").mkdir(exist_ok=True)
    shutil.move(str(dest), str(d / rel))
    held = dest.parent / ".raw" / dest.name
    if held.exists():
        (d / "samples" / ".raw").mkdir(parents=True, exist_ok=True)
        shutil.move(str(held), str(d / "samples" / ".raw" / dest.name))
    transcript = " ".join(p["text"] for p in prompts)
    registry.add_sample(speaker, d / rel, transcript, lang, base, extra=_sample_tags(info))
    return {"ok": True, "file": rel, **info}


def start_voice_check(base: Path, speaker: str, lang: str) -> dict:
    """Run the optional pronunciation check in the background (a recognizer can take minutes on first load)."""
    _gated(base, speaker)
    prompts = PROMPT_SETS.get(lang)
    if not prompts:
        raise UiError(400, "unknown language")
    d = registry.speaker_dir(speaker, base) / "raw" / lang
    takes = [(p["id"], p["text"], d / f"{p['id']}.wav") for p in prompts]
    missing = [t[0] for t in takes if not t[2].is_file()]
    if missing:
        raise UiError(400, "record every line first; missing " + ", ".join(missing))
    key = (speaker, lang)
    if _CHECKS.get(key, {}).get("state") == "running":
        return {"state": "running"}
    job = _CHECKS[key] = {"state": "running"}

    def work():
        try:
            job.update(voice_check.check_takes(takes, lang))
            job["state"] = "done"
        except Exception as exc:  # noqa: BLE001 - never break enrollment over a recognizer problem
            job.update({"state": "failed", "error": f"{type(exc).__name__}: {str(exc)[:160]}"})

    threading.Thread(target=work, daemon=True).start()
    return {"state": "running"}


def voice_check_status(speaker: str, lang: str) -> dict:
    return dict(_CHECKS.get((speaker, lang)) or {"state": "none"})


def withdraw(base: Path, speaker: str, typed_name: str) -> dict:
    try:
        rec = registry.load_consent(speaker, base)
    except registry.ConsentError as exc:
        raise UiError(404, str(exc)) from exc
    if norm_name(typed_name).casefold() != norm_name(rec["name"]).casefold():
        raise UiError(400, "type the person's full name to withdraw their consent")
    registry.revoke(speaker, base)
    return {"speaker": speaker, "revoked": True}


def cuda_host() -> bool:
    if os.uname().sysname != "Linux" or not shutil.which("nvidia-smi"):
        return False
    return subprocess.run(["nvidia-smi", "-L"], capture_output=True).returncode == 0


def synth_command(speaker: str, model: str, lang: str, out: str) -> str:
    return f"MODELS={model} LANGS={lang},en scripts/run_voice_clone.sh {out} --speakers {speaker} --limit 2"


def start_synth(base: Path, speaker: str, model: str) -> dict:
    if model not in SYNTH_MODELS:
        raise UiError(400, "model must be voxcpm2 or cosyvoice2")
    rec = _gated(base, speaker, "course_narration")
    if not rec["samples"]:
        raise UiError(400, "enroll a sample first")
    lang = sorted(rec["samples"].values(), key=lambda i: i["lang"])[0]["lang"]
    out = f"runs/{time.strftime('%F')}-clones"
    cmd = synth_command(speaker, model, lang, out)
    if not cuda_host():
        return {"started": False, "command": cmd, "reason": "this machine has no CUDA GPU; run this on the Spark"}
    job = _JOBS.get(speaker)
    if job and job["proc"].poll() is None:
        raise UiError(409, "a test for this speaker is already running")
    out_dir = ROOT / out
    out_dir.mkdir(parents=True, exist_ok=True)
    log = out_dir / f"synth-{speaker}-{model}.log"
    env = {**os.environ, "MODELS": model, "LANGS": f"{lang},en", "GS_VOICES_DIR": str(base)}
    with log.open("ab") as fh:
        proc = subprocess.Popen(["bash", str(ROOT / "scripts" / "run_voice_clone.sh"), str(out_dir), "--speakers", speaker, "--limit", "2"],
                                cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)
    _JOBS[speaker] = {"proc": proc, "log": log, "out": out_dir, "model": model}
    return {"started": True, "command": cmd, "out": str(out_dir), "listen": f"python3 -m tts_bakeoff.lab --out {out_dir}"}


def synth_status(speaker: str) -> dict:
    job = _JOBS.get(speaker)
    if not job:
        return {"state": "none"}
    rc = job["proc"].poll()
    tail = job["log"].read_text(encoding="utf-8", errors="replace")[-1200:] if job["log"].is_file() else ""
    return {"state": "running" if rc is None else ("done" if rc == 0 else "failed"), "model": job["model"], "log_tail": tail,
            "out": str(job["out"]), "listen": f"python3 -m tts_bakeoff.lab --out {job['out']}"}


def say_langs() -> dict[str, list[str]]:
    from tts_bakeoff.adapters.cosyvoice2 import CosyVoice2Adapter
    from tts_bakeoff.adapters.voxcpm2 import VoxCPM2Adapter

    return {"voxcpm2": sorted(VoxCPM2Adapter.languages), "cosyvoice2": sorted(CosyVoice2Adapter.languages)}


def _launch(argv: list[str], env: dict, log: Path) -> subprocess.Popen:
    with log.open("ab") as fh:
        return subprocess.Popen(argv, cwd=ROOT, env=env, stdout=fh, stderr=subprocess.STDOUT, start_new_session=True)


def say_state(job: dict) -> str:
    if job["proc"].poll() is None:
        return "running" if job["wav"].with_suffix(".running").exists() else "waiting for GPU lock"
    return "done" if job["proc"].returncode == 0 and job["wav"].is_file() else "failed"


def say_command(model: str, speaker: str, lang: str, text: str) -> str:
    return (f"printf %s {shlex.quote(text)} > /tmp/say.txt && "
            f"scripts/run_voice_say.sh {model} {speaker} {lang} runs/say-{speaker}.wav /tmp/say.txt")


def start_say(base: Path, speaker: str, p: dict) -> dict:
    model, lang = str(p.get("model", "")), str(p.get("lang", ""))
    text = " ".join(str(p.get("text", "")).split())
    if model not in SYNTH_MODELS:
        raise UiError(400, "model must be voxcpm2 or cosyvoice2")
    if lang not in say_langs()[model]:
        raise UiError(400, f"{model} does not speak {lang!r} (it speaks: {', '.join(say_langs()[model])})")
    if not text:
        raise UiError(400, "type the words to say")
    if len(text) > SAY_MAX_CHARS:
        raise UiError(400, f"keep it to {SAY_MAX_CHARS} characters; this is {len(text)}")
    rec = _gated(base, speaker, "course_narration")
    if not rec["samples"]:
        raise UiError(400, "enroll a sample first")
    if not cuda_host():
        return {"started": False, "command": say_command(model, speaker, lang, text),
                "reason": "this machine has no CUDA GPU; run this on the Spark"}
    for j in _SAY.values():
        if j["speaker"] == speaker and j["model"] == model and say_state(j) in SAY_ACTIVE:
            raise UiError(409, f"a {model} clip for {rec['name']} is already {say_state(j)}: wait for it to finish")
    job_id = uuid.uuid4().hex[:12]
    out_dir = base / "say" / speaker
    out_dir.mkdir(parents=True, exist_ok=True)
    wav, textfile, log = out_dir / f"{job_id}.wav", out_dir / f"{job_id}.txt", out_dir / f"{job_id}.log"
    textfile.write_text(text, encoding="utf-8")
    env = {**os.environ, "GS_VOICES_DIR": str(base)}
    proc = _launch(["bash", str(ROOT / "scripts" / "run_voice_say.sh"), model, speaker, lang, str(wav), str(textfile)], env, log)
    _SAY[job_id] = {"id": job_id, "speaker": speaker, "name": rec["name"], "model": model, "lang": lang, "text": text, "proc": proc,
                    "wav": wav, "log": log, "created": time.strftime("%H:%M:%S")}
    return {"started": True, "id": job_id, "state": say_state(_SAY[job_id])}


def say_jobs(base: Path) -> list[dict]:
    out = []
    for j in reversed(list(_SAY.values())):
        state = say_state(j)
        row = {"id": j["id"], "speaker": j["speaker"], "name": j["name"], "model": j["model"], "lang": j["lang"], "text": j["text"],
               "state": state, "created": j["created"], "label": f"AI-generated voice of {j['name']}"}
        if state == "done":
            try:
                registry.require_consent(j["speaker"], "course_narration", base)
                row["audio"] = f"/api/say/audio/{j['id']}.wav"
            except registry.ConsentError:
                row["state"] = "withdrawn"
        elif state == "failed" and j["log"].is_file():
            row["log_tail"] = j["log"].read_text(encoding="utf-8", errors="replace")[-600:]
        out.append(row)
    return out


def say_audio(base: Path, job_id: str) -> tuple[bytes, str]:
    job = _SAY.get(job_id)
    if not job or say_state(job) != "done":
        raise UiError(404, "no such clip")
    _gated(base, job["speaker"], "course_narration")
    return job["wav"].read_bytes(), f"{job['speaker']}-{job_id}.wav"


def _host_ok(value: str | None) -> bool:
    if not value:
        return False
    host = urllib.parse.urlsplit("//" + value).hostname or ""
    return host in LOCAL_HOSTS


def make_handler(base: Path):
    lock = threading.Lock()

    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "SalareenVoiceEnroll/1"

        def log_message(self, fmt, *args):
            return

        def _send(self, code: int, body: bytes, ctype: str, head: bool = False):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            if not head:
                self.wfile.write(body)

        def _json(self, code: int, data) -> None:
            self._send(code, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

        def _guard(self, post: bool) -> bool:
            """Reject DNS-rebinding (Host) and cross-site posts (Origin, and a custom header a plain form cannot send)."""
            origin = self.headers.get("Origin")
            if not _host_ok(self.headers.get("Host")) or (origin and not _host_ok(urllib.parse.urlsplit(origin).netloc)):
                self._json(403, {"error": "forbidden host"})
                return False
            if post and self.headers.get("X-Enroll") != "1":
                self._json(403, {"error": "missing X-Enroll header"})
                return False
            return True

        def _body(self) -> bytes:
            n = int(self.headers.get("Content-Length") or 0)
            if n < 0 or n > MAX_BODY:
                raise UiError(413, "upload too large")
            return self.rfile.read(n)

        def _json_body(self) -> dict:
            try:
                data = json.loads(self._body() or b"{}")
            except json.JSONDecodeError as exc:
                raise UiError(400, "invalid JSON") from exc
            if not isinstance(data, dict):
                raise UiError(400, "expected a JSON object")
            return data

        def do_GET(self):  # noqa: N802
            self._get(False)

        def do_HEAD(self):  # noqa: N802
            self._get(True)

        def _get(self, head: bool):
            if not self._guard(False):
                return
            u = urllib.parse.urlsplit(self.path)
            q = urllib.parse.parse_qs(u.query)
            try:
                if u.path in ("/", "/index.html"):
                    return self._file("index.html", head)
                if u.path in ("/enroll.js", "/enroll.css"):
                    return self._file(u.path.lstrip("/"), head)
                if u.path == "/api/config":
                    return self._json(200, config())
                if u.path == "/api/statement":
                    return self._json(200, {"text": statement((q.get("name") or [""])[0], (q.get("lang") or ["en"])[0])})
                if u.path == "/api/speakers":
                    return self._json(200, {"speakers": speakers(base), "cuda": cuda_host(), "root": str(base)})
                m = re.fullmatch(r"/api/synth/([a-z0-9_-]+)", u.path)
                if m:
                    return self._json(200, synth_status(m.group(1)))
                m = re.fullmatch(r"/api/voicecheck/([a-z0-9_-]+)/([a-z]{2,3})", u.path)
                if m:
                    return self._json(200, voice_check_status(m.group(1), m.group(2)))
                if u.path == "/api/say":
                    return self._json(200, {"jobs": say_jobs(base)})
                m = re.fullmatch(r"/api/say/audio/([a-f0-9]{12})\.wav", u.path)
                if m:
                    data, name = say_audio(base, m.group(1))
                    self.send_response(200)
                    self.send_header("Content-Type", "audio/wav")
                    self.send_header("Content-Length", str(len(data)))
                    self.send_header("Content-Disposition", f'inline; filename="{name}"')
                    self.send_header("X-AI-Generated", "true")
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    if not head:
                        self.wfile.write(data)
                    return
            except UiError as exc:
                return self._json(exc.code, {"error": exc.message})
            return self._send(404, b"not found", "text/plain; charset=utf-8", head)

        def _file(self, name: str, head: bool):
            path = STATIC / name
            if not path.is_file():
                return self._send(404, b"not found", "text/plain; charset=utf-8", head)
            self._send(200, path.read_bytes(), content_type(path), head)

        def do_POST(self):  # noqa: N802
            if not self._guard(True):
                return
            path = urllib.parse.urlsplit(self.path).path
            try:
                with lock:
                    self._post(path)
            except UiError as exc:
                self._json(exc.code, {"error": exc.message})
            except registry.ConsentError as exc:
                self._json(403, {"error": str(exc)})
            except Exception as exc:  # noqa: BLE001 - never leak a traceback to the page
                self._json(500, {"error": f"{type(exc).__name__}: {str(exc)[:200]}"})

        def _post(self, path: str):
            if path == "/api/consent":
                return self._json(200, create_consent(base, self._json_body()))
            m = re.fullmatch(r"/api/take/([a-z0-9_-]+)/([a-z]{2,3})/([a-z]{2,3}-\d+)", path)
            if m:
                return self._json(200, save_take(base, m.group(1), m.group(2), m.group(3), self._body()))
            m = re.fullmatch(r"/api/enroll/([a-z0-9_-]+)", path)
            if m:
                return self._json(200, finish_enrollment(base, m.group(1), str(self._json_body().get("lang", ""))))
            m = re.fullmatch(r"/api/voicecheck/([a-z0-9_-]+)/([a-z]{2,3})", path)
            if m:
                return self._json(200, start_voice_check(base, m.group(1), m.group(2)))
            m = re.fullmatch(r"/api/revoke/([a-z0-9_-]+)", path)
            if m:
                return self._json(200, withdraw(base, m.group(1), str(self._json_body().get("typed_name", ""))))
            m = re.fullmatch(r"/api/synth/([a-z0-9_-]+)", path)
            if m:
                return self._json(200, start_synth(base, m.group(1), str(self._json_body().get("model", ""))))
            m = re.fullmatch(r"/api/say/([a-z0-9_-]+)", path)
            if m:
                return self._json(200, start_say(base, m.group(1), self._json_body()))
            raise UiError(404, "not found")

    return Handler


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True


def serve(base: Path, port: int = 8780) -> Server:
    base.mkdir(parents=True, exist_ok=True)
    return Server(("127.0.0.1", port), make_handler(base))
