"""Khmer candidate scoring and the fine-tune script's keep-off-the-server rule."""

from pathlib import Path

from aoep_shared.cosyvoice_ingest.khmer_eval import (
    candidate_beats_baseline,
    character_error_rate,
    choose_prompts,
    choose_sample_utts,
    metric_summary,
)
from aoep_shared.cosyvoice_ingest.spark_manifest import patch_sft_yaml


def test_cer_ignores_space_and_counts_latin():
    assert character_error_rate("ក ខ។", "កខ") == 0.0
    rate = character_error_rate("កខ", "hello")
    assert rate > 1.0


def test_metric_summary_skips_failed_rows():
    summary = metric_summary(
        [
            {"ok": True, "cer": 0.2, "speaker_similarity": 0.8},
            {"ok": False, "cer": None, "speaker_similarity": None},
            {"ok": True, "cer": 0.4, "speaker_similarity": 0.6},
        ]
    )
    assert summary["scored"] == 2
    assert summary["attempts"] == 3
    assert summary["cer"] == 0.3
    assert summary["speaker_similarity"] == 0.7


def test_clear_cer_drop_is_a_metric_win_and_serving_stays():
    decision = candidate_beats_baseline(
        {"cer": 0.50, "speaker_similarity": 0.70, "scored": 20},
        {"cer": 0.40, "speaker_similarity": 0.69, "scored": 20},
    )
    assert decision["wins"] is True
    assert decision["promote_serving"] is False
    assert decision["serving_config"] == "unchanged"
    assert decision["reasons"] == []


def test_unintelligible_cer_is_not_a_clear_win():
    decision = candidate_beats_baseline(
        {"cer": 1.0986, "speaker_similarity": 0.1997, "scored": 64},
        {"cer": 1.0296, "speaker_similarity": 0.1842, "scored": 64},
    )
    assert decision["wins"] is False
    assert "cer_still_high" in decision["reasons"]
    assert decision["serving_config"] == "unchanged"


def test_tiny_cer_drop_does_not_win():
    decision = candidate_beats_baseline(
        {"cer": 0.40, "speaker_similarity": 0.70, "scored": 20},
        {"cer": 0.39, "speaker_similarity": 0.90, "scored": 20},
    )
    assert decision["wins"] is False
    assert "cer_margin" in decision["reasons"]


def test_similarity_drop_blocks_a_cer_win():
    decision = candidate_beats_baseline(
        {"cer": 0.50, "speaker_similarity": 0.80, "scored": 12},
        {"cer": 0.30, "speaker_similarity": 0.70, "scored": 12},
    )
    assert decision["wins"] is False
    assert "similarity_drop" in decision["reasons"]


def test_prompts_stay_on_the_same_speaker_and_off_the_target():
    train = ["a1", "a2", "b1"]
    holdout = ["a3", "b2"]
    speakers = {"a1": "a", "a2": "a", "a3": "a", "b1": "b", "b2": "b"}
    durations = {utt: 5.0 for utt in speakers}
    pairs = choose_prompts(train, holdout, speakers, durations, seed=3)
    by_utt = {pair["utt"]: pair for pair in pairs}
    assert by_utt["a3"]["prompt_utt"] in {"a1", "a2"}
    assert by_utt["b2"]["prompt_utt"] == "b1"
    assert by_utt["a3"]["prompt_utt"] != "a3"


def test_samples_cover_each_speaker_before_filling():
    pairs = [
        {"utt": "a1", "speaker": "fleurs"},
        {"utt": "a2", "speaker": "fleurs"},
        {"utt": "b1", "speaker": "lesson"},
        {"utt": "c1", "speaker": "story"},
    ]
    chosen = choose_sample_utts(pairs, limit=3, seed=1)
    assert len(chosen) == 3
    assert len({pair["speaker"] for pair in pairs if pair["utt"] in chosen}) == 3


def test_khmer_yaml_raises_the_text_token_cap():
    patched = patch_sft_yaml(
        "language: 'en'\ntoken_max_length: 200\n",
        language="km",
        token_max_length=700,
    )
    assert "token_max_length: 700" in patched
    assert "language: 'km'" in patched


def test_khmer_finetune_script_leaves_the_live_server_alone():
    script = Path(__file__).resolve().parents[3] / "scripts" / "spark_cosyvoice_khmer_finetune.sh"
    text = script.read_text(encoding="utf-8")
    assert "flock" in text
    assert ".gs-gpu.lock" in text
    assert "Salane skipped" in text
    assert "serving config unchanged" in text
    assert "cp " not in text
    assert "rsync" not in text
    assert "pretrained_models/CosyVoice-300M-SFT" not in text
    assert "output/spark/cosyvoice-khmer" in text
    assert "token_max_length=700" in text
