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


def test_course_outline_rich_vs_starter():
    rich = client.get("/learn/es/course").json()
    assert rich["tier"] == "rich" and rich["grammar_tip"]
    starter = client.get("/learn/sw/course").json()
    assert starter["tier"] == "starter"
    assert len(rich["skills"]) > len(starter["skills"])


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
