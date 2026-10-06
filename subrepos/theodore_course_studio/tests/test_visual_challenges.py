"""Visual challenges grade authored labels and the vetted picture catalog."""

from __future__ import annotations

import ast
import os
import subprocess
import sys
from pathlib import Path

import pytest

from theodore_course_studio import engagement
from theodore_course_studio.engagement import (
    NAMED_REGIONS,
    PICTURE_EMOJI,
    PICTURE_WORDS,
    VISUAL_GAME_KINDS,
    GameChallenge,
    GameKind,
    VisualChallengeError,
    build_classify_game,
    build_hotspot_game,
    build_image_to_word_game,
    build_label_placement_game,
    build_match_term_game,
    build_memory_pairs_game,
    build_order_steps_game,
    build_picture_order_game,
    build_sort_game,
    build_spot_difference_game,
    build_spot_gap_game,
    build_word_to_image_game,
    catalog_words_in_text,
    fold_label,
    grade_game,
    labels_match,
    pick_game_for_slide,
    pick_visual_game_for_slide,
    visual_challenge_problems,
    visual_game_from_spec,
)
from theodore_course_studio.types import CourseSlide

LAB_ENGINE = (
    Path(__file__).resolve().parents[2]
    / "theodore_children_webcam_lab"
    / "src"
    / "theodore_children_webcam_lab"
    / "game_engine.py"
)


def _assign(source: str, name: str):
    module = ast.parse(source)
    for node in module.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)
    raise AssertionError(name)


def _slide(**kwargs) -> CourseSlide:
    data = {
        "index": 1,
        "title": "Photosynthesis basics",
        "body": "Plants convert sunlight into energy. Chlorophyll absorbs light.",
        "narration": "Plants convert sunlight into energy.",
    }
    data.update(kwargs)
    return CourseSlide(**data)


def test_picture_catalog_matches_the_children_lab_without_importing_it():
    source = Path(engagement.__file__).read_text(encoding="utf-8")
    assert "import theodore_children_webcam_lab" not in source
    assert "from theodore_children_webcam_lab" not in source
    # Verify importing the catalog doesn't pull in the children lab. Checking
    # sys.modules in-process is fragile: the full pytest run shares one
    # interpreter, so an unrelated test that legitimately imported the lab
    # leaves it in sys.modules and this assertion would fail on ordering alone.
    # Run the check in a fresh interpreter (with the same src paths this
    # suite's conftest wires up) so it reflects engagement's own imports only.
    src_root = Path(engagement.__file__).resolve().parents[1]
    shared_src = src_root.parents[2] / "packages" / "shared" / "src"
    env = dict(os.environ)
    extra_paths = [str(src_root)] + (
        [str(shared_src)] if shared_src.is_dir() else []
    )
    env["PYTHONPATH"] = os.pathsep.join(
        extra_paths + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else [])
    )
    probe = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, theodore_course_studio.engagement; "
            "sys.exit(1 if 'theodore_children_webcam_lab' in sys.modules else 0)",
        ],
        capture_output=True,
        env=env,
    )
    assert probe.returncode == 0, (
        "importing theodore_course_studio.engagement pulled in "
        f"theodore_children_webcam_lab:\n{probe.stderr.decode(errors='replace')}"
    )
    assert "urlopen" not in source
    lab = _assign(LAB_ENGINE.read_text(encoding="utf-8"), "PICTURE_WORDS")
    glyphs = _assign(LAB_ENGINE.read_text(encoding="utf-8"), "PICTURE_EMOJI")
    assert PICTURE_WORDS == lab
    assert PICTURE_EMOJI == glyphs
    assert NAMED_REGIONS == (
        "top-left",
        "top",
        "top-right",
        "left",
        "center",
        "right",
        "bottom-left",
        "bottom",
        "bottom-right",
    )
    assert len(VISUAL_GAME_KINDS) == 9


def test_existing_games_keep_their_payloads_and_feedback():
    slide = _slide()
    match = build_match_term_game(slide, "obj-1")
    assert match.kind is GameKind.MATCH_TERM
    assert set(match.payload) == {"term", "options", "correct_index"}
    correct = match.payload["correct_index"]
    right = grade_game(match, {"selected_index": correct})
    wrong = grade_game(match, {"selected_index": (correct + 1) % 3})
    assert right.passed is True
    assert right.feedback == "Nice match."
    assert right.explanation == ""
    assert wrong.feedback == "Not quite — revisit the slide definition."

    order = build_order_steps_game(slide, "obj-1")
    assert set(order.payload) == {"steps_correct", "steps_shown"}
    solid = grade_game(order, {"ordered_steps": order.payload["steps_correct"]})
    assert solid.feedback == "Order looks solid."
    assert solid.passed is True

    gap = build_spot_gap_game(slide, "obj-1")
    assert set(gap.payload) == {"sentence_with_gap", "answer", "options", "correct_index"}
    spotted = grade_game(gap, {"selected_index": gap.payload["correct_index"]})
    missed = grade_game(gap, {"selected_text": "not-the-answer"})
    assert spotted.feedback == "You spotted it."
    assert missed.feedback == "Re-read the sentence and try the blank again."
    assert visual_challenge_problems(match) == []
    assert visual_challenge_problems(order) == []
    assert visual_challenge_problems(gap) == []


def test_pick_game_rotation_stays_on_the_original_three_kinds():
    slide = _slide()
    kinds = [pick_game_for_slide(slide, "obj", rotate_index=i).kind for i in range(4)]
    assert kinds == [
        GameKind.MATCH_TERM,
        GameKind.ORDER_STEPS,
        GameKind.SPOT_GAP,
        GameKind.MATCH_TERM,
    ]


def test_folding_accepts_plurals_and_accents_but_not_letter_aliases():
    assert fold_label("Café") == "cafe"
    assert labels_match("apple", "apples") is True
    assert labels_match("octopus", "octopu") is False
    assert labels_match("apple", "ay") is False


def test_unlabeled_photo_is_not_given_a_meaning():
    slide = _slide(
        picture_url="https://example.test/unknown.png",
        picture_alt="",
        title="Look",
        body="See the picture.",
    )
    assert build_image_to_word_game(slide) is None
    assert build_word_to_image_game(slide) is None
    assert pick_visual_game_for_slide(slide) is None
    with pytest.raises(VisualChallengeError) as raised:
        build_image_to_word_game(
            image={"image_url": "https://example.test/unknown.png"},
            options=["cat", "dog"],
            answer="cat",
        )
    assert any("not inferred" in problem for problem in raised.value.problems)


def test_catalog_glyph_cannot_be_relabeled():
    with pytest.raises(VisualChallengeError) as raised:
        build_image_to_word_game(
            image={"label": "truck", "glyph": PICTURE_EMOJI["apple"]},
            options=["truck", "apple"],
            answer="truck",
        )
    assert any(
        "catalog picture for" in problem and "apple" in problem
        for problem in raised.value.problems
    )


def test_image_to_word_uses_a_catalog_word_from_the_lesson():
    slide = _slide(index=4, title="The apple", body="An apple is a fruit. The ball is a toy.")
    game = build_image_to_word_game(slide, "obj")
    assert game is not None
    assert visual_challenge_problems(game) == []
    assert game.kind is GameKind.IMAGE_TO_WORD
    image = game.payload["image"]
    assert image["label"] == "apple"
    assert image["glyph"] == PICTURE_EMOJI["apple"]
    assert image["image_url"] == ""
    assert game.payload["options"][game.payload["correct_index"]] == "apple"
    correct = grade_game(game, {"selected_index": game.payload["correct_index"]})
    assert correct.passed is True
    assert "apple" in correct.feedback
    plural = grade_game(game, {"selected_text": "apples"})
    assert plural.passed is True
    almost = grade_game(game, {"selected_text": "aple"})
    assert almost.passed is False
    assert almost.feedback.startswith("Almost.")
    assert "apple" in almost.feedback
    wrong_index = (game.payload["correct_index"] + 1) % len(game.payload["options"])
    wrong = grade_game(game, {"selected_index": wrong_index})
    assert wrong.passed is False
    assert "apple" in wrong.feedback
    assert game.payload["options"][wrong_index] in wrong.feedback
    letter = grade_game(game, {"selected_text": "ay"})
    assert letter.passed is False


def test_photo_alt_wins_over_a_different_catalog_word():
    slide = _slide(
        title="Cat stories",
        body="The cat sat on the mat.",
        picture_url="https://example.test/brake.png",
        picture_alt="brake pedal",
    )
    game = build_image_to_word_game(slide, "obj")
    assert game is not None
    assert game.payload["answer"] == "brake pedal"
    assert game.payload["image"]["glyph"] == ""
    assert game.payload["image"]["image_url"].endswith("brake.png")
    assert "cat" not in game.payload["explanation"]
    word = build_word_to_image_game(slide, "obj")
    assert word is not None
    correct = next(
        card for card in word.payload["images"] if card["id"] == word.payload["correct_id"]
    )
    assert correct["label"] == "brake pedal"
    assert correct["image_url"].endswith("brake.png")
    distractor = next(card for card in word.payload["images"] if card["id"] != correct["id"])
    assert distractor["label"] != "brake pedal"
    missed = grade_game(word, {"selected_id": distractor["id"]})
    assert missed.passed is False
    assert "brake pedal" in missed.feedback
    assert distractor["label"] in missed.feedback


def test_word_to_image_grades_the_labeled_picture_only():
    game = build_word_to_image_game(word="zebra", option_count=3)
    assert game is not None
    assert visual_challenge_problems(game) == []
    right = grade_game(game, {"selected_id": game.payload["correct_id"]})
    assert right.passed is True
    assert "zebra" in right.explanation
    other = next(
        card for card in game.payload["images"] if card["id"] != game.payload["correct_id"]
    )
    wrong = grade_game(game, {"selected_id": other["id"]})
    assert wrong.passed is False
    assert "zebra" in wrong.feedback
    assert other["label"] in wrong.feedback


def test_hotspot_requires_the_named_region_not_a_neighbor():
    game = build_hotspot_game(
        regions=["center", "top-left"],
        correct_region="center",
        note="The author marked the center.",
        image={"label": "apple", "glyph": PICTURE_EMOJI["apple"]},
    )
    assert game is not None
    assert visual_challenge_problems(game) == []
    hit = grade_game(game, {"region": "center"})
    assert hit.passed is True
    assert "center" in hit.feedback
    assert "author marked" in hit.feedback
    miss = grade_game(game, {"region": "top-left"})
    assert miss.passed is False
    assert "top-left" in miss.feedback
    assert "center" in miss.feedback
    unknown = grade_game(game, {"region": "off-stage"})
    assert unknown.passed is False
    assert "not one of the marked spots" in unknown.feedback
    with pytest.raises(VisualChallengeError) as raised:
        build_hotspot_game(
            regions=[{"x": 0.2, "y": 0.4}, {"id": "center"}],
            correct_region="center",
        )
    assert any("coordinates are not graded" in problem for problem in raised.value.problems)
    assert build_hotspot_game(_slide()) is None


def test_classify_grades_the_authored_groups():
    game = build_classify_game(
        categories=["food", "animals"],
        items=[{"id": "apple", "label": "apple"}, {"id": "cat", "label": "cat"}],
        answer={"apple": "animals", "cat": "food"},
    )
    assert game is not None
    assert game.payload["items"][0]["glyph"] == PICTURE_EMOJI["apple"]
    outside = grade_game(
        game,
        {"assignments": {"apple": "food", "cat": "animals"}},
    )
    assert outside.passed is False
    assert "animals" in outside.feedback
    assert "apple" in outside.feedback
    authored = grade_game(
        game,
        {"assignments": {"apple": "animals", "cat": "food"}},
    )
    assert authored.passed is True
    partial = build_classify_game(
        categories=["food", "animals"],
        items=["apple", "cat", "fish"],
        answer={"apple": "food", "cat": "animals", "fish": "animals"},
    )
    assert partial is not None
    mixed = grade_game(
        partial,
        {"assignments": {"apple": "food", "cat": "animals", "fish": "food"}},
    )
    assert mixed.score == pytest.approx(2 / 3)
    assert mixed.passed is False
    assert "fish" in mixed.feedback
    assert "animals" in mixed.feedback


def test_sort_explains_the_authored_order():
    game = build_sort_game(
        items=[
            {"id": "seed", "label": "seed"},
            {"id": "sprout", "label": "sprout"},
            {"id": "tree", "label": "tree"},
        ]
    )
    assert game is not None
    assert visual_challenge_problems(game) == []
    right = grade_game(game, {"ordered_ids": ["seed", "sprout", "tree"]})
    assert right.passed is True
    assert "seed → sprout → tree" in right.feedback
    wrong = grade_game(game, {"ordered_ids": ["tree", "sprout", "seed"]})
    assert wrong.passed is False
    assert "seed" in wrong.feedback
    assert wrong.score == pytest.approx(1 / 3)
    with pytest.raises(VisualChallengeError):
        build_sort_game(items=["one", "two"], order_correct=["missing", "one"])


def test_label_placement_names_the_spot_and_the_label():
    game = build_label_placement_game(
        targets=["center", "top-left"],
        labels=["apple", "ball"],
        answer={"center": "apple", "top-left": "ball"},
        image={"label": "apple", "glyph": PICTURE_EMOJI["apple"]},
    )
    assert game is not None
    right = grade_game(
        game,
        {"placements": {"center": "apples", "top-left": "ball"}},
    )
    assert right.passed is True
    wrong = grade_game(
        game,
        {"placements": {"center": "ball", "top-left": "apple"}},
    )
    assert wrong.passed is False
    assert "center" in wrong.feedback
    assert "apple" in wrong.feedback
    assert "ball" in wrong.feedback
    with pytest.raises(VisualChallengeError) as raised:
        build_label_placement_game(
            targets=[{"x": 0.5, "y": 0.5}],
            labels=["apple"],
            answer={"center": "apple"},
        )
    assert any("coordinates are not graded" in problem for problem in raised.value.problems)


def test_picture_order_requires_a_real_picture():
    with pytest.raises(VisualChallengeError) as raised:
        build_picture_order_game(cards=[{"id": "1", "label": "seed"}, {"id": "2", "label": "tree"}])
    assert any("needs a picture" in problem for problem in raised.value.problems)
    game = build_picture_order_game(
        cards=[
            {"id": "1", "label": "apple"},
            {"id": "2", "label": "zebra"},
        ]
    )
    assert game is not None
    assert game.payload["cards_correct"][0]["glyph"] == PICTURE_EMOJI["apple"]
    assert game.payload["cards_shown"] != game.payload["cards_correct"]
    right = grade_game(game, {"ordered_ids": ["1", "2"]})
    assert right.passed is True
    wrong = grade_game(game, {"ordered_labels": ["zebra", "apple"]})
    assert wrong.passed is False
    assert "apple → zebra" in wrong.feedback


def test_spot_difference_uses_the_authored_note_not_the_pixels():
    with pytest.raises(VisualChallengeError) as raised:
        build_spot_difference_game(
            left={"label": "left scene", "image_url": "https://example.test/1.png"},
            right={"label": "right scene", "image_url": "https://example.test/2.png"},
            differences=[{"id": "star", "region": "top-left"}],
        )
    assert any("not compared as pixels" in problem for problem in raised.value.problems)
    game = build_spot_difference_game(
        left={"label": "left scene", "image_url": "https://example.test/1.png"},
        right={"label": "right scene", "image_url": "https://example.test/2.png"},
        differences=[
            {"id": "star", "region": "top-left", "note": "the star is only on the left"}
        ],
        decoys=[{"id": "sky", "region": "bottom"}],
    )
    assert game is not None
    assert "example.test" not in game.payload["explanation"]
    found = grade_game(game, {"selected_ids": ["star"]})
    assert found.passed is True
    decoy = grade_game(game, {"selected_ids": ["star", "sky"]})
    assert decoy.passed is False
    assert decoy.score == pytest.approx(0.5)
    assert "the star is only on the left" in decoy.feedback
    assert "bottom" in decoy.feedback
    assert "is not a difference" in decoy.feedback


def test_memory_pairs_explain_the_authored_match():
    slide = _slide(title="Apple and zebra", body="See the apple and the zebra.")
    assert catalog_words_in_text(slide.body) == ["apple", "zebra"]
    game = build_memory_pairs_game(slide, "obj")
    assert game is not None
    assert game.kind is GameKind.MEMORY_PAIRS
    assert {pair["id"] for pair in game.payload["pairs"]} == {"apple", "zebra"}
    apple = next(pair for pair in game.payload["pairs"] if pair["id"] == "apple")
    assert apple["left"]["glyph"] == PICTURE_EMOJI["apple"]
    links = [
        [pair["left"]["id"], pair["right"]["id"]] for pair in game.payload["pairs"]
    ]
    right = grade_game(game, {"matches": links})
    assert right.passed is True
    zebra = next(pair for pair in game.payload["pairs"] if pair["id"] == "zebra")
    swapped = grade_game(
        game,
        {
            "matches": [
                [apple["left"]["id"], zebra["right"]["id"]],
                [zebra["left"]["id"], apple["right"]["id"]],
            ]
        },
    )
    assert swapped.passed is False
    assert "apple" in swapped.feedback
    assert "pairs with" in swapped.feedback
    four = build_memory_pairs_game(words=["apple", "ball", "cat", "zebra"])
    assert four is not None
    pairs = four.payload["pairs"]
    almost = [[pair["left"]["id"], pair["right"]["id"]] for pair in pairs[:3]]
    partial = grade_game(four, {"matches": almost})
    assert partial.score == pytest.approx(0.75)
    assert partial.passed is True
    assert pairs[3]["left"]["label"] in partial.feedback
    assert build_memory_pairs_game(_slide()) is None
    with pytest.raises(VisualChallengeError) as raised:
        build_memory_pairs_game(words=["apple", "truck"])
    assert any("truck" in problem for problem in raised.value.problems)


def test_invalid_visual_payload_is_explained_instead_of_graded():
    bad = GameChallenge(
        game_id="g",
        kind=GameKind.HOTSPOT,
        title="Find the spot",
        prompt="Choose the marked region.",
        payload={"regions": [{"id": "center"}], "correct_region": "center", "explanation": "x"},
    )
    result = grade_game(bad, {"region": "center"})
    assert result.score == 0.0
    assert result.passed is False
    assert result.feedback.startswith("This challenge cannot be graded:")
    empty = grade_game(bad, None)  # type: ignore[arg-type]
    assert empty.feedback == "Send the answer as a response object."


def test_visual_rotation_skips_kinds_the_slide_cannot_support():
    one = _slide(title="One zebra", body="A zebra stands.")
    first = pick_visual_game_for_slide(one, rotate_index=0)
    memory_turn = pick_visual_game_for_slide(one, rotate_index=2)
    assert first is not None and first.kind is GameKind.IMAGE_TO_WORD
    assert memory_turn is not None and memory_turn.kind is GameKind.IMAGE_TO_WORD
    both = _slide(title="Apple and ball", body="An apple and a ball.")
    assert pick_visual_game_for_slide(both, rotate_index=2).kind is GameKind.MEMORY_PAIRS


def test_authored_spec_builds_the_requested_kind():
    game = visual_game_from_spec(
        {
            "kind": "spot_difference",
            "left": {"label": "moon", "glyph": PICTURE_EMOJI["moon"]},
            "right": {"label": "star", "glyph": PICTURE_EMOJI["star"]},
            "differences": [
                {"id": "moon", "region": "top", "note": "the moon is only on the left"}
            ],
        }
    )
    assert game is not None
    assert game.kind is GameKind.SPOT_DIFFERENCE
    assert visual_challenge_problems(game) == []
    assert visual_game_from_spec({"kind": "not-a-game"}) is None
    assert visual_game_from_spec({"kind": "match_term", "options": ["a", "b"]}) is None


def test_authored_picture_spec_is_the_game_the_lesson_plays():
    from theodore_course_studio.cert_multimodal import game_from_slide

    slide = _slide(
        title="Name it",
        game_spec={
            "kind": "image_to_word",
            "image": {"label": "cat", "glyph": PICTURE_EMOJI["cat"]},
            "options": ["cat", "dog"],
            "answer": "cat",
        },
    )
    game = pick_game_for_slide(slide, "obj")
    assert game.kind is GameKind.IMAGE_TO_WORD
    direct = game_from_slide(slide, "obj")
    assert direct is not None and direct.kind is GameKind.IMAGE_TO_WORD
    assert grade_game(game, {"selected_index": game.payload["correct_index"]}).passed is True


def test_checkpoint_play_prefers_a_catalog_picture(tmp_path):
    from theodore_course_studio.generate import CourseBuilder
    from theodore_course_studio.teach import TeachEngine
    from theodore_course_studio.types import CategoryId, StudioCourse

    builder = CourseBuilder(data_dir=tmp_path / "data")
    builder.save_course(
        StudioCourse(
            course_id="picture-game",
            title="Pictures",
            category=CategoryId.OTHER,
            slides=[
                CourseSlide(
                    index=0,
                    title="The cat",
                    body="A cat is an animal.",
                    narration="A cat is an animal.",
                )
            ],
            status="ready",
        )
    )
    engine = TeachEngine(builder)
    engine.start(session_id="plain", course_id="picture-game", use_voice_agent=False)
    engine.start(session_id="pic", course_id="picture-game", use_voice_agent=False)
    assert engine.game_for_current("plain").kind is GameKind.MATCH_TERM
    assert engine.game_for_current("pic", prefer_visual=True).kind is GameKind.IMAGE_TO_WORD
