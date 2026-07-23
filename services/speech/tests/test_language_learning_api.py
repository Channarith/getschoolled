"""Language-learning endpoints on the speech gateway."""

from fastapi.testclient import TestClient
from speech_gw.main import app

client = TestClient(app)


def test_learn_languages_lists_20_plus():
    body = client.get("/learn/languages").json()
    assert body["count"] >= 20
    codes = {x["code"] for x in body["languages"]}
    assert {"es", "fr", "zh", "ja", "ar", "hi"} <= codes
    assert all(x["flag"] and x["name"] for x in body["languages"])


def test_all_languages_are_full_courses():
    for language in ("es", "sw", "km"):
        course = client.get(f"/learn/{language}/course").json()
        assert course["tier"] == "full"
        assert course["dialogue_count"] >= 20
        assert course["song_count"] >= 1


def test_unsupported_language_404():
    assert client.get("/learn/zz/course").status_code == 404


def test_vocabulary_exercise():
    ex = client.post("/learn/exercise", json={"language": "fr", "skill": "vocabulary", "n": 5}).json()
    assert ex["skill"] == "vocabulary" and ex["items"]
    it = ex["items"][0]
    assert it["options"][it["answer_index"]]


def test_listening_and_match_and_pronunciation_exercises():
    li = client.post("/learn/exercise", json={"language": "de", "skill": "listening", "n": 4}).json()
    assert li["skill"] == "listening" and "audio_prompt" in li["items"][0]
    mt = client.post("/learn/exercise", json={"language": "it", "skill": "match", "n": 4}).json()
    assert mt["pairs"]
    pr = client.post("/learn/exercise", json={"language": "ja", "skill": "pronunciation"}).json()
    assert pr["target"] and pr["mouth_tip"]


def test_pronounce_scores_attempt_with_vision():
    good = client.post("/learn/pronounce", json={"target": "Hola", "heard": "hola"}).json()
    assert good["score"] == 100 and good["passed"]
    vision = client.post("/learn/pronounce",
                         json={"target": "Hola", "heard": "hola", "mouth_openness": 0.1}).json()
    assert "more" in vision["mouth_tip"].lower()


def test_phrases_and_slang():
    ph = client.get("/learn/es/phrases").json()
    assert any(p["en"] == "Hello" for p in ph["phrases"])
    sl = client.get("/learn/en/slang").json()
    assert isinstance(sl["entries"], list) and len(sl["entries"]) >= 1


def test_khmer_dialogues_slang_and_songs():
    dialogues = client.get("/learn/km/dialogues").json()["dialogues"]
    slang = client.get("/learn/km/slang").json()["entries"]
    songs = client.get("/learn/km/songs").json()["songs"]
    assert len(dialogues) >= 20
    assert len(slang) >= 50
    assert songs and len(songs[0]["verses"]) >= 4

    ex = client.post(
        "/learn/exercise",
        json={"language": "km", "skill": "conversation", "n": 20},
    ).json()
    assert len(ex["dialogues"]) >= 20


def test_khmer_vocabulary_endpoint_has_five_hundred_words():
    response = client.get("/learn/km/vocabulary")
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 500
    assert len(body["vocabulary"]) == body["count"]
    assert len({word["target"] for word in body["vocabulary"]}) == body["count"]

    school = client.get("/learn/km/vocabulary", params={"category": "school"}).json()
    assert school["count"] >= 10
    assert all(word["category"] == "school" for word in school["vocabulary"])


def test_khmer_media_challenge_uses_ten_words_and_ten_second_clips():
    body = client.get(
        "/learn/km/media-challenge",
        params={"study_size": 10, "seed": 9},
    ).json()
    assert len(body["study_words"]) == len(body["segments"]) == 10
    assert all(segment["duration_sec"] == 10 for segment in body["segments"])

    exercise = client.post(
        "/learn/exercise",
        json={"language": "km", "skill": "media-listening", "n": 10},
    ).json()
    assert exercise["skill"] == "media-listening"
    assert len(exercise["study_words"]) == 10
    assert len(exercise["segments"]) == 10


def test_khmer_three_page_reader_and_word_coach():
    story = client.get("/learn/km/reading-story").json()
    assert story["page_count"] == 3
    assert len(story["pages"]) == 3
    clickable = [
        run
        for page in story["pages"]
        for run in page["runs"]
        if run.get("word_id")
    ]
    assert len(clickable) >= 12

    exercise = client.post(
        "/learn/exercise",
        json={"language": "km", "skill": "reading"},
    ).json()
    assert exercise["story_id"] == story["story_id"]

    coach = client.post(
        "/learn/explain-word",
        json={"language": "km", "word_id": clickable[0]["word_id"]},
    )
    assert coach.status_code == 200
    body = coach.json()
    assert body["meaning"] and body["explanation"]
    assert body["pronunciation_tip"] and body["examples"]
