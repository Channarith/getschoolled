import json
import os
import re
import stat
from pathlib import Path

import pytest

from tts_bakeoff.demo_voice import assets as A

TOKEN_A, TOKEN_S = "AKIATESTTOKEN0000", "sEcReTtEsTtOkEn1111"
REPO = Path(__file__).resolve().parents[2]


def settings(**env):
    base = {"VOICE_ASSETS_ACCESS_KEY": TOKEN_A, "VOICE_ASSETS_SECRET_KEY": TOKEN_S}
    return A.load_settings({**base, **env}, env_file=Path("/nonexistent"))


def make_assets(tmp_path, active=True):
    (tmp_path / "channarith" / "en").mkdir(parents=True)
    (tmp_path / "channarith" / "en" / "0123456789abcd.mp3").write_bytes(b"x" * 10)
    (tmp_path / "channarith" / "en" / "0123456789abcd.json").write_text("{}")
    (tmp_path / "channarith" / "index.json").write_text(json.dumps({"ext": "mp3", "clips": {"en": ["0123456789abcd"]}}))
    (tmp_path / "voices.json").write_text(json.dumps({"voices": [{"id": "channarith", "active": active}]}))
    return tmp_path


@pytest.fixture(autouse=True)
def no_network_sanity_check(monkeypatch):
    """cmd_sync compares with the published list over the network: nothing published, in these tests."""
    monkeypatch.setattr(A, "remote_state", lambda s: (None, {}))


@pytest.fixture
def fake_aws(tmp_path, monkeypatch):
    """An `aws` on PATH that records argv and whether the key reached its environment (never the value)."""
    bindir, log = tmp_path / "bin", tmp_path / "aws.log"
    bindir.mkdir()
    shim = bindir / "aws"
    shim.write_text(f'#!/usr/bin/env bash\nprintf "%s\\n" "$*" >> {log}\n'
                    f'[ "${{AWS_ACCESS_KEY_ID:-}}" = "{TOKEN_A}" ] && echo KEYPRESENT >> {log}\n'
                    'if [ "$4" = "cp" ] && [ "$6" = "-" ]; then cat "$AWS_FAKE_VOICES"; fi\n')
    shim.chmod(shim.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    for k in ("VOICE_ASSETS_ACCESS_KEY", "VOICE_ASSETS_SECRET_KEY", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("VOICE_ASSETS_ACCESS_KEY", TOKEN_A)
    monkeypatch.setenv("VOICE_ASSETS_SECRET_KEY", TOKEN_S)
    return log


def test_defaults_match_the_release_bucket_and_public_url():
    s = A.load_settings({}, env_file=Path("/nonexistent"))
    assert (s.endpoint, s.bucket, s.prefix) == ("https://sjc1.vultrobjects.com", "salareen-prod", "voice-assets")
    assert s.public_base == "https://salareen-prod.sjc1.vultrobjects.com"
    assert s.s3 == "s3://salareen-prod/voice-assets"


def test_endpoint_must_be_https_and_bucket_sane():
    with pytest.raises(SystemExit):
        A.load_settings({"VOICE_ASSETS_ENDPOINT": "http://sjc1.vultrobjects.com"}, env_file=Path("/nonexistent"))
    with pytest.raises(SystemExit):
        A.load_settings({"VOICE_ASSETS_BUCKET": "bad bucket;rm"}, env_file=Path("/nonexistent"))


def test_credentials_prefer_voice_assets_then_aws_then_object_store_and_read_only_those_keys(tmp_path):
    f = tmp_path / "local.env"
    f.write_text("OPENAI_API_KEY=sk-should-not-be-read\nexport OBJECT_STORE_ACCESS_KEY='fileA'\nOBJECT_STORE_SECRET_KEY=\"fileS\"\n")
    s = A.load_settings({}, env_file=f)
    assert s.creds == {"AWS_ACCESS_KEY_ID": "fileA", "AWS_SECRET_ACCESS_KEY": "fileS"}
    assert "config/local.env" in s.cred_source and "fileA" not in s.cred_source
    s = A.load_settings({"AWS_ACCESS_KEY_ID": "e1", "AWS_SECRET_ACCESS_KEY": "e2"}, env_file=f)
    assert s.creds["AWS_ACCESS_KEY_ID"] == "e1"
    assert A.read_env_file(f, {"OBJECT_STORE_ACCESS_KEY"}) == {"OBJECT_STORE_ACCESS_KEY": "fileA"}
    assert TOKEN_S not in repr(settings())   # creds are excluded from repr


def test_sync_plan_order_headers_and_acl(tmp_path):
    cmds = A.plan_sync(make_assets(tmp_path), settings())
    assert [c[1] for c in cmds] == ["sync", "cp", "cp"]
    clips, index, voices = cmds
    assert clips[clips.index("--cache-control") + 1] == "public, max-age=31536000, immutable"
    assert clips[clips.index("--content-type") + 1] == "audio/mpeg" and "--include" in clips and "channarith/*.mp3" in clips
    assert "--delete" not in clips and clips[clips.index("--acl") + 1] == "public-read"
    assert index[3].endswith("/channarith/index.json") and voices[3].endswith("/voice-assets/voices.json")   # voices.json is last
    for c in (index, voices):
        assert c[c.index("--cache-control") + 1] == "public, max-age=300" and "application/json" in c and "public-read" in c
    assert "--delete" in A.plan_sync(tmp_path, settings(), delete_missing=True)[0]


def test_sync_skips_inactive_voices_and_requires_voices_json(tmp_path):
    cmds = A.plan_sync(make_assets(tmp_path, active=False), settings())
    assert [c[1] for c in cmds] == ["sync", "cp"]
    with pytest.raises(SystemExit):
        A.plan_sync(tmp_path / "empty", settings())


def test_dry_run_runs_no_aws_and_prints_no_secrets(tmp_path, fake_aws, capsys):
    root = make_assets(tmp_path / "a")
    assert A.main(["sync", "--assets", str(root), "--dry-run"]) == 0
    out = capsys.readouterr().out
    assert not fake_aws.exists() and "dry run" in out and TOKEN_A not in out and TOKEN_S not in out and "--endpoint-url" in out


def test_real_sync_passes_credentials_by_environment_not_argv(tmp_path, fake_aws, capsys):
    root = make_assets(tmp_path / "a")
    assert A.main(["sync", "--assets", str(root)]) == 0
    log = fake_aws.read_text()
    assert TOKEN_A not in log.replace("KEYPRESENT", "") and TOKEN_S not in log
    assert log.count("KEYPRESENT") == 3 and log.strip().splitlines()[0].startswith("--endpoint-url https://sjc1.vultrobjects.com s3 sync")
    assert TOKEN_S not in capsys.readouterr().out


def test_withdraw_validates_speaker_and_needs_yes(tmp_path, fake_aws, capsys):
    for bad in ("", "../x", "a b", "voices.json", "UP"):
        with pytest.raises(SystemExit):
            A.main(["withdraw", "--speaker", bad])
    assert A.main(["withdraw", "--speaker", "channarith"]) == 0     # no --yes: plan only
    assert not fake_aws.exists() and "--yes" in capsys.readouterr().out


def test_withdraw_deactivates_first_then_deletes(tmp_path, fake_aws, monkeypatch):
    remote = tmp_path / "remote.json"
    remote.write_text(json.dumps({"voices": [{"id": "channarith", "active": True}, {"id": "other", "active": True}]}))
    monkeypatch.setenv("AWS_FAKE_VOICES", str(remote))
    uploaded = {}
    real = A.run_aws

    def spy(s, *args, capture=False):
        if args[:2] == ("s3", "cp") and args[2].endswith(".json") and args[3].endswith("voices.json"):
            uploaded.update(json.loads(Path(args[2]).read_text()))
        return real(s, *args, capture=capture)
    monkeypatch.setattr(A, "run_aws", spy)
    assert A.main(["withdraw", "--speaker", "channarith", "--yes"]) == 0
    assert [v["active"] for v in uploaded["voices"]] == [False, True]
    lines = [l for l in fake_aws.read_text().splitlines() if l.startswith("--endpoint-url")]
    assert [l.split()[3] for l in lines] == ["cp", "cp", "rm"] and lines[-1].endswith("s3://salareen-prod/voice-assets/channarith/ --recursive")


def test_cors_keeps_other_rules_and_replaces_ours():
    other = {"ID": "apk", "AllowedOrigins": ["*"], "AllowedMethods": ["GET"]}
    merged = A.merge_cors({"CORSRules": [other, {"ID": "voice-assets", "AllowedOrigins": ["https://old"]}]}, A.DEFAULT_ORIGINS)
    assert merged["CORSRules"][0] == other and len(merged["CORSRules"]) == 2
    mine = merged["CORSRules"][1]
    assert mine["AllowedOrigins"] == ["https://salareen.com", "https://www.salareen.com"] and mine["AllowedMethods"] == ["GET", "HEAD"]
    assert "Range" in mine["AllowedHeaders"] and "Cache-Control" in mine["AllowedHeaders"]   # fetch(cache:"no-store") adds it
    assert A.merge_cors(None, ["https://x"])["CORSRules"][0]["AllowedOrigins"] == ["https://x"]


def test_policy_is_prefix_scoped_and_merges():
    s = settings()
    doc = A.merge_policy({"Version": "2012-10-17", "Statement": [{"Sid": "keep", "Effect": "Deny"}]}, s)
    assert [x["Sid"] for x in doc["Statement"]] == ["keep", "VoiceAssetsPublicRead"]
    st = doc["Statement"][1]
    assert st["Resource"] == ["arn:aws:s3:::salareen-prod/voice-assets/*"] and st["Action"] == ["s3:GetObject"]
    assert [x["Sid"] for x in A.merge_policy(doc, s)["Statement"]] == ["keep", "VoiceAssetsPublicRead"]   # idempotent


def test_site_csp_does_not_block_the_bucket():
    """next.config.mjs only sets frame-ancestors today. If someone adds media-src/connect-src/default-src it must allow the bucket."""
    src = (REPO / "apps/web/next.config.mjs").read_text(encoding="utf-8")
    csp = re.search(r'key: "Content-Security-Policy", value: "([^"]*)"', src).group(1)
    for d in ("media-src", "connect-src", "default-src"):
        if d in csp:
            assert "vultrobjects.com" in csp.split(d)[1].split(";")[0], f"{d} must allow https://*.vultrobjects.com"


def test_clients_default_to_the_bucket_url():
    base = "https://salareen-prod.sjc1.vultrobjects.com/voice-assets"
    assert base in (REPO / "apps/mobile/src/cloneVoice.ts").read_text()
    assert base in (REPO / "apps/web/Dockerfile").read_text()
    assert base in (REPO / "subrepos/theodore_children_webcam_lab/src/theodore_children_webcam_lab/static/clone_voice.js").read_text()
