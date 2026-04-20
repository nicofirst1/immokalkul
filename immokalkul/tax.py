"""
German rental tax model.

Computes annual taxable income from rental and tax owed, applying:
- AfA on building basis (price × building share + capitalizable fees + capitalized renovations)
- Anschaffungsnaher Aufwand: renovations within 3 yr of purchase exceeding 15%
  of building value get reclassified to AfA basis instead of immediate deduction
- Verlustverrechnung (§ 10d EStG): rental losses in a given year offset other
  income at the household's marginal rate. The model lets tax_owed go negative
  (refund), which is the correct economic treatment for a high-income filer
  whose salary absorbs the rental loss.
"""
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd
from . import rules_de
from .models import (Property, Financing, RentParameters, GlobalParameters,
                      CapexItem, Mode)
from .financing import (compute_purchase_costs, estimate_building_share,
                          PurchaseCostBreakdown)


@dataclass
class AfABasis:
    building_value: float            # price × building share
    capitalized_fees: float          # Grunderwerb + Makler + 80%×Notar (building share)
    capitalized_renovation: float    # initial renovation × building share
    total_basis: float
    afa_rate: float
    annual_afa: float
    useful_life_years: int


def compute_afa_basis(p: Property,
                       purchase: PurchaseCostBreakdown,
                       initial_renovation: float = 0.0) -> AfABasis:
    """Compute the annual AfA deduction.

    Methodology:
        building_share = land/building split (uses Bodenrichtwert if available)
        building_value = price × building_share
        capitalized_fees = (Grunderwerb + Makler + 80%×Notar) × building_share
        capitalized_renovation = initial_renovation × building_share
            (Note: the building/land split applies to capitalized renovation
            because pure landscape work isn't depreciable. Conservative.)
        total_basis = sum
        annual_afa = total_basis × afa_rate(year_built)
    """
    bs = estimate_building_share(p)
    building_value = p.purchase_price * bs
    cap_fees = purchase.fees_capitalizable_for_afa * bs
    cap_reno = initial_renovation * bs
    total = building_value + cap_fees + cap_reno
    rate = rules_de.afa_rate(p.year_built)
    return AfABasis(
        building_value=building_value,
        capitalized_fees=cap_fees,
        capitalized_renovation=cap_reno,
        total_basis=total,
        afa_rate=rate,
        annual_afa=total * rate,
        useful_life_years=rules_de.afa_useful_life_years(p.year_built),
    )


def classify_anschaffungsnaher_aufwand(p: Property,
                                         building_value: float,
                                         renovation_items: list[CapexItem],
                                         today_year: int) -> tuple[float, float]:
    """Apply § 6 Abs. 1 Nr. 1a EStG.

    Returns (additional_afa_basis, immediately_deductible_in_3yr_window).

    Rule: renovations within 3 years of purchase whose cumulative cost exceeds
    15% of building value (excl. VAT, simplified here) get reclassified as
    Herstellungskosten and added to AfA basis. Below the threshold, they're
    Erhaltungsaufwand (immediately deductible Werbungskosten).

    For simplicity: we look at items in years 1-3 (today_year + 0,1,2 indexed
    from purchase, i.e., today_year, today_year+1, today_year+2).
    """
    threshold = building_value * rules_de.ANSCHAFFUNGSNAH_THRESHOLD_PCT
    in_window = [it for it in renovation_items
                 if today_year <= it.year_due < today_year + rules_de.ANSCHAFFUNGSNAH_WINDOW_YEARS]
    total_in_window = sum(it.cost_eur for it in in_window)

    if total_in_window > threshold:
        # ALL renovation in the window gets capitalized (the all-or-nothing rule)
        return total_in_window, 0.0
    else:
        return 0.0, total_in_window


def annual_tax_schedule(mode: Mode,
                         p: Property,
                         financing: Financing,
                         rent: RentParameters,
                         globals_: GlobalParameters,
                         purchase: PurchaseCostBreakdown,
                         amort: pd.DataFrame,
                         capex: list[CapexItem],
                         initial_renovation_capitalized: float = 0.0) -> pd.DataFrame:
    """Year-by-year tax schedule.

    In live mode: returns a frame where everything (income, deductions, tax)
    is zero — kept for unified downstream interface.
    """
    rows = []
    horizon = globals_.horizon_years

    if mode == "live":
        for yr in range(1, horizon + 1):
            rows.append({"year": yr, "rent_income": 0, "deduct_interest": 0,
                         "deduct_costs": 0, "deduct_afa": 0, "deduct_capex": 0,
                         "taxable_income": 0, "tax_owed": 0})
        return pd.DataFrame(rows).set_index("year")

    # --- Rent mode ---
    afa_basis = compute_afa_basis(p, purchase, initial_renovation_capitalized)
    annual_afa = afa_basis.annual_afa

    # Anschaffungsnaher check (only on the user-known capex within 3yr window)
    extra_basis, _ = classify_anschaffungsnaher_aufwand(
        p, afa_basis.building_value, capex, globals_.today_year)
    if extra_basis > 0:
        # Add to AfA basis going forward (reclassified as Herstellungskosten)
        annual_afa += extra_basis * rules_de.afa_rate(p.year_built)

    # Sum total bank+LBS interest per year from amortization sheet
    interest_cols = [c for c in amort.columns if c.endswith("_interest")]

    # Compute deductible operating costs (passed in via globals_? No — this
    # function takes rent_params, so we need cost line totals. For now, accept
    # them via separate kwarg — refactor caller. Compute from rent.monthly_rent
    # context-free here is wrong. We'll fetch operating costs at the call site
    # and pass them in. Adjust signature.)
    # → Solution: accept deductible_costs_year_one_eur as a parameter.
    raise NotImplementedError("Use annual_tax_schedule_v2 with explicit deductibles.")


def annual_tax_schedule_v2(mode: Mode,
                            p: Property,
                            financing: Financing,
                            rent: RentParameters,
                            globals_: GlobalParameters,
                            purchase: PurchaseCostBreakdown,
                            amort: pd.DataFrame,
                            deductible_costs_year_one_eur: float,
                            capex: list[CapexItem],
                            initial_renovation_capitalized: float = 0.0) -> pd.DataFrame:
    """As above but with deductible costs passed in explicitly."""
    rows = []
    horizon = globals_.horizon_years

    if mode == "live":
        for yr in range(1, horizon + 1):
            rows.append({"year": yr, "rent_income": 0, "deduct_interest": 0,
                         "deduct_costs": 0, "deduct_afa": 0, "deduct_capex": 0,
                         "taxable_income": 0, "tax_owed": 0})
        return pd.DataFrame(rows).set_index("year")

    # Rent mode
    afa_basis = compute_afa_basis(p, purchase, initial_renovation_capitalized)
    annual_afa = afa_basis.annual_afa

    extra_basis, capex_in_window = classify_anschaffungsnaher_aufwand(
        p, afa_basis.building_value, capex, globals_.today_year)
    if extra_basis > 0:
        annual_afa += extra_basis * rules_de.afa_rate(p.year_built)

    # Interest deduction = sum of all loan interest columns per year
    interest_cols = [c for c in amort.columns if c.endswith("_interest")]
    annual_interest_total = amort[interest_cols].sum(axis=1)
    # Caller (cashflow.run) builds the amort frame with exactly horizon rows;
    # fail loud if that contract is broken instead of silently zero-padding.
    assert len(annual_interest_total) >= horizon, (
        f"amortization schedule has {len(annual_interest_total)} rows but "
        f"tax horizon needs {horizon}")

    # Per-year capex that's immediately deductible (not capitalized AND not in
    # the anschaffungsnah window-trigger case)
    capex_by_year = {}
    if extra_basis > 0:
        # In the trigger case, all in-window capex goes to AfA (handled above)
        # Out-of-window capex is still immediately deductible
        for it in capex:
            yr_offset = it.year_due - globals_.today_year + 1  # 1-indexed
            if (it.year_due >= globals_.today_year + rules_de.ANSCHAFFUNGSNAH_WINDOW_YEARS
                    and not it.is_capitalized):
                capex_by_year[yr_offset] = capex_by_year.get(yr_offset, 0) + it.cost_eur
    else:
        # No trigger → all non-capitalized capex is immediately deductible
        for it in capex:
            yr_offset = it.year_due - globals_.today_year + 1
            if not it.is_capitalized:
                capex_by_year[yr_offset] = capex_by_year.get(yr_offset, 0) + it.cost_eur

    base_rent_year = (rent.monthly_rent + rent.monthly_parking) * 12 \
        - (rent.monthly_rent + rent.monthly_parking) * rent.expected_vacancy_months_per_year
    # Note: vacancy-adjusted income for tax = effective rent received

    useful_life = afa_basis.useful_life_years
    for yr in range(1, horizon + 1):
        # Rent income (escalated)
        rent_income = base_rent_year * (1 + rent.annual_rent_escalation) ** (yr - 1)
        # Interest deduction (assertion above guarantees the index exists)
        deduct_int = float(annual_interest_total.iloc[yr - 1])
        # Operating costs deduction (escalated by cost inflation)
        deduct_costs = deductible_costs_year_one_eur \
            * (1 + globals_.cost_inflation_annual) ** (yr - 1)
        # AfA stops at the statutory useful life (§ 7 Abs. 4 EStG):
        # 40 yr for pre-1925 Altbau, 50 yr for 1925-2022, 33⅓ yr for
        # post-2023. After that the depreciation shield is exhausted.
        deduct_afa = annual_afa if yr <= useful_life else 0.0
        # Capex deduction this year (inflation-adjusted)
        capex_this_year = capex_by_year.get(yr, 0)
        deduct_capex = capex_this_year * (1 + globals_.cost_inflation_annual) ** (yr - 1)

        taxable = rent_income - deduct_int - deduct_costs - deduct_afa - deduct_capex
        # Verlustverrechnung: rental losses reduce the household's overall tax
        # bill at the marginal rate (§ 10d EStG), so tax_owed is signed — a
        # negative value represents tax *saved* on other income (the salary).
        tax = taxable * globals_.marginal_tax_rate

        rows.append({
            "year": yr,
            "rent_income": rent_income,
            "deduct_interest": deduct_int,
            "deduct_costs": deduct_costs,
            "deduct_afa": deduct_afa,
            "deduct_capex": deduct_capex,
            "taxable_income": taxable,
            "tax_owed": tax,
        })

    return pd.DataFrame(rows).set_index("year")
