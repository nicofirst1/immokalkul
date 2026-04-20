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


# ---------------------------------------------------------------------------
# Audit v1 [C3]: Sondertilgung + Zinsbindung metadata
# ---------------------------------------------------------------------------
def _single_loan_schedule(*, principal=300_000, rate=0.034, monthly=1_350.0,
                           extras=0.0, pct=0.0, fixed=0, horizon=50):
    """Build a 1-loan scenario + amort schedule for isolated engine tests."""
    from immokalkul import Financing
    fin = Financing(
        initial_capital=0.0,
        loans=[Loan("Bank", principal, rate, monthly, is_annuity=True,
                     is_adaptive=False,
                     annual_extra_repayment_eur=extras,
                     sondertilgung_pct_of_original_principal=pct,
                     fixed_term_years=fixed)],
        debt_budget_monthly=2_000.0,
    )
    return amortization_schedule(fin, horizon)


def test_sondertilgung_lump_sum_reduces_balance() -> None:
    """An annual extra lump of €5k must drop balance year-on-year vs a twin
    scenario without it."""
    base = _single_loan_schedule(extras=0.0)
    with_extra = _single_loan_schedule(extras=5_000.0)
    # Year 1 end-of-year balance (= year-2 opening balance) must be €5k lower.
    diff = base["Bank_balance"].iloc[1] - with_extra["Bank_balance"].iloc[1]
    assert diff == pytest.approx(5_000, abs=1)
    # <name>_extra_repayment column is present and carries the €5k.
    assert with_extra["Bank_extra_repayment"].iloc[0] == pytest.approx(5_000)
    assert base["Bank_extra_repayment"].iloc[0] == 0


def test_sondertilgung_pct_of_original_principal_reduces_balance() -> None:
    """5 % Sondertilgungsrecht on €300k principal = €15k/yr extra repayment."""
    sched = _single_loan_schedule(principal=300_000, pct=0.05)
    # Year 1 applied extra = 0.05 × 300k = €15k (balance has room).
    assert sched["Bank_extra_repayment"].iloc[0] == pytest.approx(15_000)
    # It keeps firing each year while balance > 0.
    assert sched["Bank_extra_repayment"].iloc[1] == pytest.approx(15_000)


def test_sondertilgung_clamped_to_remaining_balance() -> None:
    """Excessive Sondertilgung (much larger than principal) must not push
    the balance negative — clamped to the remaining balance at year-end."""
    sched = _single_loan_schedule(principal=30_000, extras=50_000.0)
    # All balances non-negative throughout the horizon.
    assert (sched["Bank_balance"] >= 0).all()
    # First year extra clipped: balance ~30k - regular_payment - 30k ≈ can't be
    # negative. Recorded extra ≤ the remaining balance after regular payment.
    first_year_extra = sched["Bank_extra_repayment"].iloc[0]
    assert 0 <= first_year_extra <= 30_000


def test_sondertilgung_flows_into_total_payment() -> None:
    """total_payment aggregate must include Sondertilgung extras — that's
    what cashflow.py reads as `loan_payment` for the user's outflow."""
    sched = _single_loan_schedule(extras=5_000.0)
    regular_year_1 = sched["Bank_payment"].iloc[0]
    extras_year_1 = sched["Bank_extra_repayment"].iloc[0]
    total_year_1 = sched["total_payment"].iloc[0]
    assert total_year_1 == pytest.approx(regular_year_1 + extras_year_1,
                                           abs=0.01)


def test_fixed_term_years_is_pure_metadata() -> None:
    """fixed_term_years is informational only — the engine must NOT switch
    the rate after year N. Interest in year 11 = balance × original rate
    for a 10-year fixed term."""
    sched = _single_loan_schedule(rate=0.034, fixed=10)
    # Interest year 11 / opening balance year 11 ≈ 0.034 (not some other rate).
    opening_y11 = sched["Bank_balance"].iloc[10]  # year 11 is index 10 (1-indexed)
    interest_y11 = sched["Bank_interest"].iloc[10]
    implied_rate = interest_y11 / opening_y11
    assert implied_rate == pytest.approx(0.034, rel=1e-6)


def test_loan_validates_negative_inputs() -> None:
    """Loan.__post_init__ rejects negative Sondertilgung / fixed-term values
    with a clear ValueError."""
    with pytest.raises(ValueError, match="annual_extra_repayment_eur"):
        Loan("Bad", 100_000, 0.034, 500, annual_extra_repayment_eur=-1.0)
    with pytest.raises(ValueError, match="sondertilgung_pct"):
        Loan("Bad", 100_000, 0.034, 500,
             sondertilgung_pct_of_original_principal=-0.01)
    with pytest.raises(ValueError, match="sondertilgung_pct"):
        Loan("Bad", 100_000, 0.034, 500,
             sondertilgung_pct_of_original_principal=1.5)
    with pytest.raises(ValueError, match="fixed_term_years"):
        Loan("Bad", 100_000, 0.034, 500, fixed_term_years=-1)


def test_annuity_payment_column_unchanged_by_sondertilgung() -> None:
    """Regression guard for test_annuity_payment_is_constant_until_cleared:
    <name>_payment must stay 'regular payment only' even when Sondertilgung
    is active. Only <name>_extra_repayment and total_payment reflect extras."""
    base = _single_loan_schedule(extras=0.0)
    with_extra = _single_loan_schedule(extras=10_000.0)
    # Per-loan payment column is IDENTICAL until the shorter schedule clears.
    # Compare the first 5 years where balances are still healthy in both.
    for yr in range(5):
        assert base["Bank_payment"].iloc[yr] == pytest.approx(
            with_extra["Bank_payment"].iloc[yr], abs=0.01), (
            f"regular payment column diverged at year {yr+1}")
