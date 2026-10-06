"""Presentation styles, sentence cues, and the visual timeline compiler."""

from __future__ import annotations

import pytest

from theodore_course_studio.presentation_director import (
    PresentationError,
    apply_reduced_motion,
    compile_cue_times,
    presentation_for_slide,
    presentations_for_slides,
    sentence_spans,
    validate_presentation_script,
)
from theodore_course_studio.presentation_styles import (
    PRESENTATION_STYLES,
    STYLE_FAMILIES,
    assign_presentation_style,
    rank_presentation_styles,
    select_ranked_style,
    split_sentences,
    styles_in_family,
)
from theodore_course_studio.types import (
    CourseSlide,
    PresentationCheckpoint,
    PresentationScript,
    VisualCue,
    VisualLayer,
)

LONG = (
    "The rain began at dawn. "
    "The class moved inside together. "
    "They opened their books. "
    "The lesson started quietly."
)
TIMELINE = (
    "First, check the mirror. "
    "Then signal early. "
    "Next look over your shoulder. "
    "Finally change lanes smoothly."
)


def slide(**kwargs) -> CourseSlide:
    data = {"index": 0, "title": "Slide", "body": "Hello.", "narration": "Hello."}
    data.update(kwargs)
    return CourseSlide(**data)


def test_registry_has_forty_two_explicit_styles_in_four_families():
    assert len(PRESENTATION_STYLES) >= 42
    assert len(PRESENTATION_STYLES) == 48
    seen: set[str] = set()
    for family in STYLE_FAMILIES:
        group = styles_in_family(family)
        assert len(group) == 12
        for style in group:
            assert style.family == family
            assert style.style_id not in seen
            assert style.label
            assert style.summary
            assert style.reduced_motion in {"static", "instant"}
            seen.add(style.style_id)
    assert seen == set(PRESENTATION_STYLES)


@pytest.mark.parametrize(
    ("built", "style_id"),
    [
        (slide(title="Hello", body="Hello there.", narration="Hello there."), "narrative-title-card"),
        (slide(title="Rain", body=LONG, narration=LONG), "narrative-story-arc"),
        (
            slide(title="Sign", body='The sign reads "Stop here."', narration='The sign reads "Stop here."'),
            "narrative-quote-pull",
        ),
        (
            slide(
                title="Rain",
                body="Once the rain started, we walked in.",
                narration="Once the rain started, we walked in.",
            ),
            "narrative-scene-set",
        ),
        (
            slide(title="Mina", body='Mina said, "Stop here."', narration='Mina said, "Stop here."'),
            "narrative-dialogue",
        ),
        (
            slide(
                title="Light",
                body="We stop because the light is red.",
                narration="We stop because the light is red.",
            ),
            "narrative-cause-effect",
        ),
        (slide(title="Lane change", body=TIMELINE, narration=TIMELINE), "narrative-timeline"),
        (
            slide(
                title="Lane",
                body="Wait here, however, if the lane is open.",
                narration="Wait here, however, if the lane is open.",
            ),
            "narrative-contrast",
        ),
        (
            slide(
                title="Turn",
                body="Think about the last turn.",
                narration="Think about the last turn.",
            ),
            "narrative-reflection",
        ),
        (
            slide(
                title="Review",
                body="Remember the rule and review it.",
                narration="Remember the rule and review it.",
            ),
            "narrative-recap",
        ),
        (slide(title="Ready?", body="Are you ready?", narration="Are you ready?"), "narrative-hook"),
        (
            slide(
                title="Next",
                body="Study next and finish the block.",
                narration="Study next and finish the block.",
            ),
            "narrative-closing",
        ),
        (
            slide(
                title="Yield",
                body="Yield to traffic.",
                narration="Yield to traffic.",
                picture_url="https://example.test/yield.png",
                picture_alt="Yield sign",
            ),
            "picture-hero-still",
        ),
        (
            slide(title="Rain", body=LONG, narration=LONG, picture_url="pic.png", picture_alt="Rain"),
            "picture-ken-burns",
        ),
        (
            slide(
                title="Merge",
                body="Watch the merge.",
                narration="Watch the merge.",
                video_url="clip.svg",
                video_caption="Merge clip",
            ),
            "picture-motion-card",
        ),
        (
            slide(title="Rain", body=LONG, narration=LONG, video_url="clip.svg"),
            "picture-video-lead",
        ),
        (
            slide(
                title="Cross",
                body="Cross the street.",
                narration="Cross the street.",
                storyboard_svg="<svg></svg>",
                storyboard_concept="Crossing",
            ),
            "picture-storyboard",
        ),
        (
            slide(
                title="Wave",
                body="First, look. Then wave.",
                narration="First, look. Then wave.",
                storyboard_svg="<svg></svg>",
            ),
            "picture-storyboard-steps",
        ),
        (
            slide(
                title="Signs",
                body="A yield sign versus a stop sign.",
                narration="A yield sign versus a stop sign.",
                picture_url="pic.png",
            ),
            "picture-compare",
        ),
        (
            slide(
                title="Signs",
                body="See these signs.",
                narration="See these signs.",
                picture_url="pic.png",
                examples=["Yield", "Stop"],
            ),
            "picture-example-callouts",
        ),
        (
            slide(
                title="Stop",
                body="Stop.",
                narration="Stop.",
                picture_url="pic.png",
                picture_alt="A red octagon with white letters spelling STOP",
            ),
            "picture-detail-focus",
        ),
        (
            slide(
                title="Merge",
                body="Watch the merge.",
                narration="Watch the merge.",
                picture_url="pic.png",
                video_url="clip.svg",
                storyboard_svg="<svg></svg>",
            ),
            "picture-media-stack",
        ),
        (
            slide(
                title="Cold holding",
                body="Cold holding means food stays cold.",
                narration="Cold holding means food stays cold.",
            ),
            "text-definition",
        ),
        (slide(title="Speed", body="The limit is 25.", narration="The limit is 25."), "text-big-number"),
        (
            slide(
                title="Signs",
                body="A yield sign versus a stop sign.",
                narration="A yield sign versus a stop sign.",
            ),
            "text-comparison",
        ),
        (
            slide(title="Look", body="First, stop. Then look.", narration="First, stop. Then look."),
            "text-steps",
        ),
        (
            slide(
                title="School bus",
                body="Never pass a stopped school bus.",
                narration="Never pass a stopped school bus.",
            ),
            "text-warning",
        ),
        (
            slide(
                title="Habits",
                body="Two habits.",
                narration="Two habits.",
                examples=["Yield early", "Stop fully"],
            ),
            "text-bullets",
        ),
        (
            slide(
                title="Pre-trip",
                body="- Check mirrors\n- Check lights",
                narration="Check the car.",
            ),
            "text-checklist",
        ),
        (
            slide(
                title="Regulatory",
                body="Which sign is regulatory?",
                narration="Which sign is regulatory?",
                quiz_spec={"prompt": "Which sign is regulatory?", "choices": ["Stop", "Yield"]},
            ),
            "challenge-choice-grid",
        ),
        (
            slide(
                title="Check",
                body="What should you do?",
                narration="What should you do?",
                quiz_spec={"prompt": "What should you do?"},
            ),
            "challenge-question-card",
        ),
        (
            slide(
                title="Zone",
                body="Food safety.",
                narration="Food safety.",
                quiz_spec={
                    "prompt": "Why is the zone dangerous?",
                    "explanation": "Food grows bacteria quickly.",
                    "choices": ["Heat", "Time"],
                },
            ),
            "challenge-explain-why",
        ),
        (
            slide(
                title="Gap",
                body="Find what is missing.",
                narration="Find what is missing.",
                game_spec={"kind": "spot_gap", "prompt": "Find the missing piece."},
            ),
            "challenge-spot-gap",
        ),
        (
            slide(
                title="Match",
                body="Pair the term.",
                narration="Pair the term.",
                game_spec={"kind": "match_term", "prompt": "Pair the term."},
            ),
            "challenge-match",
        ),
        (
            slide(
                title="Order",
                body="Put these in order.",
                narration="Put these in order.",
                game_spec={"kind": "order_steps", "prompt": "Order the items.", "steps": ["A", "B"]},
            ),
            "challenge-sequence",
        ),
        (
            slide(
                title="Distances",
                body="Say them aloud.",
                narration="Say them aloud.",
                activity_prompt="Name the three distances.",
            ),
            "challenge-activity",
        ),
        (
            slide(
                title="Turn",
                body="Look back.",
                narration="Look back.",
                activity_prompt="Think about the last turn you made.",
            ),
            "challenge-reflect",
        ),
        (
            slide(
                title="Handbook checkpoint",
                body="Pause and recall the rule.",
                narration="Pause and recall the rule.",
            ),
            "challenge-checkpoint",
        ),
        (
            slide(
                title="Counts",
                body="Practice the count.",
                narration="Practice the count.",
                examples=["One second", "Two seconds"],
            ),
            "challenge-try-it",
        ),
        (
            slide(title="Drill", body="Practice the stop.", narration="Practice the stop."),
            "challenge-practice",
        ),
        (
            slide(
                title="Sort",
                body="Can you sort these?",
                narration="Can you sort these?",
                game_spec={"kind": "sort", "prompt": "Sort the items."},
            ),
            "challenge-pause",
        ),
    ],
)
def test_assignment_follows_content_and_assets(built: CourseSlide, style_id: str):
    chosen = assign_presentation_style(built)
    assert chosen.style_id == style_id
    again = assign_presentation_style(built)
    assert again.style_id == chosen.style_id

    script = presentation_for_slide(built)
    assert script.style_id == style_id
    assert script.family == PRESENTATION_STYLES[style_id].family
    assert script.layout == PRESENTATION_STYLES[style_id].layout
    assert script.sentence_count >= 1
    assert script.layers
    assert script.cues
    validate_presentation_script(script)
    for cue in script.cues:
        assert cue.start_sentence <= cue.end_sentence < script.sentence_count
        assert cue.duration_s > 0
        assert cue.start_s + cue.duration_s <= script.duration_s + 0.01
        assert cue.layer_ids
    if script.family == "challenge":
        assert script.checkpoints
        assert script.checkpoints[0].prompt
        assert 0 <= script.checkpoints[0].at_sentence < script.sentence_count
        assert 0 <= script.checkpoints[0].at_s <= script.duration_s + 0.01
    if script.family == "picture":
        assert script.source == "legacy"
    else:
        assert script.source == "inferred"


def test_same_content_keeps_its_style_when_only_the_slide_key_changes():
    words = {"title": "Hello", "body": "Hello there.", "narration": "Hello there."}
    first = assign_presentation_style(slide(slide_key="demo.one", **words))
    second = assign_presentation_style(slide(slide_key="demo.two", **words))
    assert first.style_id == second.style_id == "narrative-title-card"


def test_assets_and_quiz_move_the_same_words_into_another_family():
    words = slide(slide_key="same.words", title="Hello", body="Hello there.", narration="Hello there.")
    assert assign_presentation_style(words).family == "narrative"
    pictured = words.model_copy(update={"picture_url": "a.png"})
    assert assign_presentation_style(pictured).family == "picture"
    quizzed = words.model_copy(
        update={"quiz_spec": {"prompt": "Hello?", "choices": ["Yes", "No"]}}
    )
    assert assign_presentation_style(quizzed).family == "challenge"
    assert assign_presentation_style(quizzed).style_id == "challenge-choice-grid"


def test_required_assets_drop_styles_that_cannot_run():
    hero = slide(
        title="Yield",
        body="Yield to traffic.",
        narration="Yield to traffic.",
        picture_url="pic.png",
    )
    ranked = [style.style_id for _, style in rank_presentation_styles(hero)]
    assert ranked[0] == "picture-hero-still"
    assert "picture-captioned" in ranked
    assert "picture-split-copy" in ranked
    assert "picture-video-lead" not in ranked
    assert "picture-storyboard" not in ranked

    board = slide(
        title="Cross",
        body="Cross the street.",
        narration="Cross the street.",
        storyboard_svg="<svg></svg>",
    )
    board_ids = [style.style_id for _, style in rank_presentation_styles(board)]
    assert board_ids[0] == "picture-storyboard"
    assert "picture-hero-still" not in board_ids
    assert "picture-storyboard-steps" not in board_ids

    defined = slide(
        title="Cold holding",
        body="Cold holding means food stays cold.",
        narration="Cold holding means food stays cold.",
    )
    defined_ids = [style.style_id for _, style in rank_presentation_styles(defined)]
    assert defined_ids[0] == "text-definition"
    assert "text-key-term" in defined_ids
    assert "text-two-column" in defined_ids
    assert "text-passage" in defined_ids


def test_adjacent_styles_do_not_repeat_and_pins_do():
    first = slide(slide_key="a", title="Yield", body="Yield.", narration="Yield.", picture_url="a.png")
    second = slide(slide_key="b", title="Yield", body="Yield.", narration="Yield.", picture_url="b.png")
    scripts = presentations_for_slides([first, second])
    assert scripts[0].style_id == "picture-hero-still"
    assert scripts[1].style_id != scripts[0].style_id
    assert scripts[1].family == "picture"
    again = assign_presentation_style(second, previous_style_id=scripts[0].style_id)
    assert again.style_id == scripts[1].style_id

    pinned = first.model_copy(update={"presentation_style": "text-warning"})
    assert assign_presentation_style(pinned, previous_style_id="text-warning").style_id == "text-warning"
    with pytest.raises(ValueError, match="unknown presentation style"):
        assign_presentation_style(first.model_copy(update={"presentation_style": "not-a-style"}))


def test_tie_break_uses_the_slide_key_and_can_avoid_the_previous_style():
    specs = [
        PRESENTATION_STYLES["narrative-title-card"],
        PRESENTATION_STYLES["narrative-hook"],
        PRESENTATION_STYLES["narrative-recap"],
    ]
    ranked = [(10, spec) for spec in specs]
    first = select_ranked_style(ranked, slide_key="alpha")
    assert select_ranked_style(ranked, slide_key="alpha").style_id == first.style_id
    avoided = select_ranked_style(ranked, slide_key="alpha", previous_style_id=first.style_id)
    assert avoided.style_id != first.style_id
    ids = {
        select_ranked_style(ranked, slide_key=str(index)).style_id
        for index in range(30)
    }
    assert len(ids) > 1


def test_sentence_ranges_compile_to_seconds():
    assert split_sentences("Leave 3.5 seconds. Then count.") == [
        "Leave 3.5 seconds.",
        "Then count.",
    ]
    sentences = split_sentences("Hi. This sentence is much longer than the first one.")
    spans = sentence_spans(sentences, 10)
    assert spans[0][0] == 0
    assert spans[-1][1] == pytest.approx(10)
    assert spans[0][1] - spans[0][0] < spans[1][1] - spans[1][0]
    compiled = compile_cue_times(
        [VisualCue(start_sentence=0, end_sentence=1, layer_ids=["body"])],
        sentences,
        10,
    )
    assert compiled[0].start_s == 0
    assert compiled[0].duration_s == pytest.approx(10, abs=0.02)

    script = presentation_for_slide(slide(title="Lane change", body=TIMELINE, narration=TIMELINE))
    assert script.style_id == "narrative-timeline"
    body_cues = [cue for cue in script.cues if cue.layer_ids == ["body"]]
    assert [cue.start_sentence for cue in body_cues] == [0, 1, 2, 3]
    assert [cue.end_sentence for cue in body_cues] == [0, 1, 2, 3]
    starts = [cue.start_s for cue in body_cues]
    assert starts == sorted(starts)
    assert starts[0] < starts[-1]
    assert all(cue.enter == "draw" for cue in body_cues)


def test_legacy_picture_video_and_storyboard_slides_compile_layers():
    picture = presentation_for_slide(
        slide(
            slide_key="legacy.picture",
            title="Yield",
            body="Yield to traffic.",
            narration="Yield to traffic.",
            picture_url="https://example.test/yield.png",
            picture_alt="Yield sign",
        )
    )
    assert picture.source == "legacy"
    assert picture.style_id == "picture-hero-still"
    kinds = {layer.kind for layer in picture.layers}
    assert {"picture", "title", "body"} <= kinds
    assert "video" not in kinds
    assert "storyboard" not in kinds
    assert any(layer.asset_url.endswith("yield.png") for layer in picture.layers)
    assert len(picture.layers) >= 2

    video = presentation_for_slide(
        slide(
            title="Merge",
            body="Watch the merge.",
            narration="Watch the merge.",
            video_url="https://example.test/merge.svg",
        )
    )
    assert video.source == "legacy"
    assert any(layer.kind == "video" and layer.asset_url.endswith("merge.svg") for layer in video.layers)
    assert video.layers[[layer.kind for layer in video.layers].index("video")].motion == "pulse"

    board = presentation_for_slide(
        slide(
            title="Cross",
            body="Cross the street.",
            narration="Cross the street.",
            storyboard_svg="<svg id='cross'></svg>",
            storyboard_concept="Crossing",
        )
    )
    story = next(layer for layer in board.layers if layer.kind == "storyboard")
    assert story.svg == "<svg id='cross'></svg>"
    assert story.alt == "Crossing"
    assert story.motion == "draw"

    stacked = presentation_for_slide(
        slide(
            title="Merge",
            body="Watch the merge.",
            narration="Watch the merge.",
            picture_url="pic.png",
            video_url="clip.svg",
            storyboard_svg="<svg></svg>",
        )
    )
    assert stacked.style_id == "picture-media-stack"
    assert {"picture", "video", "storyboard", "title", "body"} <= {
        layer.kind for layer in stacked.layers
    }
    assert len(stacked.layers) >= 5


def test_authored_layers_cues_and_checkpoints_compile():
    built = slide(
        title="Custom",
        body="Alpha. Beta.",
        narration="Alpha. Beta.",
        visual_layers=[VisualLayer(layer_id="note", kind="callout", text="Alpha")],
        visual_cues=[VisualCue(start_sentence=0, end_sentence=0, layer_ids=["note"])],
        presentation_checkpoints=[
            PresentationCheckpoint(at_sentence=1, kind="pause", prompt="Hold here")
        ],
    )
    script = presentation_for_slide(built)
    assert script.source == "authored"
    note = next(cue for cue in script.cues if cue.layer_ids == ["note"])
    assert note.start_s == 0
    assert note.duration_s < script.duration_s
    assert script.checkpoints[0].checkpoint_id == "checkpoint-1"
    assert script.checkpoints[0].prompt == "Hold here"
    assert script.checkpoints[0].at_s > 0
    assert any(layer.layer_id == "note" for layer in script.layers)


def test_explicit_script_compiles_sentence_ranges_and_keeps_layout():
    built = slide(
        title="Steps",
        body="First stop. Then look.",
        narration="First stop. Then look.",
        presentation_script=PresentationScript(
            style_id="text-steps",
            family="narrative",
            layout="steps",
            duration_s=3,
            layers=[
                VisualLayer(layer_id="title", kind="title", text="Steps"),
                VisualLayer(layer_id="body", kind="body", text="First stop. Then look."),
            ],
            cues=[
                VisualCue(
                    start_sentence=0,
                    end_sentence=1,
                    layer_ids=["title", "body"],
                    enter="draw",
                )
            ],
        ),
    )
    script = presentation_for_slide(built)
    assert script.source == "explicit"
    assert script.family == "text"
    assert script.layout == "steps"
    assert script.duration_s >= 3
    assert script.cues[0].start_s == 0
    assert script.cues[0].layer_ids == ["title", "body"]
    assert script.cues[0].start_s + script.cues[0].duration_s <= script.duration_s + 0.01
    validate_presentation_script(script)


def test_reduced_motion_falls_back_without_dropping_layers():
    pictured = slide(title="Rain", body=LONG, narration=LONG, picture_url="pic.png", picture_alt="Rain")
    moving = presentation_for_slide(pictured)
    assert moving.style_id == "picture-ken-burns"
    assert any(layer.motion == "ken-burns" for layer in moving.layers)

    still = presentation_for_slide(pictured, reduced_motion=True)
    assert still.reduced_motion is True
    assert still.style_id == "picture-ken-burns"
    assert any(layer.kind == "picture" and layer.asset_url == "pic.png" for layer in still.layers)
    assert all(layer.motion == "none" for layer in still.layers)
    assert all(cue.enter == "none" and cue.hold == "none" and cue.exit == "none" for cue in still.cues)
    assert len(still.cues) == len(still.layers)
    assert all(cue.end_sentence == still.sentence_count - 1 for cue in still.cues)

    timeline = presentation_for_slide(slide(title="Lane change", body=TIMELINE, narration=TIMELINE))
    assert len([cue for cue in timeline.cues if cue.layer_ids == ["body"]]) == 4
    quiet = presentation_for_slide(
        slide(title="Lane change", body=TIMELINE, narration=TIMELINE),
        reduced_motion=True,
    )
    assert len([cue for cue in quiet.cues if cue.layer_ids == ["body"]]) == 1
    assert quiet.cues[0].enter == "none"

    instant = presentation_for_slide(
        slide(
            title="Arc",
            body="Alpha. Beta.",
            narration="Alpha. Beta.",
            presentation_script=PresentationScript(
                style_id="narrative-story-arc",
                family="narrative",
                duration_s=4,
                layers=[VisualLayer(layer_id="body", kind="body", text="Alpha. Beta.")],
                cues=[
                    VisualCue(start_sentence=0, end_sentence=0, layer_ids=["body"], enter="type-on"),
                    VisualCue(start_sentence=1, end_sentence=1, layer_ids=["body"], enter="type-on"),
                ],
            ),
        ),
        reduced_motion=True,
    )
    assert instant.reduced_motion is True
    assert len(instant.cues) == 2
    assert [cue.start_sentence for cue in instant.cues] == [0, 1]
    assert all(cue.enter == "none" for cue in instant.cues)
    assert apply_reduced_motion(moving, policy="static").reduced_motion is True


def test_validator_rejects_cues_and_checkpoints_outside_bounds():
    layer = VisualLayer(layer_id="body", kind="body", text="Hi")
    with pytest.raises(PresentationError, match="outside"):
        presentation_for_slide(
            slide(
                narration="Only one sentence.",
                body="Only one sentence.",
                presentation_script=PresentationScript(
                    duration_s=3,
                    layers=[layer],
                    cues=[VisualCue(start_sentence=0, end_sentence=3, layer_ids=["body"])],
                ),
            )
        )

    with pytest.raises(PresentationError, match="reversed"):
        validate_presentation_script(
            PresentationScript(
                duration_s=3,
                sentence_count=3,
                layers=[layer],
                cues=[
                    VisualCue(
                        start_sentence=2,
                        end_sentence=1,
                        start_s=0,
                        duration_s=1,
                        layer_ids=["body"],
                    )
                ],
            )
        )
    with pytest.raises(PresentationError, match="after script duration"):
        validate_presentation_script(
            PresentationScript(
                duration_s=2,
                sentence_count=1,
                layers=[layer],
                cues=[
                    VisualCue(
                        start_sentence=0,
                        end_sentence=0,
                        start_s=1.5,
                        duration_s=1,
                        layer_ids=["body"],
                    )
                ],
            )
        )
    with pytest.raises(PresentationError, match="duplicate layer_id"):
        validate_presentation_script(
            PresentationScript(
                duration_s=2,
                sentence_count=1,
                layers=[layer, VisualLayer(layer_id="body", kind="title", text="Hi")],
                cues=[
                    VisualCue(
                        start_sentence=0,
                        end_sentence=0,
                        start_s=0,
                        duration_s=2,
                        layer_ids=["body"],
                    )
                ],
            )
        )
    with pytest.raises(PresentationError, match="unknown layer"):
        validate_presentation_script(
            PresentationScript(
                duration_s=2,
                sentence_count=1,
                layers=[layer],
                cues=[
                    VisualCue(
                        start_sentence=0,
                        end_sentence=0,
                        start_s=0,
                        duration_s=2,
                        layer_ids=["missing"],
                    )
                ],
            )
        )
    with pytest.raises(PresentationError, match="checkpoint"):
        validate_presentation_script(
            PresentationScript(
                duration_s=2,
                sentence_count=1,
                layers=[layer],
                cues=[
                    VisualCue(
                        start_sentence=0,
                        end_sentence=0,
                        start_s=0,
                        duration_s=2,
                        layer_ids=["body"],
                    )
                ],
                checkpoints=[PresentationCheckpoint(checkpoint_id="late", at_sentence=4, at_s=0)],
            )
        )


def test_older_slide_json_stays_valid_without_presentation_fields():
    built = CourseSlide.model_validate({"index": 0, "title": "Old", "body": "Old body."})
    assert built.presentation_script is None
    assert built.presentation_style == ""
    assert built.visual_layers == []
    assert built.visual_cues == []
    assert built.presentation_checkpoints == []
    assert built.avatar_script is None
    script = presentation_for_slide(built)
    assert script.source == "inferred"
    assert script.style_id == "narrative-title-card"
    restored = CourseSlide.model_validate(built.model_dump())
    assert restored.model_dump() == built.model_dump()
