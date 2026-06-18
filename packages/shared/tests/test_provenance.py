"""Content credentials / provenance tests (Trust layer, Phase 2)."""

from aoep_shared.provenance import (
    build_manifest,
    sha256_hex,
    sign_manifest,
    verify_against_content,
    verify_manifest,
)

KEY = b"test-provenance-key"


def test_sign_and_verify_roundtrip():
    m = build_manifest("scene-1", "hello lesson", ai_generated=True, model="edu-7b")
    signed = sign_manifest(m, KEY)
    assert verify_manifest(signed, KEY) is True


def test_tamper_detected():
    m = build_manifest("scene-1", "hello lesson", ai_generated=True)
    signed = sign_manifest(m, KEY)
    signed.manifest.assertions[0].data["value"] = False  # flip AI flag
    assert verify_manifest(signed, KEY) is False


def test_wrong_key_fails():
    signed = sign_manifest(build_manifest("a", "x"), KEY)
    assert verify_manifest(signed, b"other-key") is False


def test_assertions_capture_provenance():
    m = build_manifest(
        "deck-9", "the body content", ai_generated=True, model="edu-7b",
        human_reviewed=True, reviewer="Dr. Lee", sources=["https://oer.org/a"],
        training_data_source="OER corpus v2",
    )
    labels = {a.label for a in m.assertions}
    assert "c2pa.ai_generated" in labels
    assert "aoep.model" in labels
    assert "aoep.human_reviewed" in labels
    assert "aoep.sources" in labels
    assert "aoep.training_data_source" in labels


def test_verify_against_content_detects_changed_content():
    m = build_manifest("scene-1", "original", ai_generated=False)
    signed = sign_manifest(m, KEY)
    assert verify_against_content(signed, "original", KEY) is True
    assert verify_against_content(signed, "edited!", KEY) is False


def test_content_hash_is_sha256():
    m = build_manifest("a", "abc")
    assert m.content_sha256 == sha256_hex("abc")
