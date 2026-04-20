"""Pytest fixtures and shared test data."""
from __future__ import annotations

from pathlib import Path

import pytest

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
    load_scenario,
    run,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"


@pytest.fixture
def sample_yaml_paths() -> list[Path]:
    """All bundled sample scenario YAMLs."""
    return sorted(DATA_DIR.glob("*.yaml"))


@pytest.fixture
def bonn_scenario() -> Scenario:
    return load_scenario(DATA_DIR / "bonn_poppelsdorf.yaml")


@pytest.fixture
def bonn_result(bonn_scenario: Scenario):
    return run(bonn_scenario)


def make_scenario(
    *,
    mode: str = "rent",
    price: float = 400_000,
    initial_capital: float = 100_000,
    bank_principal: float | None = None,
    bank_rate: float = 0.034,
    bank_monthly: float = 1_350.0,
    monthly_income: float = 6_000,
    monthly_rent: float = 1_500,
    current_rent_warm: float = 0.0,
    extra_loans: list[Loan] | None = None,
) -> Scenario:
    """Build a synthetic Scenario with sensible defaults.

    If `bank_principal` is None, the bank loan is auto-sized to close the
    funding plan exactly (price + closing fees − initial_capital). This
    keeps affordability tests from tripping the funding-gap check
    accidentally.
    """
    prop = Property(
        name="Synthetic test property",
        purchase_price=price,
        living_space_m2=80.0,
        plot_size_m2=80.0,
        year_built=2000,
        property_type="apartment",
    )
    if bank_principal is None:
        from immokalkul.financing import compute_purchase_costs
        pc = compute_purchase_costs(prop)
        bank_principal = max(0, pc.total_cost - initial_capital)

    loans = [Loan("Bank", bank_principal, bank_rate, bank_monthly,
                  is_annuity=True, is_adaptive=False)]
    if extra_loans:
        loans.extend(extra_loans)
    return Scenario(
        mode=mode,
        property=prop,
        financing=Financing(
            initial_capital=initial_capital,
            loans=loans,
            debt_budget_monthly=2_000,
        ),
        costs=CostInputs(),
        rent=RentParameters(
            monthly_rent=monthly_rent,
            # Pin vacancy so affordability tests stay stable even if the
            # model default shifts (it did in audit v1 Phase-2b: 0.25 → 2).
            expected_vacancy_months_per_year=0.25,
        ),
        live=LiveParameters(current_monthly_rent_warm_eur=current_rent_warm),
        globals=GlobalParameters(
            monthly_household_income=monthly_income,
            horizon_years=50,
        ),
        user_capex=[],
        auto_schedule_capex=True,
    )
