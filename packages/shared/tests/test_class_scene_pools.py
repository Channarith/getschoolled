"""Class scene pools: size, uniqueness, and without-replacement draws."""

from aoep_shared.class_scenes import (
    ClassSceneSession,
    canonical_topic,
    draw_for_session,
    grade_scene_answer,
    localize_scene,
    pool_size,
    reset_session_decks,
    scenes_for_topic,
)
from aoep_shared.training_content_i18n import set_body_translator


def _skill_share(topic: str) -> tuple[str, float]:
    scenes = scenes_for_topic(topic)
    counts: dict[str, int] = {}
    for scene in scenes:
        counts[scene.skill] = counts.get(scene.skill, 0) + 1
    skill, count = max(counts.items(), key=lambda item: item[1])
    return skill, count / len(scenes)


def test_driver_and_food_pools_are_large_and_varied() -> None:
    for topic in ("drivers-ed", "food-safety"):
        scenes = scenes_for_topic(topic)
        assert len(scenes) > 1000
        prompts = [scene.prompt for scene in scenes]
        assert len(set(prompts)) == len(prompts)
        assert len({scene.scene_id for scene in scenes}) == len(scenes)
        assert len({scene.acceptable[0] for scene in scenes}) >= 80
        assert len({scene.skill for scene in scenes}) >= 15
        for scene in scenes:
            assert scene.locale == "en"
            assert scene.source_locale == "en"
            assert scene.spoken
            assert scene.rubric
            assert scene.acceptable
        skill, share = _skill_share(topic)
        assert share < 0.40, (topic, skill, share)


def test_lesson_titles_map_onto_the_pools() -> None:
    assert canonical_topic("ca-driver-ed-06-right-of-way") == "drivers-ed"
    assert canonical_topic("CA Driver Ed — Regulatory signs") == "drivers-ed"
    assert canonical_topic("ca-dmv-permit-basics") == "drivers-ed"
    assert canonical_topic("food-handler-safety") == "food-safety"
    assert canonical_topic("California / Alameda Food Handler Prep — Hygiene") == "food-safety"
    assert pool_size("ca-driver-ed-02-signs-regulatory") > 1000
    assert pool_size("ca-alameda-food-handler-temps") > 1000


def test_fresh_session_draws_differ_and_do_not_repeat() -> None:
    for topic in ("drivers-ed", "food-safety"):
        session = ClassSceneSession(topic, seed=7)
        first = session.draw()
        second = session.draw()
        assert first.scene_id != second.scene_id
        seen = {first.scene_id, second.scene_id}
        last = second.scene_id
        while len(seen) < session.size:
            last = session.draw().scene_id
            seen.add(last)
        assert len(seen) == session.size
        # The pool is exhausted. The next pass reshuffles and does not
        # immediately repeat the scene just used.
        assert session.draw().scene_id != last


def test_named_session_draws_are_stable_and_distinct() -> None:
    reset_session_decks()
    a = draw_for_session("class-1", "CA Driver Ed — Speed", seed=3)
    b = draw_for_session("class-1", "ca-driver-ed-07-speed-space")
    assert a.scene_id != b.scene_id
    # A second class gets its own deck, so it is not stuck on class-1's used set.
    other = draw_for_session("class-2", "drivers-ed", seed=3)
    assert other.scene_id == a.scene_id


def test_grade_uses_the_acceptable_answer() -> None:
    scene = scenes_for_topic("food-safety")[0]
    assert grade_scene_answer(scene, scene.acceptable[0])["correct"] is True
    assert grade_scene_answer(scene, "purple telescope")["correct"] is False


def test_locale_uses_the_request_time_translator() -> None:
    scene = scenes_for_topic("drivers-ed")[0]

    def _translate(text: str, source: str, target: str) -> str:
        assert source == "en"
        return f"{target}:{text}"

    set_body_translator(_translate)
    try:
        spanish = localize_scene(scene, "es-MX")
        assert spanish.locale == "es"
        assert spanish.prompt.startswith("es:")
        assert spanish.spoken.startswith("es:")
        english = localize_scene(scene, "en")
        assert english.locale == "en"
        assert english.prompt == scene.prompt
    finally:
        set_body_translator(None)
        missed = localize_scene(scene, "fr")
        assert missed.locale == "en"
        assert missed.prompt == scene.prompt


def test_catalog_merges_the_scene_pools() -> None:
    from aoep_shared.training_agents.catalog import count_scenarios, reload_catalog

    reload_catalog()
    assert count_scenarios(domain="road") > 1000
    assert count_scenarios(domain="food_safety") > 1000
