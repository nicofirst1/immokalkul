"""
Financing & amortization.

Handles:
- Total purchase cost build-up (price + fees + renovation)
- Building / land split (for AfA basis)
- 50-year amortization schedule for arbitrary loan tranches
- Adaptive Mamma payment (accelerates once Bank/LBS clear)
"""
from __future__ import annotations
from dataclasses import dataclass
import pandas as pd
from . import rules_de
from .models import Property, Financing, Loan, GlobalParameters


@dataclass
class PurchaseCostBreakdown:
    purchase_price: float
    grunderwerbsteuer: float
    maklerprovision: float
    notary_grundbuch: float
    renovation_capitalized: float
    fees_subtotal: float            # all of the above except price + reno
    fees_capitalizable_for_afa: float  # Grunderwerb + Makler + 80% Notar
    total_cost: float               # everything


def compute_purchase_costs(p: Property, renovation_capitalized: float = 0.0,
                            grunderwerbsteuer_rate: float = rules_de.GRUNDERWERBSTEUER_NRW,
                            makler_rate: float = rules_de.MAKLERPROVISION_TYPICAL,
                            notary_rate: float = rules_de.NOTARY_AND_GRUNDBUCH
                            ) -> PurchaseCostBreakdown:
    price = p.purchase_price
    grunderwerb = price * grunderwerbsteuer_rate
    makler = price * makler_rate
    notary = price * notary_rate
    fees = grunderwerb + makler + notary
    afa_fees = grunderwerb + makler + notary * rules_de.NOTARY_GRUNDBUCH_AFA_SHARE
    return PurchaseCostBreakdown(
        purchase_price=price,
        grunderwerbsteuer=grunderwerb,
        maklerprovision=makler,
        notary_grundbuch=notary,
        renovation_capitalized=renovation_capitalized,
        fees_subtotal=fees,
        fees_capitalizable_for_afa=afa_fees,
        total_cost=price + fees + renovation_capitalized,
    )


def estimate_building_share(p: Property) -> float:
    """Returns the fraction of the purchase price that is building (vs. land).

    Logic: if Bodenrichtwert is provided, computes:
        land_value = bodenrichtwert × plot_size
        building_value = price - land_value
        share = building_value / price
    Otherwise falls back to a property-type-aware default (apartments tend to
    have higher building share than houses in central locations because the
    plot is shared)."""
    if p.bodenrichtwert_eur_per_m2 is not None:
        land_value = p.bodenrichtwert_eur_per_m2 * p.plot_size_m2
        # For apartments in WEG, the plot is shared — only your Miteigentumsanteil
        # of the plot counts. A reasonable simplification: scale plot by living
        # space / total building living space — but we don't have that data.
        # If the user passed plot_size_m2 = living_space_m2, the calculation
        # already assumes sole ownership; for apartments, this overestimates
        # land value. We cap the land share at a property-type-specific max.
        building_value = p.purchase_price - land_value
        share = max(0.0, min(1.0, building_value / p.purchase_price))
        # Apply caps based on property type
        if p.property_type == "apartment":
            share = max(share, 0.75)  # apartments rarely have <75% building share
        else:
            share = max(share, 0.50)  # houses rarely have <50% building share
        return share
    # Fallback defaults
    return 0.80 if p.property_type == "apartment" else 0.65


def amortization_schedule(financing: Financing, horizon_years: int) -> pd.DataFrame:
    """Returns a yearly amortization schedule for all loans.

    Columns: year, then per-loan: <name>_balance, <name>_interest, <name>_payment,
    plus total_payment, total_interest.

    For Annuität loans, the annual payment is constant at year 1's
    `monthly_payment * 12`. For non-annuity loans (LBS, Mamma), payment is
    `monthly_payment * 12` until the balance is gone.

    Adaptive Mamma logic: if financing.adaptive_mamma is True AND a loan named
    "Mamma" exists, its annual payment becomes
        max(min_mamma_annual, debt_budget_annual - other_loans_payment)
    capped at the remaining balance. This redirects freed-up debt-service
    capacity (after Bank/LBS clear) to Mamma.
    """
    rows = []
    balances = {l.name: l.principal for l in financing.loans}
    annuities = {l.name: l.monthly_payment * 12 for l in financing.loans}
    rates = {l.name: l.interest_rate for l in financing.loans}
    is_annuity = {l.name: l.is_annuity for l in financing.loans}

    has_mamma = "Mamma" in balances
    mamma_min_annual = annuities.get("Mamma", 0.0)
    debt_budget_annual = financing.debt_budget_monthly * 12

    for yr in range(1, horizon_years + 1):
        row = {"year": yr}

        # Step 1: compute interest on opening balance for each loan
        interest = {name: balances[name] * rates[name] for name in balances}

        # Step 2: determine each loan's payment for this year
        payments = {}
        for name in balances:
            bal = balances[name]
            if bal <= 0:
                payments[name] = 0.0
                continue
            if is_annuity[name]:
                # Constant annuity, capped by (balance + this-year interest)
                payments[name] = min(annuities[name], bal + interest[name])
            else:
                # Fixed payment loans (LBS, Mamma): pay the fixed amount, but
                # cap at the balance (plus interest if any)
                payments[name] = min(annuities[name], bal + interest[name])

        # Step 3: adaptive Mamma reallocation
        if financing.adaptive_mamma and has_mamma and balances["Mamma"] > 0:
            other_payments = sum(p for n, p in payments.items() if n != "Mamma")
            target_mamma = max(mamma_min_annual, debt_budget_annual - other_payments)
            payments["Mamma"] = min(target_mamma,
                                     balances["Mamma"] + interest["Mamma"])

        # Step 4: update balances. New balance = old + interest - payment, floored at 0.
        new_balances = {name: max(0.0, balances[name] + interest[name] - payments[name])
                        for name in balances}

        # Record this year's row
        for name in balances:
            row[f"{name}_balance"] = balances[name]   # opening balance
            row[f"{name}_interest"] = interest[name]
            row[f"{name}_payment"] = payments[name]
        row["total_payment"] = sum(payments.values())
        row["total_interest"] = sum(interest.values())
        rows.append(row)

        balances = new_balances

    return pd.DataFrame(rows).set_index("year")


def years_to_clear(schedule: pd.DataFrame, loan_name: str) -> int:
    """Returns number of years the named loan had positive balance. If still
    outstanding at the end of the horizon, returns horizon length."""
    col = f"{loan_name}_balance"
    return int((schedule[col] > 0).sum())


def all_debt_clear_year(schedule: pd.DataFrame, loans: list[Loan]) -> int:
    """Returns the maximum years_to_clear across all loans."""
    return max(years_to_clear(schedule, l.name) for l in loans)
