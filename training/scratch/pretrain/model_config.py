#!/usr/bin/env python3
"""Track A.2 - model sizing + distributed-parallelism helpers (pure, testable).

Decoder-only transformer parameter counting, Chinchilla-optimal token budgeting,
and 3D-parallelism validation. Used by the scaling-laws ladder to pick the
compute-optimal point before committing the full run, and to sanity-check a
parallelism plan before launching on the cluster.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelSpec:
    layers: int
    hidden: int
    heads: int
    vocab: int = 64000
    ffn_mult: int = 4


def transformer_params(spec: ModelSpec) -> int:
    """Approximate parameter count of a decoder-only transformer."""
    h = spec.hidden
    attn = 4 * h * h                      # q,k,v,o projections
    ffn = 2 * spec.ffn_mult * h * h       # up + down projection
    per_layer = attn + ffn + 4 * h        # + layernorm/bias terms
    embeddings = spec.vocab * h           # (tied input/output embeddings)
    return per_layer * spec.layers + embeddings


def chinchilla_tokens(params: int, ratio: int = 20) -> int:
    """Compute-optimal training tokens (~20 tokens/param)."""
    return params * ratio


def validate_parallelism(world_size: int, tensor: int, pipeline: int) -> int:
    """Return the data-parallel degree; raise if the plan doesn't fit world_size."""
    if tensor < 1 or pipeline < 1 or world_size < 1:
        raise ValueError("degrees must be >= 1")
    model_parallel = tensor * pipeline
    if world_size % model_parallel != 0:
        raise ValueError(
            f"tensor*pipeline={model_parallel} must divide world_size={world_size}"
        )
    return world_size // model_parallel
