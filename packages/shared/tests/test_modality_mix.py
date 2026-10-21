"""Page counts from modality ratings, including delivery-context filters."""

from collections import Counter

from aoep_shared.modality_mix import (
    allocate_modality_mix,
    resolve_delivery_context,
)

EXAMPLE = {
    "tutoring": 8,
    "gaming": 10,
    "reading": 1,
    "presentation": 2,
    "video": 6,
    "live_teacher": 9,
}


def _counts(mix: dict) -> dict:
    return mix["counts"]


def test_36_page_exact_weights():
    mix = allocate_modality_mix(EXAMPLE, 36, "course")
    assert _counts(mix) == {
        "tutoring": 8,
        "gaming": 10,
        "reading": 1,
        "presentation": 2,
        "video": 6,
        "live_teacher": 9,
    }
    assert sum(_counts(mix).values()) == 36
    assert mix["removed"] == []
    tutoring = next(row for row in mix["rows"] if row["modality"] == "tutoring")
    assert tutoring["percent"] == 22.2
    assert any("22.2%" in line and "8 pages" in line for line in mix["lines"])
    assert mix["lines"][0].startswith("36 pages")


def test_10_page_tutoring_is_2():
    mix = allocate_modality_mix(EXAMPLE, 10, "course")
    assert _counts(mix)["tutoring"] == 2
    assert sum(_counts(mix).values()) == 10
    assert Counter(mix["assignment"])["tutoring"] == 2


def test_sub_half_page_drop_then_renormalize():
    mix = allocate_modality_mix(EXAMPLE, 10, "course")
    removed = {row["modality"]: row for row in mix["removed"]}
    assert removed["reading"]["reason"] == "below_half_page"
    assert removed["reading"]["share_pages"] == 0.28
    assert "reading" not in _counts(mix) or _counts(mix)["reading"] == 0
    assert _counts(mix)["gaming"] == 3
    assert any("less than half a page" in line and "Reading" in line for line in mix["lines"])
    assert any("scaled to 100%" in line for line in mix["lines"])

    # Without the drop, reading's remainder would take a seat and tutoring
    # would stay at 1. Renormalizing gives tutoring the extra page.
    narrow = allocate_modality_mix(
        {"tutoring": 3, "gaming": 3, "reading": 1},
        3,
        "course",
    )
    assert narrow["counts"]["tutoring"] == 2
    assert narrow["counts"]["gaming"] == 1
    assert "reading" not in narrow["counts"] or narrow["counts"].get("reading", 0) == 0
    assert sum(narrow["counts"].values()) == 3


def test_live_group_drops_tutoring_and_reallocates():
    mix = allocate_modality_mix(EXAMPLE, 36, "live_group")
    assert mix["counts"].get("tutoring", 0) == 0
    removed = next(row for row in mix["removed"] if row["modality"] == "tutoring")
    assert removed["reason"] == "live_group"
    assert mix["counts"]["gaming"] == 13
    assert mix["counts"]["reading"] == 1
    assert mix["counts"]["presentation"] == 2
    assert mix["counts"]["video"] == 8
    assert mix["counts"]["live_teacher"] == 12
    assert sum(mix["counts"].values()) == 36
    assert any("live group" in line and "Tutoring" in line for line in mix["lines"])
    assert "before the percentages" in mix["lines"][1]


def test_on_the_go_drops_video():
    mix = allocate_modality_mix(EXAMPLE, 36, "on_the_go")
    assert mix["counts"].get("video", 0) == 0
    removed = next(row for row in mix["removed"] if row["modality"] == "video")
    assert removed["reason"] == "on_the_go"
    assert mix["counts"]["tutoring"] == 10
    assert mix["counts"]["gaming"] == 12
    assert mix["counts"]["reading"] == 1
    assert mix["counts"]["presentation"] == 2
    assert mix["counts"]["live_teacher"] == 11
    assert sum(mix["counts"].values()) == 36
    assert any("on the go" in line and "Video" in line for line in mix["lines"])


def test_video_game_keeps_only_gaming_and_tutoring():
    mix = allocate_modality_mix(EXAMPLE, 36, "video_game")
    assert set(mix["counts"]) == {"gaming", "tutoring"}
    assert mix["counts"]["gaming"] == 20
    assert mix["counts"]["tutoring"] == 16
    assert sum(mix["counts"].values()) == 36
    dropped = {row["modality"] for row in mix["removed"]}
    assert dropped == {"reading", "presentation", "video", "live_teacher"}
    assert all(row["reason"] == "video_game" for row in mix["removed"])
    assert "Tutoring" in "".join(mix["lines"])
    assert "Gaming" in "".join(mix["lines"])


def test_counts_always_sum_to_page_count():
    ratings = dict(EXAMPLE)
    for pages in (1, 2, 7, 10, 36):
        for context in ("course", "live_group", "on_the_go", "video_game"):
            mix = allocate_modality_mix(ratings, pages, context)
            assert sum(mix["counts"].values()) == pages
            assert len(mix["assignment"]) == pages
            assert sum(Counter(mix["assignment"]).values()) == pages


def test_sub_half_page_cannot_empty_the_course():
    mix = allocate_modality_mix(
        {key: 1 for key in ("tutoring", "gaming", "reading", "presentation", "video", "live_teacher")},
        1,
        "course",
    )
    assert sum(mix["counts"].values()) == 1
    assert mix["counts"]["tutoring"] == 1
    assert len(mix["removed"]) == 5


def test_delivery_context_uses_stored_mode():
    assert resolve_delivery_context(class_type="solo") == ("course", "in-app course")
    assert resolve_delivery_context(class_type="group")[0] == "live_group"
    audio = resolve_delivery_context(class_type="group", audio_only=True)
    assert audio[0] == "on_the_go"
    assert "on the go" in audio[1]
    game = resolve_delivery_context(class_type="group", mode="arcade")
    assert game[0] == "video_game"
    assert "video game" in game[1]
    assert resolve_delivery_context(mode="drive")[0] == "on_the_go"


def test_assigned_format_changes_the_storyboard():
    from aoep_shared.cert_storyboard.generic import build_generic_storyboard

    gaming = build_generic_storyboard(
        lesson_id="sample",
        slide_index=0,
        title="Supply and demand",
        body="Price moves when buyers and sellers change their plans.",
        narration="Watch how price moves.",
        learning_modality="gaming",
    )
    reading = build_generic_storyboard(
        lesson_id="sample",
        slide_index=1,
        title="Supply and demand",
        body="Price moves when buyers and sellers change their plans.",
        narration="Read how price moves.",
        learning_modality="reading",
    )
    assert gaming.learning_modality == "gaming"
    assert gaming.profile_mode == "hands_on"
    assert gaming.activity_prompt.startswith("Game:")
    assert reading.profile_mode == "reading"
    assert reading.activity_prompt.startswith("Reading:")
    assert len(gaming.segment.scene.cast) > len(reading.segment.scene.cast)
