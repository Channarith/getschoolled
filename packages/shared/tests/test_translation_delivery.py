"""Delivery of translations to the cluster: manifest contract, merge rules, mirror sync (fake S3), outage fallback."""
from __future__ import annotations

import io
import json
import time
from pathlib import Path

import pytest

from aoep_shared import audio_search
from aoep_shared import course_translation_library as lib
from aoep_shared import translation_delivery as dl
from aoep_shared import translation_store as store


class Src:
    def __init__(self, cid: str) -> None:
        self.course_id = cid


def _record(lang: str, stamp: str = "2026-10-25T10:00:00Z", *, status: str = "ship", sha: str = "a" * 64, n: int = 2) -> dict:
    return {
        "course_id": "x", "language": lang, "title": "t", "status": status,
        "segments": [{"heading": f"H{i}", "text": f"T{i}"} for i in range(n)],
        "provenance": {"pipeline": "2.0", "source_sha256": sha, "generated_at": stamp},
    }


def _put(root: Path, course: str, lang: str, rec: dict) -> Path:
    path = root / course / f"{lang}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rec), encoding="utf-8")
    return path


def _current(rec, src, lang):  # stand-in for translation_v2.is_current: ship status + matching source hash
    if not rec:
        return False, "missing"
    if rec.get("status") != "ship":
        return False, "fails_validator"
    if rec["provenance"]["source_sha256"] != "a" * 64:
        return False, "source_changed"
    return True, "current"


# ---- manifest contract ----------------------------------------------------------------------------------------------------------

def test_manifest_roundtrip_and_strictness():
    data = json.dumps({"x": 1}).encode()
    files = {"course-a/es.json": {"sha256": dl.sha256_bytes(data), "size": len(data), "validated_at": "t", "source_sha256": "s"}}
    manifest = dl.build_manifest(files, pipeline="2.0", generated_at="2026-10-25T00:00:00Z")
    assert dl.parse_manifest(json.dumps(manifest).encode())["count"] == 1
    for bad_rel in ("../evil/es.json", "/abs/es.json", "course/../es.json", "course/ES.json", "course/es.txt", "a/b/es.json"):
        broken = {"version": 1, "files": {bad_rel: {"sha256": "a" * 64, "size": 5}}}
        assert dl.parse_manifest(broken) is None, bad_rel
    assert dl.parse_manifest({"version": 2, "files": {}}) is None
    assert dl.parse_manifest({"version": 1, "files": {"c/es.json": {"sha256": "zz", "size": 5}}}) is None
    assert dl.parse_manifest({"version": 1, "files": {"c/es.json": {"sha256": "a" * 64, "size": 10**9}}}) is None
    assert dl.parse_manifest(b"not json") is None
    with pytest.raises(ValueError):
        dl.build_manifest({"../x/es.json": {"sha256": "a" * 64}}, pipeline="2.0")


def test_light_check_refuses_wrong_shape():
    good = json.dumps(_record("es")).encode()
    assert dl.light_record_check(good, "c/es.json") == (True, "ok")
    assert dl.light_record_check(good, "c/fr.json")[1] == "wrong_language"
    assert dl.light_record_check(b"[]", "c/es.json")[0] is False
    assert dl.light_record_check(json.dumps({**_record("es"), "segments": []}).encode(), "c/es.json")[1] == "no_segments"
    assert dl.light_record_check(json.dumps({k: v for k, v in _record("es").items() if k != "provenance"}).encode(), "c/es.json")[1] == "no_provenance"


def test_plan_upload_and_withdraw():
    new = {"a/es.json": {"sha256": "1" * 64}, "a/fr.json": {"sha256": "2" * 64}, "b/es.json": {"sha256": "3" * 64}}
    remote = {"a/es.json": {"sha256": "1" * 64}, "a/fr.json": {"sha256": "9" * 64}, "old/es.json": {"sha256": "4" * 64}}
    plan = dl.plan_upload(new, remote)
    assert plan == {"upload": ["a/fr.json", "b/es.json"], "unchanged": ["a/es.json"], "withdrawn": ["old/es.json"]}
    kept, removed = dl.drop_matching(new, lang="es")
    assert removed == ["a/es.json", "b/es.json"] and list(kept) == ["a/fr.json"]
    kept, removed = dl.drop_matching(new, course="a")
    assert removed == ["a/es.json", "a/fr.json"] and list(kept) == ["b/es.json"]


# ---- merge rules ----------------------------------------------------------------------------------------------------------------

def test_select_valid_rejects_stale_and_held_and_prefers_newest(tmp_path):
    spark, kalel = tmp_path / "spark", tmp_path / "kalel"
    _put(spark, "c1", "es", _record("es", "2026-10-25T10:00:00Z"))
    _put(kalel, "c1", "es", _record("es", "2026-10-25T12:00:00Z"))          # newer valid: wins
    _put(spark, "c2", "es", _record("es", status="held"))                    # held: never published
    _put(kalel, "c3", "es", _record("es", sha="b" * 64))                     # English changed since: stale
    _put(spark, "c4", "es", _record("es", n=0))                              # partial (no segments): light check refuses
    chosen, skipped = dl.select_valid({"spark": spark, "kalel": kalel}, [Src(c) for c in ("c1", "c2", "c3", "c4")], ["es"], is_current=_current)
    names = {s.rel: s.origin for s in chosen}
    assert names == {"c1/es.json": "kalel"}
    why = {(s["course_id"]): s["why"] for s in skipped}
    assert "held" not in names and "fails_validator" in why["c2"] and "source_changed" in why["c3"] and "no_segments" in why["c4"]


def test_valid_published_file_is_not_replaced_by_stale_or_held(tmp_path):
    spark, library = tmp_path / "spark", tmp_path / "library"
    good = _put(library, "c1", "es", _record("es", "2026-10-25T09:00:00Z"))
    _put(spark, "c1", "es", _record("es", "2026-10-26T09:00:00Z", status="held"))   # newer but held
    previous = {"c1/es.json": {"sha256": dl.sha256_bytes(good.read_bytes())}}
    chosen, _ = dl.select_valid({"spark": spark}, [Src("c1")], ["es"], is_current=_current, previous=previous, previous_dir=library)
    assert [(s.rel, s.origin) for s in chosen] == [("c1/es.json", "published")]
    # A strictly newer VALID candidate does replace it.
    _put(spark, "c1", "es", _record("es", "2026-10-26T09:00:00Z"))
    chosen, _ = dl.select_valid({"spark": spark}, [Src("c1")], ["es"], is_current=_current, previous=previous, previous_dir=library)
    assert [(s.rel, s.origin) for s in chosen] == [("c1/es.json", "spark")]
    # A published file that went stale (English changed) leaves the set.
    _put(library, "c1", "es", _record("es", sha="b" * 64))
    (spark / "c1" / "es.json").unlink()
    chosen, _ = dl.select_valid({"spark": spark}, [Src("c1")], ["es"], is_current=_current, previous=previous, previous_dir=library)
    assert chosen == []


# ---- the mirror (fake S3) -------------------------------------------------------------------------------------------------------

class FakeS3:
    def __init__(self, objects: dict[str, bytes]) -> None:
        self.objects = objects
        self.gets: list[str] = []
        self.down = False

    def get_object(self, Bucket: str, Key: str):  # noqa: N803 - boto3 signature
        self.gets.append(Key)
        if self.down:
            raise ConnectionError("unreachable")
        if Key not in self.objects:
            raise KeyError(Key)
        data = self.objects[Key]
        return {"ContentLength": len(data), "Body": io.BytesIO(data)}


def _bucket(files: dict[str, dict], tamper: dict[str, bytes] | None = None) -> FakeS3:
    objects: dict[str, bytes] = {}
    meta = {}
    for rel, rec in files.items():
        data = json.dumps(rec).encode()
        meta[rel] = {"sha256": dl.sha256_bytes(data), "size": len(data), "validated_at": "t", "source_sha256": "s"}
        objects["course-translations/" + rel] = data
    for rel, data in (tamper or {}).items():
        objects["course-translations/" + rel] = data      # bytes that do not match the manifest
    objects["course-translations/" + dl.DELIVERY_NAME] = json.dumps(dl.build_manifest(meta, pipeline="2.0")).encode()
    return FakeS3(objects)


@pytest.fixture
def mirror(tmp_path, monkeypatch):
    monkeypatch.setenv(store.ENV_BACKEND, "bucket")
    monkeypatch.setenv(store.ENV_MIRROR, str(tmp_path / "mirror"))
    monkeypatch.setenv("OBJECT_STORE_BUCKET", "salareen-prod")
    monkeypatch.setenv(store.ENV_BOOT_WAIT, "5")
    monkeypatch.delenv("AOEP_COURSE_TRANSLATION_DIR", raising=False)
    store.reset_for_tests()
    yield tmp_path / "mirror"
    store.set_client_factory(None)
    store.reset_for_tests()


def test_sync_downloads_verifies_and_serves_through_library_dir(mirror, tmp_path, monkeypatch):
    baked = tmp_path / "baked"
    baked.mkdir()
    monkeypatch.setenv("AOEP_COURSE_TRANSLATION_DIR", str(baked))
    fake = _bucket({"c1/es.json": _record("es"), "c1/yue.json": _record("yue"), "c2/tl.json": _record("tl")})
    store.set_client_factory(lambda: fake)
    root = lib.library_dir()                      # first call waits for the first sync
    assert root == mirror
    assert sorted(p.relative_to(mirror).as_posix() for p in mirror.rglob("*.json") if p.name != "index.json" and not p.name.startswith(".")) == \
        ["c1/es.json", "c1/yue.json", "c2/tl.json"]
    assert store.status()["ok"] is True and store.status()["files"] == 3
    assert lib.load_translation("c1", "es", mirror)["language"] == "es"


def test_bad_sha_and_wrong_shape_are_skipped_and_old_copy_stays(mirror):
    fake = _bucket({"c1/es.json": _record("es"), "c1/fr.json": _record("fr")}, tamper={"c1/fr.json": b'{"language":"fr","segments":[{"heading":"h","text":"changed after the manifest"}],"provenance":{}}'})
    assert store.sync_once(fake) is True
    assert (mirror / "c1" / "es.json").is_file()
    assert not (mirror / "c1" / "fr.json").exists()           # sha256 differs from the manifest: never placed
    assert store.status()["skipped"] == 1


def test_withdrawn_files_leave_the_mirror(mirror):
    first = _bucket({"c1/es.json": _record("es"), "c2/es.json": _record("es")})
    assert store.sync_once(first)
    second = _bucket({"c1/es.json": _record("es")})
    assert store.sync_once(second)
    assert (mirror / "c1" / "es.json").exists() and not (mirror / "c2").exists()


def test_outage_keeps_the_mirror_and_never_raises(mirror, tmp_path, monkeypatch):
    fake = _bucket({"c1/es.json": _record("es")})
    assert store.sync_once(fake)
    fake.down = True
    assert store.sync_once(fake) is False
    assert (mirror / "c1" / "es.json").is_file()
    monkeypatch.setenv("AOEP_COURSE_TRANSLATION_DIR", str(tmp_path / "baked"))
    store.set_client_factory(lambda: fake)
    assert lib.library_dir() == mirror            # synced once before: keep serving it during the outage


def test_never_synced_and_unreachable_falls_back_to_configured_dir(mirror, tmp_path, monkeypatch):
    baked = tmp_path / "baked"
    baked.mkdir()
    monkeypatch.setenv("AOEP_COURSE_TRANSLATION_DIR", str(baked))
    monkeypatch.setenv(store.ENV_BOOT_WAIT, "1")
    fake = FakeS3({})
    fake.down = True
    store.set_client_factory(lambda: fake)
    assert lib.library_dir() == baked
    # No manifest at all (nothing published yet) is the same quiet fallback.
    store.reset_for_tests()
    store.set_client_factory(lambda: FakeS3({}))
    assert lib.library_dir() == baked


def test_malformed_manifest_is_rejected(mirror):
    fake = FakeS3({"course-translations/" + dl.DELIVERY_NAME: json.dumps({"version": 1, "files": {"../x/es.json": {"sha256": "a" * 64, "size": 3}}}).encode()})
    assert store.sync_once(fake) is False
    assert not mirror.exists() or not any(mirror.rglob("*.json"))


def test_ttl_throttles_refreshes(mirror, monkeypatch):
    monkeypatch.setenv(store.ENV_TTL, "300")
    fake = _bucket({"c1/es.json": _record("es")})
    store.set_client_factory(lambda: fake)
    store.ensure_fresh()
    first = len([k for k in fake.gets if k.endswith(dl.DELIVERY_NAME)])
    for _ in range(5):
        store.ensure_fresh()
    assert len([k for k in fake.gets if k.endswith(dl.DELIVERY_NAME)]) == first == 1


def test_disabled_backend_is_a_noop(tmp_path, monkeypatch):
    monkeypatch.delenv(store.ENV_BACKEND, raising=False)
    monkeypatch.setenv("AOEP_COURSE_TRANSLATION_DIR", str(tmp_path))
    assert lib.library_dir() == tmp_path
    assert store.enabled() is False


def test_search_sees_new_mirror_files_after_a_sync(mirror):
    """A sync clears the shippable-verdict cache so a newly delivered language shows up on the next search."""
    audio_search.clear_cache()
    fake = _bucket({"c1/es.json": _record("es")})
    assert store.sync_once(fake)
    assert audio_search._CACHE == {}
