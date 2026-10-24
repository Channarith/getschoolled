import csv
import json
import subprocess
import sys

import pytest

from tts_bakeoff import adapters, asr, panel, report, run_bakeoff, schema, score_bakeoff


@pytest.fixture(autouse=True)
def second_mock(monkeypatch):
    monkeypatch.setitem(adapters.REGISTRY, "mock_b", ("mock", "MockAdapter"))


def test_importing_the_harness_loads_no_heavy_dependency():
    code = ("import sys, tts_bakeoff.adapters, tts_bakeoff.run_bakeoff, tts_bakeoff.score_bakeoff, tts_bakeoff.report, tts_bakeoff.panel;"
            "bad=[m for m in ('torch','transformers','torchaudio','faster_whisper','voxcpm','kokoro','chatterbox','requests') if m in sys.modules];"
            "print(bad); sys.exit(1 if bad else 0)")
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert out.returncode == 0, out.stdout + out.stderr


def test_every_adapter_check_runs_without_the_model(monkeypatch):
    for name in adapters.REGISTRY:
        result = adapters.get(name).check()
        assert set(result) >= {"ok", "problems", "languages"}, name
    assert adapters.get("mock").check()["ok"] is True


def test_azure_check_reports_missing_credentials(monkeypatch):
    monkeypatch.delenv("AZURE_SPEECH_KEY", raising=False)
    monkeypatch.delenv("AZURE_SPEECH_REGION", raising=False)
    problems = adapters.get("azure").check()["problems"]
    assert any("AZURE_SPEECH_KEY" in p for p in problems)


def test_unsupported_language_is_refused(tmp_path):
    with pytest.raises(adapters.AdapterError):
        adapters.get("kokoro").synthesize("x", "km", tmp_path / "x.wav")


def test_run_is_resumable_and_writes_a_manifest(tmp_path):
    counts = run_bakeoff.run("mock", ["en", "km"], 3, tmp_path, {})
    assert counts["ok"] == 6 and counts["failed"] == 0
    again = run_bakeoff.run("mock", ["en", "km"], 3, tmp_path, {})
    assert again["ok"] == 0 and again["skipped"] == 6
    more = run_bakeoff.run("mock", ["en", "km"], 5, tmp_path, {})
    assert more["ok"] == 4 and more["skipped"] == 6
    rows = [json.loads(line) for line in (tmp_path / "mock" / "manifest.jsonl").read_text().splitlines()]
    assert len(rows) == 10 and all(r["status"] == "ok" and r["duration_s"] > 0 and r["rtf"] is not None for r in rows)
    assert (tmp_path / "mock" / "meta.json").exists() and (tmp_path / "mock" / "km" / "S01.wav").exists()


def test_failed_sentences_are_recorded_and_retried(tmp_path, monkeypatch):
    from tts_bakeoff.adapters.mock import MockAdapter

    calls = {"n": 0}
    real = MockAdapter._synth

    def flaky(self, text, lang, out):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("boom")
        return real(self, text, lang, out)

    monkeypatch.setattr(MockAdapter, "_synth", flaky)
    first = run_bakeoff.run("mock", ["en"], 3, tmp_path, {})
    assert first["failed"] == 1 and first["ok"] == 2
    second = run_bakeoff.run("mock", ["en"], 3, tmp_path, {})
    assert second["ok"] == 1 and second["failed"] == 0  # only the failed one was retried


def test_scoring_report_and_leaderboard(tmp_path):
    for model in ("mock", "mock_b"):
        run_bakeoff.run(model, ["en", "km"], 4, tmp_path, {})
    clean = asr.get("fake:0")
    noisy = asr.get("fake:0.4")
    assert score_bakeoff.score_model(tmp_path, "mock", clean)["scored"] == 8
    assert score_bakeoff.score_model(tmp_path, "mock_b", noisy)["scored"] == 8
    assert score_bakeoff.score_model(tmp_path, "mock", clean)["skipped"] == 8  # resumable
    table = report.summarize(report.load_scores(tmp_path), schema.candidates())
    assert set(table) == {"en", "km"}
    en = table["en"]
    assert [r["model"] for r in en] == ["mock", "mock_b"]  # lower error ranks first
    assert en[0]["mean_error"] == 0.0 and en[1]["mean_error"] > 0.2
    assert table["km"][0]["metric"] == "CER" and en[0]["metric"] == "WER"
    assert en[0]["license"] == "UNKNOWN"  # the mock is not in the matrix
    assert report.main(["--out", str(tmp_path)]) == 0
    html = (tmp_path / "leaderboard.html").read_text()
    assert "TTS bake-off leaderboard" in html and "km" in html
    rows = list(csv.DictReader((tmp_path / "leaderboard.csv").open()))
    assert {r["lang"] for r in rows} == {"en", "km"} and rows[0]["rank"] == "1"


def test_leaderboard_marks_non_shippable_models():
    cands = schema.candidates()
    row = {"lang": "en", "id": "S01", "model": "fish_speech15", "asr": "x", "error": {"metric": "wer", "value": 0.1, "digits_ignored": False}, "rtf": 0.5}
    table = report.summarize([row], cands)
    assert table["en"][0]["license"] == "NOT SHIPPABLE"
    assert "NOT SHIPPABLE" in report.render_html(table)


def test_blind_panel_hides_models_and_aggregates_ratings(tmp_path):
    for model in ("mock", "mock_b"):
        run_bakeoff.run(model, ["en"], 3, tmp_path, {})
    key = panel.build(tmp_path, ["en"], 3, seed=11)
    page = (tmp_path / "panel" / "panel_en.html").read_text()
    assert "mock_b" not in page and '"mock"' not in page  # nothing in the page reveals the model
    assert not any("mock" in p.name for p in (tmp_path / "panel" / "en").iterdir())
    mapping = key["panels"]["en-11"]
    assert set(mapping.values()) == {"mock", "mock_b"} and len(mapping) == 6
    again = panel.build(tmp_path, ["en"], 3, seed=11)
    assert again == key  # deterministic for a seed
    ratings = {"panel": "en-11", "lang": "en", "rater": "tester", "ratings": []}
    for slot, model in mapping.items():
        sid, label = slot.split(":")
        score = 5 if model == "mock" else 2
        ratings["ratings"].append({"id": sid, "label": label, "naturalness": score, "clarity": score})
    f = tmp_path / "r.json"
    f.write_text(json.dumps(ratings))
    rows = {r["model"]: r for r in panel.aggregate(tmp_path, [f])}
    assert rows["mock"]["naturalness"] == 5 and rows["mock_b"]["naturalness"] == 2 and rows["mock"]["raters"] == 1
    assert (tmp_path / "panel" / "panel_results.csv").exists()


def test_cli_end_to_end_on_the_mock(tmp_path):
    out = str(tmp_path / "run")
    assert run_bakeoff.main(["--model", "mock", "--langs", "en,vi", "--limit", "2", "--out", out]) == 0
    assert score_bakeoff.main(["--out", out, "--asr", "fake:0.1"]) == 0
    assert report.main(["--out", out]) == 0
    assert run_bakeoff.main(["--model", "mock", "--check"]) == 0
    assert run_bakeoff.main(["--model", "kokoro", "--check"]) == 1  # kokoro is not installed here
