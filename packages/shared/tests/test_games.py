"""Learning-games engine: round generation + scoring + points."""

from aoep_shared.games import (
    GAME_SUBJECTS,
    GameType,
    games_catalog,
    make_round,
    score_round,
)


def test_catalog_covers_requested_subjects():
    for s in ["biology", "chemistry", "physics", "math", "science",
              "history", "art", "technology", "programming"]:
        assert s in GAME_SUBJECTS
    cat = games_catalog()
    assert {g["id"] for g in cat["game_types"]} == {"quiz", "speed", "match"}


def test_quiz_round_public_hides_answers():
    rnd = make_round("biology", GameType.QUIZ, n=3, seed=1)
    pub = rnd.public()
    assert len(pub["items"]) == 3
    assert all("answer_index" not in it for it in pub["items"])


def test_perfect_quiz_scores_with_accuracy_bonus():
    rnd = make_round("math", GameType.QUIZ, n=5, seed=2)
    answers = {m.id: m.answer_index for m in rnd.mcqs}
    res = score_round(rnd, answers)
    assert res.correct == res.total == len(rnd.mcqs)
    assert res.accuracy == 1.0
    assert res.accuracy_bonus == 20
    assert res.points == res.correct * 10 + 20


def test_wrong_answers_lower_score():
    rnd = make_round("history", GameType.QUIZ, n=4, seed=3)
    answers = {m.id: (m.answer_index + 1) % len(m.options) for m in rnd.mcqs}
    res = score_round(rnd, answers)
    assert res.correct == 0
    assert res.points == 0


def test_speed_bonus_rewards_being_fast():
    rnd = make_round("physics", GameType.SPEED, n=5, seed=4)
    assert rnd.time_limit_s > 0
    answers = {m.id: m.answer_index for m in rnd.mcqs}
    fast = score_round(rnd, answers, elapsed_s=5)
    slow = score_round(rnd, answers, elapsed_s=rnd.time_limit_s - 1)
    assert fast.speed_bonus > slow.speed_bonus >= 0
    assert fast.points > slow.points


def test_match_round_scoring():
    rnd = make_round("chemistry", GameType.MATCH, n=4, seed=5)
    pub = rnd.public()
    # Options are shuffled; correct option shares the term's id.
    answers = {t["id"]: t["id"] for t in pub["terms"]}
    res = score_round(rnd, answers)
    assert res.correct == res.total == len(rnd.pairs)
    assert res.accuracy == 1.0
    # A wrong mapping reduces the score.
    ids = [t["id"] for t in pub["terms"]]
    bad = {ids[0]: ids[1], ids[1]: ids[0]}
    for i in ids[2:]:
        bad[i] = i
    res2 = score_round(rnd, bad)
    assert res2.correct == res.total - 2


def test_unknown_subject_falls_back():
    rnd = make_round("astrology", GameType.QUIZ, n=3)
    assert rnd.subject == "science"
