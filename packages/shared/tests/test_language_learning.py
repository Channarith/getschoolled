"""Language learning: catalog, phrasebook, exercises, pronunciation scoring."""

from aoep_shared.language_learning import (
    LANGUAGE_META,
    RICH_LANGUAGES,
    SKILL_AREAS,
    assess_pronunciation,
    course_outline,
    language_list,
    listening_exercise,
    match_exercise,
    mouth_shape_tip,
    practice_xp,
    pronunciation_prompt,
    vocabulary_exercise,
)
from aoep_shared.languages import SUPPORTED_LANGUAGES


def test_supports_20_plus_languages_with_metadata():
    langs = language_list()
    assert len(langs) >= 20
    assert len(langs) == len(SUPPORTED_LANGUAGES)
    # Every supported language has display metadata.
    for code in SUPPORTED_LANGUAGES:
        assert code in LANGUAGE_META
        assert LANGUAGE_META[code]["name"] and LANGUAGE_META[code]["flag"]
    # Every language is practiceable (has at least starter phrases).
    assert all(x["phrase_count"] >= 1 for x in langs)


def test_skill_areas_cover_requested_domains():
    ids = {s["id"] for s in SKILL_AREAS}
    for need in ["pronunciation", "listening", "reading", "writing", "vocabulary",
                 "grammar", "slang", "phrases", "travel", "conversation"]:
        assert need in ids
    # plus fun extras
    assert {"shadowing", "story", "culture"} <= ids


def test_rich_language_course_has_more_skills_than_starter():
    rich = course_outline("es")
    starter = course_outline("sw")
    assert rich["tier"] == "rich" and starter["tier"] == "starter"
    assert len(rich["skills"]) > len(starter["skills"])
    assert rich["grammar_tip"] and rich["culture_note"]


def test_vocabulary_exercise_has_correct_answer():
    ex = vocabulary_exercise("es", n=5, seed=1)
    assert ex["skill"] == "vocabulary"
    for it in ex["items"]:
        assert it["options"][it["answer_index"]] == it["explain"].split(" = ")[1]


def test_listening_exercise_frames_audio_prompt():
    ex = listening_exercise("fr", n=4, seed=2)
    assert ex["skill"] == "listening"
    assert all("audio_prompt" in it and "what does it mean" in it["prompt"] for it in ex["items"])


def test_match_exercise_pairs_target_to_english():
    ex = match_exercise("ja", n=4, seed=3)
    assert len(ex["pairs"]) >= 2
    assert all(p["term"] and p["match"] for p in ex["pairs"])


def test_pronunciation_prompt_includes_mouth_tip():
    p = pronunciation_prompt("es", seed=4)
    assert p["target"] and "mouth_tip" in p


def test_pronunciation_scoring_rewards_accuracy():
    perfect = assess_pronunciation("Hola", "hola")
    assert perfect["score"] == 100 and perfect["stars"] == 3 and perfect["passed"]
    close = assess_pronunciation("Bonjour", "bonjur")
    assert 50 <= close["score"] < 100
    wrong = assess_pronunciation("Gracias", "hello world")
    assert wrong["score"] < 60 and not wrong["passed"]


def test_pronunciation_uses_vision_mouth_openness():
    closed = assess_pronunciation("Hola", "hola", mouth_openness=0.1)
    assert "more" in closed["mouth_tip"].lower()
    wide = assess_pronunciation("Hola", "hola", mouth_openness=0.9)
    assert "great" in wide["mouth_tip"].lower() or "articulation" in wide["mouth_tip"].lower()


def test_mouth_shape_tips_by_sound():
    assert "open" in mouth_shape_tip("ah").lower()
    assert "lip" in mouth_shape_tip("mama").lower() or "press" in mouth_shape_tip("mama").lower()


def test_practice_xp_scales_with_skill_and_perfection():
    easy = practice_xp("vocabulary", 5, 5)
    hard = practice_xp("pronunciation", 5, 5)
    assert hard > easy            # harder skills give more XP
    assert practice_xp("vocabulary", 5, 5) > practice_xp("vocabulary", 3, 5)


def test_every_rich_language_has_full_phrasebook():
    for code in RICH_LANGUAGES:
        assert course_outline(code)["phrase_count"] >= 10
