"""Voucher validation rules (coupons, gift codes, class-bound free passes)."""

from __future__ import annotations

import pytest

from identity.vouchers import VoucherStore


def _store(tmp_path):
    return VoucherStore(tmp_path)


def test_class_bound_free_pass_requires_matching_class(tmp_path):
    store = _store(tmp_path)
    store.create("CLASSFREE", "free_pass", class_id="class-abc")

    # Valid only for its own class.
    v, final, _desc = store.validate("CLASSFREE", 99.0, class_id="class-abc")
    assert final == 0.0
    assert v.kind == "free_pass"

    # Wrong class is rejected.
    with pytest.raises(ValueError):
        store.validate("CLASSFREE", 99.0, class_id="class-xyz")

    # Regression: omitting the class must fail closed, not grant a free purchase.
    with pytest.raises(ValueError):
        store.validate("CLASSFREE", 99.0, class_id=None)


def test_unbound_free_pass_is_class_agnostic(tmp_path):
    store = _store(tmp_path)
    store.create("ANYFREE", "free_pass")  # no class_id -> valid anywhere
    _v, final, _desc = store.validate("ANYFREE", 42.0, class_id=None)
    assert final == 0.0
    _v, final, _desc = store.validate("ANYFREE", 42.0, class_id="whatever")
    assert final == 0.0
