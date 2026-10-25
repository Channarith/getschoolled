"""Cantonese in the enrollment UI: consent text, spoken statement, recording script, voice check and model support."""
from __future__ import annotations

import base64
import hashlib
import re
import threading
import time
from pathlib import Path

import pytest

from tts_bakeoff import adapters, asr
from tts_bakeoff.build_sentences import load
from tts_bakeoff.voice_clone import enroll_ui as ui
from tts_bakeoff.voice_clone import registry
from tts_bakeoff.voice_clone.enroll_ui import i18n, voice_check
from tts_bakeoff.voice_clone.enroll_ui.prompts import CONSENT_STATEMENTS, PROMPT_SETS, statement_for

from .test_enroll_ui import call, record_all, speechlike

NAME = "陳大文"
REPO = Path(__file__).resolve().parents[2]


@pytest.fixture
def server(tmp_path, monkeypatch):
    base = tmp_path / "voices"
    srv = ui.serve(base, 0)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setattr(ui, "cuda_host", lambda: False)
    yield f"http://127.0.0.1:{srv.server_address[1]}", base
    srv.shutdown()
    srv.server_close()


def yue_payload(name=NAME, **over):
    p = {"name": name, "role": "employee", "typed_name": name, "agreements": {a: True for a in ui.AGREEMENTS},
         "ui_lang": "yue", "text_sha256": ui.consent_text_sha256("yue"), "proof_wav_b64": base64.b64encode(speechlike(5)).decode()}
    p.update(over)
    return p


def poll_check(url, speaker, lang, timeout=10.0):
    end = time.time() + timeout
    while time.time() < end:
        code, j = call(url, f"/api/voicecheck/{speaker}/{lang}")
        assert code == 200
        if j["state"] != "running":
            return j
        time.sleep(0.05)
    raise AssertionError("voice check did not finish")


def test_config_offers_cantonese_with_draft_status(server):
    url, _ = server
    code, cfg = call(url, "/api/config")
    assert code == 200 and cfg["ui_langs"] == {"en": "English", "yue": "廣東話"}
    yue = cfg["consent_texts"]["yue"]
    assert yue["draft"] is True and "native speaker" in yue["status"] and "counsel" in yue["status"]
    assert yue["sha256"] == hashlib.sha256(yue["text"].encode("utf-8")).hexdigest() != cfg["consent_texts"]["en"]["sha256"]
    assert cfg["consent_texts"]["en"]["draft"] is False
    assert cfg["consent_text_sha256"] == cfg["consent_texts"]["en"]["sha256"]
    assert len(cfg["prompts"]["yue"]) == 8 and "yue" in cfg["draft_langs"] and cfg["langs"]["yue"] == "廣東話"


def test_ui_strings_have_the_same_keys_and_placeholders():
    en, yue = i18n.UI["en"], i18n.UI["yue"]
    assert set(en) == set(yue)
    ph = lambda s: sorted(re.findall(r"\{(\w+)\}", s))  # noqa: E731
    assert all(ph(en[k]) == ph(yue[k]) for k in en)
    html = (ui.STATIC / "index.html").read_text(encoding="utf-8")
    for key in set(re.findall(r'data-i18n(?:-ph)?="(\w+)"', html)):
        assert key in en, key


def test_cantonese_consent_keeps_every_clause_and_scope():
    en = (ui.CONSENT_FORM).read_text(encoding="utf-8")
    yue = i18n.consent_path("yue").read_text(encoding="utf-8")
    numbered = lambda t: re.findall(r"^(\d)\. ", t, flags=re.M)  # noqa: E731
    assert numbered(en) == numbered(yue) == list("1234567")
    for word in ("商業", "訓練", "旁白", "撤回", "30", "冒充", "僱傭", "草稿"):
        assert word in yue, word
    assert "覆核" in yue.splitlines()[0]


def test_cantonese_script_is_colloquial_cantonese_and_covers_the_tones():
    lines = [p["text"] for p in PROMPT_SETS["yue"]]
    assert len(lines) == 8 and [p["id"] for p in PROMPT_SETS["yue"]] == [f"yue-{i}" for i in range(1, 9)]
    joined = "".join(lines)
    assert all(ch in joined for ch in "詩史試時市事")
    for marker in ("嘅", "喺", "唔", "我哋", "㗎", "啦", "噃", "呀", "咩", "喇"):
        assert marker in joined, marker
    assert 200 <= len(joined) <= 340  # about 4 characters per second: roughly a minute
    assert not set(lines) & {r["text"] for r in load("yue")}, "the reference script must not repeat the bake-off sentences"


def test_cantonese_statement_has_the_name_and_is_not_english():
    s = statement_for(NAME, "yue")
    assert NAME in s and "同意" in s and "撤回" in s and s != statement_for(NAME)
    assert statement_for("Alice  Tran") == CONSENT_STATEMENTS["en"].format(name="Alice Tran")


def test_statement_endpoint_by_language(server):
    url, _ = server
    import urllib.parse

    q = urllib.parse.quote(NAME)
    assert NAME in call(url, f"/api/statement?name={q}&lang=yue")[1]["text"]
    assert "My name is" in call(url, f"/api/statement?name={q}")[1]["text"]
    assert call(url, f"/api/statement?name={q}&lang=xx")[0] == 400


def test_cantonese_consent_records_language_hash_and_draft_status(server):
    url, base = server
    code, r = call(url, "/api/consent", yue_payload())
    assert code == 200, r
    sp = r["speaker"]
    assert registry.SLUG_RE.match(sp) and sp.startswith("speaker-")
    rec = registry.require_consent(sp, "course_narration", base)
    ev = rec["evidence"]
    assert rec["name"] == NAME and ev["typed_name"] == NAME
    assert ev["consent_language"] == "yue" and ev["consent_text_sha256"] == ui.consent_text_sha256("yue")
    assert ev["consent_text_draft"] is True and "native speaker" in ev["consent_text_status"]
    assert ev["proof_audio"]["statement"] == statement_for(NAME, "yue")
    record_text = (base / sp / "forms" / "consent-record.txt").read_text(encoding="utf-8")
    assert "錄音及聲音模型同意書" in record_text and "Consent text language: yue" in record_text
    assert ui.consent_text_sha256("yue") in record_text
    assert set(registry.REQUIRED_SCOPES) <= set(rec["scopes"])


def test_english_consent_still_records_english_and_not_draft(server):
    url, base = server
    p = yue_payload("Alice Tran", ui_lang="en", text_sha256=ui.consent_text_sha256())
    p.pop("ui_lang")
    code, r = call(url, "/api/consent", p)
    assert code == 200, r
    ev = registry.load_consent(r["speaker"], base)["evidence"]
    assert ev["consent_language"] == "en" and ev["consent_text_draft"] is False
    assert ev["consent_text_sha256"] == ui.consent_text_sha256()


@pytest.mark.parametrize("change,expect", [
    ({"text_sha256": None}, 409),                     # the English hash sent with the Cantonese page
    ({"ui_lang": "xx"}, 400),
    ({"typed_name": "陳大明"}, 400),
    ({"agreements": {"commercial_use": True, "model_training": True, "course_narration": True}}, 400),
    ({"proof_wav_b64": ""}, 400),
])
def test_cantonese_consent_is_still_gated(server, change, expect):
    url, base = server
    if "text_sha256" in change:
        change = {"text_sha256": ui.consent_text_sha256("en")}
    code, r = call(url, "/api/consent", yue_payload(**change))
    assert code == expect, r
    assert registry.list_speakers(base) == []


def test_cantonese_hash_is_refused_on_the_english_page(server):
    url, base = server
    code, _ = call(url, "/api/consent", yue_payload(ui_lang="en"))
    assert code == 409 and registry.list_speakers(base) == []


def test_cantonese_enrollment_end_to_end_and_withdraw(server):
    url, base = server
    sp = call(url, "/api/consent", yue_payload())[1]["speaker"]
    record_all(url, sp, "yue")
    code, r = call(url, f"/api/enroll/{sp}", {"lang": "yue"})
    assert code == 200 and r["ok"], r
    samples = registry.load_consent(sp, base)["samples"]
    sess = samples["samples/web-yue.wav"]
    assert sess["lang"] == "yue" and sess["transcript"].startswith("大家早晨") and "嘩，答啱喇" in sess["transcript"]
    assert (registry.speaker_dir(sp, base) / "samples/web-yue.wav").is_file() and sess["consent_language"] == "yue"
    ref = samples.get("samples/ref-yue.wav")                       # the short exact-transcript reference cut from one prompt take
    assert ref and ref["role"] == "reference" and ref["transcript_exact"] and ref["transcript"] in sess["transcript"] and r["reference"]["written"]
    assert call(url, f"/api/revoke/{sp}", {"typed_name": "陳大明"})[0] == 400
    assert call(url, f"/api/revoke/{sp}", {"typed_name": NAME})[0] == 200
    assert call(url, f"/api/take/{sp}/yue/yue-1", raw=speechlike(5))[0] == 403
    with pytest.raises(registry.ConsentError):
        registry.primary_sample(sp, base)


def test_takes_need_consent_for_yue_too(server):
    url, _ = server
    assert call(url, "/api/take/nobody/yue/yue-1", raw=speechlike(5))[0] == 403


def test_voice_check_reports_per_line_and_never_blocks(server, monkeypatch):
    url, base = server
    sp = call(url, "/api/consent", yue_payload())[1]["speaker"]
    assert call(url, f"/api/voicecheck/{sp}/yue", {})[0] == 400  # nothing recorded yet
    record_all(url, sp, "yue")
    monkeypatch.setattr(voice_check, "get_engine", lambda: asr.FakeASR(0.0))
    assert call(url, f"/api/voicecheck/{sp}/yue", {})[0] == 200
    j = poll_check(url, sp, "yue")
    assert j["state"] == "done" and j["available"] and j["warnings"] == 0
    assert len(j["items"]) == 8 and all(i["pass"] and i["cer"] == 0 for i in j["items"])

    monkeypatch.setattr(voice_check, "get_engine", lambda: asr.FakeASR(0.9))
    call(url, f"/api/voicecheck/{sp}/yue", {})
    j = poll_check(url, sp, "yue")
    assert j["state"] == "done" and j["warnings"] == 8 and all(i["pass"] is False for i in j["items"])

    code, r = call(url, f"/api/enroll/{sp}", {"lang": "yue"})
    assert code == 200 and r["ok"], "a bad pronunciation check must not block enrollment"


def test_voice_check_skips_without_a_recognizer_and_survives_a_crashing_one(server, monkeypatch):
    url, _ = server
    sp = call(url, "/api/consent", yue_payload())[1]["speaker"]
    record_all(url, sp, "yue")
    monkeypatch.setattr(voice_check, "get_engine", lambda: None)
    call(url, f"/api/voicecheck/{sp}/yue", {})
    j = poll_check(url, sp, "yue")
    assert j["state"] == "done" and j["available"] is False and j["items"] == []

    class Boom(asr.ASR):
        name = "boom"

        def transcribe(self, wav_path, lang, reference=None):
            raise RuntimeError("model missing")

    monkeypatch.setattr(voice_check, "get_engine", lambda: Boom())
    call(url, f"/api/voicecheck/{sp}/yue", {})
    j = poll_check(url, sp, "yue")
    assert j["state"] == "done" and all(i["pass"] is None and "model missing" in i["error"] for i in j["items"])
    assert call(url, f"/api/voicecheck/{sp}/yue", {})[0] == 200


def test_voice_check_is_gated_by_consent(server):
    url, _ = server
    assert call(url, "/api/voicecheck/nobody/yue", {})[0] == 403


def test_cer_normalization_and_thresholds(monkeypatch):
    assert voice_check.cer("你好，世界！", "你好 世界") == 0
    assert voice_check.cer("今日天氣好好", "今日天氣好") == round(1 / 6, 3)
    assert voice_check.cer("", "") == 0 and voice_check.cer("", "x") == 1
    assert voice_check.cer("Hello, World", "hello world", "en") == 0
    assert voice_check.PASS_CER["yue"] > voice_check.PASS_CER["default"] - 0.01
    res = voice_check.check_takes([("a", "你好嗎", Path("x.wav"))], "yue", engine=asr.FakeASR(0.0))
    assert res["available"] and res["items"][0]["pass"] and res["limit"] == voice_check.PASS_CER["yue"]
    monkeypatch.setenv("ENROLL_ASR", "off")
    assert voice_check.get_engine() is None


def test_whisper_knows_cantonese():
    assert asr.WHISPER_LANG["yue"] == "yue"


def test_model_support_for_cantonese():
    """VoxCPM2 lists Cantonese under Chinese dialects; CosyVoice 2 (0.5B) does not, so it must be skipped, not mislabelled."""
    assert adapters.get("voxcpm2").supports("yue")
    assert not adapters.get("cosyvoice2").supports("yue")
    assert load("yue", 3) and all(r["lang"] == "yue" for r in load("yue"))


def test_run_script_defaults_to_each_speakers_own_language_and_all_includes_cantonese():
    script = (REPO / "scripts" / "run_voice_clone.sh").read_text(encoding="utf-8")
    assert 'LANGS="${LANGS:-}"' in script and '${LANGS:+--langs "$LANGS"}' in script     # no --langs unless asked: own language(s)
    from tts_bakeoff.voice_clone.profile import ALL_LANGS

    from tts_bakeoff.adapters.voxcpm2 import VoxCPM2Adapter

    assert "yue" in ALL_LANGS and "yue" in VoxCPM2Adapter.languages and "every language the model supports" in script   # LANGS=all still covers Cantonese (VoxCPM2)
    assert '${GS_CLONE_WORKERS:+--workers "$GS_CLONE_WORKERS"}' in script
