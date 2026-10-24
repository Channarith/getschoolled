import json
import wave
from pathlib import Path

import pytest

from aoep_shared.cosyvoice_ingest.export import CosyVoiceUtterance, write_cosyvoice_recipe
from aoep_shared.voice_dataset import Allowlist, Filters, convert, discover_splits, wav_seconds


def make_wav(path: Path, seconds: float, rate: int = 16000) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(b"\x00\x00" * int(seconds * rate))


def build_channel(root: Path, channel: str, spk: str, rows, url_prefix="https://www.youtube.com/watch?v="):
    """Write one channel the way the real ingest does (via write_cosyvoice_recipe)."""
    base = root / f"cosyvoice_{channel}"
    utts = []
    for i, (seconds, text, snr) in enumerate(rows):
        wav = base / "03_segments" / f"{spk}_{i:03d}.wav"
        make_wav(wav, seconds)
        utts.append(CosyVoiceUtterance(
            utt_id=f"{spk}_{i:03d}", wav_path=str(wav), text=text, spk_id=spk, language="km",
            source_url=f"{url_prefix}vid{i}", duration_sec=seconds, snr_db=snr, asr_engine="mms",
        ))
    write_cosyvoice_recipe(utts, base / "04_cosyvoice", language="km")
    return base


ROWS = [
    (3.0, "សួស្តី នេះជាការសាកល្បង", 20.0),
    (0.4, "ខ្លី", 20.0),                      # too short
    (30.0, "វែងពេក " * 60, 20.0),              # too long
    (3.0, "សំឡេងរំខាន", 2.0),                  # low SNR
    (3.0, "សួស្តី នេះជាការសាកល្បង", 20.0),     # duplicate text
    (4.0, "ខ្ញុំរៀនភាសាខ្មែរ", 25.0),
    (3.0, "x" * 300, 20.0),                    # text far too long for 3 s
    (3.0, "", 20.0),                            # empty text (dropped by the exporter itself)
]


def test_reads_what_the_real_exporter_writes_and_filters(tmp_path):
    ch = build_channel(tmp_path, "km_easykhmer", "easykhmer", ROWS)
    out = tmp_path / "out"
    report = convert([ch], out, Filters(val_fraction=0), None, audio="link")
    assert report["clips_seen"] == 7  # the exporter drops the empty-text row
    assert report["clips_kept"] == 2
    assert report["rejected_by_reason"] == {
        "too_short": 1, "too_long": 1, "low_snr": 1, "duplicate_text": 1, "text_length_vs_duration": 1,
    }
    rows = [json.loads(line) for line in (out / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    assert {r["speaker"] for r in rows} == {"easykhmer"}
    assert all(r["source_url"].startswith("https://www.youtube.com/") for r in rows)
    assert all(r["provenance"] == {
        "source_kind": "third_party_video", "license_status": "unconfirmed", "license": "",
        "consent": "none recorded", "ship_ok": False,
    } for r in rows)


def test_fish_layout_has_wav_and_lab_per_clip(tmp_path):
    ch = build_channel(tmp_path, "km_a", "a", ROWS[:1] + ROWS[5:6])
    out = tmp_path / "out"
    convert([ch], out, Filters(val_fraction=0), None, audio="copy")
    wavs = sorted((out / "fish" / "train" / "a").glob("*.wav"))
    labs = sorted((out / "fish" / "train" / "a").glob("*.lab"))
    assert len(wavs) == len(labs) == 2
    assert wavs[0].is_file() and not wavs[0].is_symlink()
    assert labs[0].read_text(encoding="utf-8").strip() == "សួស្តី នេះជាការសាកល្បង"
    assert wav_seconds(wavs[0]) == pytest.approx(3.0, abs=0.01)


def test_only_licensed_drops_everything_without_an_allowlist_entry(tmp_path):
    allowed = build_channel(tmp_path, "km_fleurs_km", "fleurs_km", ROWS[:1], url_prefix="huggingface://google/fleurs/")
    other = build_channel(tmp_path, "km_easykhmer", "easykhmer", ROWS[:1])
    allow = tmp_path / "licensed.txt"
    allow.write_text("# c\nfleurs\tCC-BY-4.0\tFLEURS\n", encoding="utf-8")
    report = convert([allowed, other], tmp_path / "all", Filters(val_fraction=0), allow)
    assert report["by_license_status"] == {"allowlisted": 1, "unconfirmed": 1}
    assert report["clips_ship_ok"] == 1
    shipped = convert([allowed, other], tmp_path / "ship", Filters(val_fraction=0, only_licensed=True), allow)
    assert shipped["clips_kept"] == 1 and shipped["by_license_status"] == {"allowlisted": 1}
    assert shipped["rejected_by_reason"] == {"not_licensed": 1}
    rows = [json.loads(x) for x in (tmp_path / "ship" / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    assert rows[0]["provenance"]["license"] == "CC-BY-4.0" and rows[0]["provenance"]["ship_ok"] is True


def test_validation_split_holds_out_whole_speakers(tmp_path):
    rows = [(3.0, f"ประโยค {i} ทดสอบ", 20.0) for i in range(8)]
    a = build_channel(tmp_path, "th_a", "a", rows)
    b = build_channel(tmp_path, "th_b", "b", rows)
    c = build_channel(tmp_path, "th_c", "c", rows)
    out = tmp_path / "out"
    convert([a, b, c], out, Filters(val_fraction=0.3), None, audio="none")
    manifest = [json.loads(x) for x in (out / "manifest.jsonl").read_text(encoding="utf-8").splitlines()]
    train = {r["speaker"] for r in manifest if r["split"] == "train"}
    val = {r["speaker"] for r in manifest if r["split"] == "val"}
    assert val and train and not (train & val)


def test_single_speaker_falls_back_to_utterance_split_and_says_so(tmp_path):
    rows = [(3.0, f"ประโยค {i} ทดสอบ", 20.0) for i in range(40)]
    ch = build_channel(tmp_path, "th_only", "only", rows)
    report = convert([ch], tmp_path / "out", Filters(val_fraction=0.2), None, audio="none")
    assert any("one speaker only" in n for n in report["split_notes"])
    assert 0 < report["by_split"].get("val", 0) < 40


def test_refuses_to_write_over_the_input_and_finds_nested_splits(tmp_path):
    ch = build_channel(tmp_path, "km_x", "x", ROWS[:1])
    assert len(discover_splits([tmp_path])) == 1
    with pytest.raises(SystemExit):
        convert([ch], ch / "04_cosyvoice", Filters(), None)
    with pytest.raises(SystemExit):
        convert([tmp_path / "nothing"], tmp_path / "o", Filters(), None)


def test_allowlist_parsing_and_provenance_files(tmp_path):
    allow = tmp_path / "a.txt"
    allow.write_text("# x\n\nmychannel\tCC0\tours\nhttps://example.org/lic/\tMIT\t\n", encoding="utf-8")
    al = Allowlist.load(allow)
    assert [e["source"] for e in al.entries] == ["mychannel", "https://example.org/lic/"]
    assert al.match({"speaker": "mychannel"})["license"] == "CC0"
    assert al.match({"source_url": "https://example.org/lic/a.wav"})["license"] == "MIT"
    assert al.match({"speaker": "other", "source_url": "https://youtube.com/watch?v=1"}) is None
    ch = build_channel(tmp_path, "km_p", "p", ROWS[:1])
    convert([ch], tmp_path / "o", Filters(val_fraction=0), None, audio="none")
    text = (tmp_path / "o" / "provenance.txt").read_text(encoding="utf-8")
    assert "third-party YouTube/Vimeo channels" in text and "unconfirmed" in text
