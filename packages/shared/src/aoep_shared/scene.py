"""AOEPLX - the layered live-teaching scene format.

A "scene" is one broadcastable unit of a class. It is a thin, asset-by-reference
manifest (media live in the object store, not the manifest) composed of ordered
LAYERS: video, audio, image, whiteboard (vector strokes), text/note, quiz, poll.
This makes it fast to broadcast and easy to compose live.

Key capabilities (the unique bits):
- Layering: any layer has a z-order, transform (normalized 0..1 box), time range,
  and can be ANCHORED to another layer ("attach a note/audio/video to this
  drawing"). That is how a student gets extra context attached to a highlight.
- Live deltas: small ops (add/update/remove layer, append a whiteboard stroke)
  broadcast on top of a base scene, so the wire carries diffs, not whole scenes.
- Extraction: pull a region (bbox) and/or time range out as a NEW multilayer
  object - a still "image" (instant) or a "clip" (time range) - e.g. pause a
  video, draw on it, and lift that drawing+frame out as its own object.
- Tamper-evident container: a canonical hash + HMAC signature so a distributed
  scene can be integrity-verified. (Confidentiality is TLS + object-store
  encryption; this layer is integrity/authenticity.)

Everything here is pure/serializable and fully unit-testable; the browser canvas
renderer and the realtime transport (LiveKit data channel) sit on top.
"""

from __future__ import annotations

import enum
import hashlib
import hmac
import json
import time
import uuid
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

FORMAT = "aoeplx"
FORMAT_VERSION = 1


class LayerType(str, enum.Enum):
    VIDEO = "video"
    AUDIO = "audio"
    IMAGE = "image"
    WHITEBOARD = "whiteboard"
    TEXT = "text"
    NOTE = "note"
    QUIZ = "quiz"
    POLL = "poll"


class Transform(BaseModel):
    # Normalized [0,1] box relative to the scene, so it is resolution-independent.
    x: float = 0.0
    y: float = 0.0
    w: float = 1.0
    h: float = 1.0
    rotation: float = 0.0
    opacity: float = 1.0


class TimeRange(BaseModel):
    start: float = 0.0
    end: Optional[float] = None  # None => open-ended

    def contains(self, t: float) -> bool:
        if t < self.start:
            return False
        return self.end is None or t <= self.end


class Stroke(BaseModel):
    points: List[Tuple[float, float]] = Field(default_factory=list)  # normalized
    color: str = "#ffcc00"
    width: float = 0.004


class Layer(BaseModel):
    id: str
    type: LayerType
    z: int = 0
    transform: Transform = Field(default_factory=Transform)
    time: TimeRange = Field(default_factory=TimeRange)
    asset_key: Optional[str] = None       # object-store key for media layers
    strokes: List[Stroke] = Field(default_factory=list)  # whiteboard
    text: Optional[str] = None            # text/note content
    ref: Optional[str] = None             # quiz/poll id, etc.
    anchor_to: Optional[str] = None       # layer id this annotates/attaches to
    meta: dict = Field(default_factory=dict)


class Scene(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = ""
    format: str = FORMAT
    version: int = FORMAT_VERSION
    width: int = 1280
    height: int = 720
    layers: List[Layer] = Field(default_factory=list)
    created_at: float = Field(default_factory=lambda: time.time())

    # --- authoring helpers ------------------------------------------------- #
    def add_layer(self, layer: Layer) -> Layer:
        if self.get_layer(layer.id) is not None:
            raise ValueError(f"duplicate layer id: {layer.id}")
        self.layers.append(layer)
        return layer

    def get_layer(self, layer_id: str) -> Optional[Layer]:
        return next((ly for ly in self.layers if ly.id == layer_id), None)

    def ordered(self) -> List[Layer]:
        return sorted(self.layers, key=lambda ly: ly.z)

    def attach(self, target_layer_id: str, annotation: Layer) -> Layer:
        """Anchor ``annotation`` on top of an existing layer (e.g. a drawing).

        The annotation can be a NOTE/AUDIO/VIDEO/etc., giving the student extra
        context attached to a specific drawing/region.
        """
        target = self.get_layer(target_layer_id)
        if target is None:
            raise KeyError(target_layer_id)
        annotation.anchor_to = target_layer_id
        if annotation.z <= target.z:
            annotation.z = target.z + 1
        return self.add_layer(annotation)

    def annotations_of(self, layer_id: str) -> List[Layer]:
        return [ly for ly in self.layers if ly.anchor_to == layer_id]


def new_layer(layer_type: LayerType, layer_id: Optional[str] = None, **kwargs) -> Layer:
    return Layer(id=layer_id or uuid.uuid4().hex[:8], type=layer_type, **kwargs)


# --------------------------------------------------------------------------- #
# Live deltas (broadcast diffs on top of a base scene)
# --------------------------------------------------------------------------- #
class DeltaOp(str, enum.Enum):
    ADD_LAYER = "add_layer"
    UPDATE_LAYER = "update_layer"
    REMOVE_LAYER = "remove_layer"
    APPEND_STROKE = "append_stroke"


class SceneDelta(BaseModel):
    op: DeltaOp
    layer_id: Optional[str] = None
    layer: Optional[Layer] = None
    patch: dict = Field(default_factory=dict)
    stroke: Optional[Stroke] = None


def apply_delta(scene: Scene, delta: SceneDelta) -> Scene:
    """Apply a single broadcast delta to ``scene`` in place; returns it."""
    if delta.op is DeltaOp.ADD_LAYER:
        if delta.layer is None:
            raise ValueError("ADD_LAYER requires a layer")
        scene.add_layer(delta.layer)
    elif delta.op is DeltaOp.REMOVE_LAYER:
        scene.layers = [ly for ly in scene.layers if ly.id != delta.layer_id]
    elif delta.op is DeltaOp.UPDATE_LAYER:
        layer = scene.get_layer(delta.layer_id or "")
        if layer is None:
            raise KeyError(delta.layer_id)
        updated = layer.model_copy(update=delta.patch)
        scene.layers = [updated if ly.id == layer.id else ly for ly in scene.layers]
    elif delta.op is DeltaOp.APPEND_STROKE:
        layer = scene.get_layer(delta.layer_id or "")
        if layer is None:
            raise KeyError(delta.layer_id)
        if delta.stroke is None:
            raise ValueError("APPEND_STROKE requires a stroke")
        layer.strokes.append(delta.stroke)
    return scene


# --------------------------------------------------------------------------- #
# Extraction -> a new multilayer object (image / clip)
# --------------------------------------------------------------------------- #
class ExtractedObject(BaseModel):
    kind: str           # "image" (instant) | "clip" (time range)
    source_scene_id: str
    bbox: Optional[Transform] = None
    time: Optional[TimeRange] = None
    scene: Scene        # the lifted-out multilayer object


def _intersects(a: Transform, b: Transform) -> bool:
    return not (
        a.x + a.w <= b.x or b.x + b.w <= a.x or a.y + a.h <= b.y or b.y + b.h <= a.y
    )


def extract_region(
    scene: Scene,
    *,
    bbox: Optional[Transform] = None,
    layer_ids: Optional[List[str]] = None,
    time: Optional[TimeRange] = None,
    title: str = "",
) -> ExtractedObject:
    """Lift a region/time slice out of ``scene`` as a new multilayer object.

    Selection = explicit ``layer_ids`` (plus their annotations) and/or every
    layer whose transform intersects ``bbox`` and whose time overlaps ``time``.
    If ``time`` is an instant (start == end) the result is an "image", else a
    "clip".
    """
    selected: List[Layer] = []
    explicit = set(layer_ids or [])
    for layer in scene.layers:
        keep = layer.id in explicit or layer.anchor_to in explicit
        if not keep and bbox is not None and _intersects(layer.transform, bbox):
            keep = True
        if not keep and bbox is None and not explicit:
            keep = True  # no filter -> take all
        if keep and time is not None:
            lt = layer.time
            overlap = (lt.end is None or lt.end >= time.start) and (
                time.end is None or lt.start <= time.end
            )
            keep = overlap
        if keep:
            selected.append(layer.model_copy(deep=True))

    # Rebase time so the extracted object starts at 0.
    if time is not None:
        for layer in selected:
            layer.time = TimeRange(
                start=max(0.0, layer.time.start - time.start),
                end=None
                if layer.time.end is None
                else max(0.0, layer.time.end - time.start),
            )

    sub = Scene(
        title=title or f"{scene.title} (extract)",
        width=scene.width,
        height=scene.height,
        layers=selected,
    )
    kind = "image" if (time is not None and time.end == time.start) else "clip"
    return ExtractedObject(
        kind=kind, source_scene_id=scene.id, bbox=bbox, time=time, scene=sub
    )


# --------------------------------------------------------------------------- #
# Tamper-evident container (integrity / authenticity)
# --------------------------------------------------------------------------- #
class SignedScene(BaseModel):
    format: str = FORMAT
    version: int = FORMAT_VERSION
    alg: str = "HMAC-SHA256"
    content_hash: str
    signature: str
    scene: Scene


def canonical_bytes(scene: Scene) -> bytes:
    return json.dumps(
        scene.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def content_hash(scene: Scene) -> str:
    return hashlib.sha256(canonical_bytes(scene)).hexdigest()


def sign_scene(scene: Scene, key: bytes) -> SignedScene:
    digest = content_hash(scene)
    sig = hmac.new(key, canonical_bytes(scene), hashlib.sha256).hexdigest()
    return SignedScene(content_hash=digest, signature=sig, scene=scene)


def verify_scene(signed: SignedScene, key: bytes) -> bool:
    expected_hash = content_hash(signed.scene)
    if not hmac.compare_digest(expected_hash, signed.content_hash):
        return False
    expected_sig = hmac.new(
        key, canonical_bytes(signed.scene), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_sig, signed.signature)


def serialize(signed: SignedScene) -> str:
    """Serialize the signed container to the .aoeplx (JSON) wire form."""
    return json.dumps(signed.model_dump(mode="json"), separators=(",", ":"))


def deserialize(text: str) -> SignedScene:
    return SignedScene.model_validate_json(text)
