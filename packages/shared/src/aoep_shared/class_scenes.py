"""Class question scenes — large pools drawn without replacement.

English is the source locale. Spoken lines and prompts are localized at
request time through ``training_content_i18n.translate_body`` when a
translator is registered. This module does not embed machine translations.
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Sequence

from .content_packs import load_records, pack_fingerprint
from .training_content_i18n import normalize_training_locale, translate_body

DRIVERS_ED = "drivers-ed"
FOOD_SAFETY = "food-safety"

_TOPIC_DOMAIN = {
    DRIVERS_ED: "road",
    FOOD_SAFETY: "food_safety",
}

_HANDBOOK = {
    DRIVERS_ED: (
        "California Driver Handbook",
        "rules of the road",
        "https://www.dmv.ca.gov/portal/handbook/california-driver-handbook/",
    ),
    FOOD_SAFETY: (
        "FDA Food Code / California food-handler practice",
        "cooking, holding, and hygiene controls",
        "https://www.fda.gov/food/fda-food-code/food-code-2017",
    ),
}


@dataclass(frozen=True)
class ClassScene:
    scene_id: str
    topic: str
    skill: str
    prompt: str
    acceptable: tuple[str, ...]
    rubric: tuple[str, ...]
    spoken: str
    distractors: tuple[str, ...]
    locale: str = "en"
    source_locale: str = "en"

    def to_dict(self) -> dict:
        return {
            "scene_id": self.scene_id,
            "topic": self.topic,
            "skill": self.skill,
            "prompt": self.prompt,
            "acceptable": list(self.acceptable),
            "rubric": list(self.rubric),
            "spoken": self.spoken,
            "distractors": list(self.distractors),
            "locale": self.locale,
            "source_locale": self.source_locale,
        }


def canonical_topic(raw: Optional[str]) -> Optional[str]:
    """Map a lesson id, course title, or catalog domain onto a scene pool."""
    if not raw:
        return None
    compact = re.sub(r"[^a-z0-9]+", " ", raw.lower()).strip()
    slug = compact.replace(" ", "-")
    if (
        "driver ed" in compact
        or "drivers ed" in compact
        or "driver education" in compact
        or "dmv permit" in compact
        or "drivers permit" in compact
        or slug.startswith("ca-driver")
        or slug.startswith("ca-dmv")
        or slug.startswith("drivers-permit")
        or compact in {"road", "driving"}
    ):
        return DRIVERS_ED
    if (
        "food handler" in compact
        or "food safety" in compact
        or "food health" in compact
        or "alameda food" in compact
        or slug.startswith("ca-alameda-food")
        or slug.startswith("food-handler")
        or slug.startswith("alameda-food")
    ):
        return FOOD_SAFETY
    return None


def _as_tuple(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        text = value.strip()
        return (text,) if text else ()
    if isinstance(value, Sequence):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return ()


def _parse_record(raw: dict) -> Optional[ClassScene]:
    prompt = str(raw.get("prompt") or "").strip()
    acceptable = _as_tuple(raw.get("acceptable") or raw.get("answer"))
    spoken = str(raw.get("spoken") or raw.get("spoken_line") or "").strip()
    rubric = _as_tuple(raw.get("rubric"))
    if not prompt or not acceptable or not spoken:
        return None
    topic = canonical_topic(str(raw.get("topic") or "")) or str(raw.get("topic") or "")
    if not topic:
        return None
    scene_id = str(raw.get("scene_id") or "").strip()
    if not scene_id:
        return None
    if not rubric:
        rubric = acceptable
    locale = str(raw.get("locale") or raw.get("source_locale") or "en").strip() or "en"
    source = str(raw.get("source_locale") or "en").strip() or "en"
    return ClassScene(
        scene_id=scene_id,
        topic=topic,
        skill=str(raw.get("skill") or "general").strip() or "general",
        prompt=prompt,
        acceptable=acceptable,
        rubric=rubric,
        spoken=spoken,
        distractors=_as_tuple(raw.get("distractors")),
        locale=locale,
        source_locale=source,
    )


_parsed: Dict[str, tuple] = {}


def _load_parsed() -> tuple[Dict[str, List[ClassScene]], Dict[str, ClassScene]]:
    fp = pack_fingerprint("class_scenes")
    cached = _parsed.get(fp)
    if cached is not None:
        return cached
    by_topic: Dict[str, List[ClassScene]] = {}
    by_id: Dict[str, ClassScene] = {}
    for raw in load_records("class_scenes"):
        scene = _parse_record(raw)
        if scene is None or scene.scene_id in by_id:
            continue
        by_id[scene.scene_id] = scene
        by_topic.setdefault(scene.topic, []).append(scene)
    for topic in by_topic:
        by_topic[topic].sort(key=lambda s: s.scene_id)
    cached = (by_topic, by_id)
    _parsed.clear()
    _parsed[fp] = cached
    return cached


def scenes_for_topic(topic: str) -> List[ClassScene]:
    canon = canonical_topic(topic) or topic
    by_topic, _ = _load_parsed()
    return list(by_topic.get(canon, []))


def pool_size(topic: str) -> int:
    return len(scenes_for_topic(topic))


def pool_counts() -> Dict[str, int]:
    by_topic, _ = _load_parsed()
    return {topic: len(items) for topic, items in sorted(by_topic.items())}


def get_scene(scene_id: str) -> Optional[ClassScene]:
    _, by_id = _load_parsed()
    return by_id.get(scene_id)


def localize_scene(scene: ClassScene, locale: Optional[str]) -> ClassScene:
    """Return the scene in ``locale`` when the request-time translator can.

    Missing translator or a failed translation keeps the English source and
    reports ``locale == "en"`` so speech matches the text.
    """
    target = normalize_training_locale(locale)
    source = scene.source_locale or "en"
    if target == source or target == "en":
        return replace(scene, locale=source if target == source else "en")

    def _tr(text: str) -> Optional[str]:
        return translate_body(text, target, source=source)

    prompt = _tr(scene.prompt)
    spoken = _tr(scene.spoken)
    if not prompt or not spoken:
        return replace(scene, locale="en")
    rubric = tuple(_tr(line) or line for line in scene.rubric)
    acceptable = tuple(_tr(line) or line for line in scene.acceptable)
    return replace(
        scene,
        prompt=prompt,
        spoken=spoken,
        rubric=rubric,
        acceptable=acceptable,
        locale=target,
    )


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def grade_scene_answer(scene: ClassScene, answer: str) -> dict:
    """Grade a free-text answer against the acceptable lines and rubric.

    A hit is an acceptable phrase contained in the answer, or the answer
    contained in an acceptable phrase when the learner states the rule briefly.
    """
    blob = _norm(answer)
    if not blob:
        return {"correct": False, "scene_id": scene.scene_id, "matched": ""}
    for line in scene.acceptable:
        needle = _norm(line)
        if not needle:
            continue
        if needle in blob or (len(blob) >= 12 and blob in needle):
            return {"correct": True, "scene_id": scene.scene_id, "matched": line}
    rubric_hits = 0
    for line in scene.rubric:
        words = [w for w in _norm(line).split() if len(w) > 3]
        if words and sum(1 for w in words if w in blob) >= max(2, len(words) // 2):
            rubric_hits += 1
    return {
        "correct": rubric_hits > 0,
        "scene_id": scene.scene_id,
        "matched": scene.rubric[0] if rubric_hits else "",
    }


def multiple_choice(scene: ClassScene) -> tuple[list[str], int]:
    """Four options, one acceptable answer, shuffled per scene id."""
    correct = scene.acceptable[0].strip()
    options = [correct]
    seen = {_norm(correct)}
    for raw in scene.distractors:
        key = _norm(raw)
        if not key or key in seen:
            continue
        seen.add(key)
        options.append(raw.strip())
        if len(options) == 4:
            break
    fillers = (
        "Ignore the hazard and keep your speed.",
        "That step is optional once you feel confident.",
        "Do the opposite of the posted rule.",
    )
    for filler in fillers:
        if len(options) >= 4:
            break
        if _norm(filler) not in seen:
            options.append(filler)
            seen.add(_norm(filler))
    rng = random.Random(scene.scene_id)
    rng.shuffle(options)
    return options, options.index(correct)


class ClassSceneSession:
    """Draws each scene once, then reshuffles. Back-to-back draws differ."""

    def __init__(self, topic: str, *, seed: Optional[int] = None) -> None:
        canon = canonical_topic(topic)
        if canon is None:
            raise ValueError(f"no class scene pool for {topic!r}")
        self.topic = canon
        self._scenes = scenes_for_topic(canon)
        if len(self._scenes) < 2:
            raise ValueError(f"scene pool for {canon} is too small")
        self._by_id = {s.scene_id: s for s in self._scenes}
        self.rng = random.Random(seed)
        self._unused: List[str] = []
        self._last: Optional[str] = None
        self.drawn = 0
        self._refill()

    @property
    def size(self) -> int:
        return len(self._by_id)

    def _refill(self) -> None:
        ids = list(self._by_id)
        self.rng.shuffle(ids)
        if self._last and len(ids) > 1 and ids[-1] == self._last:
            ids[0], ids[-1] = ids[-1], ids[0]
        self._unused = ids

    def draw(self) -> ClassScene:
        if not self._unused:
            self._refill()
        scene_id = self._unused.pop()
        self._last = scene_id
        self.drawn += 1
        return self._by_id[scene_id]


_decks: Dict[tuple[str, str], ClassSceneSession] = {}


def reset_session_decks() -> None:
    _decks.clear()


def draw_for_session(
    session_id: str,
    topic: str,
    *,
    locale: Optional[str] = "en",
    seed: Optional[int] = None,
) -> ClassScene:
    """Next unused scene for this session and topic."""
    canon = canonical_topic(topic)
    if canon is None:
        raise ValueError(f"no class scene pool for {topic!r}")
    key = (session_id or f"anon:{canon}", canon)
    deck = _decks.get(key)
    if deck is None:
        deck = ClassSceneSession(canon, seed=seed)
        _decks[key] = deck
    return localize_scene(deck.draw(), locale)


def scenario_pack_records() -> List[dict]:
    """Scene pools as training-catalog scenario records (English source)."""
    by_topic, _ = _load_parsed()
    records: List[dict] = []
    for topic, scenes in by_topic.items():
        domain = _TOPIC_DOMAIN.get(topic)
        if not domain:
            continue
        source, reference, url = _HANDBOOK[topic]
        for scene in scenes:
            records.append(
                {
                    "scenario_id": f"class-scene-{scene.scene_id}",
                    "title": f"{scene.skill}: {scene.prompt[:90]}",
                    "domain": domain,
                    "briefing": scene.prompt,
                    "cues": [
                        {
                            "cue_id": "spoken",
                            "text": scene.spoken,
                            "priority": "high",
                        }
                    ],
                    "decision_prompt": scene.prompt,
                    "decision_time_limit_s": 45,
                    "emergency_steps": list(scene.acceptable),
                    "foresight_prompts": [],
                    "critical_thinking_prompts": [scene.spoken],
                    "debrief_rubric": list(scene.rubric),
                    "skills": [scene.skill, topic],
                    "references": [
                        {
                            "fact": scene.rubric[0],
                            "source": source,
                            "reference": reference,
                            "category": "guideline",
                            "url": url,
                        }
                    ],
                }
            )
    return records
