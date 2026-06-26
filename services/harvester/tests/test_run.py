"""Harvester entrypoint smoke (offline, MockFetcher) + generate/critique CLI."""

import io
import json
from contextlib import redirect_stdout

from harvester.run import main

_SAMPLE = (
    "Introduction\nWelcome to algebra; we cover the core objectives.\n\n"
    "Example 1\nA worked example solving for x.\n\n"
    "Exercise\nPractice: solve the equation yourself.\n\n"
    "Summary\nIn summary, algebra solves for unknowns.\n"
)


def _run(argv):
    buf = io.StringIO()
    with redirect_stdout(buf):
        rc = main(argv)
    return rc, buf.getvalue()


def test_run_once_ingests_seed_demo():
    rc, out = _run(["--once"])
    assert rc == 0
    data = json.loads(out.strip().splitlines()[-1])
    assert data["ingested"] >= 2
    assert data["catalog_size"] >= 2


def test_generate_from_text_file(tmp_path):
    src = tmp_path / "algebra.txt"
    src.write_text(_SAMPLE, encoding="utf-8")
    rc, out = _run(["--generate", str(src), "--subject", "math",
                    "--core", "--access-tier", "free"])
    assert rc == 0
    data = json.loads(out)
    assert data["subject"] == "math"
    assert 0 <= data["composition_score"] < 1000
    assert data["slides"]
    assert "core-fundamental" in data["tags"]["labels"]


def test_critique_from_text_file(tmp_path):
    src = tmp_path / "algebra.txt"
    src.write_text(_SAMPLE, encoding="utf-8")
    rc, out = _run(["--critique", str(src), "--subject", "math"])
    assert rc == 0
    report = json.loads(out)
    assert "grade" in report
    assert "issues" in report
    assert report["composition_score"] >= 0


def test_instructions_mode():
    rc, out = _run(["--instructions"])
    assert rc == 0
    assert "HOW COURSE CONTENT IS GENERATED" in out
