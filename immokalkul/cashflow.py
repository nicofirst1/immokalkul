"""
End-to-end annual cash flow projection wiring everything together.

Returns one DataFrame with the full picture for visualization.
"""
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd
from .models import Scenario
from .financing import (compute_purchase_costs, amortization_schedule,
                          all_debt_clear_year, estimate_building_share)
from .operating_costs import (operating_costs_year_one, total_active_costs,
                                deductible_costs_in_rent)
from .capex import auto_schedule, schedule_to_capex_items, capex_year_total
from .tax import annual_tax_schedule_v2, compute_afa_basis


@dataclass
class ScenarioResult:
    """Bundles all artifacts of one scenario run for the UI."""
    scenario: Scenario
    purchase: object              # PurchaseCostBreakdown
    afa_basis: object             # AfABasis (only meaningful in rent mode)
    cost_lines: list              # list of CostLine
    amort: pd.DataFrame
    tax: pd.DataFrame
    cashflow: pd.DataFrame
    auto_capex: list              # ComponentSchedule list
    all_capex: list               # CapexItem list (auto + user)
    years_to_debt_free: int


def run(scenario: Scenario) -> ScenarioResult:
    s = scenario
    # 1. Purchase costs & financing
    initial_renovation = s.property.year_last_major_renovation is None and 0.0 or 0.0
    # (initial_renovation is a separate concept from one-off capex during ownership;
    # for now leave as 0 and use user_capex for known immediate renovations)
    purchase = compute_purchase_costs(s.property, renovation_capitalized=0.0)

    # 2. Amortization
    amort = amortization_schedule(s.financing, s.globals.horizon_years)

    # 3. Auto capex schedule
    auto = auto_schedule(s.property, s.globals.today_year, s.globals.horizon_years) \
        if s.auto_schedule_capex else []
    auto_items = schedule_to_capex_items(auto)
    all_capex = auto_items + s.user_capex

    # 4. Operating cost lines
    cost_lines = operating_costs_year_one(
        s.property, s.costs, s.rent, s.live, s.globals.today_year)
    deductible_costs_yr1 = deductible_costs_in_rent(cost_lines)
    total_costs_yr1 = total_active_costs(cost_lines, s.mode)

    # 5. AfA basis (rent mode)
    if s.mode == "rent":
        afa_b = compute_afa_basis(s.property, purchase, 0.0)
    else:
        afa_b = None

    # 6. Tax schedule
    tax = annual_tax_schedule_v2(
        s.mode, s.property, s.financing, s.rent, s.globals,
        purchase, amort, deductible_costs_yr1, all_capex)

    # 7. Cash flow
    rows = []
    cum = 0.0
    for yr in range(1, s.globals.horizon_years + 1):
        loan_payment = float(amort["total_payment"].iloc[yr - 1])

        if s.mode == "rent":
            # Rent income (gross of vacancy)
            rent_gross = (s.rent.monthly_rent + s.rent.monthly_parking) * 12 \
                * (1 + s.rent.annual_rent_escalation) ** (yr - 1)
            vacancy_loss = (s.rent.monthly_rent + s.rent.monthly_parking) \
                * s.rent.expected_vacancy_months_per_year \
                * (1 + s.rent.annual_rent_escalation) ** (yr - 1)
            rent_net = rent_gross - vacancy_loss
            # Operating costs (escalated; vacancy already netted from rent so
            # remove from costs to avoid double-counting)
            vacancy_in_costs = next(
                (l.annual_eur for l in cost_lines if l.name == "Vacancy risk"), 0)
            op_costs = (total_costs_yr1 - vacancy_in_costs) \
                * (1 + s.globals.cost_inflation_annual) ** (yr - 1)
        else:
            rent_net = 0.0
            op_costs = total_costs_yr1 * (1 + s.globals.cost_inflation_annual) ** (yr - 1)

        # Capex this year (calendar year math)
        cal_year = s.globals.today_year + yr - 1
        capex_yr = capex_year_total(all_capex, cal_year,
                                     s.globals.cost_inflation_annual,
                                     base_year=s.globals.today_year)

        tax_yr = float(tax["tax_owed"].iloc[yr - 1])

        # Net cash from property
        net_property = rent_net - loan_payment - op_costs - capex_yr - tax_yr
        # Total wealth change including unrelated savings
        other_savings = s.globals.additional_monthly_savings * 12
        net_wealth_change = net_property + other_savings
        cum += net_wealth_change

        rows.append({
            "year": yr,
            "calendar_year": cal_year,
            "rent_net": rent_net,
            "loan_payment": loan_payment,
            "op_costs": op_costs,
            "capex": capex_yr,
            "tax_owed": tax_yr,
            "net_property": net_property,
            "salary_needed": max(0.0, -net_property),
            "other_savings": other_savings,
            "net_wealth_change": net_wealth_change,
            "cumulative": cum,
            "net_property_per_month": net_property / 12,
        })

    cashflow = pd.DataFrame(rows).set_index("year")

    return ScenarioResult(
        scenario=s, purchase=purchase, afa_basis=afa_b, cost_lines=cost_lines,
        amort=amort, tax=tax, cashflow=cashflow,
        auto_capex=auto, all_capex=all_capex,
        years_to_debt_free=all_debt_clear_year(amort, s.financing.loans),
    )
