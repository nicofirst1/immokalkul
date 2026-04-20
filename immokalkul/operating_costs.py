"""
Recurring operating costs.

Each cost line knows whether it applies in live mode, rent mode, or both.
Maintenance reserve is computed two ways and the higher one chosen:
  (a) Petersche Formel based on construction cost per m²
  (b) II. BV age-based table (€7.10 / €9 / €11.50 per m²/yr)
This avoids under-provisioning for old buildings where the construction-cost
input might be too optimistic.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import pandas as pd
from . import rules_de
from .models import Property, CostInputs, RentParameters, LiveParameters, Mode


@dataclass
class CostLine:
    name: str
    annual_eur: float
    in_live: bool
    in_rent: bool
    deductible_in_rent: bool   # most things are; some (e.g. tenant-covered) aren't
    note: str = ""


def estimate_construction_cost_per_m2(p: Property) -> float:
    """Backs out an implied construction cost per m² of living space, as input
    to the Petersche Formel. Uses purchase price minus land value, divided by
    living space.

    Note this is the *current value* of the building, not historical
    Herstellungskosten. For old buildings it's typically higher than original
    construction cost, so Petersche Formel tends to over-estimate when fed
    with this. We accept that conservative bias.
    """
    from .financing import estimate_building_share
    share = estimate_building_share(p)
    building_value = p.purchase_price * share
    return building_value / p.living_space_m2


def maintenance_reserve_per_m2_year(p: Property, today_year: int) -> float:
    """Recommended Erhaltungsrücklage per m² per year. Takes max of Petersche
    and II. BV age-based estimate."""
    # Petersche
    constr = estimate_construction_cost_per_m2(p)
    weg_only = (p.property_type == "apartment")
    peters = rules_de.petersche_formel_per_m2_year(constr, weg_only=weg_only)

    # II. BV age table — uses age since last major renovation (or build)
    age = p.effective_renovation_age_years(today_year)
    ii_bv = rules_de.ii_bv_reserve_per_m2_year(age, has_elevator=p.has_elevator)

    return max(peters, ii_bv)


def estimate_electricity_kwh_year(p: Property, live: LiveParameters) -> float:
    """Heuristic: 9 kWh/m² baseline (lighting, standby) + 400/person + 200/appliance."""
    return p.living_space_m2 * 9 + live.people_in_household * 400 + live.large_appliances * 200


def estimate_heating_kwh_year(p: Property) -> float:
    return p.living_space_m2 * p.energy_demand_kwh_per_m2_year


def operating_costs_year_one(p: Property,
                              costs: CostInputs,
                              rent: RentParameters,
                              live: LiveParameters,
                              today_year: int,
                              ) -> list[CostLine]:
    """Returns the list of all cost lines (year-1 amounts), with mode flags.
    Caller then sums the ones applicable to the chosen mode.
    """
    lines: list[CostLine] = []

    # --- Hausgeld split (rent mode) ---
    # § 19 WEG distinguishes the operating portion (Werbungskosten — deductible)
    # from the Erhaltungsrücklage funding (NOT deductible until actually
    # spent on repairs). Roughly 60/40 in typical statements; user-tunable.
    reserve_frac = max(0.0, min(1.0, costs.hausgeld_reserve_share))
    operating_frac = 1.0 - reserve_frac
    hausgeld_yr = costs.hausgeld_monthly_for_rent * 12
    lines.append(CostLine(
        "Hausgeld — operating portion",
        hausgeld_yr * operating_frac,
        in_live=False, in_rent=True, deductible_in_rent=True,
        note=("Betriebskostenanteil; deductible per § 9 (1) EStG. Live mode "
              "uses the cost build-up instead.")
    ))
    lines.append(CostLine(
        "Hausgeld — reserve portion",
        hausgeld_yr * reserve_frac,
        in_live=False, in_rent=True, deductible_in_rent=False,
        note=("Erhaltungsrücklage portion (§ 19 WEG); not deductible until "
              "actually spent on repairs.")
    ))

    # --- Property tax ---
    # Post-2025 Grundsteuerreform: tax base is the Grundstückswert (land
    # value), not the whole purchase price. We compute land value from
    # Bodenrichtwert × plot when available, falling back to (1 − building
    # share) × price otherwise. Hebesatz × Steuermesszahl rolls into the
    # `grundsteuer_land_rate` input (default ≈ 0.34 % of land value).
    from .financing import estimate_building_share
    if p.bodenrichtwert_eur_per_m2 is not None:
        land_value = p.bodenrichtwert_eur_per_m2 * p.plot_size_m2
    else:
        land_value = p.purchase_price * (1 - estimate_building_share(p))
    lines.append(CostLine(
        "Grundsteuer B (property tax)",
        land_value * costs.grundsteuer_land_rate,
        in_live=True, in_rent=True, deductible_in_rent=True,
        note=("Post-2025 Bundesmodell: land value × land_rate. Real Hebesatz "
              "varies 0.20–0.50 % across Bundesländer + Kommunen.")
    ))

    # --- Heating (live mode only — rent mode passes through Nebenkosten) ---
    heating_kwh = estimate_heating_kwh_year(p)
    lines.append(CostLine(
        "Heating (gas)",
        heating_kwh * costs.gas_price_eur_per_kwh,
        in_live=True, in_rent=False, deductible_in_rent=True,
        note="Live: yours. Rent: tenant pays via Nebenkosten."
    ))

    # --- Electricity (live mode only) ---
    elec_kwh = estimate_electricity_kwh_year(p, live)
    lines.append(CostLine(
        "Electricity",
        elec_kwh * costs.electricity_price_eur_per_kwh,
        in_live=True, in_rent=False, deductible_in_rent=False,
        note="Live: yours. Rent: tenant pays direct to provider."
    ))

    # --- Routine maintenance reserve ---
    maint_per_m2 = maintenance_reserve_per_m2_year(p, today_year)
    lines.append(CostLine(
        "Maintenance reserve (Petersche/II.BV)",
        maint_per_m2 * p.living_space_m2,
        in_live=True, in_rent=True, deductible_in_rent=False,
        note=("Erhaltungsrücklage. NOT deductible in rent mode while just sitting in "
              "the reserve — only actual repairs are deductible. Petersche Formel "
              f"max'd against II.BV: {maint_per_m2:.2f} €/m²/yr.")
    ))

    # --- Administration (live mode only — apartment WEG) ---
    if p.property_type == "apartment":
        lines.append(CostLine(
            "Administration (Hausverwaltung)",
            costs.administration_monthly * 12,
            in_live=True, in_rent=False, deductible_in_rent=True,
            note="Live: yours. Rent: included in Hausgeld."
        ))

    # --- Municipal charges (Müll, Wasser) — live mode only ---
    lines.append(CostLine(
        "Municipal charges (Müll, Wasser)",
        costs.municipal_charges_eur_per_m2_month * 12 * p.living_space_m2,
        in_live=True, in_rent=False, deductible_in_rent=True,
        note="Live: yours. Rent: tenant pays via Nebenkosten."
    ))

    # --- Vacancy risk (rent mode only) ---
    monthly_rent_total = rent.monthly_rent + rent.monthly_parking
    lines.append(CostLine(
        "Vacancy risk",
        monthly_rent_total * rent.expected_vacancy_months_per_year,
        in_live=False, in_rent=True, deductible_in_rent=False,
        note="Reduces effective rent income; modeled as a cost in this view."
    ))

    # --- Building insurance (both modes) ---
    lines.append(CostLine(
        "Building insurance (Wohngebäudeversicherung)",
        costs.building_insurance_eur_per_m2_year * p.living_space_m2,
        in_live=True, in_rent=True, deductible_in_rent=True,
    ))

    # --- Liability insurance (both modes) ---
    lines.append(CostLine(
        "Liability insurance (Haus- und Grundbesitzerhaftpflicht)",
        costs.liability_insurance_annual,
        in_live=True, in_rent=True, deductible_in_rent=True,
    ))

    # --- Vermieter-Rechtsschutz (rent only) ---
    lines.append(CostLine(
        "Vermieter-Rechtsschutz",
        rent.landlord_legal_insurance_annual,
        in_live=False, in_rent=True, deductible_in_rent=True,
    ))

    # --- Property manager (rent only, optional) ---
    if rent.has_property_manager:
        lines.append(CostLine(
            "Property manager fee",
            rent.monthly_rent * 12 * rent.property_manager_pct_of_rent,
            in_live=False, in_rent=True, deductible_in_rent=True,
        ))

    # --- Schornsteinfeger (mandatory in DE) ---
    lines.append(CostLine(
        "Schornsteinfeger (chimney sweep)",
        rules_de.SCHORNSTEINFEGER_ANNUAL,
        in_live=True, in_rent=False, deductible_in_rent=True,
        note="Live: yours. Rent: typically pass-through Nebenkosten."
    ))

    # --- Heating maintenance ---
    lines.append(CostLine(
        "Heating maintenance (Wartung)",
        rules_de.HEATING_MAINTENANCE_ANNUAL,
        in_live=True, in_rent=False, deductible_in_rent=True,
        note="Live: yours. Rent: pass-through."
    ))

    return lines


def total_active_costs(lines: list[CostLine], mode: Mode) -> float:
    """Sum of annual costs applicable in the given mode."""
    if mode == "live":
        return sum(l.annual_eur for l in lines if l.in_live)
    else:
        return sum(l.annual_eur for l in lines if l.in_rent)


def deductible_costs_in_rent(lines: list[CostLine]) -> float:
    """Sum of costs deductible against rental income."""
    return sum(l.annual_eur for l in lines if l.in_rent and l.deductible_in_rent)


def costs_dataframe(lines: list[CostLine]) -> pd.DataFrame:
    """Tabular view for display."""
    return pd.DataFrame([{
        "Item": l.name,
        "Annual (€)": l.annual_eur,
        "Monthly (€)": l.annual_eur / 12,
        "Live": "✓" if l.in_live else "",
        "Rent": "✓" if l.in_rent else "",
        "Deductible": "✓" if (l.in_rent and l.deductible_in_rent) else "",
        "Note": l.note,
    } for l in lines])
