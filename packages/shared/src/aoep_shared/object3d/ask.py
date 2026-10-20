"""Answer questions about a camera observation. Measured facts win over the LLM."""

from __future__ import annotations

from typing import Callable, Optional, Sequence

from .signs import translate_sign
from .types import Answer, Observation

Translator = Callable[[str, str, str], Optional[str]]
LLM = Callable[[str], str]


def intent_of(question: str) -> str:
    q = " ".join((question or "").casefold().split())
    if any(key in q for key in ("how far", "how close", "distance", "away from", "from me")):
        return "distance"
    if "animal" in q:
        return "animal"
    if any(key in q for key in ("food", "edible", "can i eat", "is it to eat")):
        return "food"
    if any(key in q for key in (
        "translate", "what does it say", "what does the sign", "sign say", "this sign",
    )):
        return "translate"
    if any(key in q for key in (
        "who made", "who built", "manufacturer", "maker", "what brand", "brand",
    )):
        return "maker"
    if any(key in q for key in ("when was", "when built", "what year", "how old", "built in")):
        return "year"
    if any(key in q for key in ("how hot", "how cold", "temperature", "celsius", "thermal", "heat", "warm")):
        return "heat"
    if "hot" in q or "cold" in q:
        return "heat"
    if any(key in q for key in ("smell", "scent", "odor", "odour", "aroma")):
        return "smell"
    if any(key in q for key in ("feel", "touch", "texture")):
        return "touch"
    return "describe"


def select_observation(question: str, observations: Sequence[Observation]) -> Optional[Observation]:
    if not observations:
        return None
    q = " ".join(question.casefold().split())
    for obs in observations:
        name = obs.name.casefold()
        if name in q and name not in ("object", "thing"):
            return obs
    measured = [obs for obs in observations if obs.distance_m is not None]
    if measured:
        return min(measured, key=lambda obs: float(obs.distance_m or 0))
    return observations[0]


def _meters(distance: Optional[float]) -> str:
    if distance is None:
        return "I can't measure a distance in this view"
    if distance < 1:
        return f"about {distance * 100:.0f} centimeters away"
    return f"about {distance:.1f} meters away"


def _facts(obs: Optional[Observation], ocr_text: str) -> dict:
    if obs is None:
        return {"ocr": ocr_text}
    return {
        "name": obs.name,
        "label": obs.label,
        "kind": obs.kind,
        "distance_m": None if obs.distance_m is None else round(float(obs.distance_m), 3),
        "maker": obs.maker,
        "year": obs.year,
        "camera": obs.camera,
        "heat_c": obs.heat_c,
        "heat_source": obs.heat_source,
        "smell": obs.smell,
        "texture": obs.texture,
        "force_n": obs.force_n,
        "ocr": ocr_text,
    }


def _heat_words(celsius: float) -> str:
    if celsius >= 60:
        word = "very hot"
    elif celsius >= 40:
        word = "hot"
    elif celsius >= 30:
        word = "warm"
    elif celsius <= 10:
        word = "cold"
    else:
        word = "near room temperature"
    return f"{celsius:.0f} degrees Celsius, {word}"


def _grounded(
    intent: str,
    question: str,
    obs: Optional[Observation],
    ocr_text: str,
    target: str,
    source: str,
    translator: Optional[Translator],
) -> str:
    if intent == "translate":
        text = ocr_text.strip()
        if not text:
            return "I can't read a sign in this view yet."
        hit = translate_sign(text, target, source)
        if hit:
            return f"That sign says {hit}."
        if translator is not None:
            try:
                translated = translator(text, source, target)
            except Exception:
                translated = None
            if translated:
                return f"That sign says {translated}."
        return f"I can read “{text}”, and I don't have a translation for it yet."
    if obs is None:
        if intent == "heat":
            return "The heat sensor isn't connected yet, and there is no temperature on file."
        if intent == "smell":
            return "The smell sensor isn't connected yet."
        if intent == "touch":
            return "The touch sensor isn't connected yet."
        return "I don't see an object in this view."
    name = obs.name
    where = _meters(obs.distance_m)
    if intent == "distance":
        subject = f"The {name}" if name != "object" else "The nearest object"
        if obs.distance_m is None:
            return f"{subject} is in view, but this camera didn't return depth."
        return f"{subject} is {where}."
    if intent == "animal":
        if obs.kind == "animal":
            return f"Yes. It looks like a {name}, {where}."
        if obs.kind == "person":
            return f"No. That is a person, {where}."
        return f"No. The {name} is not an animal. It is {where}."
    if intent == "food":
        if obs.kind == "food":
            return f"Yes. It looks like {name}, {where}."
        return f"No. The {name} is not food. It is {where}."
    if intent == "maker":
        if obs.maker:
            return f"The {name} was made by {obs.maker}."
        return (
            f"I don't know who made the {name} yet. "
            "Enroll it with a maker on the training script."
        )
    if intent == "year":
        if obs.year:
            return f"The {name} is recorded as built in {obs.year}."
        return (
            f"I don't know when the {name} was built. "
            "Enroll it with a year on the training script."
        )
    if intent == "heat":
        if obs.heat_c is None:
            return "The heat sensor isn't connected yet, and there is no temperature on file."
        phrase = _heat_words(float(obs.heat_c))
        learned = "From training, " if obs.heat_source == "trained" else ""
        q = question.casefold()
        if "hot" in q and "how" not in q and "temperature" not in q:
            yes = "Yes" if float(obs.heat_c) >= 40 else "No"
            return f"{learned}{yes}. The {name} is {phrase}."
        if "cold" in q and "how" not in q and "temperature" not in q:
            yes = "Yes" if float(obs.heat_c) <= 10 else "No"
            return f"{learned}{yes}. The {name} is {phrase}."
        return f"{learned}The {name} is {phrase}."
    if intent == "smell":
        if not obs.smell:
            return "The smell sensor isn't connected yet."
        learned = "From training, " if obs.smell_source == "trained" else ""
        return f"{learned}The {name} smells like {obs.smell}."
    if intent == "touch":
        if not obs.texture and obs.force_n is None:
            return "The touch sensor isn't connected yet."
        learned = "From training, " if obs.touch_source == "trained" else ""
        bits = []
        if obs.texture:
            bits.append(f"feels {obs.texture}")
        if obs.force_n is not None:
            bits.append(f"contact force is {obs.force_n:.2f} newtons")
        return f"{learned}The {name} " + ", and ".join(bits) + "."
    kind_bit = ""
    if obs.kind == "animal":
        kind_bit = " It is an animal."
    elif obs.kind == "food":
        kind_bit = " It is food."
    elif obs.kind == "sign":
        kind_bit = " It looks like a sign."
    elif obs.kind == "person":
        kind_bit = " It is a person."
    made = ""
    if obs.maker and obs.year:
        made = f" {obs.maker} made it in {obs.year}."
    elif obs.maker:
        made = f" {obs.maker} made it."
    elif obs.year:
        made = f" It is recorded as built in {obs.year}."
    senses = ""
    if obs.heat_c is not None:
        senses += f" It is {_heat_words(float(obs.heat_c))}."
    if obs.smell:
        senses += f" It smells like {obs.smell}."
    if obs.texture:
        senses += f" It feels {obs.texture}."
    return f"I see a {name}, {where}.{kind_bit}{made}{senses}"


def answer_about(
    question: str,
    observations: Sequence[Observation],
    *,
    ocr_text: str = "",
    target_language: str = "en",
    source_language: str = "auto",
    translator: Optional[Translator] = None,
    llm: Optional[LLM] = None,
) -> Answer:
    """Speak a short answer. Distance, kind, and catalog facts are not guessed."""
    intent = intent_of(question)
    obs = select_observation(question, observations)
    if intent == "translate" and ocr_text.strip():
        obs = None
    text = _grounded(intent, question, obs, ocr_text, target_language, source_language, translator)
    facts = _facts(obs, ocr_text)
    facts["intent"] = intent
    facts["target_language"] = target_language
    # The model may add a sentence only where the camera has no stored fact.
    incomplete = (
        (intent == "maker" and not (obs and obs.maker))
        or (intent == "year" and not (obs and obs.year))
        or (intent == "heat" and not (obs and obs.heat_c is not None))
        or (intent == "smell" and not (obs and obs.smell))
        or (intent == "touch" and not (obs and (obs.texture or obs.force_n is not None)))
        or intent == "describe"
        or (intent == "translate" and text.startswith("I can read"))
    )
    if llm is not None and incomplete:
        prompt = (
            "You are a voice agent looking through a 3D camera. "
            "Use only these facts. Do not change a measured distance, kind, "
            "temperature, smell, texture, maker, or year. If a fact is missing, "
            "say you do not know. "
            "One or two spoken sentences.\n"
            f"Question: {question}\nFacts: {facts}\nGrounded answer: {text}"
        )
        try:
            extra = (llm(prompt) or "").strip()
        except Exception:
            extra = ""
        if extra:
            text = extra
    return Answer(text=text, intent=intent, facts=facts)
