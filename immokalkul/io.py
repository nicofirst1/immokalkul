"""
YAML serialization for Scenario objects.

Lets users save/load property scenarios as plain text files.
"""
from __future__ import annotations
from pathlib import Path
import yaml
from .models import (Scenario, Property, Loan, Financing, CapexItem,
                      RentParameters, LiveParameters, CostInputs, GlobalParameters)


def load_scenario(path: str | Path) -> Scenario:
    """Load a YAML file into a Scenario object."""
    with open(path) as f:
        d = yaml.safe_load(f)

    prop = Property(**d["property"])
    loans = [Loan(**l) for l in d["financing"]["loans"]]
    fin = Financing(
        initial_capital=d["financing"]["initial_capital"],
        loans=loans,
        adaptive_mamma=d["financing"].get("adaptive_mamma", True),
        debt_budget_monthly=d["financing"].get("debt_budget_monthly", 1745.0),
    )
    costs = CostInputs(**d["costs"])
    rent = RentParameters(**d["rent"])
    live = LiveParameters(**d["live"])
    globs = GlobalParameters(**d["globals"])
    user_capex = [CapexItem(**c) for c in d.get("user_capex", [])]

    return Scenario(
        mode=d["mode"],
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
            "adaptive_mamma": scenario.financing.adaptive_mamma,
            "debt_budget_monthly": scenario.financing.debt_budget_monthly,
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
