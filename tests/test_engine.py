"""End-to-end engine checks on the bundled sample scenarios."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from immokalkul import load_scenario, run


def test_all_sample_scenarios_load_and_run(sample_yaml_paths: list[Path]) -> None:
    """Each YAML in data/ parses into a Scenario and the engine returns a
    result object with the expected shape."""
    assert len(sample_yaml_paths) >= 4, "expected the 4 bundled samples"
    for path in sample_yaml_paths:
        s = load_scenario(path)
        r = run(s)
        assert isinstance(r.cashflow, pd.DataFrame)
        assert isinstance(r.amort, pd.DataFrame)
        assert len(r.cashflow) == s.globals.horizon_years
        assert len(r.amort) == s.globals.horizon_years
        # Cumulative must be monotone in the sense that it's always defined
        assert not r.cashflow["cumulative"].isna().any()


def test_bonn_reference_cumulative(bonn_result) -> None:
    """Guard against accidental engine drift: the Bonn sample must keep
    reproducing the long-established 50-year cumulative, within ±€1.

    Pinned value reflects:
    - Verlustverrechnung on rental losses offsetting salary at the marginal
      rate (§ 10d EStG). Pre-fix pin €405,936 floored tax at €0.
    - Apartment WEG share on Gemeinschaftseigentum capex items (heating,
      roof, façade, plumbing risers) — the WEG's Erhaltungsrücklage funds
      ~85 % of those costs via Hausgeld, so counting them 100 % against the
      owner was double-counting. Pre-fix pin €500,507 over-charged.
    """
    final = float(bonn_result.cashflow["cumulative"].iloc[-1])
    assert final == pytest.approx(525_196, abs=1)


def test_horizon_respected(bonn_scenario) -> None:
    bonn_scenario.globals.horizon_years = 20
    r = run(bonn_scenario)
    assert len(r.cashflow) == 20
    assert len(r.amort) == 20


def test_live_mode_has_no_rent_income(bonn_scenario) -> None:
    bonn_scenario.mode = "live"
    r = run(bonn_scenario)
    assert (r.cashflow["rent_net"] == 0).all()


def test_rent_mode_has_nonzero_afa(bonn_scenario) -> None:
    bonn_scenario.mode = "rent"
    r = run(bonn_scenario)
    assert r.afa_basis is not None
    assert r.afa_basis.annual_afa > 0


def test_bonn_is_pre_1925_afa_rate(bonn_scenario) -> None:
    """Bonn sample is 1904 → 2.5% AfA, 40-year useful life."""
    bonn_scenario.mode = "rent"
    r = run(bonn_scenario)
    assert r.afa_basis.afa_rate == pytest.approx(0.025)
    assert r.afa_basis.useful_life_years == 40


def test_rent_mode_avoided_rent_is_zero(bonn_scenario) -> None:
    """Rent mode never credits avoided rent, regardless of live-mode field."""
    bonn_scenario.mode = "rent"
    bonn_scenario.live.current_monthly_rent_warm_eur = 1_800
    r = run(bonn_scenario)
    assert "avoided_rent" in r.cashflow.columns
    assert (r.cashflow["avoided_rent"] == 0).all()


def test_live_mode_avoided_rent_zero_when_unset(bonn_scenario) -> None:
    """Live mode keeps the legacy behaviour if the field is left at 0."""
    bonn_scenario.mode = "live"
    bonn_scenario.live.current_monthly_rent_warm_eur = 0.0
    r = run(bonn_scenario)
    assert (r.cashflow["avoided_rent"] == 0).all()


def test_live_mode_credits_avoided_rent_year_one(bonn_scenario) -> None:
    """Year 1 avoided_rent = 12 × monthly (no escalation yet)."""
    bonn_scenario.mode = "live"
    bonn_scenario.live.current_monthly_rent_warm_eur = 1_800
    r = run(bonn_scenario)
    yr1 = r.cashflow.iloc[0]
    assert yr1["avoided_rent"] == pytest.approx(1_800 * 12)


def test_live_mode_avoided_rent_escalates_with_inflation(bonn_scenario) -> None:
    """Avoided rent escalates by cost_inflation_annual, same as op costs."""
    bonn_scenario.mode = "live"
    bonn_scenario.live.current_monthly_rent_warm_eur = 1_000
    bonn_scenario.globals.cost_inflation_annual = 0.02
    r = run(bonn_scenario)
    yr1 = r.cashflow["avoided_rent"].iloc[0]
    yr10 = r.cashflow["avoided_rent"].iloc[9]
    assert yr10 == pytest.approx(yr1 * 1.02 ** 9)


def test_rent_mode_tax_can_go_negative(bonn_scenario) -> None:
    """Early years with high interest + AfA should produce a negative
    tax_owed — that's Verlustverrechnung crediting the salary."""
    bonn_scenario.mode = "rent"
    r = run(bonn_scenario)
    tax = r.tax["tax_owed"]
    # Bonn has year-1 AfA plus Bank interest north of €10k; taxable income
    # lands negative, so tax_owed should be < 0 in the early years.
    assert tax.iloc[0] < 0


def test_loss_offset_scales_with_marginal_rate(bonn_scenario) -> None:
    """Doubling the marginal rate should double the magnitude of the
    year-1 tax credit (losses offset at the marginal rate, linearly)."""
    from copy import deepcopy
    low = deepcopy(bonn_scenario); low.mode = "rent"
    low.globals.marginal_tax_rate = 0.20
    high = deepcopy(bonn_scenario); high.mode = "rent"
    high.globals.marginal_tax_rate = 0.40

    t_low = run(low).tax["tax_owed"].iloc[0]
    t_high = run(high).tax["tax_owed"].iloc[0]
    # Both negative; high magnitude should be 2× low magnitude.
    assert t_high < 0 and t_low < 0
    assert abs(t_high) == pytest.approx(abs(t_low) * 2, rel=1e-6)


def test_live_mode_cumulative_lifts_when_rent_is_credited(bonn_scenario) -> None:
    """With avoided rent set, the live-mode cumulative must be materially
    higher than with it at 0 — exactly by the escalated sum of the credit
    (since nothing else in the cashflow changes)."""
    from copy import deepcopy
    s_unset = deepcopy(bonn_scenario)
    s_unset.mode = "live"
    s_unset.live.current_monthly_rent_warm_eur = 0.0

    s_set = deepcopy(bonn_scenario)
    s_set.mode = "live"
    s_set.live.current_monthly_rent_warm_eur = 1_800.0

    r_unset = run(s_unset)
    r_set = run(s_set)

    final_unset = float(r_unset.cashflow["cumulative"].iloc[-1])
    final_set = float(r_set.cashflow["cumulative"].iloc[-1])
    credited = float(r_set.cashflow["avoided_rent"].sum())

    assert credited > 0
    assert final_set == pytest.approx(final_unset + credited, abs=1.0)
