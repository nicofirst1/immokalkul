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
    reproducing the long-established 50-year cumulative, within ±€1."""
    final = float(bonn_result.cashflow["cumulative"].iloc[-1])
    assert final == pytest.approx(405_936, abs=1)


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
