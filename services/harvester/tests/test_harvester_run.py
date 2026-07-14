"""Harvester entrypoint smoke (offline, MockFetcher) + generate/critique CLI."""

import io
import json
from contextlib import redirect_stderr, redirect_stdout

import argparse

from harvester.run import _collect_topics, main


def test_collect_topics_merges_and_dedups():
    ns = argparse.Namespace(topic=["algebra", "Biology"], topics="chemistry, biology , physics")
    assert _collect_topics(ns) == ["algebra", "Biology", "chemistry", "physics"]
    # single --topic still works; blank/None safe
    assert _collect_topics(argparse.Namespace(topic=["math"], topics=None)) == ["math"]
    assert _collect_topics(argparse.Namespace(topic=None, topics=None)) == []
    assert _collect_topics(argparse.Namespace(topic=None, topics="a,,b")) == ["a", "b"]

_SAMPLE = (
    "Introduction\nWelcome to algebra; we cover the core objectives.\n\n"
    "Example 1\nA worked example solving for x.\n\n"
    "Exercise\nPractice: solve the equation yourself.\n\n"
    "Summary\nIn summary, algebra solves for unknowns.\n"
)


def _run(argv):
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    with redirect_stdout(out_buf), redirect_stderr(err_buf):
        rc = main(argv)
    return rc, out_buf.getvalue(), err_buf.getvalue()


def test_run_once_ingests_seed_demo():
    rc, out, _err = _run(["--once"])
    assert rc == 0
    data = json.loads(out.strip().splitlines()[-1])
    assert data["ingested"] >= 2
    assert data["catalog_size"] >= 2


def test_generate_from_text_file(tmp_path):
    src = tmp_path / "algebra.txt"
    src.write_text(_SAMPLE, encoding="utf-8")
    out_dir = tmp_path / "out"
    rc, _out, _err = _run(["--generate", str(src), "--subject", "math",
                           "--core", "--access-tier", "free", "--out-dir", str(out_dir)])
    assert rc == 0
    course_json = next(out_dir.glob("*.course.json"))
    data = json.loads(course_json.read_text(encoding="utf-8"))
    assert data["subject"] == "math"
    assert 0 <= data["composition_score"] < 1000
    assert data["slides"]
    assert "core-fundamental" in data["tags"]["labels"]


def test_critique_from_text_file(tmp_path):
    src = tmp_path / "algebra.txt"
    src.write_text(_SAMPLE, encoding="utf-8")
    rc, out, _err = _run(["--critique", str(src), "--subject", "math",
                          "--out-dir", str(tmp_path / "out")])
    assert rc == 0
    report = json.loads(out)
    assert "grade" in report
    assert "issues" in report
    assert report["composition_score"] >= 0


def test_instructions_mode():
    rc, out, _err = _run(["--instructions"])
    assert rc == 0
    assert "HOW COURSE CONTENT IS GENERATED" in out
