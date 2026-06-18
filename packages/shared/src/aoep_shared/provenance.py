"""Content credentials / provenance (Trust layer, Phase 2).

A C2PA-shaped, tamper-evident manifest that records what produced a piece of
content (AI-generated? which model? human-reviewed? what sources/training data?)
bound to the content by a SHA-256 hash and signed (HMAC) so anyone can verify it
was not altered. This is the strongest remedy to "that video/lesson is fake/AI":
content carries verifiable credentials.

Reuses the canonical-bytes + HMAC pattern from aoep_shared.scene. The schema is
deliberately C2PA-like (assertions list) so swapping to real C2PA + asymmetric
keys later is a drop-in; today HMAC gives integrity/authenticity within the
trust boundary (note: public third-party verifiability needs public-key signing).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import List, Optional, Union

from pydantic import BaseModel, Field

FORMAT = "aoep-provenance"
FORMAT_VERSION = 1


def sha256_hex(content: Union[str, bytes]) -> str:
    data = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(data).hexdigest()


class Assertion(BaseModel):
    label: str          # e.g. "c2pa.ai_generated", "aoep.human_reviewed"
    data: dict = Field(default_factory=dict)


class ContentManifest(BaseModel):
    format: str = FORMAT
    version: int = FORMAT_VERSION
    artifact_id: str
    content_sha256: str
    assertions: List[Assertion] = Field(default_factory=list)
    created_at: float = Field(default_factory=lambda: time.time())

    def has(self, label: str) -> bool:
        return any(a.label == label for a in self.assertions)


class SignedManifest(BaseModel):
    format: str = FORMAT
    version: int = FORMAT_VERSION
    alg: str = "HMAC-SHA256"
    signature: str
    manifest: ContentManifest


def build_manifest(
    artifact_id: str,
    content: Union[str, bytes],
    *,
    ai_generated: bool = False,
    model: Optional[str] = None,
    human_reviewed: bool = False,
    reviewer: Optional[str] = None,
    sources: Optional[List[str]] = None,
    training_data_source: Optional[str] = None,
) -> ContentManifest:
    """Assemble a content manifest with the common assertions."""
    assertions: List[Assertion] = [
        Assertion(label="c2pa.ai_generated", data={"value": bool(ai_generated)})
    ]
    if model:
        assertions.append(Assertion(label="aoep.model", data={"name": model}))
    if human_reviewed:
        assertions.append(
            Assertion(label="aoep.human_reviewed", data={"reviewer": reviewer or "unknown"})
        )
    if sources:
        assertions.append(Assertion(label="aoep.sources", data={"urls": list(sources)}))
    if training_data_source:
        assertions.append(
            Assertion(label="aoep.training_data_source", data={"source": training_data_source})
        )
    return ContentManifest(
        artifact_id=artifact_id, content_sha256=sha256_hex(content), assertions=assertions
    )


def canonical_bytes(manifest: ContentManifest) -> bytes:
    return json.dumps(
        manifest.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sign_manifest(manifest: ContentManifest, key: bytes) -> SignedManifest:
    sig = hmac.new(key, canonical_bytes(manifest), hashlib.sha256).hexdigest()
    return SignedManifest(signature=sig, manifest=manifest)


def verify_manifest(signed: SignedManifest, key: bytes) -> bool:
    expected = hmac.new(key, canonical_bytes(signed.manifest), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signed.signature)


def verify_against_content(
    signed: SignedManifest, content: Union[str, bytes], key: bytes
) -> bool:
    """Full check: signature valid AND the content still matches the manifest hash."""
    if not verify_manifest(signed, key):
        return False
    return hmac.compare_digest(sha256_hex(content), signed.manifest.content_sha256)
