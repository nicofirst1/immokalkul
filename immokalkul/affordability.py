"""
Affordability checks and derived KPIs.

Pure-Python helpers that take a `ScenarioResult` (from `cashflow.run`) plus
the source `Scenario` and return the numbers + pass/fail verdicts shown on
the Summary tab and in the top-of-page banner.

Kept out of `app.py` so it can be unit-tested without importing Streamlit.
"""
from __future__ import annotations

from .models import Scenario


def _fmt_eur(x: float, decimals: int = 0) -> str:
    """Match app.py's `eur` formatter — German thousands separator."""
    if x is None:
        return "—"
    if decimals == 0:
        return f"€{x:,.0f}".replace(",", ".")
    return f"€{x:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _fmt_pct(x: float, decimals: int = 1) -> str:
    return f"{x * 100:.{decimals}f}%"


def compute_affordability(result, s: Scenario) -> dict:
    """Shared computation of headline metrics + pass/fail checks.

    Feeds both the top-of-page verdict banner (one-sentence synthesis) and
    the Summary tab (metric grid + detail strip). Keeping this in one place
    keeps the two surfaces consistent — no drift between banner and strip.

    Returns a dict with keys grouped as:
      - ratios: loan_pct, burden_pct, down_pct, ltv, price_to_income
      - returns: gross_yield, net_yield, cost_per_m2_yr
      - year-1 flows: loan_mo, cost_mo, rent_mo, burden_mo
      - purchase: price, total_cost, total_debt, initial_cap, funding_gap
      - checks: list of (ok, long_ok_msg, long_fail_msg, short_fail_headline)
      - aggregates: passed, failed, n_pass, n_total, n_fail
      - verdict: level ("ok" | "warn" | "fail"), verdict (sentence)
    """
    yr1 = result.cashflow.iloc[0]
    income_mo = s.globals.monthly_household_income
    income_yr = income_mo * 12
    loan_mo = yr1["loan_payment"] / 12
    cost_mo = (yr1["loan_payment"] + yr1["op_costs"]) / 12
    rent_mo = yr1["rent_net"] / 12 if s.mode == "rent" else 0
    burden_mo = max(0, cost_mo - rent_mo)

    price = s.property.purchase_price
    total_cost = result.purchase.total_cost
    total_debt = sum(l.principal for l in s.financing.loans)
    # Funding debt = freshly originated annuity loans at closing. Non-annuity
    # loans (Bauspar, family) are typically pre-existing or their proceeds
    # already sit inside `initial_capital` — counting them would double-count.
    funding_debt = sum(l.principal for l in s.financing.loans if l.is_annuity)
    initial_cap = s.financing.initial_capital
    funding_gap = total_cost - initial_cap - funding_debt

    loan_pct = loan_mo / income_mo if income_mo else 0
    burden_pct = burden_mo / income_mo if income_mo else 0
    down_pct = initial_cap / price if price else 0
    # LTV reflects bank-secured debt — use the same funding_debt concept.
    ltv = funding_debt / price if price else 0
    price_to_income = price / income_yr if income_yr else 0

    annual_rent_net = yr1["rent_net"]
    annual_op_costs = yr1["op_costs"]
    gross_yield = annual_rent_net / price if (s.mode == "rent" and price) else None
    net_yield = (annual_rent_net - annual_op_costs) / price if (s.mode == "rent" and price) else None
    cost_per_m2_yr = (cost_mo * 12) / s.property.living_space_m2 if s.property.living_space_m2 else 0

    # (ok, long_ok_msg, long_fail_msg, short_fail_headline)
    checks = []
    checks.append((loan_pct <= 0.30,
                   f"Loan payment is {_fmt_pct(loan_pct)} of income",
                   f"Loan payment is {_fmt_pct(loan_pct)} of income — above the 30% rule",
                   f"loan is {_fmt_pct(loan_pct)} of income"))
    checks.append((burden_pct <= 0.30,
                   f"Net burden is {_fmt_pct(burden_pct)} of income",
                   f"Net burden is {_fmt_pct(burden_pct)} of income — above the 30% rule",
                   f"net burden is {_fmt_pct(burden_pct)} of income"))
    checks.append((down_pct >= 0.20,
                   f"Down payment is {_fmt_pct(down_pct)} of price (≥ 20% floor)",
                   f"Down payment is only {_fmt_pct(down_pct)} of price — below the 20% floor",
                   f"down payment is {_fmt_pct(down_pct)}"))
    checks.append((abs(funding_gap) < 1000,
                   f"Funding plan closes: capital + loans ≈ total cost ({_fmt_eur(total_cost)})",
                   (f"Under-funded by {_fmt_eur(funding_gap)} — increase a loan or capital"
                    if funding_gap > 0 else
                    f"Over-funded by {_fmt_eur(-funding_gap)} — reduce a loan"),
                   "funding plan doesn't close"))
    checks.append((ltv <= 0.80,
                   f"LTV is {_fmt_pct(ltv)} (≤ 80% bank floor)",
                   f"LTV is {_fmt_pct(ltv)} — above the typical 80% cap, expect worse rates",
                   f"LTV is {_fmt_pct(ltv)}"))
    if s.mode == "rent":
        checks.append((gross_yield >= 0.03,
                       f"Gross yield is {_fmt_pct(gross_yield, 2)} (≥ 3% rule)",
                       f"Gross yield is only {_fmt_pct(gross_yield, 2)} — below the 3% rule",
                       f"gross yield is {_fmt_pct(gross_yield, 2)}"))
        checks.append((rent_mo >= cost_mo,
                       f"Year-1 rent {_fmt_eur(rent_mo)}/mo covers all costs ({_fmt_eur(cost_mo)}/mo)",
                       f"Year-1 rent {_fmt_eur(rent_mo)}/mo doesn't cover costs {_fmt_eur(cost_mo)}/mo",
                       "year-1 rent doesn't cover costs"))
    else:
        current_rent_mo = s.live.current_monthly_rent_warm_eur or 0
        if current_rent_mo > 0:
            checks.append((cost_mo <= current_rent_mo,
                           f"Ownership ({_fmt_eur(cost_mo)}/mo) is cheaper than current rent ({_fmt_eur(current_rent_mo)}/mo)",
                           f"Ownership ({_fmt_eur(cost_mo)}/mo) costs more than current rent ({_fmt_eur(current_rent_mo)}/mo) — you're paying for equity instead of a landlord",
                           "ownership costs more than current rent"))

    passed_msgs = [m for ok, m, _, _ in checks if ok]
    failed_msgs = [m for ok, _, m, _ in checks if not ok]
    failed_headlines = [h for ok, _, _, h in checks if not ok]
    n_pass = len(passed_msgs)
    n_total = len(checks)
    n_fail = n_total - n_pass

    if n_fail == 0:
        level = "ok"
        verdict = f"✅ Looks affordable — meets all {n_total} rules."
    elif n_fail == 1:
        level = "warn"
        verdict = (f"⚠ Mostly affordable — meets {n_pass} of {n_total} rules. "
                   f"Watch: {failed_headlines[0]}.")
    else:
        level = "fail"
        issues = ", ".join(failed_headlines[:2])
        verdict = (f"❌ Doesn't pencil out — only {n_pass} of {n_total} rules pass. "
                   f"Key issues: {issues}.")

    return {
        "loan_pct": loan_pct, "burden_pct": burden_pct, "down_pct": down_pct,
        "ltv": ltv, "price_to_income": price_to_income,
        "gross_yield": gross_yield, "net_yield": net_yield,
        "loan_mo": loan_mo, "cost_mo": cost_mo, "rent_mo": rent_mo,
        "burden_mo": burden_mo, "cost_per_m2_yr": cost_per_m2_yr,
        "price": price, "total_cost": total_cost, "total_debt": total_debt,
        "funding_debt": funding_debt,
        "initial_cap": initial_cap, "funding_gap": funding_gap,
        "annual_rent_net": annual_rent_net, "annual_op_costs": annual_op_costs,
        "checks": checks, "passed": passed_msgs, "failed": failed_msgs,
        "n_pass": n_pass, "n_total": n_total, "n_fail": n_fail,
        "level": level, "verdict": verdict,
    }
