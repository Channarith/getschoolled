"""Feature-flag core: catalog, targeting, rollout, overrides, admin gate."""

import pytest

from aoep_shared.flags import (
    CATALOG_BY_KEY,
    FLAG_CATALOG,
    FlagStore,
    FlagType,
    require_admin,
)


def test_catalog_is_comprehensive_and_well_formed():
    keys = [f.key for f in FLAG_CATALOG]
    assert len(keys) == len(set(keys))  # unique keys
    cats = {f.category for f in FLAG_CATALOG}
    # Covers the major design areas the platform needs.
    assert {"engagement", "data", "access", "monetization", "ai", "ops"} <= cats
    assert "engagement.post_class_survey" in CATALOG_BY_KEY
    assert "data.multidim_datamart" in CATALOG_BY_KEY
    assert "access.user_levels" in CATALOG_BY_KEY


def test_default_resolution():
    s = FlagStore()
    assert s.resolve("engagement.post_class_survey") is False  # default off
    assert s.resolve("ai.hallucination_guard") is True          # default on
    assert s.resolve("access.user_levels") == "standard"


def test_enable_and_disable_bool_flag():
    s = FlagStore()
    s.set_flag("engagement.post_class_survey", enabled=True, value=True, actor="root")
    assert s.resolve("engagement.post_class_survey") is True
    s.set_flag("engagement.post_class_survey", enabled=False)
    assert s.resolve("engagement.post_class_survey") is False


def test_string_multivariate_with_options_validation():
    s = FlagStore()
    s.set_flag("access.user_levels", value="educator")
    assert s.resolve("access.user_levels") == "educator"
    with pytest.raises(ValueError):
        s.set_flag("access.user_levels", value="superuser")  # not allowed


def test_tier_targeting_allow_list():
    s = FlagStore()
    s.set_flag("monetization.dynamic_pricing", enabled=True, value=True,
               tiers=["pro", "premium"])
    assert s.resolve("monetization.dynamic_pricing", tier="pro") is True
    assert s.resolve("monetization.dynamic_pricing", tier="free") is False


def test_percent_rollout_is_stable_and_monotonic_ish():
    s = FlagStore()
    # 0% -> nobody; 100% -> everybody.
    s.set_flag("access.beta_program", rollout_pct=0)
    assert s.resolve("access.beta_program", subject="user-1") is False
    s.set_flag("access.beta_program", rollout_pct=100)
    assert s.resolve("access.beta_program", subject="user-1") is True
    # Partial rollout exposes a non-empty, non-full subset.
    s.set_flag("access.beta_program", rollout_pct=50)
    exposed = [s.resolve("access.beta_program", subject=f"u{i}") for i in range(200)]
    assert 0 < sum(exposed) < 200
    # Stable for the same subject.
    assert s.resolve("access.beta_program", subject="u1") == s.resolve(
        "access.beta_program", subject="u1")


def test_per_subject_override_wins():
    s = FlagStore()
    s.set_flag("engagement.post_class_survey", enabled=False)
    s.set_override("engagement.post_class_survey", "vip-user", True)
    assert s.resolve("engagement.post_class_survey", subject="vip-user") is True
    assert s.resolve("engagement.post_class_survey", subject="other") is False


def test_int_flag_coercion():
    s = FlagStore()
    s.set_flag("access.max_students_per_account", value="12")
    assert s.resolve("access.max_students_per_account") == 12


def test_list_specs_hides_admin_only_for_public():
    s = FlagStore()
    public = {d["key"] for d in s.list_specs(include_admin=False)}
    assert "data.multidim_datamart" not in public  # admin_only
    assert "engagement.post_class_survey" in public
    full = {d["key"] for d in s.list_specs(include_admin=True)}
    assert "data.multidim_datamart" in full


def test_unknown_flag_raises():
    s = FlagStore()
    with pytest.raises(KeyError):
        s.resolve("does.not.exist")
    with pytest.raises(KeyError):
        s.set_flag("does.not.exist", enabled=True)


def test_require_admin_constant_time_check():
    assert require_admin("s3cret", "s3cret") is True
    assert require_admin("wrong", "s3cret") is False
    assert require_admin("", "s3cret") is False
    assert require_admin("x", "") is False  # unset secret never authorizes


def test_evaluate_all_excludes_admin_by_default():
    s = FlagStore()
    pub = s.evaluate_all(tier="free")
    assert "engagement.post_class_survey" in pub
    assert "ops.maintenance_mode" not in pub
    full = s.evaluate_all(tier="free", include_admin=True)
    assert "ops.maintenance_mode" in full


def test_percent_type_default_resolves_via_bucket():
    s = FlagStore()
    # ux.netflix_carousels default 100 -> always on.
    assert s.resolve("ux.netflix_carousels", subject="u1") is True
    # ux.new_player default 0 -> off.
    assert s.resolve("ux.new_player", subject="u1") is False
    assert FlagType.PERCENT  # enum referenced
