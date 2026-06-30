"""Theodore - the AI presenter persona, strategy registry, and rehearsal loop."""

from aoep_shared import theodore as T


def test_persona_named_theodore():
    p = T.persona()
    assert p["name"] == "Theodore"
    assert p["strategy_count"] == T.strategy_count() >= 20
    assert p["bio"] and p["tagline"]


def test_strategies_cover_all_reference_sources():
    sources = {s.source for s in T.list_strategies()}
    # Every reference talk + general pedagogy is represented.
    assert set(T.SOURCES) == sources
    assert any("Tao" in s for s in sources)
    assert any("Musk" in s for s in sources)
    assert any("MasterClass" in s for s in sources)


def test_signature_strategies_present():
    for sid in ("first_principles", "deconstruct", "story_lens",
                "everyday_relevance", "curiosity_gap", "comprehension_check",
                "normalize_failure", "confident_close"):
        assert T.get_strategy(sid) is not None, sid


def test_system_prompt_names_theodore_and_lists_cues():
    sp = T.system_prompt(topic="recursion", level="beginner")
    assert "Theodore" in sp
    assert "recursion" in sp
    assert "first principles" in sp.lower()
    assert "rehearse" in sp.lower()


def test_rehearse_improves_a_bare_narration():
    bare = "Recursion is when a function calls itself."
    result = T.rehearse(bare, topic="recursion", passes=3)
    assert result.original == bare
    assert bare in result.rehearsed  # body preserved
    assert result.score_after > result.score_before
    assert result.applied  # at least one strategy injected
    assert result.to_dict()["improved"] is True


def test_rehearse_is_deterministic():
    a = T.rehearse("Loops repeat work.", topic="loops")
    b = T.rehearse("Loops repeat work.", topic="loops")
    assert a.rehearsed == b.rehearsed
    assert a.applied == b.applied


def test_score_narration_dimensions():
    rich = ("Here's a question worth sitting with: what makes loops work? "
            "Let's reason from first principles. In everyday life you use this. "
            "In your own words, recap the takeaway.")
    score = T.score_narration(rich)
    assert 0.0 <= score["overall"] <= 1.0
    assert score["dimensions"]["hook"] > 0
    assert score["dimensions"]["rigor"] > 0


def test_delivery_playbook_varies_by_segment_kind():
    intro = [s["id"] for s in T.delivery_playbook(segment_kind="intro", topic="x")]
    outro = [s["id"] for s in T.delivery_playbook(segment_kind="outro", topic="x")]
    assert intro and outro and intro != outro
    assert "curiosity_gap" in intro
    assert "confident_close" in outro


def test_adapt_for_attention_escalates_when_low():
    low = T.adapt_for_attention(0.2, topic="x")
    high = T.adapt_for_attention(0.9, topic="x")
    assert low["intensity"] == "high"
    assert high["intensity"] == "low"
    low_ids = [s["id"] for s in low["strategies"]]
    assert "humor" in low_ids or "curiosity_gap" in low_ids


def test_frame_answer_adds_a_comprehension_check_once():
    framed = T.frame_answer("Oxygen is released by plants.", topic="photosynthesis")
    assert "your own words" in framed.lower()
    # idempotent-ish: does not stack a second check
    twice = T.frame_answer(framed, topic="photosynthesis")
    assert twice.lower().count("your own words") == 1
