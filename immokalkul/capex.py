"""
Capex scheduling.

Two sources of capex:
1. Auto-schedule: each component (roof, heating, etc.) has a typical lifetime.
   If we know when it was last replaced (or assume = year_built if never),
   we can project its next replacement year and budget for it.
2. User-specified: explicit one-off renovations the user knows about
   (e.g., "we know the bathroom needs redoing in year 3, will cost €18k").

Costs are mid-point of low/high estimates. User can override.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pandas as pd
from . import rules_de
from .models import Property, CapexItem, GlobalParameters


@dataclass
class ComponentSchedule:
    component_name: str
    last_replaced_year: Optional[int]   # None means original (year_built)
    next_replacement_year: int           # absolute calendar year
    estimated_cost_eur: float
    cost_basis: str
    lifetime_years: int = 0              # kept so the Capex tab can derive
                                         # the steady-state annual reserve
                                         # (cost / lifetime_years) shown as
                                         # the smoothed line on the chart
    scope: str = "se_individual"         # "we_building" vs. "se_individual"
    note: str = ""


def estimate_component_cost(component, p: Property) -> float:
    """Mid-point cost estimate for a component, scaled by property metrics.

    For apartments, components flagged scope='we_building' (Gemeinschafts-
    eigentum) are reduced by WEG_SHARE_APARTMENT because the WEG's
    Erhaltungsrücklage — already funded via monthly Hausgeld in the
    operating costs — pays the rest. This avoids the big double-counted
    spike that earlier versions produced for multi-family items like
    heating.
    """
    midpoint_per_unit = (component.cost_low + component.cost_high) / 2
    cb = component.cost_basis
    if cb == "flat":
        cost = midpoint_per_unit
    elif cb == "per_m2_living":
        cost = midpoint_per_unit * p.living_space_m2
    elif cb == "per_m2_roof":
        # Roof area ~= 1.0 × footprint-of-top-floor ≈ living for a SFH.
        cost = midpoint_per_unit * p.living_space_m2
    elif cb == "per_m2_facade":
        # Façade area ~= 2.5 × living for a typical multi-storey.
        cost = midpoint_per_unit * p.living_space_m2 * 2.5
    elif cb == "per_window":
        # Estimate windows: 1 per ~10 m² of living for older buildings.
        n_windows = max(1, int(p.living_space_m2 / 10))
        cost = midpoint_per_unit * n_windows
    elif cb == "per_bathroom":
        # Estimate 1 bathroom per 60 m², minimum 1.
        n = max(1, int(p.living_space_m2 / 60))
        cost = midpoint_per_unit * n
    else:
        cost = midpoint_per_unit

    scope = getattr(component, "scope", "se_individual")
    if p.property_type == "apartment" and scope == "we_building":
        cost *= rules_de.WEG_SHARE_APARTMENT
    return cost


def auto_schedule(p: Property,
                   today_year: int,
                   horizon_years: int) -> list[ComponentSchedule]:
    """For each component, project next replacement based on its lifetime and
    last-replacement year (defaulting to year_built or year_last_major_renovation
    for things that get rebuilt during a Kernsanierung)."""
    schedule = []
    for comp in rules_de.COMPONENTS:
        # Anchor year: use year_last_major_renovation if available, else year_built
        anchor = p.year_last_major_renovation or p.year_built
        # Find next replacement year: smallest k×lifetime + anchor that's >= today_year
        if anchor + comp.lifetime_years >= today_year:
            next_year = anchor + comp.lifetime_years
        else:
            # How many cycles have passed?
            cycles_passed = (today_year - anchor) // comp.lifetime_years + 1
            next_year = anchor + cycles_passed * comp.lifetime_years

        if next_year > today_year + horizon_years:
            continue  # too far out

        cost = estimate_component_cost(comp, p)
        schedule.append(ComponentSchedule(
            component_name=comp.name,
            last_replaced_year=anchor,
            next_replacement_year=next_year,
            estimated_cost_eur=cost,
            cost_basis=comp.cost_basis,
            lifetime_years=comp.lifetime_years,
            scope=getattr(comp, "scope", "se_individual"),
            note=comp.notes,
        ))
    return schedule


def schedule_to_capex_items(scheds: list[ComponentSchedule]) -> list[CapexItem]:
    """Convert auto-schedule entries to CapexItems for downstream use."""
    return [CapexItem(
        name=s.component_name,
        cost_eur=s.estimated_cost_eur,
        year_due=s.next_replacement_year,
        # Major renovations (heating, roof) post-purchase are usually
        # Erhaltungsaufwand (immediately deductible), unless they trigger
        # Anschaffungsnaher Aufwand. We default to non-capitalized; the
        # tax module checks the 15% threshold rule globally.
        is_capitalized=False,
    ) for s in scheds]


def capex_year_total(items: list[CapexItem],
                      year: int,
                      cost_inflation: float = 0.0,
                      base_year: int = 2026) -> float:
    """Total capex spending in a given calendar year, with inflation applied."""
    total = 0.0
    for it in items:
        if it.year_due == year:
            inflation_factor = (1 + cost_inflation) ** (year - base_year)
            total += it.cost_eur * inflation_factor
    return total


def capex_dataframe(items: list[CapexItem],
                     today_year: int,
                     horizon_years: int,
                     cost_inflation: float = 0.0) -> pd.DataFrame:
    """Year-by-year capex schedule for display."""
    rows = []
    for yr in range(today_year, today_year + horizon_years):
        items_this_year = [it for it in items if it.year_due == yr]
        if items_this_year:
            for it in items_this_year:
                inflation_factor = (1 + cost_inflation) ** (yr - today_year)
                rows.append({
                    "Year": yr,
                    "Yr offset": yr - today_year + 1,
                    "Item": it.name,
                    "Cost (today's €)": it.cost_eur,
                    "Cost (inflated €)": it.cost_eur * inflation_factor,
                    "Capitalized?": "Yes (AfA)" if it.is_capitalized else "No (deductible)",
                })
    return pd.DataFrame(rows)
