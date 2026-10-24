import json
from pathlib import Path

from aoep_shared import mobile_release as mr


def make_repo(tmp_path, version="0.97.11", pkg=None, app=None, ts=None):
    (tmp_path / "apps/mobile/src").mkdir(parents=True)
    (tmp_path / "VERSION").write_text(version + "\n")
    (tmp_path / "apps/mobile/package.json").write_text(json.dumps({"version": pkg or version}))
    (tmp_path / "apps/mobile/app.json").write_text(json.dumps({"expo": {"version": app or version, "ios": {"buildNumber": version}}}))
    (tmp_path / "apps/mobile/src/version.ts").write_text(f'export const APP_VERSION = "{ts or version}";\nconst GENERATED_VERSION = "{ts or version}";\n')
    return tmp_path


def test_parity_ok(tmp_path):
    p = mr.check_parity(make_repo(tmp_path))
    assert p.ok and not p.problems


def test_parity_catches_each_drifting_file(tmp_path):
    p = mr.check_parity(make_repo(tmp_path, app="0.97.3", ts="0.97.10"))
    assert not p.ok
    assert any("app.json" in x for x in p.problems) and any("version.ts" in x for x in p.problems)


def test_repo_files_are_in_parity():
    repo = Path(__file__).resolve().parents[3]
    assert mr.check_parity(repo).ok, mr.check_parity(repo).problems


def test_version_only_edits_do_not_count_as_native_changes():
    old = json.dumps({"expo": {"version": "0.97.3", "ios": {"buildNumber": "0.97.3", "bundleIdentifier": "com.x"}, "android": {"versionCode": 1}}})
    bumped = json.dumps({"expo": {"version": "0.97.9", "ios": {"buildNumber": "0.97.9", "bundleIdentifier": "com.x"}, "android": {"versionCode": 2}}})
    assert not mr.native_config_changed(old, bumped, "app.json")
    permission = json.dumps({"expo": {"version": "0.97.9", "ios": {"buildNumber": "0.97.9", "bundleIdentifier": "com.x", "infoPlist": {"NSCameraUsageDescription": "hi"}}, "android": {"versionCode": 2}}})
    assert mr.native_config_changed(old, permission, "app.json")
    deps_old = json.dumps({"version": "1", "dependencies": {"a": "1"}})
    assert not mr.native_config_changed(deps_old, json.dumps({"version": "2", "dependencies": {"a": "1"}}), "package.json")
    assert mr.native_config_changed(deps_old, json.dumps({"version": "2", "dependencies": {"a": "2"}}), "package.json")


def test_changed_paths_are_tiered():
    k = mr.classify_changed_paths([
        "apps/mobile/src/api.ts", "apps/mobile/src/__tests__/x.test.ts", "apps/mobile/app.json", "apps/mobile/plugins/p.js",
        "apps/web/app/page.tsx", "apps/mobile/assets/a.png", "docs/a.txt",
    ])
    assert k["native"] == ["apps/mobile/app.json", "apps/mobile/plugins/p.js"]
    assert k["bundle"] == ["apps/mobile/src/api.ts", "apps/mobile/assets/a.png"]


def fake_git(tags, diff_files, blobs, main_version="0.97.11"):
    def run(args):
        if args[:1] == ["show"] and args[1] == "origin/main:VERSION":
            return main_version + "\n"
        if args[:1] == ["show"]:
            return blobs.get(args[1], "")
        if args[:2] == ["rev-parse", "--verify"]:
            return "abc\n" if args[-1] in tags else ""
        if args[:2] == ["tag", "--list"]:
            return "\n".join(tags) + "\n"
        if args[:1] == ["diff"]:
            return "\n".join(diff_files) + "\n"
        return ""
    return run


def test_staleness_counts_versions_and_native_commits(tmp_path):
    (tmp_path / "VERSION").write_text("0.97.11\n")
    tags = ["v0.97.3", "v0.97.4", "v0.97.5", "v0.97.11"]
    blobs = {
        "v0.97.3:apps/mobile/app.json": json.dumps({"expo": {"version": "0.97.3"}}),
        "origin/main:apps/mobile/app.json": json.dumps({"expo": {"version": "0.97.11"}}),
    }
    git = fake_git(tags, ["apps/mobile/app.json", "apps/mobile/src/a.ts", "apps/mobile/src/b.ts", "apps/mobile/src/__tests__/c.test.ts"], blobs)
    s = mr.staleness(tmp_path, "0.97.3", git=git)
    assert s.versions_behind == 3
    assert s.native_commits_behind == 0, "app.json only changed its version"
    assert s.bundle_commits_behind == 2
    assert s.needs_build
    assert "3 version(s) behind v0.97.11" in s.line()


def test_staleness_is_current_when_nothing_changed(tmp_path):
    (tmp_path / "VERSION").write_text("0.97.11\n")
    git = fake_git(["v0.97.11"], [], {})
    s = mr.staleness(tmp_path, "0.97.11", git=git)
    assert s.versions_behind == 0 and not s.needs_build
    assert "is current" in s.line()


def test_no_published_build_is_reported():
    s = mr.Staleness("", "0.97.11", 0, 0, 0)
    assert s.needs_build and "no published build" in s.line()


def test_release_pruning_keeps_the_newest():
    versions = ["0.97.3", "0.97.12", "0.97.2", "0.97.11", "0.97.4", "0.97.5", "0.96.0"]
    assert mr.versions_to_prune(versions, keep=5) == ["0.97.2", "0.96.0"]


def test_manifest_has_hash_and_filename(tmp_path):
    apk = tmp_path / "a.apk"
    apk.write_bytes(b"x" * 10)
    m = mr.build_manifest(version="0.97.12", version_code=9712, git_sha="abc", apk_url="https://h/x.apk", sha256=mr.sha256_file(apk), size=10, built_at="now")
    assert m["sha256"] == mr.sha256_file(apk) and m["filename"] == "salareen-0.97.12-9712-release.apk"


def test_update_decision_matches_the_app_rules():
    man = {"version": "0.97.12", "min_supported": "0.95.0"}
    assert mr.update_decision("0.97.3", man) == {"prompt": True, "force": False, "latest": "0.97.12"}
    assert mr.update_decision("0.97.3", man, dismissed="0.97.12")["prompt"] is False
    assert mr.update_decision("0.94.0", man, dismissed="0.97.12") == {"prompt": True, "force": True, "latest": "0.97.12"}
    assert mr.update_decision("0.97.12", man)["prompt"] is False
    assert mr.update_decision("0.97.3", None)["prompt"] is False
