"""Security properties of the voice stack: slugs, file permissions, the signed-form path, revoke and publish."""
import json
import os
import stat

import pytest

from tts_bakeoff.demo_voice import assets as A
from tts_bakeoff.voice_clone import registry
from tts_bakeoff.voice_clone.enroll_ui import UiError, vet_form_path


def mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


def make_speaker(base, speaker="wei", form_dir=None):
    form = (form_dir or base.parent) / "signed.pdf"
    form.write_bytes(b"%PDF-1.4 " + b"x" * 500)
    return registry.record_consent(speaker, "Wei", "employee", form, base=base)


def test_a_trailing_newline_is_not_a_valid_speaker_id(tmp_path):
    for bad in ("wei\n", "wei\r\n", "../wei", "wei/../x", "", "W", "a" * 60, "Wei"):
        with pytest.raises(registry.ConsentError):
            registry.speaker_dir(bad, tmp_path)
    assert registry.speaker_dir("wei-miao", tmp_path).name == "wei-miao"


def test_assets_voice_id_rejects_a_trailing_newline():
    assert A.VOICE_ID.fullmatch("channarith") and not A.VOICE_ID.fullmatch("channarith\n")
    with pytest.raises(SystemExit):
        A.cmd_withdraw(type("a", (), {"speaker": "wei\n", "dry_run": True, "yes": False})(), A.Settings())


def test_recordings_and_forms_are_owner_only(tmp_path):
    base = tmp_path / "voices"
    base.mkdir()
    os.chmod(base, 0o755)
    make_speaker(base)
    take = base / "wei" / "raw" / "en" / "en-1.wav"
    take.parent.mkdir(parents=True)
    take.write_bytes(b"RIFF" + b"\0" * 60)
    os.chmod(take, 0o644)
    os.chmod(take.parent, 0o755)
    registry.tighten(base / "wei")
    assert mode(base) == 0o700
    for p in (base / "wei", base / "wei" / "forms", take.parent):
        assert mode(p) == 0o700, p
    for p in (take, base / "wei" / "consent.json", base / "wei" / "forms" / "signed.pdf"):
        assert mode(p) == 0o600, p


def test_tighten_never_walks_a_home_directory(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / "docs").mkdir(parents=True)
    f = home / "docs" / "notes.txt"
    f.write_text("x")
    os.chmod(f, 0o644)
    monkeypatch.setattr("pathlib.Path.home", classmethod(lambda cls: home))
    registry.tighten(home)
    assert mode(f) == 0o644   # untouched


def test_revoke_leaves_a_marker_next_to_the_published_clips(tmp_path, monkeypatch):
    base, assets = tmp_path / "voices", tmp_path / "voice-assets"
    (assets / "wei" / "yue").mkdir(parents=True)
    monkeypatch.setenv("GS_VOICE_ASSETS", str(assets))
    make_speaker(base)
    registry.revoke("wei", base)
    assert (assets / "wei" / "REVOKED").is_file()
    with pytest.raises(registry.ConsentError):
        registry.require_consent("wei", "course_narration", base)


def make_assets(root, voices):
    for vid in voices:
        d = root / vid / "en"
        d.mkdir(parents=True)
        (d / "a.mp3").write_bytes(b"x")
        (root / vid / "index.json").write_text("{}")
    (root / "voices.json").write_text(json.dumps({"voices": [{"id": v, "active": a} for v, a in voices.items()]}))
    return root


def settings():
    return A.Settings(endpoint="https://example.vultrobjects.com", bucket="b", prefix="voice-assets", public_base="https://b.example")


def test_sync_uploads_only_active_voices_and_never_a_revoked_one(tmp_path):
    root = make_assets(tmp_path, {"live": True, "off": False, "gone": True})
    (root / "gone" / "REVOKED").write_text("consent revoked")
    clips = A.plan_sync(root, settings())[0]
    includes = [clips[i + 1] for i, a in enumerate(clips) if a == "--include"]
    assert includes == ["live/*.mp3"]
    assert clips[clips.index("--exclude") + 1] == "*"
    uploaded_indexes = [c[3] for c in A.plan_sync(root, settings())[1:-1]]
    assert len(uploaded_indexes) == 1 and uploaded_indexes[0].endswith("/live/index.json")


def test_signed_form_path_must_be_an_ordinary_document(tmp_path):
    ok = tmp_path / "Documents" / "signed.pdf"
    ok.parent.mkdir()
    ok.write_bytes(b"%PDF-1.4 " + b"x" * 500)
    assert vet_form_path(str(ok)) == ok.resolve()

    hidden_dir = tmp_path / ".ssh"
    hidden_dir.mkdir()
    (hidden_dir / "notes.txt").write_text("x" * 500)
    hidden_file = tmp_path / ".secret.txt"
    hidden_file.write_text("x" * 500)
    link = tmp_path / "innocent.txt"
    link.symlink_to(hidden_dir / "notes.txt")
    big = tmp_path / "big.pdf"
    with big.open("wb") as fh:
        fh.truncate(26 * 1024 * 1024)
    for bad in (hidden_dir / "notes.txt", hidden_file, link, big, tmp_path / "missing.pdf", tmp_path / "x.exe", "/etc/passwd", "/etc/hosts.txt"):
        with pytest.raises(UiError):
            vet_form_path(str(bad))
