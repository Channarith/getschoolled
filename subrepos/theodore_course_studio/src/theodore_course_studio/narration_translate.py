"""Batch-translate catalog slides into the platform languages.

Curated certification and early-learning fields are kept as authored. Only
missing title, body, or narration is sent to the configured xAI chat endpoint.
Phonics and sight-word slides are adapted into the target language instead of
translated word for word. Every model payload is checked before it is cached,
and a disk cache makes a rerun skip work that already validated.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from .cert_i18n import translate_cert_slide
from .child_i18n import curated_languages, translate_beats
from .narration_catalog import CatalogSlide, canonical_hash, safe_token
from .studio_languages import SUPPORTED_LANGUAGES, language_name
from .voice_agent import XAI_DEFAULT_MODEL

CACHE_VERSION = 1
_FIELDS = ("title", "body", "narration")
_SOURCES = frozenset({"english", "curated", "xai", "persisted"})
_LETTER_ANCHORS = ("apple", "ball", "cat")
_SIGHT_PHRASES = (
    "i see a cat",
    "i can hop",
    "the sun is hot",
    "a dog can run",
    "the cat is soft",
)
_SCRIPTS = {
    "km": re.compile(r"[\u1780-\u17FF]"),
    "zh": re.compile(r"[\u4e00-\u9fff]"),
    "ja": re.compile(r"[\u3040-\u30ff\u4e00-\u9fff]"),
    "ko": re.compile(r"[\uac00-\ud7af]"),
    "ar": re.compile(r"[\u0600-\u06FF]"),
    "he": re.compile(r"[\u0590-\u05FF]"),
    "hi": re.compile(r"[\u0900-\u097F]"),
    "bn": re.compile(r"[\u0980-\u09FF]"),
    "ur": re.compile(r"[\u0600-\u06FF]"),
    "fa": re.compile(r"[\u0600-\u06FF]"),
    "th": re.compile(r"[\u0E00-\u0E7F]"),
    "el": re.compile(r"[\u0370-\u03FF]"),
    "ru": re.compile(r"[\u0400-\u04FF]"),
    "uk": re.compile(r"[\u0400-\u04FF]"),
}
_MEASUREMENT = re.compile(r"^[\d\s.,:+\-/%°ºFfCc()]+$")
_EARLY_BEATS: dict[tuple[str, str], tuple] = {}


class TranslationError(RuntimeError):
    """The translation stage cannot continue."""


class TranslationRejected(TranslationError):
    """The model output failed a strict check and was not cached."""


@dataclass(frozen=True)
class SlideText:
    """Title, on-screen body, and spoken narration for one slide and language."""

    slide_key: str
    language: str
    title: str
    body: str
    narration: str
    source: str
    adapted: bool
    sound_specific: bool
    source_hash: str
    course_id: str = ""
    course_kind: str = ""
    sound_topic: str = ""
    model: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": CACHE_VERSION,
            "slide_key": self.slide_key,
            "language": self.language,
            "title": self.title,
            "body": self.body,
            "narration": self.narration,
            "source": self.source,
            "adapted": self.adapted,
            "sound_specific": self.sound_specific,
            "source_hash": self.source_hash,
            "course_id": self.course_id,
            "course_kind": self.course_kind,
            "sound_topic": self.sound_topic,
            "model": self.model,
        }


def canonical_language(language: str) -> str:
    """Return a supported language code, accepting regional tags such as km-KH."""
    code = (language or "").strip().lower().replace("_", "-").split("-")[0]
    if code not in SUPPORTED_LANGUAGES:
        known = ", ".join(SUPPORTED_LANGUAGES)
        raise TranslationError(
            f"unsupported language {language!r}; choose one of: {known}"
        )
    return code


def source_hash(slide: CatalogSlide) -> str:
    return canonical_hash(
        {
            "slide_key": slide.slide_key,
            "title": slide.title,
            "body": slide.body,
            "narration": slide.narration,
            "source_language": slide.source_language,
        }
    )


def translation_path(cache_dir: Path, language: str, slide_key: str) -> Path:
    return cache_dir / language / f"{safe_token(slide_key)}.json"


def curated_fields_for(slide: CatalogSlide, language: str) -> dict[str, str]:
    """Curated title/body/narration that must not be machine-translated.

    Empty when this slide has no authored overlay for ``language``. A present
    field is returned verbatim from the curated catalogs.
    """
    lang = canonical_language(language)
    if lang == slide.source_language:
        return {}
    if slide.course_kind == "cert":
        translated = translate_cert_slide(slide.slide_key, lang)
        if translated is None:
            return {}
        fields = {
            "title": (translated.title or "").strip(),
            "body": (translated.body or "").strip(),
            "narration": (translated.say or "").strip(),
        }
        return {key: value for key, value in fields.items() if value}
    if slide.course_kind == "early":
        beat = _early_curated_beat(slide.course_id, lang, slide.slide_index)
        if beat is None:
            return {}
        fields = {
            "title": beat.title.strip(),
            "body": beat.words.strip(),
            "narration": beat.say.strip(),
        }
        return {key: value for key, value in fields.items() if value}
    return {}


def _early_curated_beat(topic_id: str, language: str, index: int):
    if language not in set(curated_languages(topic_id)):
        return None
    key = (topic_id, language)
    beats = _EARLY_BEATS.get(key)
    if beats is None:
        result = translate_beats(
            topic_id=topic_id,
            language=language,
            beats=((".", ".", ".", "."),),
            allow_xai=False,
        )
        beats = result.beats if result.source == "curated" else ()
        _EARLY_BEATS[key] = beats
    if not beats:
        return None
    if index < 0 or index >= len(beats):
        raise TranslationError(
            f"curated {topic_id}/{language} has {len(beats)} beats; "
            f"slide index {index} is outside that lesson"
        )
    return beats[index]


def translate_slides(
    slides: Sequence[CatalogSlide],
    languages: Sequence[str],
    *,
    cache_dir: Path,
    batch_size: int = 4,
    max_chars: int = 12000,
    opener: Callable[..., Any] | None = None,
) -> list[SlideText]:
    """Resolve every slide into each language, calling xAI only for gaps.

    Results are written under ``cache_dir`` and reused when the source text
    and the configured model are unchanged.
    """
    if batch_size < 1:
        raise TranslationError("batch_size must be >= 1")
    if max_chars < 1:
        raise TranslationError("max_chars must be >= 1")
    langs = [canonical_language(language) for language in languages]
    if not langs:
        raise TranslationError("at least one language is required")
    http = opener or _urlopen
    model = configured_model()
    resolved: list[SlideText] = []
    pending: list[dict[str, Any]] = []
    for slide in slides:
        digest = source_hash(slide)
        for language in langs:
            text, curated = _resolve_local(
                slide, language, digest, cache_dir, model
            )
            if text is not None:
                _write_text(cache_dir, text)
                resolved.append(text)
                continue
            pending.append(
                {
                    "slide": slide,
                    "language": language,
                    "curated": curated,
                    "source_hash": digest,
                }
            )
    if pending:
        resolved.extend(
            _translate_pending(
                pending,
                cache_dir=cache_dir,
                batch_size=batch_size,
                max_chars=max_chars,
                opener=http,
                model=model,
            )
        )
    order = {
        (slide.slide_key, language): (index, lang_index)
        for index, slide in enumerate(slides)
        for lang_index, language in enumerate(langs)
    }
    resolved.sort(key=lambda row: order[(row.slide_key, row.language)])
    return resolved


def read_slide_text(path: Path) -> SlideText | None:
    """Load a previously written slide translation. None when unusable."""
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("version") != CACHE_VERSION:
        return None
    try:
        return _slide_text_from_payload(payload)
    except (KeyError, TypeError, ValueError):
        return None


def parse_model_content(content: str) -> list:
    """Accept a JSON array, or an object whose only key is translations/items."""
    text = (content or "").strip()
    fenced = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise TranslationRejected(f"translation was not JSON: {exc}") from exc
    if isinstance(data, dict):
        keys = set(data)
        if keys == {"translations"}:
            data = data["translations"]
        elif keys == {"items"}:
            data = data["items"]
        else:
            raise TranslationRejected(
                "translation object must contain only 'translations' or 'items'"
            )
    if not isinstance(data, list):
        raise TranslationRejected("translation must be a JSON array")
    return data


def validate_rows(
    requested: Sequence[dict[str, Any]],
    rows: Sequence[Any],
) -> list[dict[str, str]]:
    """Check a model batch against the items that were sent.

    Returns the accepted field map for each request, in request order.
    """
    if len(rows) != len(requested):
        raise TranslationRejected(
            f"translation length {len(rows)} != requested {len(requested)}"
        )
    by_index: dict[int, Any] = {}
    for row in rows:
        if not isinstance(row, dict):
            raise TranslationRejected("each translation must be an object")
        extra = set(row) - {"i", "adapted", "title", "body", "narration"}
        if extra:
            raise TranslationRejected(
                "unexpected translation keys: " + ", ".join(sorted(extra))
            )
        marker = row.get("i")
        if type(marker) is not int:
            raise TranslationRejected("translation i must be an integer")
        if marker in by_index:
            raise TranslationRejected(f"duplicate translation i={marker}")
        by_index[marker] = row
    accepted: list[dict[str, str]] = []
    for item in requested:
        row = by_index.get(item["i"])
        if row is None:
            raise TranslationRejected(f"missing translation for i={item['i']}")
        fields = tuple(item["fields"])
        unknown = [field for field in fields if field not in _FIELDS]
        if unknown:
            raise TranslationRejected(
                "unknown fields requested: " + ", ".join(unknown)
            )
        sound_specific = bool(item.get("sound_specific"))
        adapted = row.get("adapted")
        if type(adapted) is not bool:
            raise TranslationRejected("translation adapted must be a boolean")
        if sound_specific and adapted is not True:
            raise TranslationRejected(
                f"{item['slide_key']}: phonics and sight words require adapted=true"
            )
        if not sound_specific and adapted:
            raise TranslationRejected(
                f"{item['slide_key']}: adapted=true is only for phonics and sight words"
            )
        out = {field: _validate_field(item, row, field) for field in fields}
        _reject_literal(item, out)
        accepted.append(out)
    return accepted


def _validate_field(item: dict[str, Any], row: dict[str, Any], field: str) -> str:
    if field not in row or type(row[field]) is not str:
        raise TranslationRejected(f"{item['slide_key']}: {field} must be a string")
    translated = row[field].strip()
    source = str(item.get(field) or "").strip()
    if not translated:
        raise TranslationRejected(f"{item['slide_key']}: {field} is empty")
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", translated):
        raise TranslationRejected(
            f"{item['slide_key']}: {field} has control characters"
        )
    if not re.search(r"\w", translated, flags=re.UNICODE):
        raise TranslationRejected(f"{item['slide_key']}: {field} has no letters")
    if translated == item["slide_key"]:
        raise TranslationRejected(
            f"{item['slide_key']}: {field} echoes the slide key"
        )
    limit = max(600, len(source) * 6)
    if len(translated) > limit:
        raise TranslationRejected(
            f"{item['slide_key']}: {field} is too long ({len(translated)} > {limit})"
        )
    if (
        source
        and translated.casefold() == source.casefold()
        and not _measurement_only(source)
    ):
        raise TranslationRejected(
            f"{item['slide_key']}: {field} is unchanged from the source"
        )
    script = _SCRIPTS.get(item["language"])
    if (
        script is not None
        and not _measurement_only(translated)
        and not script.search(translated)
    ):
        raise TranslationRejected(
            f"{item['slide_key']}: {field} is missing {item['language']} script"
        )
    return translated


def _measurement_only(text: str) -> bool:
    return bool(_MEASUREMENT.match(text.strip()))


def _reject_literal(item: dict[str, Any], fields: dict[str, str]) -> None:
    if not item.get("sound_specific"):
        return
    topic = item.get("sound_topic") or ""
    for field, translated in fields.items():
        source = str(item.get(field) or "")
        if _literal_sound_copy(topic, source, translated):
            raise TranslationRejected(
                f"{item['slide_key']}: {field} is a literal phonics or sight-word translation"
            )


def _literal_sound_copy(topic: str, source: str, translated: str) -> bool:
    source_low = source.casefold()
    translated_low = translated.casefold()
    if topic == "letter_sounds":
        for word in _LETTER_ANCHORS:
            if re.search(rf"\b{word}\b", source_low) and re.search(
                rf"\b{word}\b", translated_low
            ):
                return True
    if topic == "sight_words":
        for phrase in _SIGHT_PHRASES:
            if phrase in source_low and phrase in translated_low:
                return True
    return False


def _resolve_local(
    slide: CatalogSlide,
    language: str,
    digest: str,
    cache_dir: Path,
    model: str,
) -> tuple[SlideText | None, dict[str, str]]:
    """Return a finished slide, or the curated fields still needing a model."""
    curated = curated_fields_for(slide, language)
    adapted = bool(slide.sound_specific and language != slide.source_language)
    if language == slide.source_language:
        source = "persisted" if slide.course_kind == "persisted" else "english"
        return (
            _compose(
                slide,
                language,
                curated={},
                translated={},
                source=source,
                model="",
                adapted=False,
                digest=digest,
            ),
            {},
        )
    gaps = [field for field in _FIELDS if field not in curated]
    if not gaps:
        return (
            _compose(
                slide,
                language,
                curated=curated,
                translated={},
                source="curated",
                model="",
                adapted=adapted,
                digest=digest,
            ),
            {},
        )
    cached = _read_xai_cache(
        cache_dir, slide, language, digest, model, curated, tuple(gaps)
    )
    if cached is not None:
        return cached, {}
    return None, curated


def _read_xai_cache(
    cache_dir: Path,
    slide: CatalogSlide,
    language: str,
    digest: str,
    model: str,
    curated: dict[str, str],
    gaps: tuple[str, ...],
) -> SlideText | None:
    cached = read_slide_text(translation_path(cache_dir, language, slide.slide_key))
    if cached is None or cached.source != "xai":
        return None
    if cached.source_hash != digest or cached.model != model:
        return None
    if cached.language != language or cached.slide_key != slide.slide_key:
        return None
    translated = {field: getattr(cached, field) for field in gaps}
    item = _request_item(slide, language, gaps, index=0)
    try:
        accepted = validate_rows(
            [item], [{**translated, "i": 0, "adapted": bool(slide.sound_specific)}]
        )
    except TranslationRejected:
        return None
    return _compose(
        slide,
        language,
        curated=curated,
        translated=accepted[0],
        source="xai",
        model=model,
        adapted=bool(slide.sound_specific),
        digest=digest,
    )


def _compose(
    slide: CatalogSlide,
    language: str,
    *,
    curated: dict[str, str],
    translated: dict[str, str],
    source: str,
    model: str,
    adapted: bool,
    digest: str,
) -> SlideText:
    if source not in _SOURCES:
        raise TranslationError(f"unknown translation source {source!r}")
    fields: dict[str, str] = {}
    for field in _FIELDS:
        if curated.get(field, "").strip():
            fields[field] = curated[field].strip()
        elif translated.get(field, "").strip():
            fields[field] = translated[field].strip()
        else:
            fields[field] = str(getattr(slide, field) or "").strip()
    if not all(fields.values()):
        raise TranslationError(
            f"{slide.slide_key}/{language} is missing title, body, or narration"
        )
    return SlideText(
        slide_key=slide.slide_key,
        language=language,
        title=fields["title"],
        body=fields["body"],
        narration=fields["narration"],
        source=source,
        adapted=adapted,
        sound_specific=slide.sound_specific,
        source_hash=digest,
        course_id=slide.course_id,
        course_kind=slide.course_kind,
        sound_topic=slide.sound_topic,
        model=model,
    )


def _translate_pending(
    pending: list[dict[str, Any]],
    *,
    cache_dir: Path,
    batch_size: int,
    max_chars: int,
    opener: Callable[..., Any],
    model: str,
) -> list[SlideText]:
    groups: dict[tuple[str, bool], list[dict[str, Any]]] = {}
    for item in pending:
        slide: CatalogSlide = item["slide"]
        groups.setdefault((item["language"], slide.sound_specific), []).append(item)
    done: list[SlideText] = []
    for (language, sound_specific), items in groups.items():
        for chunk in _chunks(items, batch_size, max_chars):
            done.extend(
                _translate_chunk(
                    chunk,
                    language=language,
                    sound_specific=sound_specific,
                    cache_dir=cache_dir,
                    opener=opener,
                    model=model,
                )
            )
    return done


def _chunks(
    items: Sequence[dict[str, Any]], batch_size: int, max_chars: int
) -> Iterable[list[dict[str, Any]]]:
    chunk: list[dict[str, Any]] = []
    chars = 0
    for item in items:
        slide: CatalogSlide = item["slide"]
        size = len(slide.title) + len(slide.body) + len(slide.narration)
        if chunk and (len(chunk) >= batch_size or chars + size > max_chars):
            yield chunk
            chunk = []
            chars = 0
        chunk.append(item)
        chars += size
    if chunk:
        yield chunk


def _translate_chunk(
    chunk: list[dict[str, Any]],
    *,
    language: str,
    sound_specific: bool,
    cache_dir: Path,
    opener: Callable[..., Any],
    model: str,
) -> list[SlideText]:
    requested = []
    for index, item in enumerate(chunk):
        slide: CatalogSlide = item["slide"]
        curated = item["curated"]
        gaps = tuple(field for field in _FIELDS if field not in curated)
        requested.append(_request_item(slide, language, gaps, index))
        item["gaps"] = gaps
    content = complete_chat(
        _messages(language, sound_specific, requested),
        opener=opener,
    )
    accepted = validate_rows(requested, parse_model_content(content))
    written: list[SlideText] = []
    for item, fields in zip(chunk, accepted):
        text = _compose(
            item["slide"],
            language,
            curated=item["curated"],
            translated=fields,
            source="xai",
            model=model,
            adapted=bool(item["slide"].sound_specific),
            digest=item["source_hash"],
        )
        _write_text(cache_dir, text)
        written.append(text)
    return written


def _request_item(
    slide: CatalogSlide, language: str, fields: tuple[str, ...], index: int
) -> dict[str, Any]:
    item: dict[str, Any] = {
        "i": index,
        "slide_key": slide.slide_key,
        "language": language,
        "sound_specific": slide.sound_specific,
        "sound_topic": slide.sound_topic,
        "fields": list(fields),
    }
    for field in fields:
        item[field] = getattr(slide, field)
    return item


def _messages(
    language: str, sound_specific: bool, requested: list[dict[str, Any]]
) -> list[dict[str, str]]:
    payload = [
        {
            "i": item["i"],
            "slide_key": item["slide_key"],
            "fields": item["fields"],
            "sound_specific": item["sound_specific"],
            "sound_topic": item["sound_topic"],
            **{field: item[field] for field in item["fields"]},
        }
        for item in requested
    ]
    return [
        {
            "role": "system",
            "content": system_prompt(language, sound_specific=sound_specific),
        },
        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
    ]


def system_prompt(language: str, *, sound_specific: bool) -> str:
    """Instructions sent to xAI. Sound-specific lessons must be adapted."""
    name = language_name(language)
    prompt = (
        f"You translate course slides into {name} ({language}) for spoken teaching. "
        "Return ONLY a JSON array with one object per input, same length. "
        "Each object must include integer i, boolean adapted, and every requested "
        "field as a non-empty string. Preserve numbers, units, URLs, and proper "
        "nouns that should stay as written (California, DMV, Alameda, Theodore). "
        "Do not add commentary, markdown, or extra keys. Keep each field a similar "
        "length to the source. "
    )
    if sound_specific:
        prompt += (
            "These items teach phonics or sight words. Produce an adapted rather "
            "than literal translation: teach the same skill with words that really "
            "start with the target sound, or with real high-frequency sight words, "
            "in the target language. Do not keep English example words such as "
            "apple, ball, or cat, and do not keep English sentences such as "
            "'I see a cat'. Set adapted to true on every item."
        )
    else:
        prompt += (
            "Translate the meaning faithfully for a learner. Set adapted to false."
        )
    return prompt


def _urlopen(request: urllib.request.Request, timeout: float | None = None):
    """Open a request, skipping an env proxy that refuses the xAI tunnel."""
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.URLError as exc:
        text = str(exc).lower()
        if "tunnel connection failed" not in text or "403" not in text:
            raise
        direct = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return direct.open(request, timeout=timeout)


_MODEL_REJECTION = (
    "does not exist",
    "not available",
    "not found",
    "unknown model",
    "deprecated",
    "no access",
)


def _model_was_rejected(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(phrase in text for phrase in _MODEL_REJECTION)


def complete_chat(
    messages: list[dict[str, str]],
    *,
    opener: Callable[..., Any] | None = None,
    timeout_s: float | None = None,
) -> str:
    """One configured xAI chat completion. Returns the assistant content string.

    If ``XAI_MODEL`` names a model this key cannot use, the same request is
    sent once more with the default model.
    """
    model = configured_model()
    try:
        return _complete_chat_once(
            messages, model=model, opener=opener, timeout_s=timeout_s
        )
    except TranslationError as first:
        if model == XAI_DEFAULT_MODEL or not _model_was_rejected(first):
            raise
        return _complete_chat_once(
            messages, model=XAI_DEFAULT_MODEL, opener=opener, timeout_s=timeout_s
        )


def _complete_chat_once(
    messages: list[dict[str, str]],
    *,
    model: str,
    opener: Callable[..., Any] | None,
    timeout_s: float | None,
) -> str:
    api_key = os.environ.get("XAI_API_KEY", "").strip()
    if not api_key:
        raise TranslationError(
            "XAI_API_KEY is not configured; set it to translate missing slide text"
        )
    base = os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1").rstrip("/")
    if timeout_s is None:
        timeout_s = float(os.environ.get("XAI_TIMEOUT_S", "90") or "90")
    body = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": 8192,
    }
    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    http = opener or _urlopen
    try:
        with http(request, timeout=timeout_s) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except TranslationError:
        raise
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="replace").strip()[:400]
        except Exception:  # noqa: BLE001
            detail = ""
        raise TranslationError(
            f"xAI request failed: HTTP {exc.code} for model '{model}': {detail or exc.reason}"
        ) from exc
    except Exception as exc:  # noqa: BLE001 — surface config and transport failures
        raise TranslationError(f"xAI request failed: {exc}") from exc
    try:
        content = raw["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise TranslationError(
            "xAI response did not include message content"
        ) from exc
    if not isinstance(content, str) or not content.strip():
        raise TranslationError("xAI response content was empty")
    return content


def configured_model() -> str:
    return os.environ.get("XAI_MODEL", "").strip() or XAI_DEFAULT_MODEL


def _write_text(cache_dir: Path, text: SlideText) -> None:
    path = translation_path(cache_dir, text.language, text.slide_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(text.to_dict(), ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(payload, encoding="utf-8")
    os.replace(temporary, path)


def _slide_text_from_payload(payload: dict[str, Any]) -> SlideText:
    source = str(payload["source"])
    if source not in _SOURCES:
        raise ValueError(source)
    text = SlideText(
        slide_key=str(payload["slide_key"]),
        language=str(payload["language"]),
        title=str(payload["title"]).strip(),
        body=str(payload["body"]).strip(),
        narration=str(payload["narration"]).strip(),
        source=source,
        adapted=bool(payload.get("adapted")),
        sound_specific=bool(payload.get("sound_specific")),
        source_hash=str(payload["source_hash"]),
        course_id=str(payload.get("course_id") or ""),
        course_kind=str(payload.get("course_kind") or ""),
        sound_topic=str(payload.get("sound_topic") or ""),
        model=str(payload.get("model") or ""),
    )
    if not text.title or not text.body or not text.narration:
        raise ValueError("empty field")
    return text
