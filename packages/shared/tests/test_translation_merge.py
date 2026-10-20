"""NLLB + MADLAD merge keeps the sentence that round-trips, and checkpoints list it."""

import threading
import time

from aoep_shared.course_translation_library import (
    latest_checkpoint,
    save_translation,
    snapshot_checkpoint,
)
from aoep_shared.madlad import MADLAD_MAX_MODEL, prompt_for, target_tag
from aoep_shared.nllb import NLLB_MAX_MODEL, flores_code, model_id
from aoep_shared.translation_merge import choose_translation, merged_translate, round_trip_score


def test_max_models_are_the_large_checkpoints():
    assert NLLB_MAX_MODEL == "facebook/nllb-200-3.3B"
    assert MADLAD_MAX_MODEL == "google/madlad400-10b-mt"
    assert model_id() == NLLB_MAX_MODEL


def test_madlad_prompt_uses_the_target_tag():
    assert target_tag("km") == "<2km>"
    assert target_tag("yue") == "<2yue>"
    assert target_tag("tl") == "<2tl>"
    assert flores_code("yue") == "yue_Hant"
    assert flores_code("tl") == "tgl_Latn"
    assert prompt_for("The immune system protects the body.", "es").startswith("<2es> ")


def test_round_trip_prefers_the_closer_sentence():
    score = round_trip_score("The cat sat.", "The cat sat.")
    assert score > round_trip_score("The cat sat.", "A dog ran away yesterday.")
    merged = choose_translation(
        "The cat sat.",
        nllb_text="El gato se sentó.",
        madlad_text="El gato estaba sentado.",
        nllb_back="The cat sat.",
        madlad_back="Something else entirely.",
    )
    assert merged.chosen == "nllb"
    assert merged.text == "El gato se sentó."


def test_close_scores_keep_the_madlad_sentence():
    merged = choose_translation(
        "Welcome to class.",
        nllb_text="Bienvenido a la clase.",
        madlad_text="Te damos la bienvenida a la clase.",
        nllb_back="Welcome to class.",
        madlad_back="welcome to class.",
    )
    assert merged.chosen == "madlad"


def test_merged_translate_runs_both_models(monkeypatch):
    def nllb_translate(text, *, source, target):
        if target == "en":
            return "The cat sat."
        return "Gato rígido."

    def madlad_translate(text, *, source, target):
        if target == "en":
            return "The cat sat down."
        return "El gato se sentó."

    monkeypatch.setattr("aoep_shared.nllb.translate_text", nllb_translate)
    monkeypatch.setattr("aoep_shared.madlad.translate_text", madlad_translate)
    merged = merged_translate("The cat sat.", source="en", target="es")
    assert merged.chosen == "nllb"
    assert merged.nllb_text == "Gato rígido."
    assert merged.madlad_text == "El gato se sentó."


def test_merged_translate_runs_one_request_at_a_time(monkeypatch):
    active = 0
    peak = 0
    guard = threading.Lock()

    def fake(text, *, source, target):
        nonlocal active, peak
        with guard:
            active += 1
            peak = max(peak, active)
        time.sleep(0.05)
        with guard:
            active -= 1
        return "hola" if target == "es" else "hello"

    monkeypatch.setattr("aoep_shared.nllb.translate_text", fake)
    monkeypatch.setattr("aoep_shared.madlad.translate_text", fake)
    errors: list[BaseException] = []

    def run() -> None:
        try:
            merged_translate("The cat sat.", source="en", target="es")
        except BaseException as exc:  # noqa: BLE001 — the test reports it
            errors.append(exc)

    threads = [threading.Thread(target=run) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert errors == []
    # One request uses both models together. A second request waits.
    assert peak == 2


def test_daily_checkpoint_lists_saved_courses(tmp_path):
    save_translation(
        {
            "course_id": "audio-immune",
            "title": "El sistema inmunológico",
            "category": "science",
            "language": "es",
            "segments": [{"heading": "Células", "text": "Las células defienden el cuerpo.", "kind": "narration"}],
        },
        tmp_path,
    )
    manifest = snapshot_checkpoint(tmp_path, day="2026-10-14")
    assert manifest["day"] == "2026-10-14"
    assert manifest["languages"]["es"] == 1
    assert manifest["ready"][0]["course_id"] == "audio-immune"
    assert latest_checkpoint(tmp_path)["files"] == 1
    assert (tmp_path / "checkpoints" / "2026-10-14.json").is_file()
