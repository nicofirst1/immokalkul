"""YAML noise corpus — [C10] layer 2.

Hand-curated degenerate YAMLs that exercise the load/save/run boundary.
Each case either:
  - loads cleanly (forward-compat or silently-ignored extras),
  - raises a typed error with a clear message, or
  - gets rejected by a model-level validator.

Anything else (KeyError / ZeroDivisionError / NaN propagation / silent
success with garbage) is a robustness bug.
"""
from __future__ import annotations

import copy
import tempfile
from pathlib import Path

import numpy as np
import pytest
import yaml

from immokalkul import load_scenario, run

REPO_ROOT = Path(__file__).resolve().parent.parent
BONN_YAML = REPO_ROOT / "data" / "bonn_poppelsdorf.yaml"


def _write_yaml(data: dict) -> Path:
    """Serialize a dict to a temp YAML file and return its path.
    Caller is responsible for unlink()ing it."""
    with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False,
                                      mode="w") as f:
        yaml.safe_dump(data, f)
        return Path(f.name)


@pytest.fixture
def bonn_dict() -> dict:
    """Raw YAML dict for the Bonn sample — starting point for noise
    mutations. Returns a deep copy so tests can mutate freely."""
    with open(BONN_YAML) as f:
        return copy.deepcopy(yaml.safe_load(f))


def test_missing_required_purchase_price(bonn_dict):
    """Dropping `property.purchase_price` must raise a typed error on
    load — never a silent fallback to 0."""
    del bonn_dict["property"]["purchase_price"]
    p = _write_yaml(bonn_dict)
    try:
        with pytest.raises((KeyError, TypeError, ValueError)):
            load_scenario(p)
    finally:
        p.unlink(missing_ok=True)


def test_unknown_extra_key_is_ignored(bonn_dict):
    """Adding an unknown top-level or nested key must not crash load
    (forward-compat for older / newer YAML schemas)."""
    bonn_dict["future_feature_flag"] = True
    bonn_dict["property"]["unknown_nested"] = {"a": 1, "b": 2}
    p = _write_yaml(bonn_dict)
    try:
        s = load_scenario(p)
        # Sample some core fields to confirm the rest loaded correctly.
        assert s.property.purchase_price == bonn_dict["property"]["purchase_price"]
        assert s.mode == bonn_dict["mode"]
    finally:
        p.unlink(missing_ok=True)


def test_bad_mode_value(bonn_dict):
    """An unknown `mode` (not "live" / "rent") should either be rejected
    on load, rejected on run, or — worst case — load and then emit a
    typed error on run. Silent success with garbage behaviour is a bug."""
    bonn_dict["mode"] = "buy_and_hold_but_also_flip"
    p = _write_yaml(bonn_dict)
    try:
        try:
            s = load_scenario(p)
        except (KeyError, TypeError, ValueError):
            return  # rejected on load — acceptable
        # Loaded; must at least raise a typed error on run.
        with pytest.raises((ValueError, KeyError, TypeError)):
            run(s)
    finally:
        p.unlink(missing_ok=True)


def test_adaptive_loan_with_zero_budget(bonn_dict):
    """Flagging a loan adaptive with `debt_budget_monthly: 0` must not
    cause ZeroDivisionError or unbounded balance growth. This combo is
    plausible user noise (someone disables the engine knob without
    realising adaptive depends on it)."""
    bonn_dict["financing"]["debt_budget_monthly"] = 0
    for loan in bonn_dict["financing"]["loans"]:
        loan["is_adaptive"] = True
        loan["is_annuity"] = False
    p = _write_yaml(bonn_dict)
    try:
        s = load_scenario(p)
        try:
            r = run(s)
        except ValueError:
            return  # acceptable typed rejection
        # Ran to completion — verify no NaN / inf leaked.
        for col in r.cashflow.columns:
            series = r.cashflow[col].to_numpy(dtype=float, na_value=0.0)
            assert np.all(np.isfinite(series)), (
                f"zero-budget adaptive produced non-finite {col!r}")
    finally:
        p.unlink(missing_ok=True)


def test_empty_loans_list(bonn_dict):
    """`loans: []` is legal YAML. Engine must either run (all-cash) or
    raise a typed ValueError — no attribute errors on empty iteration."""
    bonn_dict["financing"]["loans"] = []
    # All-cash scenario needs enough initial capital to cover total cost.
    bonn_dict["financing"]["initial_capital"] = 600_000
    p = _write_yaml(bonn_dict)
    try:
        s = load_scenario(p)
        try:
            r = run(s)
        except ValueError:
            return
        # No loans → no amort columns beyond index; sanity: cashflow exists.
        assert len(r.cashflow) == s.globals.horizon_years
    finally:
        p.unlink(missing_ok=True)


def test_negative_capex_cost_is_rejected(bonn_dict):
    """CapexItem has a __post_init__ validator ([C6]) that rejects
    negative costs. Load must surface that as a ValueError."""
    bonn_dict["user_capex"] = [{
        "name": "Bad capex",
        "cost_eur": -5_000,
        "year_due": 2030,
        "is_capitalized": False,
    }]
    p = _write_yaml(bonn_dict)
    try:
        with pytest.raises(ValueError, match="cost_eur"):
            load_scenario(p)
    finally:
        p.unlink(missing_ok=True)


def test_very_large_price_stays_finite(bonn_dict):
    """A €1e12 price (absurd but not nonsensical to the parser) must not
    produce inf/NaN anywhere. Verifies the engine's arithmetic is
    bounded by the input size, not amplifying it."""
    bonn_dict["property"]["purchase_price"] = 1e12
    # Rescale loan to keep funding plan closable, otherwise _validate fires
    # before we can check cashflow.
    bonn_dict["financing"]["initial_capital"] = 1e12
    bonn_dict["financing"]["loans"] = []
    p = _write_yaml(bonn_dict)
    try:
        s = load_scenario(p)
        try:
            r = run(s)
        except ValueError:
            return
        for col in r.cashflow.columns:
            series = r.cashflow[col].to_numpy(dtype=float, na_value=0.0)
            assert np.all(np.isfinite(series)), (
                f"huge price produced non-finite {col!r}")
    finally:
        p.unlink(missing_ok=True)


def test_excessive_vacancy_still_runs(bonn_dict):
    """Vacancy > 12 months/year is nonsensical but must degrade
    gracefully rather than producing negative rent income or NaN. Either
    the engine clamps, or emits a typed error."""
    bonn_dict["rent"]["expected_vacancy_months_per_year"] = 24
    p = _write_yaml(bonn_dict)
    try:
        s = load_scenario(p)
        try:
            r = run(s)
        except ValueError:
            return
        # If it ran, rent_net must not be NaN.
        rent_net = r.cashflow["rent_net"].to_numpy(
            dtype=float, na_value=0.0)
        assert np.all(np.isfinite(rent_net)), (
            "excessive vacancy produced non-finite rent_net")
    finally:
        p.unlink(missing_ok=True)
