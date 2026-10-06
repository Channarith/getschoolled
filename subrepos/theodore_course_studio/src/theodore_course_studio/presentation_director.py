"""Compile a slide into a timed visual timeline.

Sentence-range cues become seconds against the same narration clock the avatar
director uses. Legacy slides that only carry a picture, video, or storyboard
still compile. Reduced motion keeps every layer and drops the animation.
"""

from __future__ import annotations

from .avatar_director import narration_duration
from .presentation_styles import (
    PRESENTATION_STYLES,
    StyleSpec,
    assign_presentation_style,
    sentences_for,
    spoken_text,
    step_style,
)
from .types import (
    CheckpointKind,
    CourseSlide,
    PresentationCheckpoint,
    PresentationScript,
    PresentationSource,
    ReducedMotionPolicy,
    VisualCue,
    VisualLayer,
    VisualMotion,
)

_MEDIA_MOTIONS = frozenset({"none", "fade", "slide", "ken-burns", "pulse"})


class PresentationError(ValueError):
    """A visual timeline cue, layer, or checkpoint is outside its bounds."""


def sentence_spans(sentences: list[str], duration_s: float) -> list[tuple[float, float]]:
    """Map each sentence to ``(start_s, end_s)`` inside ``duration_s``.

    Longer sentences take more of the clock. The first span starts at 0 and
    the last span ends on ``duration_s``.
    """
    if not sentences:
        raise PresentationError("cannot time an empty sentence list")
    if duration_s <= 0:
        raise PresentationError("duration must be positive")
    weights = [max(1, len(sentence)) for sentence in sentences]
    total = float(sum(weights))
    cursor = 0.0
    spans: list[tuple[float, float]] = []
    last = len(sentences) - 1
    for index, weight in enumerate(weights):
        end = float(duration_s) if index == last else cursor + duration_s * (weight / total)
        spans.append((cursor, end))
        cursor = end
    rounded: list[tuple[float, float]] = []
    for index, (start, end) in enumerate(spans):
        start_s = round(start, 3)
        end_s = round(float(duration_s) if index == last else end, 3)
        if end_s < start_s:
            end_s = start_s
        rounded.append((start_s, end_s))
    return rounded


def compile_cue_times(
    cues: list[VisualCue],
    sentences: list[str],
    duration_s: float,
) -> list[VisualCue]:
    """Fill ``start_s`` and ``duration_s`` from each cue's sentence range."""
    spans = sentence_spans(sentences, duration_s)
    count = len(spans)
    compiled: list[VisualCue] = []
    for cue in cues:
        out_of_range = cue.start_sentence >= count or cue.end_sentence >= count
        if cue.end_sentence < cue.start_sentence or out_of_range:
            raise PresentationError(
                f"cue sentences {cue.start_sentence}-{cue.end_sentence} "
                f"outside 0-{count - 1}"
            )
        start_s = spans[cue.start_sentence][0]
        end_s = spans[cue.end_sentence][1]
        duration = round(max(0.0, end_s - start_s), 3)
        if start_s + duration > duration_s + 0.001:
            duration = round(max(0.0, duration_s - start_s), 3)
        if duration <= 0:
            raise PresentationError(
                f"cue sentences {cue.start_sentence}-{cue.end_sentence} compile to no time"
            )
        updated = cue.model_copy(deep=True)
        updated.start_s = round(start_s, 3)
        updated.duration_s = duration
        compiled.append(updated)
    return compiled


def compile_checkpoint_times(
    checkpoints: list[PresentationCheckpoint],
    sentences: list[str],
    duration_s: float,
) -> list[PresentationCheckpoint]:
    spans = sentence_spans(sentences, duration_s)
    count = len(spans)
    compiled: list[PresentationCheckpoint] = []
    for index, checkpoint in enumerate(checkpoints):
        if checkpoint.at_sentence >= count:
            raise PresentationError(
                f"checkpoint {checkpoint.checkpoint_id or index} sentence "
                f"{checkpoint.at_sentence} outside 0-{count - 1}"
            )
        updated = checkpoint.model_copy(deep=True)
        updated.at_s = round(spans[checkpoint.at_sentence][0], 3)
        if updated.at_s > duration_s + 0.001:
            raise PresentationError(
                f"checkpoint {updated.checkpoint_id or index} at {updated.at_s:.2f}s "
                f"exceeds duration {duration_s:.2f}s"
            )
        if not updated.checkpoint_id:
            updated.checkpoint_id = f"checkpoint-{index + 1}"
        compiled.append(updated)
    return compiled


def apply_reduced_motion(
    script: PresentationScript,
    *,
    policy: ReducedMotionPolicy = "static",
) -> PresentationScript:
    """Drop animation. Static policy holds every layer for the whole slide."""
    updated = script.model_copy(deep=True)
    updated.reduced_motion = True
    for layer in updated.layers:
        layer.motion = "none"
    if policy == "static" and updated.sentence_count > 0:
        updated.cues = [
            VisualCue(
                start_sentence=0,
                end_sentence=updated.sentence_count - 1,
                layer_ids=[layer.layer_id],
                enter="none",
                hold="none",
                exit="none",
            )
            for layer in updated.layers
        ]
    else:
        for cue in updated.cues:
            cue.enter = "none"
            cue.hold = "none"
            cue.exit = "none"
    return updated


def validate_presentation_script(
    script: PresentationScript,
    *,
    sentence_count: int | None = None,
) -> None:
    """Reject cues or checkpoints that leave the narration clock or sentence list."""
    count = script.sentence_count if sentence_count is None else sentence_count
    if script.duration_s <= 0:
        raise PresentationError("duration must be positive")
    if count < 1:
        raise PresentationError("sentence_count must be positive")
    if not script.layers:
        raise PresentationError("presentation needs at least one layer")
    layer_ids = [layer.layer_id for layer in script.layers]
    if len(set(layer_ids)) != len(layer_ids):
        raise PresentationError("duplicate layer_id")
    known = set(layer_ids)
    for cue in script.cues:
        if cue.end_sentence < cue.start_sentence:
            raise PresentationError(
                f"cue sentence range {cue.start_sentence}-{cue.end_sentence} is reversed"
            )
        if cue.start_sentence >= count or cue.end_sentence >= count:
            raise PresentationError(
                f"cue sentences {cue.start_sentence}-{cue.end_sentence} "
                f"outside 0-{count - 1}"
            )
        if cue.duration_s <= 0:
            raise PresentationError("cue duration must be compiled")
        if cue.start_s < -0.001 or cue.start_s + cue.duration_s > script.duration_s + 0.01:
            raise PresentationError(
                f"cue ends after script duration "
                f"({cue.start_s + cue.duration_s:.2f} > {script.duration_s:.2f})"
            )
        if not cue.layer_ids:
            raise PresentationError("cue needs at least one layer")
        missing = [layer_id for layer_id in cue.layer_ids if layer_id not in known]
        if missing:
            raise PresentationError(f"cue references unknown layer {missing[0]!r}")
    for checkpoint in script.checkpoints:
        if checkpoint.at_sentence >= count:
            raise PresentationError(
                f"checkpoint {checkpoint.checkpoint_id or checkpoint.kind!r} sentence "
                f"{checkpoint.at_sentence} outside 0-{count - 1}"
            )
        if checkpoint.at_s < -0.001 or checkpoint.at_s > script.duration_s + 0.01:
            raise PresentationError(
                f"checkpoint {checkpoint.checkpoint_id or checkpoint.kind!r} at "
                f"{checkpoint.at_s:.2f}s exceeds duration {script.duration_s:.2f}s"
            )


def _clock(slide: CourseSlide, narration: str | None, duration_s: float | None) -> float:
    estimated = narration_duration(spoken_text(slide, narration))
    duration = estimated if duration_s is None else float(duration_s)
    if duration <= 0:
        duration = estimated
    return round(min(600.0, duration), 3)


def _source_for(slide: CourseSlide) -> PresentationSource:
    if slide.visual_layers or slide.visual_cues or slide.presentation_checkpoints:
        return "authored"
    has_picture = bool((slide.picture_url or "").strip())
    has_video = bool((slide.video_url or "").strip())
    has_storyboard = bool((slide.storyboard_svg or "").strip())
    if has_picture or has_video or has_storyboard:
        return "legacy"
    return "inferred"


def _layer_motion(style: StyleSpec, kind: str) -> VisualMotion:
    motion: VisualMotion = style.motion
    if kind == "picture":
        return motion if motion in _MEDIA_MOTIONS else "fade"
    if kind == "video":
        return "pulse" if motion == "pulse" else "fade"
    if kind == "storyboard":
        return "draw" if motion == "draw" else "fade"
    if kind == "title":
        return "none" if motion == "none" else "fade"
    if kind == "body":
        if motion == "none":
            return "none"
        if motion in {"type-on", "draw"}:
            return motion
        return "fade"
    return "fade"


def _has_kind(layers: list[VisualLayer], kind: str) -> bool:
    return any(layer.kind == kind for layer in layers)


def _has_id(layers: list[VisualLayer], layer_id: str) -> bool:
    return any(layer.layer_id == layer_id for layer in layers)


def _compose_layers(slide: CourseSlide, style: StyleSpec) -> list[VisualLayer]:
    layers = [layer.model_copy(deep=True) for layer in slide.visual_layers]
    policy = style.reduced_motion

    def add(layer: VisualLayer) -> None:
        if not _has_id(layers, layer.layer_id):
            layers.append(layer)

    if (slide.picture_url or "").strip() and not _has_kind(layers, "picture"):
        add(
            VisualLayer(
                layer_id="picture",
                kind="picture",
                asset_url=slide.picture_url,
                alt=slide.picture_alt,
                z_index=1,
                motion=_layer_motion(style, "picture"),
                reduced_motion=policy,
            )
        )
    if (slide.video_url or "").strip() and not _has_kind(layers, "video"):
        add(
            VisualLayer(
                layer_id="video",
                kind="video",
                asset_url=slide.video_url,
                alt=slide.video_caption,
                z_index=2,
                motion=_layer_motion(style, "video"),
                reduced_motion=policy,
            )
        )
    if (slide.storyboard_svg or "").strip() and not _has_kind(layers, "storyboard"):
        add(
            VisualLayer(
                layer_id="storyboard",
                kind="storyboard",
                svg=slide.storyboard_svg,
                alt=slide.storyboard_concept,
                text=slide.storyboard_scene_id,
                z_index=3,
                motion=_layer_motion(style, "storyboard"),
                reduced_motion="static",
            )
        )
    if slide.title and not _has_kind(layers, "title"):
        add(
            VisualLayer(
                layer_id="title",
                kind="title",
                text=slide.title,
                z_index=10,
                motion=_layer_motion(style, "title"),
                reduced_motion="static",
            )
        )
    body = (slide.body or slide.narration or "").strip()
    if body and not _has_kind(layers, "body"):
        add(
            VisualLayer(
                layer_id="body",
                kind="body",
                text=body,
                z_index=11,
                motion=_layer_motion(style, "body"),
                reduced_motion="static",
            )
        )
    for index, example in enumerate(slide.examples):
        add(
            VisualLayer(
                layer_id=f"example-{index + 1}",
                kind="callout",
                text=example,
                z_index=20 + index,
                motion="fade",
                reduced_motion="instant",
            )
        )
    if not layers:
        add(
            VisualLayer(
                layer_id="title",
                kind="title",
                text=slide.title or "Slide",
                z_index=1,
                motion="none",
                reduced_motion="static",
            )
        )
    return layers


def _window(index: int, count: int, sentence_count: int) -> tuple[int, int]:
    if sentence_count <= 1 or count <= 1:
        return 0, max(0, sentence_count - 1)
    start = min(sentence_count - 1, (index * sentence_count) // count)
    end = min(sentence_count - 1, ((index + 1) * sentence_count) // count - 1)
    if end < start:
        end = start
    return start, end


def _infer_cues(style: StyleSpec, layers: list[VisualLayer], sentence_count: int) -> list[VisualCue]:
    last = sentence_count - 1
    stepping = step_style(style.style_id)
    callouts = [layer for layer in layers if layer.kind == "callout"]
    cues: list[VisualCue] = []
    for layer in layers:
        enter = layer.motion
        if layer.kind == "callout":
            continue
        if stepping and layer.kind == "body":
            for index in range(sentence_count):
                cues.append(
                    VisualCue(
                        start_sentence=index,
                        end_sentence=index,
                        layer_ids=[layer.layer_id],
                        enter=enter,
                    )
                )
            continue
        cues.append(
            VisualCue(
                start_sentence=0,
                end_sentence=last,
                layer_ids=[layer.layer_id],
                enter=enter,
            )
        )
    for index, layer in enumerate(callouts):
        start, end = _window(index, len(callouts), sentence_count)
        cues.append(
            VisualCue(
                start_sentence=start,
                end_sentence=end,
                layer_ids=[layer.layer_id],
                enter=layer.motion,
            )
        )
    return cues


def _checkpoint_kind(slide: CourseSlide, style: StyleSpec) -> CheckpointKind:
    if style.style_id == "challenge-checkpoint":
        return "pause"
    if slide.quiz_spec:
        return "quiz"
    if (slide.activity_prompt or "").strip():
        return "reflect"
    return "practice"


def _checkpoint_prompt(slide: CourseSlide) -> str:
    quiz = slide.quiz_spec if isinstance(slide.quiz_spec, dict) else {}
    game = slide.game_spec if isinstance(slide.game_spec, dict) else {}
    return (
        (slide.activity_prompt or "").strip()
        or str(quiz.get("prompt") or "").strip()
        or str(game.get("prompt") or "").strip()
        or slide.title
    )


def _infer_checkpoints(
    slide: CourseSlide,
    style: StyleSpec,
    sentence_count: int,
) -> list[PresentationCheckpoint]:
    if style.family != "challenge":
        return []
    key = (slide.slide_key or slide.title or "slide").strip() or "slide"
    return [
        PresentationCheckpoint(
            checkpoint_id=f"{key}-check",
            at_sentence=sentence_count - 1,
            kind=_checkpoint_kind(slide, style),
            prompt=_checkpoint_prompt(slide),
            blocks_advance=True,
        )
    ]


def _style_for_script(
    script: PresentationScript,
    slide: CourseSlide,
    narration: str | None,
    previous: str | None,
) -> StyleSpec | None:
    if script.style_id:
        return PRESENTATION_STYLES.get(script.style_id)
    style = assign_presentation_style(slide, previous_style_id=previous, narration=narration)
    script.style_id = style.style_id
    script.family = style.family
    if not script.layout or script.layout == "stack":
        script.layout = style.layout
    return style


def presentation_for_slide(
    slide: CourseSlide,
    *,
    narration: str | None = None,
    reduced_motion: bool = False,
    previous_style_id: str | None = None,
    duration_s: float | None = None,
) -> PresentationScript:
    """Compile explicit, authored, legacy, or inferred choreography for a slide."""
    sentences = sentences_for(slide, narration)
    duration = _clock(slide, narration, duration_s)

    if slide.presentation_script is not None:
        script = slide.presentation_script.model_copy(deep=True)
        script.source = "explicit"
        script.duration_s = round(min(600.0, max(script.duration_s, duration)), 3)
        script.sentence_count = len(sentences)
        style = _style_for_script(script, slide, narration, previous_style_id)
        if style is not None:
            script.family = style.family
        policy: ReducedMotionPolicy = style.reduced_motion if style is not None else "static"
        if reduced_motion:
            script = apply_reduced_motion(script, policy=policy)
        script.cues = compile_cue_times(script.cues, sentences, script.duration_s)
        script.checkpoints = compile_checkpoint_times(script.checkpoints, sentences, script.duration_s)
        validate_presentation_script(script)
        return script

    style = assign_presentation_style(
        slide,
        previous_style_id=previous_style_id,
        narration=narration,
    )
    layers = _compose_layers(slide, style)
    if slide.visual_cues:
        cues = [cue.model_copy(deep=True) for cue in slide.visual_cues]
        referenced = {layer_id for cue in cues for layer_id in cue.layer_ids}
        last = len(sentences) - 1
        for layer in layers:
            if layer.layer_id not in referenced:
                cues.append(
                    VisualCue(
                        start_sentence=0,
                        end_sentence=last,
                        layer_ids=[layer.layer_id],
                        enter=layer.motion,
                    )
                )
    else:
        cues = _infer_cues(style, layers, len(sentences))
    if slide.presentation_checkpoints:
        checkpoints = [item.model_copy(deep=True) for item in slide.presentation_checkpoints]
    else:
        checkpoints = _infer_checkpoints(slide, style, len(sentences))
    script = PresentationScript(
        style_id=style.style_id,
        family=style.family,
        layout=style.layout,
        duration_s=duration,
        layers=layers,
        cues=cues,
        checkpoints=checkpoints,
        reduced_motion=False,
        source=_source_for(slide),
        sentence_count=len(sentences),
    )
    if reduced_motion:
        script = apply_reduced_motion(script, policy=style.reduced_motion)
    script.cues = compile_cue_times(script.cues, sentences, script.duration_s)
    script.checkpoints = compile_checkpoint_times(script.checkpoints, sentences, script.duration_s)
    validate_presentation_script(script)
    return script


def presentations_for_slides(
    slides: list[CourseSlide],
    *,
    reduced_motion: bool = False,
) -> list[PresentationScript]:
    """Compile a deck, avoiding the same automatic style on adjacent slides."""
    compiled: list[PresentationScript] = []
    previous: str | None = None
    for slide in slides:
        script = presentation_for_slide(
            slide,
            reduced_motion=reduced_motion,
            previous_style_id=previous,
        )
        compiled.append(script)
        previous = script.style_id
    return compiled
