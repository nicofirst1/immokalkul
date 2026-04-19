"""
Streamlit UI for immokalkul.

Run with: streamlit run app.py

Layout:
- Sidebar: all editable inputs grouped by section + load/save scenarios
- Main: 7 tabs (Summary, Live vs Rent, Cash Flow, Costs, Debt, Capex, Tax)
- Header: scenario name + mode toggle + key affordability indicators
"""
from __future__ import annotations
import sys, os
from pathlib import Path
from copy import deepcopy
import io as io_module

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Make the package importable when running from project root
sys.path.insert(0, str(Path(__file__).parent))

from immokalkul import (Scenario, Property, Loan, Financing, CapexItem,
                            RentParameters, LiveParameters, CostInputs,
                            GlobalParameters, run, load_scenario, save_scenario,
                            compute_affordability, rules_de)

# -----------------------------------------------------------------------------
# Page config
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Property Calculator",
    layout="wide",
    initial_sidebar_state="expanded",
    page_icon="🏠",
)

DATA_DIR = Path(__file__).parent / "data"
DEFAULT_SCENARIO = DATA_DIR / "bonn_poppelsdorf.yaml"

# -----------------------------------------------------------------------------
# Number formatting helpers
# -----------------------------------------------------------------------------
def eur(x: float, decimals: int = 0) -> str:
    """Format as EUR with German thousands separators."""
    if x is None:
        return "—"
    if decimals == 0:
        return f"€{x:,.0f}".replace(",", ".")
    return f"€{x:,.{decimals}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def pct(x: float, decimals: int = 1) -> str:
    return f"{x*100:.{decimals}f}%"


# -----------------------------------------------------------------------------
# Scenario state management
# -----------------------------------------------------------------------------
def init_scenario():
    """Load default scenario into session state if not already there."""
    if "scenario" not in st.session_state:
        if DEFAULT_SCENARIO.exists():
            st.session_state.scenario = load_scenario(DEFAULT_SCENARIO)
            st.session_state.scenario_source = DEFAULT_SCENARIO.stem
        else:
            st.session_state.scenario = _make_blank_scenario()
            st.session_state.scenario_source = "blank"
        st.session_state.scenario_original = deepcopy(st.session_state.scenario)


def _is_scenario_modified() -> bool:
    """True if the user has edited the loaded scenario in the sidebar."""
    from dataclasses import asdict
    orig = st.session_state.get("scenario_original")
    curr = st.session_state.get("scenario")
    if orig is None or curr is None:
        return False
    try:
        return asdict(orig) != asdict(curr)
    except Exception:
        return False


def _make_blank_scenario() -> Scenario:
    return Scenario(
        mode="rent",
        property=Property(
            name="New property", purchase_price=400000, living_space_m2=100,
            plot_size_m2=100, year_built=2000),
        financing=Financing(
            initial_capital=100000,
            loans=[
                Loan("Bank", 300000, 0.034, 1350, is_annuity=True, is_adaptive=False),
            ],
            debt_budget_monthly=1500,
        ),
        costs=CostInputs(),
        rent=RentParameters(monthly_rent=1500),
        live=LiveParameters(),
        globals=GlobalParameters(),
    )


# -----------------------------------------------------------------------------
# Sidebar — input editing
# -----------------------------------------------------------------------------
def sidebar_inputs():
    """All editable inputs. Mutates st.session_state.scenario in place."""
    s = st.session_state.scenario

    with st.sidebar:
        st.title("🏠 Property Calculator")
        st.caption("German property finance — live vs. rent")

        # --- Load / Save ---
        with st.expander("📂 Scenarios", expanded=True):
            available = sorted(DATA_DIR.glob("*.yaml")) if DATA_DIR.exists() else []
            if available:
                names = [f.stem for f in available]
                default_idx = next((i for i, f in enumerate(available)
                                     if f.name == DEFAULT_SCENARIO.name), 0)
                picked = st.selectbox("Load scenario", names, index=default_idx)
                if st.button("Load selected"):
                    st.session_state.scenario = load_scenario(DATA_DIR / f"{picked}.yaml")
                    st.session_state.scenario_original = deepcopy(st.session_state.scenario)
                    st.session_state.scenario_source = picked
                    st.rerun()

            uploaded = st.file_uploader("Upload YAML scenario", type=["yaml", "yml"])
            if uploaded:
                tmp_path = Path("/tmp") / uploaded.name
                tmp_path.write_bytes(uploaded.getvalue())
                st.session_state.scenario = load_scenario(tmp_path)
                st.session_state.scenario_original = deepcopy(st.session_state.scenario)
                st.session_state.scenario_source = uploaded.name
                st.success(f"Loaded {uploaded.name}")
                st.rerun()

            # Save current to YAML for download
            buf = io_module.StringIO()
            tmp_yaml = Path("/tmp") / f"{s.property.name.replace(' ', '_')}.yaml"
            save_scenario(s, tmp_yaml)
            st.download_button("⬇ Download current scenario (YAML)",
                                data=tmp_yaml.read_text(), file_name=tmp_yaml.name,
                                mime="text/yaml")

        # --- Mode ---
        st.markdown("### Mode")
        s.mode = st.radio("Analysis mode", ["live", "rent"],
                          index=0 if s.mode == "live" else 1,
                          horizontal=True,
                          format_func=lambda m: "Live in it" if m == "live" else "Rent it out",
                          help="Live in it: you occupy it (your costs only). "
                               "Rent it out: buy-to-let (rental income, taxes, vacancy).")

        # --- Property ---
        with st.expander("🏘 Property", expanded=False):
            s.property.name = st.text_input("Name", s.property.name)
            c1, c2 = st.columns(2)
            with c1:
                s.property.purchase_price = st.number_input(
                    "Purchase price (€)", value=float(s.property.purchase_price),
                    step=5000.0, format="%.0f")
                s.property.living_space_m2 = st.number_input(
                    "Living space (m²)", value=float(s.property.living_space_m2),
                    step=1.0, format="%.2f")
                s.property.year_built = int(st.number_input(
                    "Year built", value=int(s.property.year_built),
                    min_value=1700, max_value=2030, step=1))
                s.property.plot_size_m2 = st.number_input(
                    "Plot size (m²)", value=float(s.property.plot_size_m2),
                    step=1.0, format="%.2f",
                    help="For an apartment, your share of the WEG plot. For a house, full plot.")
            with c2:
                s.property.property_type = st.selectbox(
                    "Type", ["apartment", "house"],
                    index=0 if s.property.property_type == "apartment" else 1)
                s.property.has_elevator = st.checkbox("Has elevator", s.property.has_elevator)

            with st.expander("🔬 Tax-relevant details (can skip for first pass)", expanded=False):
                lr = s.property.year_last_major_renovation
                s.property.year_last_major_renovation = int(st.number_input(
                    "Year last renovated (0 = never)",
                    value=int(lr) if lr else 0, min_value=0, max_value=2030, step=1,
                    help="Kernsanierung year, if any. Resets the component "
                         "lifecycle clock for heating, bathroom, electrics.")) or None
                s.property.energy_demand_kwh_per_m2_year = st.number_input(
                    "Energy demand (kWh/m²/yr)",
                    value=float(s.property.energy_demand_kwh_per_m2_year),
                    step=5.0, format="%.0f",
                    help="From the Energieausweis. <100 good, 100-150 average, 150+ poor.")
                s.property.bodenrichtwert_eur_per_m2 = st.number_input(
                    "Bodenrichtwert (€/m²)",
                    value=float(s.property.bodenrichtwert_eur_per_m2 or 0),
                    step=10.0, format="%.0f",
                    help="Land value per m² from BORIS NRW. Drives the AfA "
                         "building/land split. Leave 0 to use property-type "
                         "defaults.") or None
                s.property.is_denkmal = st.checkbox(
                    "Listed building (Denkmal)", s.property.is_denkmal,
                    help="Special AfA rules apply (§ 7i EStG — not yet fully modelled).")

        # --- Financing ---
        with st.expander("💰 Financing", expanded=False):
            with st.expander("❓ Initial capital vs. loans — what's the difference?",
                              expanded=False):
                st.markdown(
                    "**Initial capital** is *your own money* at closing — "
                    "savings, a gift, a Bauspar payout. No repayment, no "
                    "interest.\n\n"
                    "**Loans** are money a third party fronts; you pay them "
                    "back over time.\n\n"
                    "**Closing identity:** `initial_capital + Σ annuity loans "
                    "= price + fees`. The 'Suggested Bank principal' hint "
                    "below is exactly that residual.\n\n"
                    "**Family / Bauspar loans.** If a family loan's cash is "
                    "already inside *Initial capital* at closing, add the "
                    "loan as a **non-annuity** row below to track the "
                    "repayment only — don't double-count it at closing. "
                    "Flag it *Adaptive* if you want freed-up capacity to "
                    "flow into it once other loans clear.")
            s.financing.initial_capital = st.number_input(
                "Initial capital deployed (€)",
                value=float(s.financing.initial_capital), step=5000.0, format="%.0f",
                help="Your own money at closing — savings, gifts, Bauspar "
                     "payouts. No repayment. Contrast with Loans (below) = "
                     "third-party money you repay over time.")

            any_adaptive = any(l.is_adaptive for l in s.financing.loans)
            if any_adaptive:
                s.financing.debt_budget_monthly = st.number_input(
                    "Total monthly debt budget (€)",
                    value=float(s.financing.debt_budget_monthly),
                    step=50.0, format="%.0f",
                    help="Ceiling for total monthly debt service. Freed-up "
                         "capacity (after non-adaptive loans clear) flows "
                         "into the adaptive loans, up to this ceiling.")

            st.markdown("**Loans** — one row per tranche. Add / remove rows freely.")
            loans_df = pd.DataFrame([{
                "Name": l.name,
                "Principal (€)": l.principal,
                "Rate (%)": l.interest_rate * 100,
                "Monthly (€)": l.monthly_payment,
                "Annuity?": l.is_annuity,
                "Adaptive?": l.is_adaptive,
            } for l in s.financing.loans])
            edited = st.data_editor(
                loans_df, num_rows="dynamic", key="loans_editor",
                column_config={
                    "Principal (€)": st.column_config.NumberColumn(format="%.0f"),
                    "Rate (%)": st.column_config.NumberColumn(format="%.3f", step=0.1),
                    "Monthly (€)": st.column_config.NumberColumn(format="%.2f"),
                    "Annuity?": st.column_config.CheckboxColumn(),
                    "Adaptive?": st.column_config.CheckboxColumn(),
                })
            # Column key lives below the table — per-column hover tooltips
            # overflow the sidebar on narrow viewports.
            with st.expander("ℹ What do these columns mean?", expanded=False):
                st.markdown(
                    "- **Name** — free-text label (Bank, LBS, Mamma, …) "
                    "shown in charts and summary tables.\n"
                    "- **Principal (€)** — amount borrowed at closing.\n"
                    "- **Rate (%)** — annual interest rate (e.g. `3.4` = 3.4 %).\n"
                    "- **Monthly (€)** — fixed monthly payment. For an "
                    "Annuitätendarlehen this is principal × (rate + Tilgung) "
                    "/ 12. For an adaptive loan it's the **minimum** — the "
                    "engine may lift it once other loans clear.\n"
                    "- **Annuity?** — check for a German Annuitätendarlehen "
                    "(constant monthly payment; interest shrinks, principal "
                    "grows). Uncheck for fixed-payment loans like LBS "
                    "Bausparverträge or family loans.\n"
                    "- **Adaptive?** — check to absorb freed-up debt "
                    "capacity once other loans clear, up to the Total "
                    "monthly debt budget above. Typical for low-priority "
                    "family / 0 %-interest loans you want to retire faster.")
            # Write back
            new_loans = []
            for _, row in edited.iterrows():
                if pd.notna(row["Name"]) and row["Name"]:
                    new_loans.append(Loan(
                        name=str(row["Name"]),
                        principal=float(row["Principal (€)"] or 0),
                        interest_rate=float(row["Rate (%)"] or 0) / 100,
                        monthly_payment=float(row["Monthly (€)"] or 0),
                        is_annuity=bool(row["Annuity?"]),
                        is_adaptive=bool(row.get("Adaptive?", False)),
                    ))
            s.financing.loans = new_loans

            # Helper note on bank principal
            from immokalkul.financing import compute_purchase_costs
            try:
                pc = compute_purchase_costs(s.property)
                residual = pc.total_cost - s.financing.initial_capital
                st.caption(f"💡 Suggested Bank principal "
                           f"(total cost − initial capital): **{eur(residual)}**")
            except Exception:
                pass

        # --- Rent params ---
        with st.expander("🏘 Rent parameters", expanded=False):
            st.caption("These fields are **only used in rent mode** "
                       "(buy-to-let). Live mode ignores them. Safe to leave at "
                       "defaults if you only care about living in the place.")
            s.rent.monthly_rent = st.number_input(
                "Monthly rent (Kaltmiete, €)",
                value=float(s.rent.monthly_rent), step=50.0, format="%.0f",
                help="Net cold rent you expect to charge (Kaltmiete, no utilities). "
                     "For a realistic number, look up Mietspiegel or comparable "
                     "listings on ImmoScout24 for your postcode.")
            s.rent.monthly_parking = st.number_input(
                "Monthly parking (€)",
                value=float(s.rent.monthly_parking), step=10.0, format="%.0f",
                help="Separate rent for a parking spot / Tiefgarage, if any. "
                     "Leave 0 if parking isn't part of the lease.")
            s.rent.annual_rent_escalation = st.slider(
                "Annual rent escalation", 0.0, 5.0,
                value=float(s.rent.annual_rent_escalation) * 100,
                step=0.1, format="%.1f%%",
                help="Assumed yearly rent growth. German rents are capped by "
                     "Mietspiegel / Mietpreisbremse — 1.5-2.5% is typical.") / 100
            s.rent.expected_vacancy_months_per_year = st.slider(
                "Vacancy (months/year)", 0.0, 3.0,
                value=float(s.rent.expected_vacancy_months_per_year), step=0.05,
                help="Months per year the flat is empty between tenants. "
                     "0.15 = hot city, 1.0+ = rural.")
            s.rent.has_property_manager = st.checkbox(
                "Use property manager?", s.rent.has_property_manager,
                help="Check if you'll outsource tenant handling / rent "
                     "collection / minor repairs to a Hausverwaltung. Typical "
                     "in buy-to-let across cities; waive it if you self-manage "
                     "a single unit you know well.")
            if s.rent.has_property_manager:
                s.rent.property_manager_pct_of_rent = st.slider(
                    "Manager fee (% of rent)", 0.0, 10.0,
                    value=float(s.rent.property_manager_pct_of_rent) * 100,
                    step=0.1, format="%.1f%%",
                    help="Monthly fee as a share of gross rent. German market "
                         "range: 4-8% for a single unit, sometimes a flat "
                         "€25-40/month instead. Fully deductible in rent mode.") / 100

        # --- Live params ---
        with st.expander("🛏 Live parameters", expanded=False):
            st.caption("These fields are **only used in live mode** "
                       "(owner-occupied). Rent mode ignores them.")
            s.live.people_in_household = int(st.number_input(
                "People in household", value=int(s.live.people_in_household),
                min_value=1, max_value=10, step=1,
                help="Drives heating and electricity consumption. Adults and "
                     "children count the same here — the model uses a per-head "
                     "kWh adjustment."))
            s.live.large_appliances = int(st.number_input(
                "Large appliances", value=int(s.live.large_appliances),
                min_value=0, max_value=20, step=1,
                help="Count of large electric appliances (fridge, freezer, "
                     "washer, dryer, dishwasher, oven). Proxy for electricity "
                     "base load."))
            s.live.current_monthly_rent_warm_eur = st.number_input(
                "Current rent you pay now (warm, €/mo)",
                value=float(s.live.current_monthly_rent_warm_eur),
                step=50.0, format="%.0f",
                help="What you currently pay all-inclusive (Warmmiete + "
                     "utilities). Buying replaces this cost — the Summary "
                     "uses it to compare. Leave 0 if not relevant.")

        # --- Costs ---
        with st.expander("⚡ Operating costs", expanded=False):
            st.caption("All running costs, separate from the purchase and the "
                       "loans. Most have sensible German-market defaults — "
                       "tune only what you know. Everything here escalates by "
                       "the cost-inflation rate in Global assumptions.")
            c = s.costs
            c.gas_price_eur_per_kwh = st.number_input("Gas €/kWh",
                value=float(c.gas_price_eur_per_kwh), step=0.01, format="%.3f",
                help="Retail gas price per kWh for heating. Typical 2024-2026 "
                     "German range: €0.10-0.14. Check your Energieversorger bill.")
            c.electricity_price_eur_per_kwh = st.number_input("Electricity €/kWh",
                value=float(c.electricity_price_eur_per_kwh), step=0.01, format="%.3f",
                help="Retail electricity price per kWh. Typical 2025 German "
                     "Grundversorger rate: €0.32-0.40 (Ökostrom tariffs "
                     "€0.28-0.35). Only used in live mode for Nebenkosten.")
            c.grundsteuer_rate_of_price = st.slider(
                "Property tax rate (Grundsteuer, % of price)", 0.0, 1.0,
                value=float(c.grundsteuer_rate_of_price) * 100,
                step=0.01, format="%.2f%%",
                help="Property tax as a share of purchase price. Since the "
                     "2025 Grundsteuer reform, the Bundesmodell roughly lands "
                     "between 0.15% and 0.35% of market value depending on "
                     "Bundesland + Hebesatz. 0.2% is a reasonable default.") / 100
            c.hausgeld_monthly_for_rent = st.number_input("Building fee (Hausgeld) — €/mo, rent mode",
                value=float(c.hausgeld_monthly_for_rent), step=10.0, format="%.0f",
                help="Monthly WEG fee covering Gemeinschaftseigentum "
                     "(common-area maintenance, admin, building insurance "
                     "shared share). Typical: €2.50-4.50 per m² living space. "
                     "Set 0 for a freestanding house. Only the non-allocable "
                     "portion counts in rent mode (the rest is recovered via "
                     "Betriebskostenabrechnung).")
            c.administration_monthly = st.number_input("Administration (€/mo)",
                value=float(c.administration_monthly), step=5.0, format="%.0f",
                help="Verwalterhonorar or self-landlord admin costs (accounting, "
                     "Steuerberater share). Typical: €25-40/month for a single "
                     "unit. Set 0 for a freestanding house you manage yourself.")
            c.municipal_charges_eur_per_m2_month = st.number_input("Municipal €/m²/mo",
                value=float(c.municipal_charges_eur_per_m2_month), step=0.05, format="%.2f",
                help="City-level charges: trash, water, sewage, street cleaning, "
                     "chimney sweep. Typical range: €0.40-0.80/m²/month "
                     "depending on Kommune.")
            c.building_insurance_eur_per_m2_year = st.number_input("Building insurance €/m²/yr",
                value=float(c.building_insurance_eur_per_m2_year), step=0.5, format="%.1f",
                help="Wohngebäudeversicherung — covers fire, storm, water "
                     "damage to the building shell. Typical: €3-6 per m²/yr "
                     "depending on region and flood zone.")
            c.liability_insurance_annual = st.number_input("Liability insurance €/yr",
                value=float(c.liability_insurance_annual), step=10.0, format="%.0f",
                help="Haus- und Grundbesitzerhaftpflicht (owner's liability). "
                     "Typical: €80-200/yr. Sometimes bundled into private "
                     "liability insurance — leave 0 if already covered there.")

        # --- Globals ---
        with st.expander("🌍 Global assumptions", expanded=False):
            g = s.globals
            g.monthly_household_income = st.number_input(
                "Monthly household net income (€)",
                value=float(g.monthly_household_income), step=100.0, format="%.0f",
                help="Total household take-home pay, Netto. Used only to "
                     "compute the 'burden-on-salary' metric (30%-rule check). "
                     "Does not affect the cashflow projection.")
            g.additional_monthly_savings = st.number_input(
                "Other monthly savings (€)",
                value=float(g.additional_monthly_savings), step=50.0, format="%.0f",
                help="Savings you set aside that are NOT related to the "
                     "property. Used for the cumulative-wealth line so the "
                     "chart shows property vs total household wealth.")
            g.cost_inflation_annual = st.slider(
                "Cost inflation (annual)", 0.0, 6.0,
                value=float(g.cost_inflation_annual) * 100,
                step=0.1, format="%.1f%%",
                help="Yearly escalation applied to operating costs and capex. "
                     "**Default 2%** = ECB price-stability target and German "
                     "long-run CPI anchor (Destatis 10-year average 2014-2024 "
                     "≈ 2.5% incl. 2022-2023 spike). Bump to 3% if you think "
                     "the 2022+ regime shift persists.") / 100
            g.marginal_tax_rate = st.slider(
                "Marginal tax rate (Grenzsteuersatz)", 10.0, 55.0,
                value=float(g.marginal_tax_rate) * 100,
                step=1.0, format="%.0f%%",
                help="Your top German income-tax rate. Roughly 30% at €35k, "
                     "42% above €68k single.") / 100
            g.horizon_years = int(st.slider(
                "Horizon (years)", 10, 60, value=int(g.horizon_years),
                help="How far out to project. **50 years is the convention** "
                     "for property investment (matches German AfA useful life "
                     "for 1925-2022 builds). Shorter horizons miss post-"
                     "debt-free years when the property starts paying out; "
                     "longer ones compound more model error."))

        # --- Capex ---
        with st.expander("🔨 User-specified renovations", expanded=False):
            st.caption("One-off capex on top of auto-scheduled component lifecycles. "
                       "Set 'is_capitalized' = True for Herstellungskosten (depreciated via AfA), "
                       "False for Erhaltungsaufwand (immediately deductible).")
            capex_df = pd.DataFrame([{
                "Name": c.name, "Cost (€)": c.cost_eur,
                "Year due": c.year_due, "Capitalized?": c.is_capitalized,
            } for c in s.user_capex])
            if capex_df.empty:
                capex_df = pd.DataFrame([{
                    "Name": "", "Cost (€)": 0, "Year due": s.globals.today_year,
                    "Capitalized?": False}])
            edited_cx = st.data_editor(
                capex_df, num_rows="dynamic", key="capex_editor",
                column_config={
                    "Cost (€)": st.column_config.NumberColumn(format="%.0f", min_value=0),
                    "Year due": st.column_config.NumberColumn(format="%d", step=1),
                    "Capitalized?": st.column_config.CheckboxColumn(),
                })
            new_cx = []
            for _, row in edited_cx.iterrows():
                if pd.notna(row["Name"]) and row["Name"] and float(row["Cost (€)"] or 0) > 0:
                    new_cx.append(CapexItem(
                        name=str(row["Name"]),
                        cost_eur=float(row["Cost (€)"]),
                        year_due=int(row["Year due"]),
                        is_capitalized=bool(row["Capitalized?"]),
                    ))
            s.user_capex = new_cx
            s.auto_schedule_capex = st.checkbox(
                "Auto-schedule component capex (heating, roof, etc.)",
                s.auto_schedule_capex,
                help="Uses component lifecycle table to project replacements based on year built.")


# -----------------------------------------------------------------------------
# Header — affordability KPIs
# -----------------------------------------------------------------------------
def render_header(result_current, result_other, s: Scenario, afford: dict):
    """Top-of-page summary: verdict banner + 4-tile KPI strip."""
    modified = " *(modified)*" if _is_scenario_modified() else ""
    st.title(f"🏠 {s.property.name}{modified}")

    # Sample-scenario framing banner
    source = st.session_state.get("scenario_source", "")
    if source and source != "blank" and not modified:
        st.info(
            f"📌 You're viewing the **{source}** sample scenario. Edit any "
            f"input on the left to try your own numbers — or pick a "
            f"different sample in the Scenarios expander.")

    # Verdict banner — single-sentence synthesis of the affordability checks
    banner_fn = {"ok": st.success, "warn": st.warning, "fail": st.error}[afford["level"]]
    banner_fn(afford["verdict"])

    cf_cur = result_current.cashflow
    final = float(cf_cur["cumulative"].iloc[-1])
    cols = st.columns(4)
    cols[0].metric("Total purchase cost", eur(result_current.purchase.total_cost))
    cols[1].metric("Years until debt-free", f"{result_current.years_to_debt_free} yr")
    cols[2].metric(
        f"50-yr cumulative wealth",
        eur(final),
        delta_color="normal" if final > 0 else "inverse",
        help="Net 50-year change in wealth from owning this property. "
             "Positive = pays back; negative = costs more than it earns.")
    level_label = {"ok": "Within rules", "warn": "Mostly within rules",
                   "fail": "Stretching the rules"}[afford["level"]]
    cols[3].metric(
        "Affordability",
        f"{afford['n_pass']} / {afford['n_total']} rules",
        delta=level_label,
        delta_color=("normal" if afford["level"] == "ok" else
                     "off" if afford["level"] == "warn" else "inverse"),
        help="How many German rules-of-thumb this scenario passes (loan/income, "
             "LTV, down payment, funding plan, yield, …). See Summary for detail.")


# -----------------------------------------------------------------------------
# Tabs
# -----------------------------------------------------------------------------
def tab_summary(result, s: Scenario, afford: dict):
    """High-level dashboard. Affordability + returns at the top, then detail."""
    st.markdown("## Summary")

    if s.mode == "live" and (s.live.current_monthly_rent_warm_eur or 0) == 0:
        st.warning(
            "⚠ **Set 'Current rent you pay now (warm, €/mo)' in the "
            "🛏 Live parameters sidebar.** Without it, the cumulative wealth "
            "chart treats ownership as 100 % pure outflow and doesn't credit "
            "the rent you'd otherwise pay — so live mode looks artificially "
            "hundreds of thousands of euros worse than reality."
        )

    # ---------- In-context on-ramp: collapsed walkthrough ----------
    with st.expander("🚀 New here? 2-minute walkthrough", expanded=False):
        st.markdown(
            "1. **Pick a scenario** from the 📂 Scenarios expander in the "
            "sidebar — or upload your own YAML.\n"
            "2. **Tweak inputs** in the sidebar. Every field updates the "
            "results instantly. Hover ❓ next to a field for its meaning.\n"
            "3. **Read this tab** for the headline, then **Buy vs Rent** "
            "for the cross-mode comparison, and **Cash flow / Debt / Tax / "
            "Capex** for depth.\n\n"
            "Full guided tour of every sidebar section is on the **New here?** "
            "tab.")

    # ---------- Limitations — elevated for transparency ----------
    with st.expander("⚠ What this tool does NOT model", expanded=False):
        st.markdown(
            "- **Property appreciation** — no market-price growth assumed. "
            "Equity is built purely through amortization.\n"
            "- **Loss carryforward** — German rules let rental losses offset "
            "other income in early years; this model floors tax at €0.\n"
            "- **Sonderumlagen** (WEG special assessments) — baked into the "
            "maintenance reserve rather than modelled separately.\n"
            "- **Denkmal-AfA** (§ 7i EStG) and **§ 7b Sonder-AfA** for new "
            "builds — not yet implemented.\n"
            "- **VAT / Kirchensteuer nuances** beyond the marginal rate.\n\n"
            "For anything affecting a tax filing, verify with a Steuerberater.")

    # Pull metrics from the shared helper
    price = afford["price"]; total_cost = afford["total_cost"]
    total_debt = afford["total_debt"]; initial_cap = afford["initial_cap"]
    loan_pct = afford["loan_pct"]; burden_pct = afford["burden_pct"]
    down_pct = afford["down_pct"]; ltv = afford["ltv"]
    price_to_income = afford["price_to_income"]
    gross_yield = afford["gross_yield"]; net_yield = afford["net_yield"]
    loan_mo = afford["loan_mo"]; cost_mo = afford["cost_mo"]; rent_mo = afford["rent_mo"]
    cost_per_m2_yr = afford["cost_per_m2_yr"]

    st.markdown("### Can you afford this?")
    a1, a2, a3, a4 = st.columns(4)
    a1.metric(
        "Loan / income",
        pct(loan_pct, 1),
        delta=("within 30%" if loan_pct <= 0.30 else f"+{pct(loan_pct - 0.30, 1)} over"),
        delta_color="normal" if loan_pct <= 0.30 else "inverse",
        help="Monthly debt service as a share of monthly net income. "
             "German banks use 30% as a rule of thumb for the loan alone.")
    a2.metric(
        "Net burden / income",
        pct(burden_pct, 1),
        delta=("within 30%" if burden_pct <= 0.30 else f"+{pct(burden_pct - 0.30, 1)} over"),
        delta_color="normal" if burden_pct <= 0.30 else "inverse",
        help="Loan + operating costs − rent income, as a share of income. "
             "The total monthly drain on your salary.")
    a3.metric(
        "Down payment / price",
        pct(down_pct, 1),
        delta=("≥ 20% floor" if down_pct >= 0.20 else f"{pct(0.20 - down_pct, 1)} short"),
        delta_color="normal" if down_pct >= 0.20 else "inverse",
        help="Initial capital as a share of purchase price. German banks "
             "typically want ≥ 20% down (ideally enough to cover closing "
             "fees too, so the loan stays ≤ price).")
    a4.metric(
        "Price / annual income",
        f"{price_to_income:.1f}×",
        delta=("affordable" if price_to_income <= 8 else
               "stretched" if price_to_income <= 10 else "very stretched"),
        delta_color=("normal" if price_to_income <= 8 else
                     "off" if price_to_income <= 10 else "inverse"),
        help="Purchase price divided by annual household net income. "
             "5-8× is the traditional safe range; 8-10× is stretched; "
             "10×+ is typical only in top cities and implies long horizons.")

    st.markdown("### Return, leverage, timing")
    b1, b2, b3, b4 = st.columns(4)
    if s.mode == "rent":
        b1.metric(
            "Gross rental yield",
            pct(gross_yield, 2),
            delta=("≥ 3% rule" if gross_yield >= 0.03 else f"{pct(0.03 - gross_yield, 2)} short"),
            delta_color="normal" if gross_yield >= 0.03 else "inverse",
            help="Annual net rent (after vacancy) ÷ purchase price. "
                 "German buy-to-let rule of thumb: ≥ 3% gross yield, "
                 "ideally ≥ 4% in regulated markets.")
        b2.metric(
            "Net rental yield",
            pct(net_yield, 2),
            delta=("≥ 2% healthy" if net_yield >= 0.02 else f"{pct(0.02 - net_yield, 2)} short"),
            delta_color="normal" if net_yield >= 0.02 else "inverse",
            help="(Rent − operating costs) ÷ price. Excludes financing and tax. "
                 "≥ 2% is reasonable; < 1% means operating costs eat the rent.")
    else:
        current_rent_mo = s.live.current_monthly_rent_warm_eur or 0
        if current_rent_mo > 0:
            delta_vs_rent = cost_mo - current_rent_mo
            b1.metric(
                "Ownership vs current rent",
                f"{eur(cost_mo, 0)} / mo",
                delta=(f"{eur(delta_vs_rent, 0)}/mo more"
                       if delta_vs_rent > 0 else
                       f"{eur(-delta_vs_rent, 0)}/mo less"),
                delta_color="inverse" if delta_vs_rent > 0 else "normal",
                help=f"Year-1 monthly ownership cost (loan + op costs) vs. "
                     f"your current all-in rent of {eur(current_rent_mo, 0)}/mo. "
                     f"A positive delta means buying costs more than renting "
                     f"today — but you're also building equity on the loan.")
        else:
            b1.metric(
                "Year-1 monthly cost",
                eur(cost_mo, 0),
                help="Loan payment + operating costs per month. No rent "
                     "income offsets this in live mode. Set your current "
                     "warm rent in the sidebar to compare directly.")
        b2.metric(
            "Cost per m² / year",
            eur(cost_per_m2_yr, 0),
            help="Year-1 loan + operating costs, divided by living space. "
                 "Compare to local Kaltmiete per m²/year — if ownership costs "
                 "a lot more, renting may be the better deal.")
    b3.metric(
        "Loan-to-value (LTV)",
        pct(ltv, 1),
        delta=("≤ 80% bank floor" if ltv <= 0.80 else f"+{pct(ltv - 0.80, 1)} over"),
        delta_color="normal" if ltv <= 0.80 else "inverse",
        help="Total debt ÷ purchase price. German banks typically cap at "
             "80% LTV for residential lending (90%+ with worse rates).")
    b4.metric(
        "Years to debt-free",
        f"{result.years_to_debt_free} yr",
        help="When all loan balances reach 0. Compare to your retirement "
             "horizon — debt shouldn't outlive income.")

    # ---------- Pass/fail narrative strip (from the shared helper) ----------
    if afford["failed"]:
        st.error("❌ " + "  \n❌ ".join(afford["failed"]))
    if afford["passed"]:
        st.success("✅ " + "  \n✅ ".join(afford["passed"]))

    # ---------- Next steps — branches on fail count ----------
    with st.expander("✅ What now?", expanded=True):
        if afford["n_fail"] <= 1:
            st.markdown(
                "Looks affordable. Next steps:\n"
                "1. Ask your bank for a **Finanzierungszusage** with these "
                "numbers.\n"
                "2. Verify the Bodenrichtwert on "
                "[BORIS NRW](https://www.boris.nrw.de/) (or your state's "
                "equivalent).\n"
                "3. Request the **Energieausweis** from the seller.\n\n"
                "*Not financial advice — confirm with a Steuerberater if you're "
                "planning to rent this out.*")
        else:
            st.markdown(
                "Some rules are stretched. Before pushing ahead:\n"
                "1. Try raising **Initial capital** or lowering **Purchase "
                "price** on the sidebar and watch the checks above update.\n"
                "2. Read each failed rule — the headline names the lever to "
                "adjust.\n"
                "3. If it still doesn't pencil out, consider waiting or "
                "looking at a cheaper market.\n\n"
                "*Not financial advice — verify with a Steuerberater or your "
                "bank.*")

    st.markdown("---")

    # ---------- Detail: property / purchase / financing / AfA ----------
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("### Property")
        prop = s.property
        st.write(f"**Built:** {prop.year_built} "
                  f"({2026 - prop.year_built} years old)")
        st.write(f"**Living space:** {prop.living_space_m2:.2f} m²")
        st.write(f"**Price per m²:** {eur(prop.purchase_price / prop.living_space_m2)}")
        st.write(f"**Type:** {prop.property_type}")
        if prop.year_last_major_renovation:
            st.write(f"**Last renovated:** {prop.year_last_major_renovation}")

        st.markdown("### Purchase costs")
        p = result.purchase
        df = pd.DataFrame([
            ("Purchase price", p.purchase_price),
            ("Property transfer tax (Grunderwerbsteuer, 6.5% NRW)", p.grunderwerbsteuer),
            ("Agent fee (Maklerprovision, ~3.57% buyer share)", p.maklerprovision),
            ("Notary + land registry (~2%)", p.notary_grundbuch),
            ("Initial renovation (capitalized, AfA)", p.renovation_capitalized),
            ("**Total**", p.total_cost),
        ], columns=["Item", "Amount (€)"])
        df["Amount (€)"] = df["Amount (€)"].apply(lambda x: eur(x))
        st.dataframe(df, hide_index=True, width="stretch")

        with st.expander("What are these fees?", expanded=False):
            st.markdown(
                "- **Grunderwerbsteuer** — one-time property-transfer tax. "
                "Varies by Bundesland; NRW is 6.5%. Goes to the state, "
                "not deductible.\n"
                "- **Maklerprovision** — estate-agent commission. Since 2020 "
                "the buyer covers ~half (~3.57% incl. VAT in NRW).\n"
                "- **Notar + Grundbuch** — notary and land-registry fees. "
                "Legally required for any property transfer; roughly 2% of "
                "price combined.\n"
                "- **Initial renovation** — major work in the first 3 years "
                "may be treated as *Herstellungskosten* (added to the AfA "
                "basis and depreciated) rather than immediately deductible "
                "*Erhaltungsaufwand* — the Anschaffungsnaher-Aufwand rule "
                "(§ 6 Abs. 1 Nr. 1a EStG).")

    with c2:
        st.markdown("### Financing")
        fin_df = pd.DataFrame([{
            "Loan": l.name,
            "Principal (€)": eur(l.principal),
            "Rate": pct(l.interest_rate, 2),
            "Monthly (€)": eur(l.monthly_payment),
            "Annual (€)": eur(l.monthly_payment * 12),
            "Cleared": _years_until_clear(result, l.name),
        } for l in s.financing.loans])
        st.dataframe(fin_df, hide_index=True, width="stretch")

        total_monthly = sum(l.monthly_payment for l in s.financing.loans)
        st.write(f"**Total debt:** {eur(total_debt)} "
                  f"({pct(total_debt / price)} of price)")
        st.write(f"**Total monthly payment:** {eur(total_monthly)}")
        st.write(f"**Initial capital:** {eur(initial_cap)}")
        st.write(f"**Years until all debt cleared:** "
                  f"**{result.years_to_debt_free}**")

        if s.mode == "rent" and result.afa_basis:
            st.markdown("### AfA (annual depreciation)")
            a = result.afa_basis
            st.write(f"**Building value:** {eur(a.building_value)}")
            st.write(f"**+ Capitalized fees:** {eur(a.capitalized_fees)}")
            st.write(f"**= AfA basis:** {eur(a.total_basis)}")
            st.write(f"**× Rate:** {pct(a.afa_rate, 2)} "
                      f"({a.useful_life_years}-year life — "
                      f"{'pre-1925 Altbau' if s.property.year_built < 1925 else 'post-1925'})")
            st.write(f"**= Annual AfA:** {eur(a.annual_afa)}")


def tab_compare(result_live, result_rent, s: Scenario):
    """Side-by-side live vs rent comparison."""
    st.markdown("## Buy vs Rent comparison")
    st.caption("Same property, both modes computed in parallel. Pick whichever pencils out.")

    if (s.live.current_monthly_rent_warm_eur or 0) == 0:
        st.warning(
            "⚠ **Live mode isn't being credited for avoided rent.** Set "
            "'Current rent you pay now (warm, €/mo)' in the 🛏 Live parameters "
            "sidebar — without it the red (live) line is artificially low."
        )

    # Cross-mode verdict: one sentence naming the 50-year winner + the month-1 winner
    final_live = float(result_live.cashflow["cumulative"].iloc[-1])
    final_rent = float(result_rent.cashflow["cumulative"].iloc[-1])
    yr1_burden_live = max(0, (result_live.cashflow["loan_payment"].iloc[0]
                              + result_live.cashflow["op_costs"].iloc[0]
                              - result_live.cashflow["rent_net"].iloc[0]) / 12)
    yr1_burden_rent = max(0, (result_rent.cashflow["loan_payment"].iloc[0]
                              + result_rent.cashflow["op_costs"].iloc[0]
                              - result_rent.cashflow["rent_net"].iloc[0]) / 12)
    if final_rent > final_live:
        long_winner, long_gap = "Rent it out", final_rent - final_live
        short_winner, short_gap = "Live in it", yr1_burden_rent - yr1_burden_live
    else:
        long_winner, long_gap = "Live in it", final_live - final_rent
        short_winner, short_gap = "Rent it out", yr1_burden_live - yr1_burden_rent
    st.info(
        f"Over 50 years, **{long_winner}** ends ahead by {eur(long_gap)}. "
        f"**{short_winner}** costs less in year 1 by {eur(abs(short_gap))} / month.")

    cf_live = result_live.cashflow
    cf_rent = result_rent.cashflow

    # Headline metrics
    cols = st.columns(2)
    with cols[0]:
        st.markdown("### 🛏 Live mode")
        _mode_summary_block(result_live, s)
    with cols[1]:
        st.markdown("### 🏘 Rent mode")
        _mode_summary_block(result_rent, s)

    st.markdown("---")
    st.markdown("### 50-year cumulative wealth change")
    chart_df = pd.DataFrame({
        "Year": cf_live.index,
        "Live": cf_live["cumulative"],
        "Rent": cf_rent["cumulative"],
    })
    st.caption("Red solid = live in it; blue dashed = rent it out.")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=chart_df["Year"], y=chart_df["Live"],
                              mode="lines", name="Live in it",
                              line=dict(color="#E15759", width=3, dash="solid")))
    fig.add_trace(go.Scatter(x=chart_df["Year"], y=chart_df["Rent"],
                              mode="lines", name="Rent it out",
                              line=dict(color="#4E79A7", width=3, dash="dash")))
    fig.add_hline(y=0, line_dash="dash", line_color="grey")
    fig.update_layout(height=400, hovermode="x unified",
                       xaxis_title="Year", yaxis_title="Cumulative wealth change (€)",
                       yaxis_tickformat=",.0f")
    st.plotly_chart(fig, width="stretch")
    st.caption("💡 Try raising the Horizon slider in Global assumptions — "
               "watch where the two lines cross over.")

    st.markdown("### Year-1 monthly cash flow")
    live_avoided = cf_live.get("avoided_rent", pd.Series([0.0])).iloc[0]
    rent_avoided = cf_rent.get("avoided_rent", pd.Series([0.0])).iloc[0]
    rows = [
        ("Loan payment",     cf_live["loan_payment"].iloc[0] / 12,  cf_rent["loan_payment"].iloc[0] / 12),
        ("Operating costs",  cf_live["op_costs"].iloc[0] / 12,      cf_rent["op_costs"].iloc[0] / 12),
        ("Tax",              cf_live["tax_owed"].iloc[0] / 12,      cf_rent["tax_owed"].iloc[0] / 12),
        ("Rent income",     -cf_live["rent_net"].iloc[0] / 12,     -cf_rent["rent_net"].iloc[0] / 12),
    ]
    if live_avoided > 0 or rent_avoided > 0:
        rows.append(("Avoided rent (imputed)",
                     -live_avoided / 12, -rent_avoided / 12))
    rows.append(("Net cash burden",
                 -cf_live["net_property"].iloc[0] / 12,
                 -cf_rent["net_property"].iloc[0] / 12))
    cmp_df = pd.DataFrame(rows, columns=["Item", "Live (€/mo)", "Rent (€/mo)"])
    cmp_df_display = cmp_df.copy()
    for col in ["Live (€/mo)", "Rent (€/mo)"]:
        cmp_df_display[col] = cmp_df_display[col].apply(lambda x: eur(x, 0))
    st.dataframe(cmp_df_display, hide_index=True, width="stretch")


def _mode_summary_block(result, s: Scenario):
    cf = result.cashflow
    yr1 = cf.iloc[0]
    final = cf["cumulative"].iloc[-1]
    monthly_burden = max(0, (yr1["loan_payment"] + yr1["op_costs"] - yr1["rent_net"]) / 12)
    st.metric("Year-1 monthly burden", eur(monthly_burden))
    st.metric("Total interest paid (50 yr)",
               eur(float(result.amort["total_interest"].sum())))
    st.metric("Total tax paid (50 yr)", eur(float(cf["tax_owed"].sum())))
    st.metric("Total capex (50 yr)", eur(float(cf["capex"].sum())))
    st.metric("Final cumulative wealth change", eur(final),
               delta_color="normal" if final > 0 else "inverse")


def tab_cashflow(result, s: Scenario):
    """50-year cashflow detail."""
    st.markdown(f"## Cash flow  :violet-background[{s.mode.upper()} mode]")
    cf = result.cashflow

    fig = go.Figure()
    fig.add_trace(go.Bar(x=cf.index, y=cf["rent_net"], name="Rent income",
                          marker_color="#59A14F"))
    if s.mode == "live" and "avoided_rent" in cf.columns and cf["avoided_rent"].sum() > 0:
        fig.add_trace(go.Bar(x=cf.index, y=cf["avoided_rent"],
                              name="Avoided rent (imputed)",
                              marker_color="#8CD17D"))
    fig.add_trace(go.Bar(x=cf.index, y=-cf["loan_payment"], name="Loan payment",
                          marker_color="#E15759"))
    fig.add_trace(go.Bar(x=cf.index, y=-cf["op_costs"], name="Operating costs",
                          marker_color="#F28E2B"))
    fig.add_trace(go.Bar(x=cf.index, y=-cf["capex"], name="Capex",
                          marker_color="#B07AA1"))
    if s.mode == "rent":
        fig.add_trace(go.Bar(x=cf.index, y=-cf["tax_owed"], name="Tax",
                              marker_color="#76B7B2"))
    fig.add_trace(go.Scatter(x=cf.index, y=cf["net_property"], mode="lines+markers",
                              name="Net property cashflow", line=dict(color="black", width=3)))
    fig.update_layout(barmode="relative", height=500, hovermode="x unified",
                       xaxis_title="Year", yaxis_title="€ per year",
                       yaxis_tickformat=",.0f")
    st.plotly_chart(fig, width="stretch")
    st.caption("Red / orange / purple / teal = money out; green = money in; "
               "black line = net per year. Where the black line crosses zero, "
               "rent income starts covering all costs.")

    st.markdown("### Cumulative position")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=cf.index, y=cf["cumulative"], fill="tozeroy",
                                name="Cumulative wealth change",
                                line=dict(color="#4E79A7", width=2)))
    fig2.add_hline(y=0, line_dash="dash", line_color="grey")
    fig2.update_layout(height=350, hovermode="x unified",
                        xaxis_title="Year", yaxis_title="Cumulative (€)",
                        yaxis_tickformat=",.0f")
    st.plotly_chart(fig2, width="stretch")
    st.caption("Total wealth change from this property. Positive = it pays "
               "back; negative = it costs more than it earns, cumulatively.")

    with st.expander("📊 Year-by-year table"):
        cols = ["calendar_year", "rent_net"]
        labels = ["Cal yr", "Rent net"]
        if s.mode == "live" and cf.get("avoided_rent", pd.Series([0])).sum() > 0:
            cols.append("avoided_rent")
            labels.append("Avoided rent")
        cols += ["loan_payment", "op_costs", "capex", "tax_owed",
                 "net_property", "cumulative"]
        labels += ["Loan", "Op costs", "Capex", "Tax",
                   "Net property", "Cumulative"]
        display = cf[cols].copy()
        display.columns = labels
        fmt = {"Cal yr": "{:.0f}"}
        for c in labels[1:]:
            fmt[c] = "€{:,.0f}"
        st.dataframe(display.style.format(fmt),
                      width="stretch", height=400)


def tab_costs(result, s: Scenario):
    """Operating cost breakdown."""
    st.markdown(f"## Operating costs (year 1)  :violet-background[{s.mode.upper()} mode]")
    st.caption(f"Showing all cost lines. **{s.mode.upper()} mode** uses only the lines flagged for that mode. Costs escalate by {pct(s.globals.cost_inflation_annual)} per year on the cash flow tab.")

    rows = []
    total_active = 0
    for cl in result.cost_lines:
        active = (s.mode == "live" and cl.in_live) or (s.mode == "rent" and cl.in_rent)
        if active:
            total_active += cl.annual_eur
        rows.append({
            "Item": cl.name,
            "Annual (€)": cl.annual_eur,
            "Monthly (€)": cl.annual_eur / 12,
            "Live": "✓" if cl.in_live else "—",
            "Rent": "✓" if cl.in_rent else "—",
            "Active": "✓" if active else "—",
            "Deductible (rent)": "✓" if (cl.in_rent and cl.deductible_in_rent) else "—",
            "Note": cl.note or "",
        })
    df = pd.DataFrame(rows)
    st.dataframe(df.style.format({
        "Annual (€)": "€{:,.0f}", "Monthly (€)": "€{:,.0f}",
    }), width="stretch", hide_index=True, height=500)

    st.markdown(f"**Total active in {s.mode.upper()} mode:** "
                 f"{eur(total_active)}/yr ({eur(total_active / 12)}/mo)")

    # Pie chart
    active_lines = [cl for cl in result.cost_lines
                    if (s.mode == "live" and cl.in_live) or (s.mode == "rent" and cl.in_rent)]
    if active_lines:
        pie = pd.DataFrame([{"Item": cl.name, "€/yr": cl.annual_eur} for cl in active_lines])
        fig = px.pie(pie, values="€/yr", names="Item", title="Cost composition")
        fig.update_traces(textposition="inside", textinfo="percent+label")
        st.plotly_chart(fig, width="stretch")


def tab_debt(result, s: Scenario):
    """Debt amortization detail."""
    st.markdown(f"## Debt amortization  :violet-background[{s.mode.upper()} mode]")
    st.caption(f"All loans projected over {s.globals.horizon_years} years. "
               "Annuitätendarlehen loans use a constant annuity (principal × (rate + Tilgung)). "
               "Non-annuity loans use their fixed monthly payment; adaptive loans "
               "absorb freed-up debt capacity once other loans clear.")

    am = result.amort

    # Balance chart
    bal_cols = [c for c in am.columns if c.endswith("_balance")]
    bal_df = am[bal_cols].copy()
    bal_df.columns = [c.replace("_balance", "") for c in bal_df.columns]
    bal_df["Total"] = bal_df.sum(axis=1)

    fig = go.Figure()
    for col in bal_df.columns:
        if col == "Total":
            fig.add_trace(go.Scatter(x=bal_df.index, y=bal_df[col], mode="lines",
                                      name=col, line=dict(color="black", width=3, dash="dash")))
        else:
            fig.add_trace(go.Scatter(x=bal_df.index, y=bal_df[col], mode="lines",
                                      name=col, stackgroup="loans"))
    fig.update_layout(height=400, hovermode="x unified",
                       xaxis_title="Year", yaxis_title="Outstanding balance (€)",
                       yaxis_tickformat=",.0f")
    st.plotly_chart(fig, width="stretch")
    st.caption("Each colour band is one loan. The black dashed line shows "
               "total debt — the steeper it falls, the faster you're "
               "deleveraging.")

    # Annual payment breakdown
    pay_cols = [c for c in am.columns if c.endswith("_payment") and c != "total_payment"]
    int_cols = [c for c in am.columns if c.endswith("_interest") and c != "total_interest"]
    fig2 = go.Figure()
    for col in pay_cols:
        loan_name = col.replace("_payment", "")
        fig2.add_trace(go.Bar(x=am.index, y=am[col], name=loan_name))
    fig2.update_layout(barmode="stack", height=350,
                        xaxis_title="Year", yaxis_title="Annual payment (€)",
                        yaxis_tickformat=",.0f", hovermode="x unified")
    st.plotly_chart(fig2, width="stretch")

    # Summary table
    st.markdown("### Per-loan summary")
    summary_rows = []
    for l in s.financing.loans:
        bal_col = f"{l.name}_balance"
        pay_col = f"{l.name}_payment"
        int_col = f"{l.name}_interest"
        total_paid = float(am[pay_col].sum())
        total_interest = float(am[int_col].sum())
        years = int((am[bal_col] > 0).sum())
        summary_rows.append({
            "Loan": l.name,
            "Principal (€)": eur(l.principal),
            "Rate": pct(l.interest_rate, 2),
            "Years to clear": years if years < s.globals.horizon_years else f"≥{years}",
            "Total payments (€)": eur(total_paid),
            "Total interest (€)": eur(total_interest),
            "Interest %": pct(total_interest / l.principal if l.principal else 0, 1),
        })
    st.dataframe(pd.DataFrame(summary_rows), hide_index=True, width="stretch")

    with st.expander("📊 Year-by-year amortization table"):
        st.dataframe(am.style.format("€{:,.0f}"),
                      width="stretch", height=400)


def tab_capex(result, s: Scenario):
    """Capex schedule."""
    st.markdown(f"## Capex schedule  :violet-background[{s.mode.upper()} mode]")

    auto_on = s.auto_schedule_capex
    n_auto = len(result.auto_capex) if auto_on else 0
    n_user = len(s.user_capex)

    st.caption(
        f"**{n_auto} auto-scheduled** + **{n_user} user-specified** items. "
        + ("Auto-scheduled items come from the German component lifecycle "
           "table (heating ~20 yr, roof ~40 yr, façade paint ~12 yr, …) "
           "projected forward from the last Kernsanierung (or year built). "
           "Turn them off with the **Auto-schedule component capex** "
           "checkbox in the 🔨 sidebar expander."
           if auto_on else
           "Auto-scheduling is **off** — only user-specified items below. "
           "Enable it in the 🔨 sidebar expander to project component "
           "replacements from the German lifecycle table."))

    items = result.all_capex
    if not items:
        st.info("No capex scheduled.")
        return

    # Tag each item as Auto vs User so the user can see where the schedule
    # is coming from. `result.auto_capex` is a ComponentSchedule list; the
    # matching CapexItems live at the front of `all_capex`.
    source_of = {}
    for it in result.auto_capex:
        source_of[(it.component_name, it.next_replacement_year)] = "Auto"
    for it in s.user_capex:
        source_of[(it.name, it.year_due)] = "User"

    rows = []
    for it in items:
        offset = it.year_due - s.globals.today_year + 1
        infl_factor = (1 + s.globals.cost_inflation_annual) ** (it.year_due - s.globals.today_year)
        rows.append({
            "Year": it.year_due,
            "Yr offset": offset,
            "Item": it.name,
            "Source": source_of.get((it.name, it.year_due), "Auto"),
            "Cost today (€)": it.cost_eur,
            "Cost inflated (€)": it.cost_eur * infl_factor,
            "Capitalized": "AfA" if it.is_capitalized else "Deductible",
        })
    df = pd.DataFrame(rows).sort_values("Year")

    # Timeline chart (Gantt-like) — colour by source so the user sees at a
    # glance what came from the auto-schedule vs their own entries.
    fig = px.scatter(df, x="Year", y="Item", size="Cost inflated (€)",
                      color="Source", hover_data=["Cost today (€)", "Capitalized"],
                      title="Capex timeline (bubble size = inflated cost)")
    fig.update_layout(height=max(400, 30 * len(df)))
    st.plotly_chart(fig, width="stretch")
    st.caption("Each bubble is a scheduled renovation; bigger = more "
               "expensive. Colour indicates **Source**: Auto = generated "
               "from the component lifecycle table; User = entered in the "
               "sidebar. Hover for cost and Capitalized flag (AfA vs. "
               "immediately deductible).")

    # Annual aggregate
    annual = df.groupby("Year")["Cost inflated (€)"].sum().reset_index()
    # Steady-state reserve — the flat annual amount you'd accrue if you
    # saved `cost / lifetime` every year for each auto-scheduled component.
    steady_reserve_yr = sum(
        (s.estimated_cost_eur / s.lifetime_years)
        for s in result.auto_capex
        if s.lifetime_years > 0
    )
    fig2 = go.Figure()
    fig2.add_trace(go.Bar(x=annual["Year"], y=annual["Cost inflated (€)"],
                           name="Actual lumpy spend",
                           marker_color="#4E79A7"))
    if steady_reserve_yr > 0:
        fig2.add_trace(go.Scatter(
            x=annual["Year"], y=[steady_reserve_yr] * len(annual),
            name=f"Smoothed reserve ({eur(steady_reserve_yr)}/yr)",
            mode="lines",
            line=dict(color="#E15759", width=2, dash="dash")))
    fig2.update_layout(height=320, yaxis_tickformat=",.0f",
                        title="Annual capex — lumpy actual vs. smoothed reserve",
                        hovermode="x unified",
                        xaxis_title="Year", yaxis_title="€ per year")
    st.plotly_chart(fig2, width="stretch")
    st.caption(
        f"**Blue bars** = what you actually pay in each year (components "
        f"cluster because multiple systems share the same installation age). "
        f"**Red dashed line** = {eur(steady_reserve_yr)}/yr — the flat annual "
        f"amount a prudent owner would accrue into a reserve (`Σ cost / "
        f"lifetime` across components). This is also roughly what the "
        f"**Maintenance reserve** line in Operating costs is supposed to "
        f"fund; for an apartment, the WEG's Erhaltungsrücklage pays the "
        f"Gemeinschaftseigentum portion out of Hausgeld.")

    # Detail table
    st.dataframe(df.style.format({
        "Cost today (€)": "€{:,.0f}", "Cost inflated (€)": "€{:,.0f}",
    }), hide_index=True, width="stretch")

    # Total
    total_today = df["Cost today (€)"].sum()
    total_infl = df["Cost inflated (€)"].sum()
    st.markdown(f"**Total capex over horizon:** {eur(total_today)} in today's €, "
                 f"{eur(total_infl)} inflated.")


def tab_tax(result, s: Scenario):
    """Tax detail (rent mode only)."""
    st.markdown(f"## Tax detail  :violet-background[{s.mode.upper()} mode]")
    if s.mode == "live":
        st.info("Tax model is only meaningful in rent mode. (Owner-occupied "
                 "homes don't generate taxable income or AfA deductions.)")
        return

    a = result.afa_basis
    st.markdown("### AfA basis")
    st.write(f"**Building share of price:** "
              f"{pct(a.building_value / s.property.purchase_price, 1)}")
    st.write(f"**Building value:** {eur(a.building_value)}")
    st.write(f"**Capitalized purchase fees:** {eur(a.capitalized_fees)} "
              f"(Grunderwerb + Makler + 80% of Notar, × building share)")
    st.write(f"**Capitalized renovation:** {eur(a.capitalized_renovation)}")
    st.write(f"**Total AfA basis:** {eur(a.total_basis)}")
    st.write(f"**AfA rate:** {pct(a.afa_rate, 2)} ({a.useful_life_years}-year useful life)")
    st.write(f"**Annual AfA deduction:** **{eur(a.annual_afa)}**")

    st.markdown("### Annual tax computation")
    tx = result.tax
    fig = go.Figure()
    fig.add_trace(go.Bar(x=tx.index, y=tx["rent_income"], name="Rent income (taxable basis)",
                          marker_color="#59A14F"))
    fig.add_trace(go.Bar(x=tx.index, y=-tx["deduct_interest"], name="Interest deduction",
                          marker_color="#E15759"))
    fig.add_trace(go.Bar(x=tx.index, y=-tx["deduct_costs"], name="Op costs deduction",
                          marker_color="#F28E2B"))
    fig.add_trace(go.Bar(x=tx.index, y=-tx["deduct_afa"], name="AfA deduction",
                          marker_color="#76B7B2"))
    fig.add_trace(go.Bar(x=tx.index, y=-tx["deduct_capex"], name="Capex deduction",
                          marker_color="#B07AA1"))
    fig.add_trace(go.Scatter(x=tx.index, y=tx["taxable_income"],
                              mode="lines+markers", name="Taxable income",
                              line=dict(color="black", width=3)))
    fig.update_layout(barmode="relative", height=400, hovermode="x unified",
                       xaxis_title="Year", yaxis_title="€",
                       yaxis_tickformat=",.0f")
    st.plotly_chart(fig, width="stretch")
    st.caption("Green = taxable rent income; other colours = deductions that "
               "shrink it. Black line = your taxable result after all deductions.")

    st.markdown(f"**Total tax over {s.globals.horizon_years} years:** "
                 f"{eur(float(tx['tax_owed'].sum()))}")
    st.markdown(f"**Marginal rate applied:** {pct(s.globals.marginal_tax_rate)}")
    st.markdown("Rental losses offset other income at your marginal rate "
                 "(Verlustverrechnung, § 10d EStG), so `tax_owed` is signed: "
                 "a **negative value means a refund** on your salary, typical "
                 "in early years when AfA + interest + costs exceed rent.")

    with st.expander("📊 Annual tax table"):
        st.dataframe(tx.style.format("€{:,.0f}"), width="stretch", height=400)


def tab_getting_started():
    """On-ramp: what the app does, how to drive it, what each sidebar section
    means, what can safely be left at defaults."""
    st.markdown("## Welcome")
    st.markdown(
        "This is a German property finance calculator. Put a scenario in, see "
        "**50 years of cash flow, taxes, debt amortization, and a live-vs-rent "
        "comparison**. It encodes the rules that make German property "
        "different (AfA, Petersche Formel, Annuitätendarlehen, "
        "Anschaffungsnaher Aufwand, Bodenrichtwert split) so you don't need "
        "to re-derive them in a spreadsheet."
    )

    st.info(
        "🔒 **Privacy** — everything runs in your browser session. No inputs, "
        "no uploads, and no downloads are logged or sent anywhere beyond the "
        "Streamlit process serving this page. The code contains no telemetry."
    )

    st.markdown("### 3-step walkthrough")
    st.markdown(
        "1. **Pick a scenario** from the 📂 Scenarios expander in the sidebar "
        "— Bonn-Poppelsdorf, Munich Neubau, Berlin Altbau, or Köln "
        "Einfamilienhaus. Or upload your own YAML.\n"
        "2. **Tweak inputs** in the sidebar. Every field updates the results "
        "instantly — no save button needed for what-if exploration. Hover "
        "the ❓ icon next to any field for an explanation.\n"
        "3. **Read the tabs** above: Summary for the headline, Live vs Rent "
        "for the big comparison, then Cash Flow / Debt / Tax / Capex for "
        "depth."
    )

    st.markdown("### Sidebar sections, in plain terms")

    with st.expander("🏘 Property — physical facts about the unit", expanded=False):
        st.markdown(
            "- **Purchase price**: what's on the contract.\n"
            "- **Living space / plot size**: Wohnfläche in m²; plot is your "
            "share of the WEG plot for an apartment, the full Grundstück for "
            "a house.\n"
            "- **Year built / last renovated**: drives AfA rate and capex "
            "scheduling. Leave year-last-renovated at 0 if nothing major "
            "happened.\n"
            "- **Bodenrichtwert (€/m²)**: land value per m² from "
            "[boris.nrw.de](https://www.boris.nrw.de/). **Can be left blank** — "
            "the engine then uses property-type defaults (apartment = 80% "
            "building share, house = 65%).\n"
            "- **Energy demand (kWh/m²/yr)**: from the Energieausweis. "
            "<100 good, 100-150 average, 150+ poor.\n"
            "- **Type / elevator / Denkmal**: apartment vs. house, lift flag, "
            "listed-building flag."
        )

    with st.expander("💰 Financing — initial capital and loans", expanded=False):
        st.markdown(
            "**Mental model:** you close the purchase with `initial_capital "
            "+ Σ annuity loans = price + fees`.\n\n"
            "- **Initial capital deployed** = your own money at closing "
            "(savings, gifts, Bauspar payouts). No repayment, no interest. "
            "This shrinks what the bank has to finance.\n"
            "- **Loans table** = third-party money you pay back over time. "
            "One row per tranche. Columns:\n"
            "  - *Annuity?* → German Annuitätendarlehen (constant monthly "
            "payment). Uncheck for fixed-payment loans (LBS Bausparverträge, "
            "family loans).\n"
            "  - *Adaptive?* → this loan absorbs freed-up debt capacity "
            "once the others clear. The *Monthly (€)* field then becomes the "
            "**minimum** payment; the engine lifts it up to the total "
            "monthly debt budget. Typical for low-priority family / "
            "0%-interest loans you want to retire faster.\n"
            "- **Family / Bauspar loans.** If the family cash arrives at "
            "closing, fold it into *Initial capital* and add a non-annuity "
            "row here to track the ongoing repayment — don't double-count.\n"
            "- **Total monthly debt budget** — only used when ≥ 1 loan is "
            "flagged Adaptive. Otherwise it's inert and hidden.\n"
            "- **Suggested Bank principal hint** in the sidebar is "
            "`total purchase cost − initial capital`. If your actual bank "
            "loan differs, one of the two numbers is probably off."
        )

    with st.expander("🏘 Rent parameters — rent-mode only", expanded=False):
        st.markdown(
            "Used **only** when the mode radio is set to *rent*. Safe to "
            "leave at defaults if you only care about living in the place.\n"
            "- **Monthly rent (Kaltmiete)**: expected net cold rent. Look up "
            "Mietspiegel or comparable listings for your postcode.\n"
            "- **Annual rent escalation**: 1.5-2.5% for regulated markets "
            "(Berlin, Munich, Hamburg Mietpreisbremse); up to 3% outside the "
            "cap. Long-run German CPI anchors around 2% (ECB target).\n"
            "- **Vacancy (months/year)**: risk discount for empty periods "
            "between tenants or during renovations. 0.15 (low-turnover city) "
            "to 1.0+ (problem asset). Engine multiplies rent by "
            "(12 − vacancy) / 12.\n"
            "- **Property manager**: check if you'll outsource tenant "
            "handling to a Hausverwaltung. 4-8% of gross rent is typical. "
            "Leave unchecked if you self-manage."
        )

    with st.expander("🛏 Live parameters — live-mode only", expanded=False):
        st.markdown(
            "Used **only** in live mode. Drives household heating / "
            "electricity consumption estimates.\n"
            "- **People in household**: adults + children.\n"
            "- **Large appliances**: count of fridges, freezers, washers, "
            "dryers, dishwashers, ovens. Proxy for electricity base load."
        )

    with st.expander("⚡ Operating costs — safe to leave at defaults", expanded=False):
        st.markdown(
            "Most fields have sensible German-market defaults (2025-2026). "
            "Only tune what you actually know.\n"
            "- **Gas / electricity €/kWh**: from your Energieversorger bill.\n"
            "- **Grundsteuer rate (% of price)**: typically 0.15-0.35% post-"
            "2025 reform.\n"
            "- **Hausgeld (€/mo, rent mode)**: monthly WEG fee covering "
            "common-area costs. Typical €2.50-4.50 per m². Set 0 for a "
            "freestanding house.\n"
            "- **Administration, Municipal charges, Building / liability "
            "insurance**: see the help icons next to each field for typical "
            "ranges."
        )

    with st.expander("🌍 Global assumptions — defaults are well-sourced", expanded=False):
        st.markdown(
            "- **Monthly household net income**: Netto take-home. Used only "
            "for the 30%-of-income affordability check.\n"
            "- **Other monthly savings**: savings unrelated to the property.\n"
            "- **Cost inflation**: **2% default** (ECB target, Destatis "
            "long-run). Bump to 3% if you think the 2022+ regime persists.\n"
            "- **Marginal tax rate**: your Grenzsteuersatz (§ 32a EStG). "
            "Roughly 30% around €35k single / €70k couple, 38% around €60k / "
            "€120k, 42% at the €68k single / €136k couple reitch-threshold.\n"
            "- **Horizon**: **50 years default** (matches German AfA useful "
            "life for 1925-2022 builds). Shorter misses post-debt-free "
            "years; longer compounds more model error."
        )

    with st.expander("🔨 User-specified renovations — optional", expanded=False):
        st.markdown(
            "Safe to leave empty. Auto-scheduled component capex (heating, "
            "roof, bathroom, …) is computed from year-built + component "
            "lifecycles regardless.\n"
            "Add a row here only if you have concrete information — e.g., "
            "'bathroom redo in 2027 for €18k, Erhaltungsaufwand (not "
            "capitalized)'. The Anschaffungsnaher-Aufwand check triggers "
            "automatically if such items in the first 3 years exceed 15% of "
            "the building value."
        )

    with st.expander("📖 Glossary of German terms (A–Z)", expanded=False):
        st.markdown(
            "| Term | Plain meaning |\n"
            "| --- | --- |\n"
            "| AfA *(Absetzung für Abnutzung)* | Linear depreciation of the "
            "building over 40 / 50 / 33⅓ years. Available only in rent mode. |\n"
            "| Annuitätendarlehen | Loan with a constant monthly payment; "
            "interest portion shrinks, principal portion grows. The typical "
            "German mortgage structure. |\n"
            "| Anschaffungsnaher Aufwand | Renovations in the first 3 years "
            "exceeding 15% of building value get reclassified from expense "
            "to capital spend (§ 6 Abs. 1 Nr. 1a EStG). |\n"
            "| Bausparvertrag (LBS) | Savings-plus-loan hybrid. Fixed monthly "
            "payment on both sides. |\n"
            "| Betriebskostenabrechnung | Annual reconciliation of utility "
            "costs between landlord and tenant. |\n"
            "| Bodenrichtwert | Official land value per m² in your area. "
            "Look up on BORIS NRW (or your state's equivalent). |\n"
            "| Denkmal | Listed building. Qualifies for special AfA (§ 7i "
            "EStG, not yet modelled here). |\n"
            "| Energieausweis | Legally required energy-efficiency "
            "certificate. Gives the kWh/m²/yr figure. |\n"
            "| Erhaltungsaufwand | Ordinary maintenance — immediately "
            "deductible in rent mode. |\n"
            "| Erhaltungsrücklage | Post-2020 legal name for the building's "
            "maintenance reserve (was *Instandhaltungsrücklage*). |\n"
            "| Finanzierungszusage | Written bank commitment to fund the "
            "loan at stated terms. Ask for this early. |\n"
            "| Gemeinschaftseigentum | Shared portions of a WEG building "
            "(roof, façade, stairs). Covered by Hausgeld. |\n"
            "| Grenzsteuersatz | Marginal income-tax rate — applies to each "
            "extra euro of income. |\n"
            "| Grundbuch | Land registry. Ownership and encumbrances are "
            "recorded here; updates cost ~0.5% of price. |\n"
            "| Grunderwerbsteuer | One-off property-transfer tax. 6.5% in "
            "NRW; 3.5–6.5% elsewhere. |\n"
            "| Grundsteuer | Annual property tax paid to the Kommune. "
            "Typically 0.15–0.35% of price post-2025 reform. |\n"
            "| Hausgeld | Monthly WEG fee for common-area costs, admin, "
            "shared insurance — for apartments only. |\n"
            "| Hausverwaltung | Property management company. 4–8% of gross "
            "rent typical. |\n"
            "| Herstellungskosten | Capital spend that adds to the AfA "
            "basis and is depreciated over the building's useful life. |\n"
            "| Kaltmiete | Net cold rent — rent only, no utilities. |\n"
            "| Kernsanierung | Full-gut renovation. Resets component-"
            "lifecycle clocks. |\n"
            "| Kommune | Municipality. Sets the Grundsteuer Hebesatz. |\n"
            "| Maklerprovision | Estate-agent commission. Since 2020 the "
            "buyer covers ~3.57% in most Bundesländer. |\n"
            "| Mietpreisbremse | Rent cap in tight markets — limits new "
            "leases to ~10% above local Mietspiegel. |\n"
            "| Mietspiegel | Official city rent-comparison table. |\n"
            "| Nebenkosten | Warm-side utilities (heating, water, etc.) on "
            "top of Kaltmiete. Nebenkosten + Kaltmiete = Warmmiete. |\n"
            "| Notar | Notary. German property transfers require a notarised "
            "deed; fees ~1.5% of price. |\n"
            "| Petersche Formel | 1984 formula for the maintenance reserve: "
            "`(build cost/m² × 1.5) / 80 × 0.7`. |\n"
            "| Sonderumlage | Special one-off WEG assessment when the reserve "
            "isn't enough. |\n"
            "| Steuerberater | Tax advisor. Required reading for anything "
            "sensitive to §7 or §6 EStG interpretation. |\n"
            "| Tilgung | Repayment rate on an annuity loan — the % of "
            "principal you pay down per year at the start. |\n"
            "| Warmmiete | All-in rent: Kaltmiete + Nebenkosten. |\n"
            "| WEG *(Wohnungseigentümergemeinschaft)* | Owners' association "
            "for an apartment building. |\n")

    st.markdown("### What to read after this")
    st.markdown(
        "- **📋 Summary** — the headline numbers: price, debt, AfA, "
        "year-1 burden on salary.\n"
        "- **⚖ Buy vs Rent** — the core comparison. 50-year wealth chart "
        "with both modes overlaid.\n"
        "- **🏦 Debt** — stacked balance chart; see how each loan amortizes.\n"
        "- **🧾 Tax** (rent mode only) — AfA, deductions, taxable income.\n"
        "- **📚 Methodology** — citations and the rules encoded in "
        "`immokalkul/rules_de.py`."
    )


def tab_methodology():
    st.markdown("## Methodology")
    st.markdown(
        "Jump to: "
        "[Key rules](#key-german-rules-applied) · "
        "[Component lifecycles](#component-lifecycles) · "
        "[NOT modelled](#what-this-tool-does-not-model) · "
        "[Citations](#citations)"
    )
    st.markdown("""
This tool computes German property finance for both **live** (owner-occupied) and **rent** (buy-to-let) modes from a single scenario.

### Key German rules applied

**AfA (Absetzung für Abnutzung)** — § 7 Abs. 4 EStG:
- Built before 1925: **2.5%/yr** over 40 years
- Built 1925–2022: 2%/yr over 50 years
- Built 2023+: 3%/yr over 33⅓ years
- Land value isn't depreciable; building share derived from Bodenrichtwert
- Capitalizable purchase fees added to AfA basis (Grunderwerbsteuer, Maklerprovision, ~80% of Notar)

**Anschaffungsnaher Aufwand** — § 6 Abs. 1 Nr. 1a EStG:
- Renovations within 3 years of purchase exceeding 15% of building value get reclassified as Herstellungskosten and depreciated via AfA instead of being immediately deductible

**Petersche Formel** for maintenance reserve:
- (Construction cost/m² × 1.5) / 80 years × 0.7 (WEG portion for apartments)
- Combined with II. BV age table (€7.10 / €9.00 / €11.50 per m²/yr based on building age) — model takes the higher of the two

**Bank loan** — German Annuitätendarlehen logic:
- Annual annuity = principal × (interest rate + initial repayment rate)
- Constant payment; principal portion grows over time as interest portion shrinks

**Component lifecycles** — based on paritätische Lebensdauertabelle (HEV/MV) and Sparkasse references:
- Heating: 20 yr; Roof: 40 yr; Façade paint: 12 yr; Windows: 30 yr; Bathroom: 28 yr; Electrical: 35 yr; Plumbing: 45 yr; etc.
- Costs from Baukosteninformationszentrum BKI Q4/2025

### What this tool does NOT model

- **Property value appreciation** — equity built through amortization is shown via cumulative cash flow, but no market price growth assumed. Add manually if relevant.
- **Loss carry-back limits** — the model applies full Verlustverrechnung (losses offset salary at the marginal rate), but real German rules have annual and cumulative caps (§ 10d EStG) for very large losses. For typical residential buy-to-let this approximation is fine.
- **Sonderumlagen** (WEG special assessments) — modeled implicitly through the maintenance reserve.
- **Denkmal-AfA** (§7i EStG) — flag exists in Property but special rules not yet implemented.
- **§7b Sonder-AfA** for new builds.

### Citations

All German constants live in `immokalkul/rules_de.py` with citations to source. Key links below; the [REFERENCES.md](https://github.com/nicofirst1/immokalkul/blob/main/REFERENCES.md) file in the repo has the full bibliography with a reliability ranking.

**Primary / official sources**
- [Finanzamt NRW — Abschreibung für Vermietungsobjekte](https://www.finanzamt.nrw.de/steuerinfos/privatpersonen/haus-und-grund/so-ermitteln-sie-die-abschreibung-fuer-ihr) — AfA rates (2.5% / 2% / 3%) and capitalizable fees
- [BORIS NRW](https://www.boris.nrw.de/) — official Bodenrichtwert for North Rhine-Westphalia
- [Wikipedia — Peterssche Formel](https://de.wikipedia.org/wiki/Peterssche_Formel) — canonical derivation of the maintenance-reserve formula
- [Gesetze im Internet — § 7 EStG](https://www.gesetze-im-internet.de/estg/__7.html) — depreciation rules
- [Gesetze im Internet — § 6 EStG](https://www.gesetze-im-internet.de/estg/__6.html) — Anschaffungsnaher Aufwand (§ 6 Abs. 1 Nr. 1a)
- [Gesetze im Internet — § 19 WEG](https://www.gesetze-im-internet.de/woeigg/__19.html) — Erhaltungsrücklage (post-WEG-Reform 2020)
- [Gesetze im Internet — § 28 II. BV](https://www.gesetze-im-internet.de/bv_2/__28.html) — age-based maintenance reserve table

**Reputable professional / institutional** — Rosepartner, Pandotax, Schiffer, Sparkasse, Wüstenrot, Interhyp, Hypofriend (see REFERENCES.md).

**Aggregators / content marketing** — Immowelt, Homeday, Techem, Effi, LPE, private Bodenrichtwert portals. Use only for cross-checking.

For anything affecting an actual tax filing, verify with a Steuerberater. For Bodenrichtwert, always use BORIS NRW directly — it's free and authoritative.
    """)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _years_until_clear(result, loan_name: str) -> str:
    col = f"{loan_name}_balance"
    if col not in result.amort.columns:
        return "—"
    yrs = int((result.amort[col] > 0).sum())
    if yrs >= len(result.amort):
        return f"≥{yrs} yr"
    return f"{yrs} yr"


# `compute_affordability(result, scenario)` lives in `immokalkul.affordability`
# so it can be unit-tested without importing Streamlit. See tests/.


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
def main():
    init_scenario()
    sidebar_inputs()

    s = st.session_state.scenario

    # Compute both modes (cheap; lets us show comparisons everywhere)
    s_live = deepcopy(s); s_live.mode = "live"
    s_rent = deepcopy(s); s_rent.mode = "rent"

    try:
        result_live = run(s_live)
        result_rent = run(s_rent)
    except Exception as e:
        import traceback
        traceback.print_exc()
        st.error(
            "Something went wrong computing this scenario. "
            "Try reloading the default scenario from the Scenarios expander "
            "in the sidebar.")
        st.caption(f"Internal detail: {type(e).__name__}: {e}")
        return

    result_current = result_live if s.mode == "live" else result_rent
    result_other = result_rent if s.mode == "live" else result_live

    afford = compute_affordability(result_current, s)
    render_header(result_current, result_other, s, afford)

    tabs = st.tabs([
        "📋 Summary",
        "🚀 New here?",
        "⚖ Buy vs Rent",
        "💸 Cash flow",
        "💡 Costs",
        "🏦 Debt",
        "🔨 Capex",
        "🧾 Tax",
        "📚 Methodology",
    ])
    with tabs[0]: tab_summary(result_current, s, afford)
    with tabs[1]: tab_getting_started()
    with tabs[2]: tab_compare(result_live, result_rent, s)
    with tabs[3]: tab_cashflow(result_current, s)
    with tabs[4]: tab_costs(result_current, s)
    with tabs[5]: tab_debt(result_current, s)
    with tabs[6]: tab_capex(result_current, s)
    with tabs[7]: tab_tax(result_current, s)
    with tabs[8]: tab_methodology()

    _render_footer()


def _render_footer():
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #6b7280; font-size: 0.85rem; "
        "padding: 0.5rem 0; line-height: 1.6;'>"
        "Made by <a href='http://nicolobrandizzi.com/' target='_blank' "
        "style='color: #4E79A7; text-decoration: none;'>Nicolo' Brandizzi</a>"
        "<br>"
        "Not financial advice — verify with a Steuerberater or your bank. "
        "See <a href='https://github.com/nicofirst1/immokalkul/blob/main/REFERENCES.md' "
        "target='_blank' style='color: #4E79A7; text-decoration: none;'>"
        "REFERENCES.md</a> for sources."
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
