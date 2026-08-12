"""Shared frozen-dataclass patching helpers (env + live PATCH)."""

from __future__ import annotations

import dataclasses
import os
from typing import Any, Type, TypeVar

T = TypeVar("T")


def env_overrides(cls: Type[T], prefix: str, environ: dict[str, str] | None = None) -> dict[str, Any]:
    env = environ if environ is not None else os.environ
    out: dict[str, Any] = {}
    fields = {f.name: f for f in dataclasses.fields(cls)}  # type: ignore[arg-type]
    for name, field in fields.items():
        raw = env.get(f"{prefix}{name.upper()}")
        if raw is None or raw == "":
            continue
        typ = field.type
        if typ is bool or typ == "bool":
            out[name] = str(raw).strip().lower() in ("1", "true", "yes", "on")
        elif typ is int or typ == "int":
            out[name] = int(raw)
        elif typ is float or typ == "float":
            out[name] = float(raw)
        else:
            out[name] = raw
    return out


def patch_knobs(instance: T, overrides: dict[str, Any]) -> T:
    data = dataclasses.asdict(instance)  # type: ignore[arg-type]
    for key, value in (overrides or {}).items():
        if key not in data:
            raise ValueError(f"Unknown knob '{key}'")
        data[key] = value
    return type(instance)(**data)  # type: ignore[misc]
