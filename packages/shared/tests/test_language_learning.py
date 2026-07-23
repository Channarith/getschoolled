"""Language learning: catalog, phrasebook, exercises, pronunciation scoring."""

from aoep_shared.language_learning import (
    LANGUAGE_META,
    RICH_LANGUAGES,
    SKILL_AREAS,
    assess_pronunciation,
    assess_translation_gist,
    course_outline,
    dialogues_for,
    language_list,
    listening_exercise,
    match_exercise,
    mouth_shape_tip,
    music_video_challenge,
    music_videos_for,
    practice_xp,
    pronunciation_prompt,
    score_music_video_section,
    songs_for,
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
    assert {"shadowing", "story", "culture", "songs", "media-listening", "music-video"} <= ids


def test_every_language_is_a_full_course():
    expected_skills = {skill["id"] for skill in SKILL_AREAS}
    for code in SUPPORTED_LANGUAGES:
        course = course_outline(code)
        assert course["tier"] == "full"
        assert {skill["id"] for skill in course["skills"]} == expected_skills
        assert course["dialogue_count"] >= 20
        assert course["song_count"] >= 1
        assert course["music_video_count"] >= 1


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


def test_every_language_has_dialogue_and_song_practice():
    assert RICH_LANGUAGES == set(SUPPORTED_LANGUAGES)
    for code in SUPPORTED_LANGUAGES:
        assert len(dialogues_for(code)) >= 20
        song = songs_for(code)[0]
        assert len(song["verses"]) >= 1
        assert all(v["target"] and v["en"] and v["explain_en"] for v in song["verses"])


def test_music_video_challenge_is_section_driven():
    challenge = music_video_challenge("es")
    assert challenge["skill"] == "music-video"
    assert challenge["sections"]
    assert all(
        section["id"] and section["target"] and section["en"] and section["prompt"]
        for section in challenge["sections"]
    )
    assert music_videos_for("km")[0]["video_id"] == "km-everyday-music-video"
    km = music_video_challenge("km")
    assert len(km["sections"]) >= 6
    assert km["license"] == "original-salareen"


def test_translation_gist_accepts_paraphrase_via_rag():
    reference = "Hello, how are you? It is very nice to meet you."
    explain = "A warm greeting: say hello, ask how someone is, and say you are happy to meet them."
    paraphrases = [
        "Greeting someone and saying nice to meet you",
        "Hello and asking if they are well",
    ]
    gist = assess_translation_gist(
        reference,
        "saying hello and nice to meet you",
        explain_en=explain,
        paraphrases_en=paraphrases,
        language="km",
    )
    assert gist["passed"] and gist["point"] == 1
    assert gist["retrieved"]

    exact = assess_translation_gist(reference, reference, paraphrases_en=paraphrases)
    assert exact["passed"] and exact["score"] >= 80

    wrong = assess_translation_gist(
        reference,
        "the bathroom is on the right and too expensive",
        explain_en=explain,
        paraphrases_en=paraphrases,
    )
    assert not wrong["passed"]


def test_score_music_video_section_awards_point_for_gist():
    challenge = music_video_challenge("km")
    section = challenge["sections"][0]
    result = score_music_video_section(
        "km",
        video_id=challenge["video_id"],
        section_id=section["id"],
        translation="hello how are you nice to meet you",
    )
    assert result["passed"] and result["point"] == 1
    assert result["section_id"] == section["id"]
    assert "hello" in result["reference_en"].lower() or "meet" in result["reference_en"].lower()
