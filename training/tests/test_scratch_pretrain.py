"""Track A.2 model sizing + parallelism + pretrain --check smoke."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scratch" / "pretrain"))

from model_config import (  # noqa: E402
    ModelSpec,
    chinchilla_tokens,
    transformer_params,
    validate_parallelism,
)


def test_param_count_in_expected_range():
    proxy = transformer_params(ModelSpec(layers=24, hidden=2048, heads=16))
    assert 0.8e9 < proxy < 1.8e9  # ~1B rung


def test_bigger_model_has_more_params():
    proxy = transformer_params(ModelSpec(layers=24, hidden=2048, heads=16))
    mid = transformer_params(ModelSpec(layers=32, hidden=4096, heads=32))
    assert mid > proxy


def test_chinchilla_ratio():
    assert chinchilla_tokens(1_000_000_000) == 20_000_000_000


def test_parallelism_valid_and_invalid():
    assert validate_parallelism(8, tensor=8, pipeline=1) == 1
    assert validate_parallelism(16, tensor=4, pipeline=2) == 2
    with pytest.raises(ValueError):
        validate_parallelism(8, tensor=8, pipeline=2)  # 16 does not divide 8


def test_pretrain_check_plan():
    from run_pretrain import plan_from_ladder

    ladder = Path(__file__).resolve().parents[1] / "scratch" / "config" / "model_ladder.yaml"
    plan = plan_from_ladder(str(ladder), world_size=8, tensor=8, pipeline=1)
    assert plan["data_parallel"] == 1
    named = {r["name"]: r for r in plan["rungs"]}
    assert named["proxy-1b"]["params_billions"] >= 0.8
    assert named["target"].get("skipped") is True  # placeholder rung skipped
