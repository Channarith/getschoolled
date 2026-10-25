"""Tax is carried out as configured; nothing here asserts a tax rule."""

from aoep_shared.checkout_tax import compute_tax, manual_rates, needs_billing_state, tax_mode


def test_default_is_no_tax_and_asks_for_no_location(monkeypatch):
    monkeypatch.delenv("COURSE_TAX_MODE", raising=False)
    assert tax_mode() == "none" and not needs_billing_state()
    assert compute_tax(1999)["tax_cents"] == 0 and compute_tax(1999)["requires_state"] is False


def test_an_unknown_mode_falls_back_to_none(monkeypatch):
    monkeypatch.setenv("COURSE_TAX_MODE", "sure-why-not")
    assert tax_mode() == "none"


def test_provider_mode_adds_nothing_here_because_the_processor_calculates(monkeypatch):
    monkeypatch.setenv("COURSE_TAX_MODE", "provider")
    assert compute_tax(1999)["tax_cents"] == 0 and not needs_billing_state()


def test_manual_mode_uses_the_configured_rate_for_the_state_and_rounds_half_up(monkeypatch):
    monkeypatch.setenv("COURSE_TAX_MODE", "manual")
    monkeypatch.setenv("COURSE_TAX_RATES_JSON", '{"ca": 0.0725, "NY": 0.04, "bad": "x", "XX": 5}')
    assert needs_billing_state() and set(manual_rates()) == {"CA", "NY"}
    ca = compute_tax(1999, state="ca")
    assert ca["tax_cents"] == 145 and ca["rate"] == 0.0725 and ca["state"] == "CA"  # 144.9275 -> 145
    assert compute_tax(1999, state="NY")["tax_cents"] == 80
    assert compute_tax(1999, state="TX")["tax_cents"] == 0  # no entry: no tax charged


def test_manual_mode_needs_a_state_before_it_can_quote(monkeypatch):
    monkeypatch.setenv("COURSE_TAX_MODE", "manual")
    monkeypatch.setenv("COURSE_TAX_RATES_JSON", '{"CA": 0.0725}')
    quote = compute_tax(1999)
    assert quote["requires_state"] is True and quote["tax_cents"] == 0


def test_garbage_rates_json_disables_manual_tax_instead_of_crashing(monkeypatch):
    monkeypatch.setenv("COURSE_TAX_MODE", "manual")
    monkeypatch.setenv("COURSE_TAX_RATES_JSON", "{not json")
    assert manual_rates() == {} and compute_tax(1999, state="CA")["tax_cents"] == 0
