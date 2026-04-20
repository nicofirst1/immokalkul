"""Financing / amortization correctness."""
from __future__ import annotations

import pytest

from immokalkul import Loan, run
from immokalkul.financing import (
    amortization_schedule,
    compute_purchase_costs,
)

from .conftest import make_scenario


def test_annuity_payment_is_constant_until_cleared() -> None:
    """For a pure annuity loan, annual payment is constant while balance>0."""
    s = make_scenario(bank_principal=300_000, bank_rate=0.034, bank_monthly=1_350.0)
    am = amortization_schedule(s.financing, s.globals.horizon_years)
    active = am[am["Bank_balance"] > 0]
    # Annual payments are all equal to 12 × monthly, with ≤€1 rounding.
    target = 1_350.0 * 12
    assert all(abs(p - target) < 1.0 or abs(p - active["Bank_payment"].max()) < 1.0
               for p in active["Bank_payment"].tolist()[:-1])


def test_adaptive_loan_absorbs_freed_capacity() -> None:
    """Once non-adaptive loans clear, the adaptive loan's payment should
    exceed its stated minimum (if debt_budget allows)."""
    adaptive = Loan("Family", 80_000, 0.0, 150.0, is_annuity=False,
                    is_adaptive=True)
    s = make_scenario(
        bank_principal=120_000, bank_rate=0.04, bank_monthly=700.0,
        extra_loans=[adaptive],
    )
    s.financing.debt_budget_monthly = 1_200.0
    am = amortization_schedule(s.financing, s.globals.horizon_years)

    # While bank is outstanding, family gets ≈ its minimum.
    bank_active_years = am["Bank_balance"] > 0
    assert bank_active_years.any()

    # Find a year where bank has cleared AND family still has balance.
    bank_clear = (~bank_active_years) & (am["Family_balance"] > 0)
    if bank_clear.any():
        clear_year = am[bank_clear].iloc[0]
        # With the bank gone and debt_budget 1200/mo = 14400/yr freed up,
        # family payment must exceed its 12×150 = 1800/yr minimum.
        assert clear_year["Family_payment"] > 1_800 + 100


def test_non_adaptive_loan_stays_at_fixed_payment() -> None:
    """Without the adaptive flag, a fixed-payment loan never exceeds
    12 × monthly_payment."""
    fixed = Loan("Family", 80_000, 0.0, 150.0, is_annuity=False,
                 is_adaptive=False)
    s = make_scenario(
        bank_principal=120_000, bank_rate=0.04, bank_monthly=700.0,
        extra_loans=[fixed],
    )
    am = amortization_schedule(s.financing, s.globals.horizon_years)
    max_family = am["Family_payment"].max()
    assert max_family <= 150 * 12 + 1  # ≤ minimum + €1 rounding


def test_purchase_cost_components_add_up() -> None:
    """Total cost must equal price + fees + initial renovation."""
    s = make_scenario(price=400_000)
    pc = compute_purchase_costs(s.property, renovation_capitalized=25_000)
    assert pc.total_cost == pytest.approx(
        pc.purchase_price + pc.fees_subtotal + pc.renovation_capitalized,
        abs=0.01,
    )


def test_notary_grundbuch_default_split_matches_rules_de() -> None:
    """Default Notar + Grundbuch rates must match rules_de and sum to the
    legacy bundled 2 % figure — guarantees numeric stability when the
    split was introduced in [C7]."""
    from immokalkul import rules_de
    s = make_scenario(price=400_000)
    pc = compute_purchase_costs(s.property)
    assert pc.notary_fee == pytest.approx(400_000 * rules_de.NOTARY_FEE)
    assert pc.grundbuch_fee == pytest.approx(400_000 * rules_de.GRUNDBUCH_FEE)
    # Backward-compat property keeps the bundled number available.
    assert pc.notary_grundbuch == pytest.approx(
        pc.notary_fee + pc.grundbuch_fee)
    # Sum still equals the legacy combined 2 % of price.
    assert pc.notary_grundbuch == pytest.approx(400_000 * 0.02, abs=1.0)


def test_notary_grundbuch_overrides_are_honoured() -> None:
    """Explicit notary_rate / grundbuch_rate kwargs must flow through to
    the breakdown — the mechanism the sidebar Advanced expander uses."""
    s = make_scenario(price=500_000)
    pc = compute_purchase_costs(s.property,
                                 notary_rate=0.018,
                                 grundbuch_rate=0.007)
    assert pc.notary_fee == pytest.approx(500_000 * 0.018)
    assert pc.grundbuch_fee == pytest.approx(500_000 * 0.007)
    # AfA-capitalizable portion uses 80 % of the combined Notar + Grundbuch.
    from immokalkul import rules_de
    expected_afa = (pc.grunderwerbsteuer + pc.maklerprovision
                    + (pc.notary_fee + pc.grundbuch_fee)
                      * rules_de.NOTARY_GRUNDBUCH_AFA_SHARE)
    assert pc.fees_capitalizable_for_afa == pytest.approx(expected_afa)


def test_all_debt_clears_within_horizon_for_small_loans() -> None:
    """A small loan with a high monthly payment must clear before horizon's
    end — a sanity check on the amortization loop."""
    s = make_scenario(bank_principal=30_000, bank_rate=0.034, bank_monthly=500.0)
    r = run(s)
    assert r.years_to_debt_free < s.globals.horizon_years
