"""Voice-training queue shared by the RAG lab and the CLI."""

from __future__ import annotations

import json
from pathlib import Path

from aoep_shared.cosyvoice_ingest.queue import (
    catalog_summary,
    discover_jobs,
    execute_queue,
    load_catalog,
    request_stop,
)


def _tree(tmp_path: Path) -> dict[str, Path]:
    urls = tmp_path / "urls"
    es = urls / "cosyvoice_es"
    fr = urls / "cosyvoice_fr"
    es.mkdir(parents=True)
    fr.mkdir(parents=True)
    (es / "lesson.txt").write_text(
        "https://www.youtube.com/watch?v=aaaaaaaaaaa\n"
        "https://www.youtube.com/watch?v=bbbbbbbbbbb\n",
        encoding="utf-8",
    )
    (fr / "france24.txt").write_text(
        "https://www.youtube.com/watch?v=ccccccccccc\n",
        encoding="utf-8",
    )
    (urls / "cosyvoice_CORPUS_STATUS.txt").write_text(
        "  es          whisper=es    videos=  12  label=Spanish\n"
        "  fr          whisper=fr    videos=   3  label=French\n",
        encoding="utf-8",
    )
    catalog = {
        "pools": [
            {"pool_id": "es", "whisper": "es", "label": "Spanish"},
            {"pool_id": "fr", "whisper": "fr", "label": "French"},
        ]
    }
    catalog_path = urls / "channels.json"
    catalog_path.write_text(json.dumps(catalog), encoding="utf-8")
    return {"urls": urls, "catalog": catalog_path, "output": tmp_path / "output"}


def test_catalog_reads_status_file_counts(tmp_path: Path):
    paths = _tree(tmp_path)
    summary = catalog_summary(paths["catalog"], paths["urls"], paths["output"])
    by_id = {pool["pool_id"]: pool for pool in summary["pools"]}
    assert by_id["es"]["videos"] == 12
    assert by_id["es"]["channels"] == 1
    assert by_id["es"]["label"] == "Spanish"
    assert summary["total_videos"] == 15


def test_discover_skips_news_channels(tmp_path: Path):
    paths = _tree(tmp_path)
    jobs = discover_jobs(
        load_catalog(paths["catalog"]),
        urls_root=paths["urls"],
        output_root=paths["output"],
        pools=None,
        skip_news=True,
        min_videos=1,
    )
    assert [job.slug for job in jobs] == ["lesson"]
    assert jobs[0].video_count == 2
    assert jobs[0].whisper == "es"


def test_execute_queue_uses_injected_runner_and_stop_file(tmp_path: Path):
    paths = _tree(tmp_path)
    calls: list[str] = []

    def fake(job, max_urls, repo, script):
        calls.append(job.slug)
        request_stop(paths["output"])
        return {
            "pool_id": job.pool_id,
            "slug": job.slug,
            "videos": job.video_count,
            "returncode": 0,
            "elapsed_s": 0,
        }

    code = execute_queue(
        catalog_path=paths["catalog"],
        urls_root=paths["urls"],
        output_root=paths["output"],
        cosyvoice_repo=tmp_path,
        ingest_script=tmp_path / "missing.py",
        pools=None,
        workers=1,
        max_urls=1,
        max_channels=None,
        include_news=True,
        min_videos=1,
        run_channel=fake,
    )
    assert calls == ["france24"]
    assert code == 0
    status = json.loads(
        (paths["output"] / "cosyvoice_voice_queue_status.json").read_text(encoding="utf-8")
    )
    assert status["running"] is False
    assert status["stopped"] is True
    assert status["ok"] == 1
    assert status["queued"] == 2
