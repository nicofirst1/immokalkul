"""
Financing & amortization.

Handles:
- Total purchase cost build-up (price + fees + renovation)
- Building / land split (for AfA basis)
- 50-year amortization schedule for arbitrary loan tranches
- Adaptive loan payments (accelerate once other loans clear)
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

    If Bodenrichtwert is provided:
        land_value = bodenrichtwert × plot_size
        land_share = land_value / price (clamped to [0, 1])
        building_share = 1 - land_share

    No floor — when the user gives us a Bodenrichtwert that implies the
    land alone is worth most of the price, we honour it (with a warning).
    Pre-fix code floored building_share at 0.75/0.50, silently inflating
    AfA basis on land-dominant properties.

    If Bodenrichtwert is None, falls back to a property-type prior
    (apartments share the plot via Miteigentumsanteil, so they typically
    carry a higher building share than freestanding houses).
    """
    if p.bodenrichtwert_eur_per_m2 is None:
        return 0.80 if p.property_type == "apartment" else 0.65

    land_value = p.bodenrichtwert_eur_per_m2 * p.plot_size_m2
    land_share = max(0.0, min(1.0, land_value / p.purchase_price))
    building_share = 1.0 - land_share
    if building_share < 0.10:
        import warnings
        warnings.warn(
            f"Bodenrichtwert × plot implies land is "
            f"{land_share:.0%} of price — AfA basis is near zero. Verify "
            f"the Bodenrichtwert via BORIS and the plot_size_m2 (apartments "
            f"share the WEG plot via Miteigentumsanteil).",
            stacklevel=2,
        )
    return building_share


def amortization_schedule(financing: Financing, horizon_years: int) -> pd.DataFrame:
    """Returns a yearly amortization schedule for all loans.

    Columns: year, then per-loan: <name>_balance, <name>_interest, <name>_payment,
    plus total_payment, total_interest.

    Convention: German Annuitätendarlehen per § 488 BGB compounds **annually**
    — interest is credited once per year on the opening balance, even though
    the borrower pays monthly. This engine matches that convention. A user
    using a monthly-compounding model would see slightly higher total
    interest (sub-1 % over a 30-year loan).

    For Annuität loans, the annual payment is constant at year 1's
    `monthly_payment * 12`. For non-annuity loans, payment is
    `monthly_payment * 12` until the balance is gone.

    Negative interest rates are clamped to 0 (subsidized-loan realism); a
    runtime warning is emitted so user input errors don't pass silently.

    Adaptive loan logic: for any loan with `is_adaptive=True`, the annual
    payment becomes
        max(min_annual, (debt_budget_annual - other_loans_payment) / n_adaptive)
    capped at that loan's remaining balance. This redirects freed-up
    debt-service capacity (after non-adaptive loans clear) to adaptive loans.
    If multiple loans are adaptive, the freed capacity is split equally.
    """
    rows = []
    balances = {l.name: l.principal for l in financing.loans}
    annuities = {l.name: l.monthly_payment * 12 for l in financing.loans}
    rates = {}
    for l in financing.loans:
        if l.interest_rate < 0:
            import warnings
            warnings.warn(
                f"Loan {l.name!r} has negative interest_rate "
                f"{l.interest_rate:.4f}; clamping to 0.",
                stacklevel=2)
            rates[l.name] = 0.0
        else:
            rates[l.name] = l.interest_rate
    is_annuity = {l.name: l.is_annuity for l in financing.loans}
    is_adaptive = {l.name: l.is_adaptive for l in financing.loans}

    adaptive_names = [l.name for l in financing.loans if l.is_adaptive]
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
                # Fixed payment (and adaptive) loans: pay the fixed amount,
                # cap at balance + interest. Adaptive reallocation happens next.
                payments[name] = min(annuities[name], bal + interest[name])

        # Step 3: adaptive reallocation — split freed capacity across adaptive
        # loans with non-zero balance.
        active_adaptive = [n for n in adaptive_names if balances[n] > 0]
        if active_adaptive:
            non_adaptive_payment = sum(p for n, p in payments.items()
                                       if n not in adaptive_names)
            freed = max(0.0, debt_budget_annual - non_adaptive_payment)
            per_loan_target = freed / len(active_adaptive)
            for name in active_adaptive:
                min_annual = annuities[name]
                target = max(min_annual, per_loan_target)
                payments[name] = min(target, balances[name] + interest[name])

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
