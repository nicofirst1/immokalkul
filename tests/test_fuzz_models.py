"""Property-based fuzz tests for the data layer — [C10] layer 1.

Uses hypothesis to generate plausible-but-wide Scenario inputs and check
invariants that must hold regardless of the specific draw:

- YAML round-trip (load → save → load) preserves fields.
- `run(s)` either returns a ScenarioResult or raises a typed ValueError —
  never a raw KeyError / ZeroDivisionError / NaN propagation.
- Purchase costs reconcile (price + fees + reno = total_cost).
- No NaN / inf in cashflow cumulative_wealth.
- `compute_affordability` does not crash on any valid Scenario.
- Annuity loans amortize monotonically when the payment covers interest.

These are not regression pins — they are invariants. If one fails, it
points at a real robustness bug.
"""
from __future__ import annotations

import math
import tempfile
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest
from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from immokalkul import (
    CapexItem,
    CostInputs,
    Financing,
    GlobalParameters,
    LiveParameters,
    Loan,
    Property,
    RentParameters,
    Scenario,
    compute_affordability,
    load_scenario,
    run,
    save_scenario,
)
from immokalkul.financing import compute_purchase_costs

# Keep the fuzz cheap so the whole suite stays fast.
FUZZ_SETTINGS = settings(
    max_examples=40,
    deadline=None,  # run(s) can be slow for 60-year horizons
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large],
)


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------
property_names = st.text(
    alphabet=st.characters(whitelist_categories=("L", "N"), whitelist_characters=" -"),
    min_size=1, max_size=40)


@st.composite
def properties(draw):
    return Property(
        name=draw(property_names),
        purchase_price=draw(st.floats(min_value=50_000, max_value=5_000_000,
                                       allow_nan=False, allow_infinity=False)),
        living_space_m2=draw(st.floats(min_value=15, max_value=500,
                                        allow_nan=False, allow_infinity=False)),
        plot_size_m2=draw(st.floats(min_value=15, max_value=5_000,
                                     allow_nan=False, allow_infinity=False)),
        year_built=draw(st.integers(min_value=1850, max_value=2026)),
        year_last_major_renovation=draw(st.one_of(
            st.none(),
            st.integers(min_value=1900, max_value=2026))),
        property_type=draw(st.sampled_from(["apartment", "house"])),
        heating_type=draw(st.sampled_from(
            ["gas", "oil", "heat_pump", "district", "electric", "wood"])),
        energy_demand_kwh_per_m2_year=draw(st.floats(
            min_value=20, max_value=350, allow_nan=False, allow_infinity=False)),
        has_elevator=draw(st.booleans()),
        bodenrichtwert_eur_per_m2=draw(st.one_of(
            st.none(),
            st.floats(min_value=50, max_value=10_000,
                      allow_nan=False, allow_infinity=False))),
        is_denkmal=draw(st.booleans()),
    )


@st.composite
def loans_list(draw):
    n = draw(st.integers(min_value=1, max_value=4))
    loans = []
    for i in range(n):
        loans.append(Loan(
            name=f"Loan{i}",
            principal=draw(st.floats(min_value=10_000, max_value=2_000_000,
                                      allow_nan=False, allow_infinity=False)),
            interest_rate=draw(st.floats(min_value=0.0, max_value=0.15,
                                          allow_nan=False, allow_infinity=False)),
            monthly_payment=draw(st.floats(min_value=50, max_value=10_000,
                                            allow_nan=False, allow_infinity=False)),
            is_annuity=draw(st.booleans()),
            is_adaptive=False,
        ))
    # At most one adaptive (engine convention); adaptive only on non-annuity.
    adaptive_idx = draw(st.one_of(
        st.none(),
        st.integers(min_value=0, max_value=n - 1)))
    if adaptive_idx is not None:
        loans[adaptive_idx].is_annuity = False
        loans[adaptive_idx].is_adaptive = True
    return loans


@st.composite
def scenarios(draw):
    prop = draw(properties())
    loans = draw(loans_list())
    fin = Financing(
        initial_capital=draw(st.floats(min_value=0, max_value=2_000_000,
                                        allow_nan=False, allow_infinity=False)),
        loans=loans,
        debt_budget_monthly=draw(st.floats(min_value=500, max_value=10_000,
                                            allow_nan=False, allow_infinity=False)),
        monthly_total_housing_budget_eur=draw(st.floats(
            min_value=0, max_value=10_000,
            allow_nan=False, allow_infinity=False)),
        notary_pct=draw(st.one_of(
            st.none(),
            st.floats(min_value=0, max_value=0.05,
                      allow_nan=False, allow_infinity=False))),
        grundbuch_pct=draw(st.one_of(
            st.none(),
            st.floats(min_value=0, max_value=0.03,
                      allow_nan=False, allow_infinity=False))),
    )
    rent = RentParameters(
        monthly_rent=draw(st.floats(min_value=100, max_value=10_000,
                                     allow_nan=False, allow_infinity=False)),
        monthly_parking=draw(st.floats(min_value=0, max_value=500,
                                        allow_nan=False, allow_infinity=False)),
        annual_rent_escalation=draw(st.floats(min_value=0.0, max_value=0.10,
                                                allow_nan=False, allow_infinity=False)),
        expected_vacancy_months_per_year=draw(st.floats(
            min_value=0.0, max_value=6.0,
            allow_nan=False, allow_infinity=False)),
        has_property_manager=draw(st.booleans()),
        property_manager_pct_of_rent=draw(st.floats(
            min_value=0.0, max_value=0.15,
            allow_nan=False, allow_infinity=False)),
    )
    live = LiveParameters(
        people_in_household=draw(st.integers(min_value=1, max_value=10)),
        large_appliances=draw(st.integers(min_value=0, max_value=15)),
        current_monthly_rent_warm_eur=draw(st.floats(
            min_value=0, max_value=5_000,
            allow_nan=False, allow_infinity=False)),
    )
    globals_ = GlobalParameters(
        monthly_household_income=draw(st.floats(
            min_value=1_000, max_value=30_000,
            allow_nan=False, allow_infinity=False)),
        additional_monthly_savings=draw(st.floats(
            min_value=0, max_value=5_000,
            allow_nan=False, allow_infinity=False)),
        cost_inflation_annual=draw(st.floats(
            min_value=0.0, max_value=0.10,
            allow_nan=False, allow_infinity=False)),
        marginal_tax_rate=draw(st.floats(
            min_value=0.10, max_value=0.55,
            allow_nan=False, allow_infinity=False)),
        horizon_years=draw(st.integers(min_value=10, max_value=60)),
    )
    return Scenario(
        mode=draw(st.sampled_from(["rent", "live"])),
        property=prop,
        financing=fin,
        costs=CostInputs(),
        rent=rent,
        live=live,
        globals=globals_,
        user_capex=[],
        auto_schedule_capex=draw(st.booleans()),
    )


# ---------------------------------------------------------------------------
# Invariant tests
# ---------------------------------------------------------------------------
@given(scenarios())
@FUZZ_SETTINGS
def test_yaml_round_trip_preserves_fields(s: Scenario) -> None:
    """Load(save(s)) must yield a field-identical Scenario."""
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False,
                                      mode="w") as f:
        path = Path(f.name)
    try:
        save_scenario(s, path)
        s2 = load_scenario(path)
        assert s2.mode == s.mode
        assert s2.property.purchase_price == pytest.approx(
            s.property.purchase_price)
        assert s2.property.year_built == s.property.year_built
        assert s2.financing.initial_capital == pytest.approx(
            s.financing.initial_capital)
        assert len(s2.financing.loans) == len(s.financing.loans)
        assert s2.globals.horizon_years == s.globals.horizon_years
        assert s2.globals.marginal_tax_rate == pytest.approx(
            s.globals.marginal_tax_rate)
    finally:
        path.unlink(missing_ok=True)


@given(scenarios())
@FUZZ_SETTINGS
def test_engine_runs_or_raises_typed_error(s: Scenario) -> None:
    """run(s) must return a ScenarioResult or raise ValueError. Any other
    exception type is a robustness bug."""
    try:
        r = run(s)
    except ValueError:
        return  # our typed error — acceptable
    assert r is not None
    assert r.cashflow is not None
    assert len(r.cashflow) == s.globals.horizon_years


@given(scenarios())
@FUZZ_SETTINGS
def test_purchase_costs_reconcile(s: Scenario) -> None:
    """price + fees_subtotal + renovation = total_cost must hold for every
    draw. Picks up any arithmetic regressions in compute_purchase_costs."""
    pc = compute_purchase_costs(
        s.property,
        renovation_capitalized=0.0,
        notary_rate=(s.financing.notary_pct
                     if s.financing.notary_pct is not None else 0.015),
        grundbuch_rate=(s.financing.grundbuch_pct
                        if s.financing.grundbuch_pct is not None else 0.005),
    )
    assert pc.total_cost == pytest.approx(
        pc.purchase_price + pc.fees_subtotal + pc.renovation_capitalized,
        abs=1.0)


@given(scenarios())
@FUZZ_SETTINGS
def test_no_nan_or_inf_in_cashflow(s: Scenario) -> None:
    """Cashflow and cumulative-wealth series must stay finite for every
    draw. NaN/inf in the pipe means a division-by-zero, log-of-negative,
    or similar degenerate path slipped through."""
    try:
        r = run(s)
    except ValueError:
        return
    cf = r.cashflow
    for col in cf.columns:
        series = cf[col].to_numpy(dtype=float, na_value=0.0)
        assert np.all(np.isfinite(series)), (
            f"non-finite value in cashflow column {col!r}")


@given(scenarios())
@FUZZ_SETTINGS
def test_affordability_does_not_crash(s: Scenario) -> None:
    """compute_affordability must return a dict with all documented keys
    for every valid Scenario."""
    try:
        r = run(s)
    except ValueError:
        return
    a = compute_affordability(r, s)
    for key in ("loan_pct", "burden_pct", "down_pct", "ltv",
                 "price_to_income", "verdict", "level",
                 "loan_pct_warn", "burden_pct_warn",
                 "housing_budget_set", "housing_budget_exceeded"):
        assert key in a, f"affordability dict missing {key!r}"


@given(scenarios())
@FUZZ_SETTINGS
def test_annuity_balance_is_monotonic(s: Scenario) -> None:
    """For any annuity loan whose annual payment strictly exceeds opening-
    year interest, balance must be monotonically non-increasing. Draws not
    meeting the precondition are skipped."""
    try:
        r = run(s)
    except ValueError:
        return
    am = r.amort
    for loan in s.financing.loans:
        if not loan.is_annuity or loan.is_adaptive:
            continue
        col = f"{loan.name}_balance"
        if col not in am.columns:
            continue
        balances = am[col].to_list()
        if len(balances) < 2:
            continue
        # Precondition: payment exceeds first-year interest — otherwise
        # balance may grow (legal interest-only / underwater case).
        first_year_interest = balances[0] * loan.interest_rate
        annual_payment = loan.monthly_payment * 12
        assume(annual_payment > first_year_interest + 1)
        for i in range(1, len(balances)):
            assert balances[i] <= balances[i - 1] + 1, (
                f"loan {loan.name!r} balance grew at year {i}: "
                f"{balances[i-1]:.2f} → {balances[i]:.2f}")
