"""Khmer / Salane voice-data source selection and transcript checks."""

from __future__ import annotations

import wave
from pathlib import Path

from aoep_shared.cosyvoice_ingest.licensed import index_wavs, pair_fleurs_rows, parse_fleurs_tsv
from aoep_shared.cosyvoice_ingest.local_pool import select_local_khmer
from aoep_shared.cosyvoice_ingest.quality import transcript_reject_reason
from aoep_shared.dictionary_audio import write_wav_mono


def _wav(path: Path, seconds: float = 0.2) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = int(24000 * seconds)
    write_wav_mono(path, b"\x00\x10" * n, 24000)


def test_khmer_transcript_rules():
    assert transcript_reject_reason("hello world", "km") == "few_khmer_chars"
    assert transcript_reject_reason("hello សួស្តី there friend", "km") == "not_mostly_khmer"
    assert transcript_reject_reason("សួស្តី​អ្នកទាំងអស់គ្នា", "km") == ""
    assert transcript_reject_reason("hello world", "en") == ""
    repeated = "ប្រាប់ " * 8
    assert transcript_reject_reason(repeated.strip(), "km") == "repetition"


def test_parse_fleurs_tsv_uses_normalized_text(tmp_path: Path):
    tsv = tmp_path / "dev.tsv"
    tsv.write_text(
        "1605\t1701.wav\traw line\tអត្ថបទស្អាត\tchars\t999\n"
        "\n"
        "bad-short\n",
        encoding="utf-8",
    )
    rows = parse_fleurs_tsv(tsv)
    assert len(rows) == 1
    assert rows[0]["filename"] == "1701.wav"
    assert rows[0]["text"] == "អត្ថបទស្អាត"
    assert rows[0]["raw_text"] == "raw line"
    wav = tmp_path / "nested" / "1701.wav"
    _wav(wav)
    paired, missing = pair_fleurs_rows(rows, index_wavs(tmp_path))
    assert missing == 0
    assert paired[0]["wav"] == wav


def test_select_local_khmer_dedupes_mirrors_and_caps_budget(tmp_path: Path):
    easy = tmp_path / "cosyvoice_km_easykhmer" / "01_raw"
    mirror = tmp_path / "cosyvoice_km_easykhmerofficial" / "01_raw"
    dance = tmp_path / "cosyvoice_km_traditional_dance_palelainea" / "01_raw"
    story = tmp_path / "cosyvoice_km_buddhist_stories_playlist" / "01_raw"
    _wav(easy / "src_aaa.wav", 2.0)
    _wav(mirror / "src_aaa.wav", 1.0)
    _wav(easy / "src_bbb.wav", 2.0)
    _wav(dance / "src_dance.wav", 5.0)
    _wav(story / "src_long.wav", 30.0)
    _wav(story / "src_also.wav", 40.0)
    rows = select_local_khmer(
        tmp_path,
        lesson_budget_sec=2.0,
        narration_head_sec=8.0,
        narration_files=1,
    )
    stems = [row["stem"] for row in rows]
    assert stems.count("src_aaa") == 1
    assert "src_dance" not in stems
    assert "src_bbb" not in stems  # budget filled by the 2s lesson clip
    narration = [row for row in rows if row["kind"] == "narration"]
    assert len(narration) == 1
    assert narration[0]["stem"] == "src_long"
    assert narration[0]["take_sec"] == 8.0
    # The helper really wrote a wav the selector can time.
    with wave.open(str(easy / "src_aaa.wav"), "rb") as handle:
        assert handle.getnframes() > 0
