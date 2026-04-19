"""Tests for the affordability helper that powers the Summary dashboard."""
from __future__ import annotations

import pytest

from immokalkul import Loan, compute_affordability, run

from .conftest import make_scenario


def _afford(s):
    """Run the engine and compute affordability in one step."""
    return compute_affordability(run(s), s)


def test_verdict_levels_match_fail_count() -> None:
    """0 fails → ok, 1 fail → warn, 2+ fails → fail."""
    # A clean scenario: large income, large down payment, modest price.
    # bank_principal auto-balances to close the funding plan exactly.
    clean = make_scenario(
        price=250_000, initial_capital=100_000,
        bank_rate=0.034, bank_monthly=720.0,
        monthly_income=9_000, monthly_rent=1_600,
    )
    a = _afford(clean)
    assert a["level"] == "ok", f"expected ok, got {a['level']}: failed = {a['failed']}"
    assert a["n_fail"] == 0
    assert "✅" in a["verdict"]

    # Stretched scenario: tiny income, undersized down payment, loan auto-
    # balances to the full cost so LTV blows past 80%.
    stretched = make_scenario(
        price=800_000, initial_capital=10_000,
        bank_rate=0.04, bank_monthly=3_900.0,
        monthly_income=3_000, monthly_rent=1_500,
    )
    a = _afford(stretched)
    assert a["level"] == "fail"
    assert a["n_fail"] >= 2
    assert "❌" in a["verdict"]


def test_rent_mode_has_yield_checks() -> None:
    s = make_scenario(mode="rent")
    a = _afford(s)
    headlines = [c[3] for c in a["checks"]]
    assert any("yield" in h for h in headlines)
    assert any("rent doesn't cover" in h or "rent" in h for h in headlines)


def test_live_mode_yield_checks_absent() -> None:
    s = make_scenario(mode="live")
    a = _afford(s)
    headlines = [c[3] for c in a["checks"]]
    assert not any("yield" in h for h in headlines)


def test_live_mode_premium_check_only_when_rent_set() -> None:
    # No current rent set → no premium check.
    s_unset = make_scenario(mode="live", current_rent_warm=0.0)
    a = _afford(s_unset)
    headlines = [c[3] for c in a["checks"]]
    assert not any("premium" in h for h in headlines)

    # Current rent set → premium check appears.
    s_set = make_scenario(mode="live", current_rent_warm=1_800.0)
    a = _afford(s_set)
    headlines = [c[3] for c in a["checks"]]
    assert any("premium" in h for h in headlines)


def test_live_mode_small_premium_passes() -> None:
    """A small monthly premium over current rent (< 15 % of income) should
    not fail the affordability check — you're just shifting rent to equity."""
    s = make_scenario(
        mode="live", price=400_000, initial_capital=150_000,
        bank_rate=0.034, bank_monthly=1_200.0,
        monthly_income=6_000, current_rent_warm=1_800.0,
    )
    a = _afford(s)
    premium_checks = [c for c in a["checks"]
                       if "premium" in c[3]]
    assert premium_checks
    # Expect it to pass — this scenario has low loan payment + moderate ops,
    # so the monthly ownership premium over €1,800 rent should be < 15 %
    # of a €6,000 income.
    assert bool(premium_checks[0][0]) is True


def test_live_mode_burden_subtracts_current_rent(bonn_scenario) -> None:
    """With current warm rent set, live-mode burden_pct should reflect the
    INCREMENTAL drain, not the gross ownership cost."""
    from copy import deepcopy
    s = deepcopy(bonn_scenario)
    s.mode = "live"
    s.live.current_monthly_rent_warm_eur = 1_800.0
    a = compute_affordability(run(s), s)

    s_gross = deepcopy(bonn_scenario)
    s_gross.mode = "live"
    s_gross.live.current_monthly_rent_warm_eur = 0.0
    a_gross = compute_affordability(run(s_gross), s_gross)

    # Setting current rent must reduce burden_pct (smaller is better here).
    assert a["burden_pct"] < a_gross["burden_pct"]


def test_ratios_have_expected_signs_and_ranges() -> None:
    s = make_scenario(
        price=500_000, initial_capital=150_000, bank_principal=400_000,
        monthly_income=7_000,
    )
    a = _afford(s)
    assert 0 <= a["down_pct"] <= 1
    assert 0 <= a["ltv"] <= 1
    assert a["price_to_income"] > 0
    assert a["total_debt"] == pytest.approx(400_000)
    assert a["initial_cap"] == pytest.approx(150_000)


def test_gross_yield_is_none_in_live_mode() -> None:
    s = make_scenario(mode="live")
    a = _afford(s)
    assert a["gross_yield"] is None
    assert a["net_yield"] is None


def test_funding_gap_flags_under_funding() -> None:
    """If capital + loans don't cover total cost, the check must fail and
    the verdict names the shortfall."""
    # Total cost is price + fees (~12.07%). Capital + loan deliberately short.
    s = make_scenario(
        price=400_000, initial_capital=20_000, bank_principal=350_000,
    )
    a = _afford(s)
    assert a["funding_gap"] > 1_000
    funding_checks = [c for c in a["checks"]
                       if "Funding plan closes" in c[1]]
    assert funding_checks
    ok = funding_checks[0][0]
    assert ok is False


def test_bonn_sample_passes_most_rules(bonn_scenario) -> None:
    """Regression guard on the bundled sample — must stay largely affordable."""
    a = compute_affordability(run(bonn_scenario), bonn_scenario)
    assert a["level"] in ("ok", "warn")
    assert a["n_pass"] >= a["n_total"] - 1
