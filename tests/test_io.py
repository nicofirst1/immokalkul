"""YAML round-trip + legacy-format migration."""
from __future__ import annotations

from pathlib import Path

import yaml

from immokalkul import Loan, load_scenario, save_scenario


def test_roundtrip_preserves_key_fields(tmp_path: Path, bonn_scenario) -> None:
    out = tmp_path / "roundtrip.yaml"
    save_scenario(bonn_scenario, out)
    reloaded = load_scenario(out)
    assert reloaded.property.name == bonn_scenario.property.name
    assert reloaded.property.purchase_price == bonn_scenario.property.purchase_price
    assert reloaded.property.year_built == bonn_scenario.property.year_built
    assert reloaded.mode == bonn_scenario.mode
    assert len(reloaded.financing.loans) == len(bonn_scenario.financing.loans)
    for orig, new in zip(bonn_scenario.financing.loans,
                          reloaded.financing.loans):
        assert new.name == orig.name
        assert new.principal == orig.principal
        assert new.is_annuity == orig.is_annuity
        assert new.is_adaptive == orig.is_adaptive


def test_legacy_adaptive_mamma_migrates(tmp_path: Path) -> None:
    """Legacy YAML with top-level `adaptive_mamma: true` must flag the loan
    named 'Mamma' as is_adaptive on load — preserves behaviour of old files."""
    legacy = {
        "mode": "rent",
        "property": {
            "name": "legacy", "purchase_price": 400000.0, "living_space_m2": 80.0,
            "plot_size_m2": 80.0, "year_built": 2000,
        },
        "financing": {
            "initial_capital": 100000.0,
            "adaptive_mamma": True,
            "debt_budget_monthly": 1800.0,
            "loans": [
                {"name": "Bank", "principal": 300000.0, "interest_rate": 0.03,
                 "monthly_payment": 1350.0, "is_annuity": True},
                {"name": "Mamma", "principal": 50000.0, "interest_rate": 0.0,
                 "monthly_payment": 100.0, "is_annuity": False},
            ],
        },
        "costs": {}, "rent": {"monthly_rent": 1500.0},
        "live": {}, "globals": {},
        "user_capex": [], "auto_schedule_capex": True,
    }
    path = tmp_path / "legacy.yaml"
    path.write_text(yaml.safe_dump(legacy))

    s = load_scenario(path)
    mamma = next(l for l in s.financing.loans if l.name == "Mamma")
    bank = next(l for l in s.financing.loans if l.name == "Bank")
    assert mamma.is_adaptive is True
    assert bank.is_adaptive is False


def test_bundesland_roundtrip(tmp_path: Path, bonn_scenario) -> None:
    """Germany-expansion Phase 1: Bundesland must serialize as its short
    `.value` code ("NW", "BY", …) and reconstruct as an enum on load."""
    from immokalkul import rules_de
    # Mutate to a non-default state so the test isn't tautological.
    bonn_scenario.property.bundesland = rules_de.Bundesland.BY
    out = tmp_path / "bundesland.yaml"
    save_scenario(bonn_scenario, out)

    blob = yaml.safe_load(out.read_text())
    assert blob["property"]["bundesland"] == "BY", (
        f"expected enum serialised as 'BY', got {blob['property'].get('bundesland')!r}")

    reloaded = load_scenario(out)
    assert reloaded.property.bundesland == rules_de.Bundesland.BY
    assert isinstance(reloaded.property.bundesland, rules_de.Bundesland)


def test_missing_bundesland_defaults_to_nw(tmp_path: Path) -> None:
    """Old YAMLs without a `bundesland:` key must load with NRW default —
    backward-compat for pre-expansion scenarios."""
    from immokalkul import rules_de
    legacy = {
        "mode": "rent",
        "property": {
            "name": "pre-expansion", "purchase_price": 400000.0,
            "living_space_m2": 80.0, "plot_size_m2": 80.0, "year_built": 2000,
        },
        "financing": {"initial_capital": 100000.0, "loans": []},
        "costs": {}, "rent": {"monthly_rent": 1500.0},
        "live": {}, "globals": {}, "user_capex": [],
    }
    path = tmp_path / "legacy.yaml"
    path.write_text(yaml.safe_dump(legacy))
    s = load_scenario(path)
    assert s.property.bundesland == rules_de.Bundesland.NW


def test_saved_yaml_has_no_legacy_adaptive_mamma(tmp_path: Path,
                                                   bonn_scenario) -> None:
    """The current writer must never emit the legacy flag."""
    out = tmp_path / "out.yaml"
    save_scenario(bonn_scenario, out)
    blob = yaml.safe_load(out.read_text())
    assert "adaptive_mamma" not in blob["financing"]
    # Each loan should carry the per-loan flag instead.
    for loan in blob["financing"]["loans"]:
        assert "is_adaptive" in loan
