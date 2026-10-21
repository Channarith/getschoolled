from __future__ import annotations

import zipfile

import pytest

from aoep_shared.harvest import (
    CategoryBlueprint,
    SQLiteAcquisitionQueue,
    inspect_import,
    validate_rights,
)


def test_category_blueprint_enforces_program_course_bounds():
    assert CategoryBlueprint(slug="drivers-ed", title="Driver's education").max_courses == 60
    with pytest.raises(ValueError):
        CategoryBlueprint(slug="bad", title="Bad", min_courses=2, max_courses=61)


def test_rights_allow_open_or_explicit_owned_content(tmp_path):
    source = tmp_path / "owned.txt"
    source.write_text("Owned training material", encoding="utf-8")
    assert validate_rights(license="CC-BY", rights_assertion="")
    assert validate_rights(license="", rights_assertion="owned")
    asset = inspect_import(source, rights_assertion="owned")
    assert asset.byte_size > 0
    with pytest.raises(ValueError):
        inspect_import(source, rights_assertion="")


def test_queue_claims_once_per_category_and_retries(tmp_path):
    queue = SQLiteAcquisitionQueue(tmp_path / "jobs.db")
    payload = {"source_uri": "file:///training.pdf", "sha256": "abc"}
    assert queue.enqueue(category_slug="drivers-ed", payload=payload)
    assert not queue.enqueue(category_slug="drivers-ed", payload=payload)
    assert queue.claim_next(worker_id="biology-worker", category_slug="biology") is None
    job = queue.claim_next(worker_id="driver-worker", category_slug="drivers-ed")
    assert job is not None
    queue.fail(job, error="temporary", retry_delay_s=0)
    retry = queue.claim_next(worker_id="driver-worker", category_slug="drivers-ed")
    assert retry is not None
    assert retry.attempts == 2
    queue.finish(retry, result={"course_ids": ["course-1"]})
    assert queue.claim_next(worker_id="driver-worker", category_slug="drivers-ed") is None


def test_import_rejects_unsafe_archive_member(tmp_path):
    archive = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive, "w") as out:
        out.writestr("../escape.txt", "not safe")
    from aoep_shared.harvest.acquisition import iter_import_files

    with pytest.raises(ValueError, match="unsafe"):
        list(iter_import_files(archive))
