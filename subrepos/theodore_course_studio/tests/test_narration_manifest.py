"""Catalog translation and narration-manifest pipeline.

Network and neural TTS are mocked. ffprobe is mocked except where a test
checks that a missing binary is rejected.
"""

from __future__ import annotations

import importlib.util
import json
import threading
import urllib.request
from pathlib import Path

import pytest

from theodore_course_studio import narration_manifest, neural_tts
from theodore_course_studio.cert_i18n import translate_cert_slide
from theodore_course_studio.generate import CourseBuilder
from theodore_course_studio.narration_catalog import (
    CERT_COURSE_COUNT,
    EARLY_COURSE_COUNT,
    CatalogSlide,
    enumerate_courses,
    iter_slides,
)
from theodore_course_studio.narration_manifest import (
    GENDERS,
    PUBLIC_FIELDS,
    AudioPipelineError,
    IncompleteManifest,
    NarrationRecord,
    build_record,
    open_object_store,
    probe_duration,
    publish_manifest,
    render_audio,
    sentence_timeline,
    synthesize_course_audio,
    upload_audio,
    upload_manifest,
)
from theodore_course_studio.narration_translate import (
    TranslationError,
    TranslationRejected,
    SlideText,
    parse_model_content,
    read_slide_text,
    system_prompt,
    translate_slides,
    translation_path,
    validate_rows,
)
from theodore_course_studio.studio_languages import SUPPORTED_LANGUAGES
from theodore_course_studio.types import CategoryId, CourseSlide, StudioCourse


def _slide(**overrides) -> CatalogSlide:
    fields = dict(
        course_kind="cert",
        course_id="demo",
        course_title="Demo",
        slide_index=0,
        slide_key="demo.one",
        title="Stop at the line",
        body="A red light means stop the car.",
        narration="Stop the car when the light is red.",
        source_language="en",
        sound_specific=False,
        sound_topic="",
    )
    fields.update(overrides)
    return CatalogSlide(**fields)


class _Body:
    def __init__(self, payload: dict):
        self._raw = json.dumps(payload).encode("utf-8")

    def read(self) -> bytes:
        return self._raw

    def __enter__(self):
        return self

    def __exit__(self, *args) -> bool:
        return False


def _xai_response(rows: list[dict]) -> _Body:
    return _Body({"choices": [{"message": {"content": json.dumps(rows)}}]})


def _translated_rows(request) -> list[dict]:
    body = json.loads(request.data.decode("utf-8"))
    system = body["messages"][0]["content"]
    items = json.loads(body["messages"][1]["content"])
    rows = []
    for item in items:
        row = {"i": item["i"], "adapted": bool(item.get("sound_specific"))}
        for field in item["fields"]:
            if "(km)" in system:
                row[field] = f"ការបកប្រែ {field}"
            else:
                row[field] = f"Traduccion de {item['slide_key']} {field}."
        rows.append(row)
    return rows


def _opener_from(rows_for):
    calls = {"n": 0, "requests": []}

    def opener(request, timeout=0):
        calls["n"] += 1
        calls["requests"].append(request)
        return _xai_response(rows_for(request))

    return calls, opener


def _patch_probe(monkeypatch, *, duration="1.5", code=0, binary="/usr/bin/ffprobe"):
    monkeypatch.setattr(
        narration_manifest.shutil,
        "which",
        lambda name: binary if name == "ffprobe" else None,
    )

    def fake_run(cmd, **kwargs):
        class Proc:
            returncode = code
            stdout = duration if code == 0 else ""
            stderr = "" if code == 0 else "invalid audio"

        return Proc()

    monkeypatch.setattr(narration_manifest.subprocess, "run", fake_run)


def _audio() -> bytes:
    return b"ID3" + (b"\x00" * 64)


def _load_cli():
    path = Path(__file__).resolve().parents[1] / "scripts" / "generate_course_audio.py"
    spec = importlib.util.spec_from_file_location("generate_course_audio", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _text(**overrides) -> SlideText:
    fields = dict(
        slide_key="demo.one",
        language="es",
        title="Alto",
        body="La luz roja significa parar.",
        narration="Para el coche cuando la luz esta roja.",
        source="xai",
        adapted=False,
        sound_specific=False,
        source_hash="src",
    )
    fields.update(overrides)
    return SlideText(**fields)


def test_catalog_lists_cert_and_early_courses_with_stable_keys(tmp_path):
    saved = StudioCourse(
        course_id="saved-demo",
        title="Saved demo",
        category=CategoryId.OTHER,
        language="en",
        slides=[
            CourseSlide(
                index=0,
                slide_key="ca-dmv-basics.prep-not-a-dmv-course",
                title="Saved title",
                body="Saved body",
                narration="Saved narration",
            ),
            CourseSlide(
                index=1,
                title="Another saved slide",
                body="More body",
                narration="More narration",
            ),
        ],
    )
    CourseBuilder(data_dir=tmp_path).save_course(saved)

    first = enumerate_courses(data_dir=tmp_path)
    second = enumerate_courses(include_persisted=True, data_dir=tmp_path)
    cert = [course for course in first if course.course_kind == "cert"]
    early = [course for course in first if course.course_kind == "early"]
    assert len(cert) == CERT_COURSE_COUNT == 16
    assert len(early) == EARLY_COURSE_COUNT == 8
    assert {course.course_id for course in early} == {
        "colors",
        "shapes",
        "counting_1_10",
        "letter_sounds",
        "sight_words",
        "addition_to_10",
        "story_sequence",
        "animal_habitats",
    }
    keys = [slide.slide_key for slide in iter_slides(first)]
    persisted_only = [
        slide.slide_key
        for slide in iter_slides(second)
        if slide.course_kind != "persisted"
    ]
    assert keys == persisted_only
    assert len(keys) == len(set(keys))
    assert all("." in key and key.strip() for key in keys)
    sounds = [
        course
        for course in early
        if course.course_id in {"letter_sounds", "sight_words"}
    ]
    assert sounds
    for course in sounds:
        assert all(
            slide.sound_specific and slide.sound_topic == course.course_id
            for slide in course.slides
        )
    colors = [course for course in early if course.course_id == "colors"][0]
    assert all(not slide.sound_specific for slide in colors.slides)
    letters = [course for course in early if course.course_id == "letter_sounds"][0]
    assert letters.slides[0].slide_key == "letter_sounds.letters-make-sounds"

    persisted = [course for course in second if course.course_kind == "persisted"]
    assert [course.course_id for course in persisted] == ["saved-demo"]
    persisted_keys = [slide.slide_key for slide in persisted[0].slides]
    assert persisted_keys[0].startswith("persisted.saved-demo.")
    assert persisted_keys[1] == "saved-demo.another-saved-slide"
    limited = iter_slides(enumerate_courses(limit=1))
    assert len(limited) == 1
    assert limited[0].course_kind == "cert"


def test_curated_fields_are_kept_and_not_sent_to_xai(tmp_path, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    calls, opener = _opener_from(_translated_rows)
    curated = _slide(
        slide_key="ca-dmv-basics.prep-not-a-dmv-course",
        course_id="ca-dmv-basics",
        title="California driver education",
        body="English body that must stay out of the model request.",
        narration="English narration that must stay out of the model request.",
    )
    missing = _slide(
        slide_key="ca-dmv-sign.stop",
        title="Stop",
        body="A red octagon means stop.",
        narration="Stop behind the line.",
    )
    km_rows = translate_slides(
        [curated, missing], ["km-KH"], cache_dir=tmp_path, opener=opener
    )
    by_key = {(row.slide_key, row.language): row for row in km_rows}
    km = by_key[("ca-dmv-basics.prep-not-a-dmv-course", "km")]
    authored = translate_cert_slide(curated.slide_key, "km")
    assert authored is not None
    assert km.source == "curated"
    assert km.title == authored.title
    assert km.body == authored.body
    assert km.narration == authored.say
    sent = []
    for request in calls["requests"]:
        payload = json.loads(request.data.decode())
        sent.extend(
            item["slide_key"]
            for item in json.loads(payload["messages"][1]["content"])
        )
    assert curated.slide_key not in sent
    assert sent == ["ca-dmv-sign.stop"]
    es_rows = translate_slides([missing], ["es"], cache_dir=tmp_path, opener=opener)
    assert es_rows[0].source == "xai"
    assert es_rows[0].title.startswith("Traduccion")


def test_early_phonics_keeps_adapted_curation_and_rejects_literal_models(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.setenv("XAI_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("XAI_MODEL", "grok-test")
    phonics = _slide(
        course_kind="early",
        course_id="letter_sounds",
        course_title="Meet A, B, and C",
        slide_index=1,
        slide_key="letter_sounds.a-says-a",
        title="A says /a/",
        body="A is for apple.",
        narration="A can make the short a sound, like apple. A, apple.",
        sound_specific=True,
        sound_topic="letter_sounds",
    )
    calls, opener = _opener_from(_translated_rows)
    spanish = translate_slides([phonics], ["es"], cache_dir=tmp_path, opener=opener)
    assert calls["n"] == 0
    assert spanish[0].source == "curated"
    assert spanish[0].adapted is True
    assert "avión" in spanish[0].body
    assert "apple" not in spanish[0].narration.casefold()

    def literal(request, timeout=0):
        body = json.loads(request.data.decode("utf-8"))
        assert body["model"] == "grok-test"
        assert body["temperature"] == 0
        assert request.full_url == "https://example.test/v1/chat/completions"
        assert request.get_header("Authorization") == "Bearer test-key"
        assert "adapted rather than literal" in body["messages"][0]["content"]
        items = json.loads(body["messages"][1]["content"])
        return _xai_response(
            [
                {
                    "i": item["i"],
                    "adapted": True,
                    "title": "A est pour apple.",
                    "body": "A est pour apple.",
                    "narration": "A est pour apple.",
                }
                for item in items
            ]
        )

    with pytest.raises(TranslationRejected, match="literal"):
        translate_slides([phonics], ["fr"], cache_dir=tmp_path, opener=literal)
    assert not translation_path(tmp_path, "fr", phonics.slide_key).is_file()

    def adapted(request, timeout=0):
        items = json.loads(json.loads(request.data.decode())["messages"][1]["content"])
        return _xai_response(
            [
                {
                    "i": item["i"],
                    "adapted": True,
                    "title": "A dit /a/.",
                    "body": "A comme avion.",
                    "narration": "La lettre A sonne comme avion.",
                }
                for item in items
            ]
        )

    french = translate_slides([phonics], ["fr"], cache_dir=tmp_path, opener=adapted)
    assert french[0].source == "xai"
    assert french[0].adapted is True
    assert "apple" not in french[0].body.casefold()
    assert "adapted rather than literal" in system_prompt("fr", sound_specific=True)
    assert "adapted rather than literal" not in system_prompt("de", sound_specific=False)


def test_translation_cache_resumes_and_validation_is_strict(tmp_path, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.setenv("XAI_MODEL", "grok-test")
    slides = [
        _slide(
            slide_key=f"demo.{index}",
            title=f"Title {index}",
            body="B" * 80,
            narration=f"Say {index} clearly.",
        )
        for index in range(3)
    ]
    calls, opener = _opener_from(_translated_rows)
    first = translate_slides(
        slides[:2],
        ["de"],
        cache_dir=tmp_path,
        batch_size=10,
        max_chars=100,
        opener=opener,
    )
    assert calls["n"] == 2
    assert len(first) == 2
    translate_slides(
        slides[:2],
        ["de"],
        cache_dir=tmp_path,
        batch_size=10,
        max_chars=100,
        opener=opener,
    )
    assert calls["n"] == 2
    monkeypatch.setenv("XAI_MODEL", "grok-other")
    translate_slides(slides[:1], ["de"], cache_dir=tmp_path, opener=opener)
    assert calls["n"] == 3

    broken = translation_path(tmp_path, "de", slides[1].slide_key)
    broken.write_text("{", encoding="utf-8")
    translate_slides(slides[1:2], ["de"], cache_dir=tmp_path, opener=opener)
    assert calls["n"] == 4
    restored = read_slide_text(broken)
    assert restored is not None and restored.source == "xai"

    def bad(request, timeout=0):
        return _Body({"choices": [{"message": {"content": "hello there"}}]})

    with pytest.raises(TranslationRejected):
        translate_slides([slides[2]], ["de"], cache_dir=tmp_path, opener=bad)
    assert not translation_path(tmp_path, "de", slides[2].slide_key).is_file()

    item = {
        "i": 0,
        "slide_key": "demo.measure",
        "language": "de",
        "sound_specific": False,
        "sound_topic": "",
        "fields": ["body"],
        "body": "41°F",
    }
    assert validate_rows([item], [{"i": 0, "adapted": False, "body": "41°F"}])[0]["body"] == "41°F"
    with pytest.raises(TranslationRejected, match="unchanged"):
        validate_rows(
            [{**item, "body": "Stop the car."}],
            [{"i": 0, "adapted": False, "body": "Stop the car."}],
        )
    with pytest.raises(TranslationRejected, match="unexpected"):
        validate_rows(
            [item],
            [{"i": 0, "adapted": False, "body": "Einundvierzig.", "note": "extra"}],
        )
    with pytest.raises(TranslationRejected, match="script"):
        validate_rows(
            [{**item, "language": "km", "body": "Stop the car now."}],
            [{"i": 0, "adapted": False, "body": "Still Latin text here."}],
        )
    fenced = "```json\n" + json.dumps([{"i": 0}]) + "\n```"
    assert parse_model_content(fenced) == [{"i": 0}]
    assert parse_model_content(json.dumps({"items": [{"i": 1}]})) == [{"i": 1}]
    with pytest.raises(TranslationRejected):
        parse_model_content("not json")


def test_partial_curated_fields_are_not_overwritten(tmp_path, monkeypatch):
    monkeypatch.setenv("XAI_API_KEY", "test-key")

    def only_some(slide, language):
        return {"title": "Titulo curado", "body": "Cuerpo curado"}

    monkeypatch.setattr(
        "theodore_course_studio.narration_translate.curated_fields_for",
        only_some,
    )
    calls, opener = _opener_from(_translated_rows)
    rows = translate_slides([_slide()], ["es"], cache_dir=tmp_path, opener=opener)
    requested = json.loads(
        json.loads(calls["requests"][0].data.decode())["messages"][1]["content"]
    )
    assert requested[0]["fields"] == ["narration"]
    assert rows[0].title == "Titulo curado"
    assert rows[0].body == "Cuerpo curado"
    assert rows[0].narration.startswith("Traduccion")
    assert rows[0].source == "xai"


def test_english_copy_does_not_call_xai(tmp_path):
    calls, opener = _opener_from(_translated_rows)
    rows = translate_slides([_slide()], ["en"], cache_dir=tmp_path, opener=opener)
    assert calls["n"] == 0
    assert rows[0].source == "english"
    assert rows[0].narration == "Stop the car when the light is red."
    with pytest.raises(TranslationError, match="unsupported"):
        translate_slides([_slide()], ["xx"], cache_dir=tmp_path, opener=opener)


def test_missing_api_key_is_an_error(tmp_path, monkeypatch):
    monkeypatch.delenv("XAI_API_KEY", raising=False)
    with pytest.raises(TranslationError, match="XAI_API_KEY"):
        translate_slides(
            [_slide(slide_key="ca-dmv-sign.stop")], ["es"], cache_dir=tmp_path
        )


def test_render_upload_and_atomic_publish(tmp_path, monkeypatch):
    text = _text()
    khmer = _text(
        slide_key="demo.two",
        language="km",
        title="ឈប់",
        body="ភ្លើងក្រហមមានន័យថាឈប់។",
        narration="ឈប់ពេលភ្លើងក្រហម។",
        source="curated",
    )
    _patch_probe(monkeypatch)
    calls = []

    def synth(spoken, language, gender):
        calls.append((spoken, language, gender, threading.get_ident()))
        return _audio()

    clips = render_audio(
        [text, khmer],
        genders=("female",),
        work_dir=tmp_path,
        workers=2,
        synthesizer=synth,
    )
    assert len(clips) == 2
    assert len({item[3] for item in calls}) == 2
    assert clips[0].record.duration == 1.5
    assert clips[0].record.text == clips[0].record.narration == text.narration
    assert clips[0].record.display == "Alto\nLa luz roja significa parar."
    assert clips[0].record.hash[:12] in clips[0].record.object_key
    assert (tmp_path / clips[0].clip_path).is_file()

    def fail_resume(*args):
        raise AssertionError("resume should not synthesize")

    render_audio(
        [text], genders=("female",), work_dir=tmp_path, workers=1, synthesizer=fail_resume
    )
    assert build_record(text, "male").hash != build_record(text, "female").hash

    class Store:
        def __init__(self):
            self.puts = []

        def put(self, key, data, content_type="application/octet-stream"):
            self.puts.append((key, bytes(data), content_type))
            return f"https://cdn.example/{key}"

        def url_for(self, key):
            return f"https://cdn.example/{key}"

    store = Store()
    uploaded = upload_audio(clips, work_dir=tmp_path, store=store)
    assert len(store.puts) == 2
    assert {item[2] for item in store.puts} == {"audio/mpeg"}
    assert uploaded[0].audio_url.startswith("https://cdn.example/course-audio/v1/")
    again = upload_audio(clips, work_dir=tmp_path, store=store)
    assert len(store.puts) == 2
    assert again[0].audio_url == uploaded[0].audio_url

    manifest = tmp_path / "manifest.json"
    manifest.write_text("OLD", encoding="utf-8")
    expected = {clip.record.identity() for clip in clips}
    with pytest.raises(IncompleteManifest):
        publish_manifest(manifest, uploaded[:1], expected=expected)
    assert manifest.read_text(encoding="utf-8") == "OLD"
    assert not manifest.with_name(manifest.name + ".tmp").exists()
    publish_manifest(manifest, uploaded, expected=expected)
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["version"] == narration_manifest.MANIFEST_VERSION == 2
    assert payload["complete"] is True
    assert [tuple(row) for row in payload["records"]] == [PUBLIC_FIELDS, PUBLIC_FIELDS]
    assert any(row["narration"] == khmer.narration for row in payload["records"])
    assert all(row["segments"] for row in payload["records"])
    manifest_url = upload_manifest(manifest, store=store)
    assert manifest_url.endswith("course-audio/manifest-v2.json")
    assert store.puts[-1][2] == "application/json"
    assert not manifest.with_name(manifest.name + ".tmp").exists()


def test_ffprobe_failure_discards_the_clip(tmp_path, monkeypatch):
    text = _text(slide_key="demo.bad", narration="Para el coche ahora mismo.")
    _patch_probe(monkeypatch, code=1)
    with pytest.raises(AudioPipelineError, match="ffprobe"):
        render_audio(
            [text],
            genders=("female",),
            work_dir=tmp_path,
            workers=1,
            synthesizer=lambda *args: _audio(),
        )
    assert list(tmp_path.rglob("*.mp3")) == []
    assert list(tmp_path.rglob("*.part")) == []
    monkeypatch.setattr(narration_manifest.shutil, "which", lambda name: None)
    with pytest.raises(AudioPipelineError, match="ffprobe"):
        probe_duration(tmp_path / "missing.mp3")
    with pytest.raises(AudioPipelineError):
        render_audio(
            [text],
            genders=("female",),
            work_dir=tmp_path,
            workers=0,
            synthesizer=lambda *args: _audio(),
        )


def test_synthesize_and_object_store_wiring(monkeypatch):
    seen = {}

    def fake(text, language, rate=1.0, gender="female"):
        seen["args"] = (text, language, rate, gender)
        return b"mp3"

    monkeypatch.setattr(neural_tts, "synthesize_course", fake)
    assert synthesize_course_audio("Hola", "es", "male") == b"mp3"
    assert seen["args"] == ("Hola", "es", 1.0, "male")

    sentinel = object()

    class Factory:
        def __init__(self, config):
            assert config == "cfg"

        def object_store(self):
            return sentinel

    import aoep_shared.config as config_mod
    import aoep_shared.factory as factory_mod

    monkeypatch.setattr(config_mod, "load_config", lambda: "cfg")
    monkeypatch.setattr(factory_mod, "ProviderFactory", Factory)
    assert open_object_store() is sentinel
    assert GENDERS == ("female", "male")


def test_cli_translate_render_upload_publishes_only_when_complete(tmp_path, monkeypatch):
    cli = _load_cli()
    assert cli.selected_languages(None) == list(SUPPORTED_LANGUAGES)
    assert len(SUPPORTED_LANGUAGES) == 27
    assert cli.main(["translate", "--language", "xx", "--work-dir", str(tmp_path)]) == 1

    calls, opener = _opener_from(_translated_rows)
    monkeypatch.setenv("XAI_API_KEY", "test-key")
    monkeypatch.setattr(urllib.request, "urlopen", opener)
    code = cli.main(
        [
            "translate",
            "--language",
            "de",
            "--limit",
            "1",
            "--work-dir",
            str(tmp_path),
            "--batch-size",
            "2",
        ]
    )
    assert code == 0
    assert calls["n"] == 1

    _patch_probe(monkeypatch, duration="2.0")
    monkeypatch.setattr(
        neural_tts,
        "synthesize_course",
        lambda text, language, rate=1.0, gender="female": _audio(),
    )
    assert (
        cli.main(
            [
                "render",
                "--language",
                "de",
                "--gender",
                "female",
                "--limit",
                "1",
                "--work-dir",
                str(tmp_path),
                "--workers",
                "2",
            ]
        )
        == 0
    )

    class Store:
        def __init__(self):
            self.puts = []

        def put(self, key, data, content_type="application/octet-stream"):
            self.puts.append(content_type)
            return f"https://cdn.example/{key}"

        def url_for(self, key):
            return f"https://cdn.example/{key}"

    store = Store()
    monkeypatch.setattr(narration_manifest, "open_object_store", lambda: store)
    monkeypatch.setattr(cli, "open_object_store", lambda: store)
    incomplete = cli.main(
        ["upload", "--language", "de", "--limit", "1", "--work-dir", str(tmp_path)]
    )
    assert incomplete == 1
    assert not (tmp_path / "manifest.json").exists()
    assert store.puts == ["audio/mpeg"]
    published = cli.main(
        [
            "upload",
            "--language",
            "de",
            "--gender",
            "female",
            "--limit",
            "1",
            "--work-dir",
            str(tmp_path),
        ]
    )
    assert published == 0
    manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["complete"] is True
    assert manifest["records"][0]["gender"] == "female"
    assert manifest["records"][0]["duration"] == 2.0
    assert store.puts == ["audio/mpeg", "application/json"]


def test_record_identity_fields_round_trip():
    record = build_record(
        _text(narration="Para el coche."),
        "female",
        audio_url="https://cdn.example/a.mp3",
        duration=1.25,
    )
    assert isinstance(record, NarrationRecord)
    payload = record.to_dict()
    assert tuple(payload) == PUBLIC_FIELDS
    assert payload["text"] == payload["narration"] == "Para el coche."
    restored = narration_manifest.record_from_dict(payload)
    assert restored == record


def test_sentence_timeline_covers_measured_duration_without_gaps():
    rows = sentence_timeline(
        "First idea. Second idea is longer! តើនេះជាគំនិតទីបីមែនទេ។",
        12.5,
    )
    assert len(rows) == 3
    assert rows[0]["start_s"] == 0
    for previous, current in zip(rows, rows[1:]):
        assert current["start_s"] == pytest.approx(
            previous["start_s"] + previous["duration_s"], abs=0.002
        )
    assert rows[-1]["start_s"] + rows[-1]["duration_s"] == pytest.approx(
        12.5, abs=0.002
    )
