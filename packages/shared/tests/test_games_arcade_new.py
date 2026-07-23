"""Arcade expansions: shape drop, stocks/finance, Challenge the AI."""

from aoep_shared.games import (
    GAME_SUBJECTS,
    AgeGroup,
    GameType,
    games_catalog,
    make_round,
    score_round,
    simulate_ai_answers,
)
from aoep_shared.games_extended import extended_bank


def test_catalog_includes_new_modes_and_finance():
    assert "finance" in GAME_SUBJECTS
    assert "workplace" in GAME_SUBJECTS
    cat = games_catalog()
    ids = {g["id"] for g in cat["game_types"]}
    assert "shape_drop" in ids
    assert "stocks" in ids
    assert "challenge" in ids
    assert "scenario" in ids
    assert "finance" in cat["subjects"]
    assert "workplace" in cat["subjects"]


def test_shape_drop_round():
    rnd = make_round("geometry", GameType.SHAPE_DROP, n=4, seed=21)
    assert len(rnd.mcqs) >= 2
    assert all(m.kind == "shape_drop" for m in rnd.mcqs)
    pub = rnd.public()
    assert all("answer_index" not in it for it in pub["items"])


def test_stocks_finance_round():
    rnd = make_round("finance", GameType.STOCKS, n=5, seed=22)
    assert len(rnd.mcqs) >= 3
    assert all(m.kind == "stocks" for m in rnd.mcqs)
    answers = {m.id: m.answer_index for m in rnd.mcqs}
    res = score_round(rnd, answers)
    assert res.correct == res.total
    assert res.points >= res.correct * 10


def test_extended_bank_shape_and_stocks():
    shapes = extended_bank("geometry", "shape_drop", AgeGroup.TEEN)
    assert shapes and all("shape_drop" in r["game_types"] for r in shapes)
    stocks = extended_bank("finance", "stocks", AgeGroup.TEEN)
    assert stocks and all("stocks" in r["game_types"] for r in stocks)


def test_challenge_ai_versus_scoring_win():
    rnd = make_round("math", GameType.CHALLENGE, n=6, seed=23)
    assert rnd.game_type is GameType.CHALLENGE
    assert rnd.time_limit_s > 0
    pub = rnd.public()
    assert pub["versus"] == "ai"
    assert 0 < pub["ai_skill"] < 1
    # Perfect human answers beat typical AI.
    answers = {m.id: m.answer_index for m in rnd.mcqs}
    res = score_round(rnd, answers)
    assert res.ai_total == len(rnd.mcqs)
    assert res.versus_outcome in ("win", "tie")  # perfect should win or rare tie
    assert res.versus_bonus > 0
    assert res.points == res.base_points + res.accuracy_bonus + res.versus_bonus


def test_challenge_ai_lose_when_all_wrong():
    rnd = make_round("science", GameType.CHALLENGE, n=5, seed=24)
    answers = {m.id: (m.answer_index + 1) % len(m.options) for m in rnd.mcqs}
    res = score_round(rnd, answers)
    assert res.correct == 0
    assert res.versus_outcome == "lose"
    assert res.versus_bonus == 0
    assert res.ai_correct >= 0


def test_simulate_ai_deterministic():
    rnd = make_round("biology", GameType.CHALLENGE, n=4, seed=25)
    a1 = simulate_ai_answers(rnd)
    a2 = simulate_ai_answers(rnd)
    assert a1 == a2


def test_workplace_scenario_round():
    rnd = make_round("workplace", GameType.SCENARIO, n=6, seed=26)
    assert len(rnd.mcqs) >= 4
    assert all(m.kind == "scenario" for m in rnd.mcqs)
    pub = rnd.public()
    assert all("answer_index" not in it for it in pub["items"])
    assert pub["items"][0]["meta"].get("track")
    answers = {m.id: m.answer_index for m in rnd.mcqs}
    res = score_round(rnd, answers)
    assert res.correct == res.total


def test_extended_bank_workplace_scenarios():
    rows = extended_bank("workplace", "scenario", AgeGroup.ADULT)
    assert rows and all("scenario" in r["game_types"] for r in rows)
