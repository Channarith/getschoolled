"""Spark CosyVoice manifest: passing reports, dedupe, Salane, one-epoch yaml."""

from __future__ import annotations

import json
import math
import struct
from pathlib import Path

from aoep_shared.cosyvoice_ingest.export import CosyVoiceUtterance, write_cosyvoice_recipe
from aoep_shared.cosyvoice_ingest.spark_manifest import (
    MEANINGFUL_MIN_SECONDS,
    MEANINGFUL_MIN_UTTERANCES,
    build_spark_manifests,
    is_salane_speaker,
    parse_cv_metrics,
    patch_sft_yaml,
    split_kaldi_holdout,
    training_decision,
)
from aoep_shared.dictionary_audio import write_wav_mono


def _tone(seconds: float = 0.2, hz: float = 220.0) -> bytes:
    sr = 24000
    n = int(seconds * sr)
    samples = [int(0.2 * 32767 * math.sin(2 * math.pi * hz * (i / sr))) for i in range(n)]
    return struct.pack("<" + "h" * n, *samples)


def _channel(root: Path, name: str, ok: bool, rows: list[tuple[str, bytes, str, str]], lang: str) -> None:
    channel = root / name
    utterances = []
    for utt_id, pcm, text, speaker in rows:
        wav = channel / "wavs" / f"{utt_id}.wav"
        wav.parent.mkdir(parents=True, exist_ok=True)
        write_wav_mono(wav, pcm, 24000)
        utterances.append(
            CosyVoiceUtterance(utt_id, str(wav.resolve()), text, speaker, language=lang)
        )
    recipe_parent = channel / "04_cosyvoice"
    write_cosyvoice_recipe(utterances, recipe_parent, language=lang, split_name="train")
    report = {
        "ok": ok,
        "utterances": len(rows),
        "recipe_dir": str((recipe_parent / "train").resolve()),
        "errors": ["do-not-copy-this-into-census"],
    }
    (channel / "report.json").write_text(json.dumps(report), encoding="utf-8")


def test_passing_merge_dedupes_and_keeps_failed_km_only_in_export(tmp_path: Path):
    scan = tmp_path / "output"
    same = _tone(0.25, 330.0)
    _channel(
        scan,
        "cosyvoice_km_ok",
        True,
        [("utt1", same, "សួស្តី", "km_a")],
        "km",
    )
    _channel(
        scan,
        "cosyvoice_km_mirror",
        True,
        [("utt9", same, "សួស្តី", "km_a")],
        "km",
    )
    _channel(
        scan,
        "cosyvoice_km_partial",
        False,
        [("utt3", _tone(0.25, 440.0), "ល្អ", "km_b")],
        "km",
    )
    _channel(
        scan,
        "cosyvoice_vi_ok",
        True,
        [("utt1", _tone(0.2, 500.0), "xin chao", "vi_a")],
        "vi",
    )
    _channel(
        scan,
        "cosyvoice_en_sala",
        True,
        [("utt1", _tone(0.2, 180.0), "hello sala", "sala")],
        "en",
    )
    merged = scan / "cosyvoice_km_merged"
    _channel(merged, "nested", True, [("utt1", _tone(), "nope", "km_a")], "km")
    # The helper nests under merged/nested. Also drop a merged report at the top.
    (scan / "cosyvoice_km_merged").mkdir(parents=True, exist_ok=True)
    (scan / "cosyvoice_km_merged" / "report.json").write_text(
        json.dumps({"ok": True, "utterances": 99, "errors": ["secret-ish"]}),
        encoding="utf-8",
    )

    voices = tmp_path / "voices" / "sala"
    voices.mkdir(parents=True)
    (voices / "ref.wav").write_bytes(b"RIFFstub")

    dest = tmp_path / "spark"
    census = build_spark_manifests(
        scan, dest, cosyvoice_repo=tmp_path / "CosyVoice", voices_root=tmp_path / "voices"
    )

    blob = json.dumps(census)
    assert "do-not-copy-this-into-census" not in blob
    assert "secret-ish" not in blob
    assert census["passing_channels"] == 4
    assert census["by_language"]["km"]["utterances"] == 1
    assert census["by_language"]["km"]["dropped_duplicate_audio"] == 1
    assert census["by_language"]["vi"]["utterances"] == 1
    assert census["km_exported"]["utterances"] == 2
    assert "cosyvoice_km_partial" in census["km_exported"]["channels"]
    assert "cosyvoice_km_merged" not in census["passing_channel_names"]
    handoff = Path(census["km_exported"]["train_handoff"])
    assert handoff.is_file()
    text = handoff.read_text(encoding="utf-8")
    assert "CosyVoice train handoff" in text
    assert "wav.scp" in text
    assert census["km_exported"]["audio_files_copied"] == 2
    copied = Path(census["km_exported"]["recipe"]).parent.parent / "audio"
    assert list(copied.glob("*.wav"))
    assert census["salane"]["training_utterances"] == 1
    assert census["salane"]["speakers"] == ["sala"]
    assert census["salane"]["voice_reference_files"] == 1
    assert census["decision"]["salane"]["run"] is False
    assert census["decision"]["km"]["meaningful"] is False
    assert census["decision"]["km"]["run"] is True
    # Scan root report bytes are unchanged.
    raw = (scan / "cosyvoice_km_ok" / "report.json").read_text(encoding="utf-8")
    assert "do-not-copy-this-into-census" in raw


def test_salane_id_and_training_floor():
    assert is_salane_speaker("sala")
    assert is_salane_speaker("salane_km")
    assert not is_salane_speaker("salareen")
    assert not is_salane_speaker("km_sala")
    small = training_decision("km", 10, 120.0)
    assert small["meaningful"] is False and small["run"] is True
    empty = training_decision("km", 0, 0.0)
    assert empty["run"] is False
    salane = training_decision("salane", 3, 40.0)
    assert salane["run"] is False
    enough = training_decision(
        "salane", MEANINGFUL_MIN_UTTERANCES, MEANINGFUL_MIN_SECONDS
    )
    assert enough["run"] is True and enough["meaningful"] is True


def test_holdout_and_yaml_and_cv_parse(tmp_path: Path):
    src = tmp_path / "train"
    src.mkdir()
    lines_wav = []
    lines_text = []
    lines_spk = []
    lines_lang = []
    for idx in range(10):
        utt = f"u{idx}"
        lines_wav.append(f"{utt} /tmp/{utt}.wav")
        lines_text.append(f"{utt} hello {idx}")
        lines_spk.append(f"{utt} spk")
        lines_lang.append(f"{utt} km")
    (src / "wav.scp").write_text("\n".join(lines_wav) + "\n", encoding="utf-8")
    (src / "text").write_text("\n".join(lines_text) + "\n", encoding="utf-8")
    (src / "utt2spk").write_text("\n".join(lines_spk) + "\n", encoding="utf-8")
    (src / "utt2lang").write_text("\n".join(lines_lang) + "\n", encoding="utf-8")
    split = split_kaldi_holdout(src, tmp_path / "tr", tmp_path / "dv", holdout=4, seed=17)
    assert split["held_out"] == 2
    assert split["train_utterances"] == 8
    assert split["dev_utterances"] == 2
    assert split["dev_is_copy_of_train"] is False

    yaml = "\n".join(
        [
            "    language: 'en'",
            "    use_spk_embedding: False # change to True during sft",
            "    lr: 0.001 # change to 1e-5 during sft",
            "    scheduler: warmuplr # change to constantlr during sft",
            "    max_epoch: 200",
            "    accum_grad: 2",
            "    log_interval: 100",
            "    max_epoch: 200",
        ]
    )
    patched = patch_sft_yaml(yaml, language="km", max_epoch=1)
    assert "language: 'km'" in patched
    assert "use_spk_embedding: True" in patched
    assert "lr: 0.00001" in patched
    assert "scheduler: constantlr" in patched
    assert "max_epoch: 1" in patched
    assert "max_epoch: 200" in patched  # gan block left alone
    assert "accum_grad: 1" in patched

    log = "Epoch 0 Step 1 CV info lr 1e-05 0 rank loss 2.5\n"
    rows = parse_cv_metrics(log)
    assert rows[0]["losses"]["loss"] == 2.5
    assert rows[0]["epoch"] == "0"


def test_finetune_script_stays_off_the_live_server():
    script = Path(__file__).resolve().parents[3] / "scripts" / "spark_cosyvoice_km_finetune.sh"
    text = script.read_text(encoding="utf-8")
    assert ".gs-gpu.lock" in text
    assert "flock" in text
    assert "promoted" in text
    assert "not promoted" in text
    assert "cp " not in text
    assert "rsync" not in text
    assert "pretrained_models/CosyVoice-300M" in text
    assert "--model_dir" in text
    assert "output/spark/cosyvoice" in text
