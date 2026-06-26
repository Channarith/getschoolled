"""Extended arcade modes: tiles, RPG, farm, cartoon, idioms, etc."""

from aoep_shared.games import AgeGroup, GameType, make_round, score_round
from aoep_shared.games_extended import extended_bank, extended_bank_for_subject


def test_extended_bank_filters_by_mode():
    rows = extended_bank("wordplay", "tiles", AgeGroup.TEEN)
    assert rows
    assert all("tiles" in r["game_types"] for r in rows)


def test_extended_bank_for_subject_etiquette():
    rows = extended_bank_for_subject("etiquette", AgeGroup.TEEN)
    assert len(rows) >= 2


def test_farm_mode_scores():
    rnd = make_round("farming", GameType.FARM, n=3, seed=4)
    answers = {m.id: m.answer_index for m in rnd.mcqs}
    res = score_round(rnd, answers)
    assert res.correct == res.total


def test_cartoon_mode_has_scene_meta():
    rnd = make_round("life_growth", GameType.CARTOON, n=2, seed=5)
    pub = rnd.public()
    assert pub["items"][0]["kind"] == "cartoon"


def test_idiom_mode_wordplay():
    rnd = make_round("wordplay", GameType.IDIOM, n=3, seed=6)
    assert len(rnd.mcqs) >= 2


def test_spelling_mode():
    rnd = make_round("wordplay", GameType.SPELLING, n=3, seed=7)
    assert all(m.kind == "spelling" for m in rnd.mcqs)


def test_resource_constraint_mode():
    rnd = make_round("farming", GameType.RESOURCE, n=2, seed=8)
    assert rnd.mcqs[0].kind == "resource"


def test_dependency_mode():
    rnd = make_round("programming", GameType.DEPENDENCY, n=2, seed=9)
    assert rnd.mcqs[0].kind == "dependency"


def test_create_mode():
    rnd = make_round("creation", GameType.CREATE, n=2, seed=10)
    assert rnd.mcqs[0].kind == "create"


def test_doing_mode():
    rnd = make_round("chemistry", GameType.DOING, n=2, seed=11)
    assert rnd.mcqs[0].kind == "doing"


def test_locale_spanish_prompt():
    rnd = make_round("wordplay", GameType.IDIOM, n=1, seed=12, locale="es")
    pub = rnd.public()
    prompt = pub["items"][0]["prompt"]
    assert "significa" in prompt or "break" in prompt.lower()
