import wave

import numpy as np
import pytest

from tts_bakeoff import scoring


def write(path, samples, rate=16000):
    arr = (np.clip(np.asarray(samples), -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(arr.tobytes())


def tone(seconds, rate=16000, amp=0.3, freq=220.0):
    t = np.arange(int(seconds * rate)) / rate
    return amp * np.sin(2 * np.pi * freq * t)


def test_edit_distance_and_rates():
    assert scoring.edit_distance(list("kitten"), list("sitting")) == 3
    assert scoring.error_rate("the cat sat", "the cat sat", "en")["value"] == 0.0
    assert scoring.error_rate("the cat sat", "the dog sat", "en") == {"metric": "wer", "value": pytest.approx(1 / 3), "edits": 1, "ref_len": 3, "digits_ignored": False}
    assert scoring.error_rate("一二三四", "一二三五", "zh")["metric"] == "cer"
    assert scoring.error_rate("", "", "en")["value"] == 0.0 and scoring.error_rate("", "x", "en")["value"] == 1.0


def test_numbers_become_words_in_en_es_zh():
    assert scoring.num_words_en(25) == "twenty-five" and scoring.num_words_en(92) == "ninety-two" and scoring.num_words_en(100) == "one hundred"
    assert scoring.num_words_es(25) == "veinticinco" and scoring.num_words_es(45) == "cuarenta y cinco" and scoring.num_words_es(100) == "cien"
    assert scoring.num_words_zh(25) == "二十五" and scoring.num_words_zh(15) == "十五" and scoring.num_words_zh(92) == "九十二" and scoring.num_words_zh(100) == "一百"
    # an ASR transcript with digits scores the same as the spelled-out reference
    assert scoring.error_rate("There are twenty-five students.", "There are 25 students.", "en")["value"] == 0.0
    assert scoring.error_rate("班里有二十五名学生。", "班里有25名学生", "zh")["value"] == 0.0
    assert scoring.error_rate("Hay veinticinco estudiantes.", "hay 25 estudiantes", "es")["value"] == 0.0


def test_digits_in_other_languages_are_dropped_and_flagged_not_silently_scored():
    r = scoring.error_rate("មានសិស្សម្ភៃប្រាំនាក់", "មានសិស្ស 25 នាក់", "km")
    assert r["digits_ignored"] is True


def test_khmer_and_thai_ignore_spacing_and_zero_width_marks():
    a = scoring.error_rate("សូមស្វាគមន៍មកកាន់មេរៀន។", "សូម ស្វាគមន៍​មកកាន់ មេរៀន", "km")
    assert a["value"] == 0.0 and a["metric"] == "cer"
    assert scoring.error_rate("ยินดีต้อนรับ", "ยินดี ต้อนรับ", "th")["value"] == 0.0


def test_punctuation_and_case_are_ignored():
    assert scoring.error_rate("Great job, keep going!", "great job keep going", "en")["value"] == 0.0


def test_audio_analysis_clean_tone(tmp_path):
    p = tmp_path / "a.wav"
    write(p, tone(3.0))
    a = scoring.analyze_audio(p, "one two three four five six seven eight", "en")
    assert a["duration_s"] == pytest.approx(3.0, abs=0.01)
    assert a["flags"] == [] and a["clipped_fraction"] == 0


def test_audio_analysis_flags_silence_clipping_pauses_and_rate(tmp_path):
    silent = tmp_path / "s.wav"
    write(silent, np.zeros(16000))
    assert "silent" in scoring.analyze_audio(silent, "hello there", "en")["flags"]

    clipped = tmp_path / "c.wav"
    write(clipped, np.clip(tone(2.0, amp=3.0), -1, 1))
    assert "clipped" in scoring.analyze_audio(clipped, "one two three four five six", "en")["flags"]

    paused = tmp_path / "p.wav"
    write(paused, np.concatenate([tone(1.0), np.zeros(32000), tone(1.0)]))
    flags = scoring.analyze_audio(paused, "one two three four five six seven eight nine ten", "en")["flags"]
    assert "long_pause" in flags

    lead = tmp_path / "l.wav"
    write(lead, np.concatenate([np.zeros(24000), tone(2.0)]))
    assert "dead_air_start" in scoring.analyze_audio(lead, "one two three four five six seven eight", "en")["flags"]

    fast = tmp_path / "f.wav"
    write(fast, tone(1.0))
    assert "too_fast" in scoring.analyze_audio(fast, " ".join(["word"] * 20), "en")["flags"]
    slow = tmp_path / "w.wav"
    write(slow, tone(8.0))
    assert "too_slow" in scoring.analyze_audio(slow, "one two", "en")["flags"]
