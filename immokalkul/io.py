"""
YAML serialization for Scenario objects.

Lets users save/load property scenarios as plain text files.
"""
from __future__ import annotations
from dataclasses import fields
from pathlib import Path
import yaml
from .models import (Scenario, Property, Loan, Financing, CapexItem,
                      RentParameters, LiveParameters, CostInputs, GlobalParameters)

_VALID_MODES = {"live", "rent"}


def _only_known_fields(cls, d: dict) -> dict:
    """Filter a YAML-derived dict to the subset of keys `cls` accepts.
    Unknown keys are silently dropped — forward-compat with older /
    newer YAML schemas so users can annotate without crashing load."""
    known = {f.name for f in fields(cls)}
    return {k: v for k, v in (d or {}).items() if k in known}


def load_scenario(path: str | Path) -> Scenario:
    """Load a YAML file into a Scenario object."""
    with open(path) as f:
        d = yaml.safe_load(f)

    prop = Property(**_only_known_fields(Property, d["property"]))
    loans = [Loan(**_only_known_fields(Loan, l))
             for l in d["financing"]["loans"]]

    # Backward compat: legacy YAMLs had a top-level `adaptive_mamma` flag and
    # hardcoded the adaptive loan by name. Migrate by flagging the loan named
    # "Mamma" (if any) with is_adaptive=True.
    legacy_adaptive = d["financing"].get("adaptive_mamma")
    if legacy_adaptive:
        for l in loans:
            if l.name == "Mamma" and not l.is_adaptive:
                l.is_adaptive = True

    fin = Financing(
        initial_capital=d["financing"]["initial_capital"],
        loans=loans,
        debt_budget_monthly=d["financing"].get("debt_budget_monthly", 1745.0),
        monthly_total_housing_budget_eur=d["financing"].get(
            "monthly_total_housing_budget_eur", 0.0),
        notary_pct=d["financing"].get("notary_pct"),
        grundbuch_pct=d["financing"].get("grundbuch_pct"),
    )
    costs = CostInputs(**_only_known_fields(CostInputs, d["costs"]))
    rent = RentParameters(**_only_known_fields(RentParameters, d["rent"]))
    live = LiveParameters(**_only_known_fields(LiveParameters, d["live"]))
    globs = GlobalParameters(**_only_known_fields(GlobalParameters, d["globals"]))
    user_capex = [CapexItem(**_only_known_fields(CapexItem, c))
                  for c in d.get("user_capex", [])]

    mode = d["mode"]
    if mode not in _VALID_MODES:
        raise ValueError(
            f"Scenario.mode must be one of {sorted(_VALID_MODES)}, "
            f"got {mode!r}")

    return Scenario(
        mode=mode,
        property=prop,
        financing=fin,
        costs=costs,
        rent=rent,
        live=live,
        globals=globs,
        user_capex=user_capex,
        auto_schedule_capex=d.get("auto_schedule_capex", True),
    )


def save_scenario(scenario: Scenario, path: str | Path) -> None:
    """Serialize a Scenario back to YAML."""
    d = {
        "mode": scenario.mode,
        "property": _asdict(scenario.property),
        "financing": {
            "initial_capital": scenario.financing.initial_capital,
            "debt_budget_monthly": scenario.financing.debt_budget_monthly,
            "monthly_total_housing_budget_eur":
                scenario.financing.monthly_total_housing_budget_eur,
            "notary_pct": scenario.financing.notary_pct,
            "grundbuch_pct": scenario.financing.grundbuch_pct,
            "loans": [_asdict(l) for l in scenario.financing.loans],
        },
        "costs": _asdict(scenario.costs),
        "rent": _asdict(scenario.rent),
        "live": _asdict(scenario.live),
        "globals": _asdict(scenario.globals),
        "user_capex": [_asdict(c) for c in scenario.user_capex],
        "auto_schedule_capex": scenario.auto_schedule_capex,
    }
    with open(path, "w") as f:
        yaml.safe_dump(d, f, sort_keys=False, allow_unicode=True)


def _asdict(obj):
    """Lightweight dataclass-to-dict that avoids dependencies."""
    from dataclasses import asdict
    return asdict(obj)
