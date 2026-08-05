"""Shared helpers for the flat, env/API-tunable knob sets.

Both the vision and voice knob sets are frozen dataclasses of plain numbers that
need the same three behaviours: coerce a string to the declared type, read
overrides from prefixed environment variables, and apply a validated partial
patch. Keeping that logic here stops the two from drifting apart.
"""

from __future__ import annotations

import os
from dataclasses import fields, replace
from typing import Any, TypeVar

T = TypeVar("T")


def coerce_value(declared_type: Any, raw: Any, field_name: str) -> Any:
    """Coerce an env string or JSON value to the field's declared numeric type."""
    wants_int = declared_type is int or declared_type == "int"
    try:
        return int(raw) if wants_int else float(raw)
    except (TypeError, ValueError) as exc:
        kind = "an integer" if wants_int else "a number"
        raise ValueError(f"{field_name} must be {kind} (got {raw!r})") from exc


def env_overrides(
    cls: type, prefix: str, environ: dict[str, str] | None = None
) -> dict[str, Any]:
    """Collect <PREFIX><FIELD_NAME_UPPERCASE> overrides for a knob dataclass."""
    env = os.environ if environ is None else environ
    overrides: dict[str, Any] = {}
    for field in fields(cls):
        raw = env.get(prefix + field.name.upper())
        if raw is None or not str(raw).strip():
            continue
        overrides[field.name] = coerce_value(field.type, raw, field.name)
    return overrides


def patch_knobs(instance: T, overrides: dict[str, Any]) -> T:
    """Return a copy of `instance` with `overrides` applied, rejecting unknown keys."""
    known = {f.name: f for f in fields(instance)}
    unknown = sorted(set(overrides) - set(known))
    if unknown:
        raise ValueError(f"Unknown tuning knob(s): {', '.join(unknown)}")
    coerced: dict[str, Any] = {}
    for key, raw in overrides.items():
        if raw is None:
            continue
        coerced[key] = coerce_value(known[key].type, raw, key)
    return replace(instance, **coerced)
