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
                            rules_de)

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
        else:
            st.session_state.scenario = _make_blank_scenario()


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
        with st.expander("📂 Scenarios", expanded=False):
            available = sorted(DATA_DIR.glob("*.yaml")) if DATA_DIR.exists() else []
            if available:
                names = [f.stem for f in available]
                default_idx = next((i for i, f in enumerate(available)
                                     if f.name == DEFAULT_SCENARIO.name), 0)
                picked = st.selectbox("Load scenario", names, index=default_idx)
                if st.button("Load selected"):
                    st.session_state.scenario = load_scenario(DATA_DIR / f"{picked}.yaml")
                    st.rerun()

            uploaded = st.file_uploader("Upload YAML scenario", type=["yaml", "yml"])
            if uploaded:
                tmp_path = Path("/tmp") / uploaded.name
                tmp_path.write_bytes(uploaded.getvalue())
                st.session_state.scenario = load_scenario(tmp_path)
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
                          help="Live: you live in it (your costs only). "
                               "Rent: buy-to-let (rental income, taxes, vacancy).")

        # --- Property ---
        with st.expander("🏘 Property", expanded=True):
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
                lr = s.property.year_last_major_renovation
                s.property.year_last_major_renovation = int(st.number_input(
                    "Year last renovated (0 = never)",
                    value=int(lr) if lr else 0, min_value=0, max_value=2030, step=1)) or None
            with c2:
                s.property.plot_size_m2 = st.number_input(
                    "Plot size (m²)", value=float(s.property.plot_size_m2),
                    step=1.0, format="%.2f",
                    help="For an apartment, your share of the WEG plot. For a house, full plot.")
                s.property.energy_demand_kwh_per_m2_year = st.number_input(
                    "Energy demand (kWh/m²/yr)",
                    value=float(s.property.energy_demand_kwh_per_m2_year),
                    step=5.0, format="%.0f",
                    help="From the Energieausweis. <100 = good, 100-150 = average, 150+ = poor.")
                s.property.bodenrichtwert_eur_per_m2 = st.number_input(
                    "Bodenrichtwert (€/m²)",
                    value=float(s.property.bodenrichtwert_eur_per_m2 or 0),
                    step=10.0, format="%.0f",
                    help="Land value per m² from BORIS NRW. Used for AfA building/land split.") or None
                s.property.property_type = st.selectbox(
                    "Type", ["apartment", "house"],
                    index=0 if s.property.property_type == "apartment" else 1)
                s.property.has_elevator = st.checkbox("Has elevator", s.property.has_elevator)
                s.property.is_denkmal = st.checkbox(
                    "Listed building (Denkmal)", s.property.is_denkmal,
                    help="Special AfA rules apply (§7i EStG).")

        # --- Financing ---
        with st.expander("💰 Financing", expanded=True):
            s.financing.initial_capital = st.number_input(
                "Initial capital deployed (€)",
                value=float(s.financing.initial_capital), step=5000.0, format="%.0f",
                help="Total cash put down at closing — savings + any Bauspar "
                     "payout + family-loan proceeds. The residual is what the "
                     "bank must finance.")

            any_adaptive = any(l.is_adaptive for l in s.financing.loans)
            s.financing.debt_budget_monthly = st.number_input(
                "Total monthly debt budget (€)",
                value=float(s.financing.debt_budget_monthly),
                step=50.0, format="%.0f",
                help="Ceiling for total monthly debt service. Only used when "
                     "at least one loan is flagged Adaptive — freed-up "
                     "capacity (after non-adaptive loans clear) flows into "
                     "the adaptive ones, up to this ceiling."
                     + ("" if any_adaptive else
                        " No adaptive loan set, so this value is inert."))

            st.markdown("**Loans** — one row per tranche. Add / remove rows freely.")
            loans_df = pd.DataFrame([{
                "Name": l.name,
                "Principal (€)": l.principal,
                "Rate": l.interest_rate,
                "Monthly (€)": l.monthly_payment,
                "Annuity?": l.is_annuity,
                "Adaptive?": l.is_adaptive,
            } for l in s.financing.loans])
            edited = st.data_editor(
                loans_df, num_rows="dynamic", key="loans_editor",
                column_config={
                    "Name": st.column_config.TextColumn(
                        "Name",
                        help="Free-text label (e.g. Bank, LBS, Mamma). "
                             "Shown in charts and summary tables."),
                    "Principal (€)": st.column_config.NumberColumn(
                        format="%.0f",
                        help="Amount borrowed at closing."),
                    "Rate": st.column_config.NumberColumn(
                        format="%.4f", step=0.001,
                        help="Annual interest rate as a decimal "
                             "(e.g. 0.034 = 3.4%)."),
                    "Monthly (€)": st.column_config.NumberColumn(
                        format="%.2f",
                        help="Fixed monthly payment. For an Annuitätendarlehen "
                             "this is principal × (rate + Tilgung) / 12. "
                             "For an adaptive loan this is the MINIMUM — "
                             "the engine may lift it once other loans clear."),
                    "Annuity?": st.column_config.CheckboxColumn(
                        help="Check for German Annuitätendarlehen "
                             "(constant annual payment; interest shrinks, "
                             "principal grows). Uncheck for fixed-payment "
                             "loans like LBS Bausparverträge or family loans."),
                    "Adaptive?": st.column_config.CheckboxColumn(
                        help="If checked, this loan absorbs freed-up debt "
                             "capacity once other loans clear, up to the "
                             "Total monthly debt budget above. Typical for "
                             "low-priority loans (family / 0%-interest) that "
                             "you want to retire faster over time."),
                })
            # Write back
            new_loans = []
            for _, row in edited.iterrows():
                if pd.notna(row["Name"]) and row["Name"]:
                    new_loans.append(Loan(
                        name=str(row["Name"]),
                        principal=float(row["Principal (€)"] or 0),
                        interest_rate=float(row["Rate"] or 0),
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
        with st.expander("🏘 Rent parameters", expanded=(s.mode == "rent")):
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
                "Annual rent escalation", 0.0, 0.05,
                value=float(s.rent.annual_rent_escalation), step=0.005, format="%.1f%%",
                help="Assumed yearly rent growth. German rents are constrained "
                     "by Mietspiegel and Mietpreisbremse — 1.5-2.5% is typical "
                     "for regulated markets (Berlin, Munich, Hamburg), up to "
                     "3% in hot markets outside the cap. German long-run CPI "
                     "anchors around 2% (ECB target).")
            s.rent.expected_vacancy_months_per_year = st.slider(
                "Vacancy (months/year)", 0.0, 3.0,
                value=float(s.rent.expected_vacancy_months_per_year), step=0.05,
                help="Vacancy **risk discount** — the average number of months "
                     "per year the flat is empty between tenants or during "
                     "renovations. Realistic range: 0.15 (low-turnover, "
                     "high-demand city) to 1.0+ (rural, problem tenants). "
                     "The engine multiplies rent income by (12 − vacancy) / 12.")
            s.rent.has_property_manager = st.checkbox(
                "Use property manager?", s.rent.has_property_manager,
                help="Check if you'll outsource tenant handling / rent "
                     "collection / minor repairs to a Hausverwaltung. Typical "
                     "in buy-to-let across cities; waive it if you self-manage "
                     "a single unit you know well.")
            if s.rent.has_property_manager:
                s.rent.property_manager_pct_of_rent = st.slider(
                    "Manager fee (% of rent)", 0.0, 0.10,
                    value=float(s.rent.property_manager_pct_of_rent), step=0.005, format="%.1f%%",
                    help="Monthly fee as a share of gross rent. German market "
                         "range: 4-8% for a single unit, sometimes a flat "
                         "€25-40/month instead. Fully deductible in rent mode.")

        # --- Live params ---
        with st.expander("🛏 Live parameters", expanded=(s.mode == "live")):
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
                help="What you currently pay to rent, **all-inclusive**: "
                     "Warmmiete (Kaltmiete + Nebenkosten) + electricity + "
                     "internet + anything else. This is the opportunity cost "
                     "of buying: by owning you stop paying this rent, so the "
                     "Summary tab uses it to compare to your ownership cost. "
                     "Leave 0 if you already own or it's not relevant.")

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
            c.grundsteuer_rate_of_price = st.number_input("Grundsteuer rate (% of price)",
                value=float(c.grundsteuer_rate_of_price), step=0.0001, format="%.4f",
                help="Property tax as a share of purchase price. Since the "
                     "2025 Grundsteuer reform, the Bundesmodell roughly lands "
                     "between 0.15% and 0.35% of market value depending on "
                     "Bundesland + Hebesatz. 0.2% is a reasonable default.")
            c.hausgeld_monthly_for_rent = st.number_input("Hausgeld (€/mo, rent mode)",
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
                "Cost inflation (annual)", 0.0, 0.06,
                value=float(g.cost_inflation_annual), step=0.005, format="%.1f%%",
                help="Yearly escalation applied to operating costs and capex. "
                     "**Default 2%** = ECB price-stability target and German "
                     "long-run CPI anchor (Destatis 10-year average 2014-2024 "
                     "≈ 2.5% incl. 2022-2023 spike). Bump to 3% if you think "
                     "the 2022+ regime shift persists.")
            g.marginal_tax_rate = st.slider(
                "Marginal tax rate (rent mode)", 0.20, 0.50,
                value=float(g.marginal_tax_rate), step=0.01, format="%.0f%%",
                help="Your Grenzsteuersatz on rental income. Look up your "
                     "taxable income against the German Einkommensteuer "
                     "bracket table (§32a EStG): ~30% around €35k single / "
                     "€70k couple, ~38% around €60k single / €120k couple, "
                     "42% above €68k single / €136k couple (2025 values). "
                     "Includes Soli and church tax if applicable.")
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
                    "Cost (€)": st.column_config.NumberColumn(format="%.0f"),
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
def render_header(result_current, result_other, s: Scenario):
    """Top-of-page summary metrics. Always shows current mode + a comparison."""
    st.title(f"🏠 {s.property.name}")
    cols = st.columns([1, 1, 1, 1, 1])

    cf_cur = result_current.cashflow
    cf_oth = result_other.cashflow

    # Year-1 metrics
    yr1_loan = float(result_current.amort["total_payment"].iloc[0])
    yr1_costs = float(cf_cur["op_costs"].iloc[0])
    yr1_rent = float(cf_cur["rent_net"].iloc[0])
    yr1_burden_on_salary = max(0, yr1_loan + yr1_costs - yr1_rent)
    pct_of_income = yr1_burden_on_salary / 12 / s.globals.monthly_household_income

    with cols[0]:
        st.metric("Mode", s.mode.upper())
    with cols[1]:
        st.metric("Total purchase cost", eur(result_current.purchase.total_cost))
    with cols[2]:
        st.metric("Year-1 monthly burden on salary",
                   eur(yr1_burden_on_salary / 12),
                   delta=f"{pct(pct_of_income, 1)} of income",
                   delta_color="inverse" if pct_of_income > 0.30 else "normal")
    with cols[3]:
        st.metric("Years until debt-free", f"{result_current.years_to_debt_free} yr")
    with cols[4]:
        final = float(cf_cur["cumulative"].iloc[-1])
        st.metric(f"50yr cumulative ({s.mode})", eur(final),
                   delta_color="normal" if final > 0 else "inverse")


# -----------------------------------------------------------------------------
# Tabs
# -----------------------------------------------------------------------------
def tab_summary(result, s: Scenario):
    """High-level dashboard. Affordability + returns at the top, then detail."""
    st.markdown("## Summary")

    # ---------- Top: headline affordability & returns dashboard ----------
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
    initial_cap = s.financing.initial_capital
    funded = initial_cap + total_debt
    funding_gap = total_cost - funded

    loan_pct = loan_mo / income_mo if income_mo else 0
    burden_pct = burden_mo / income_mo if income_mo else 0
    down_pct = initial_cap / price if price else 0
    ltv = total_debt / price if price else 0
    price_to_income = price / income_yr if income_yr else 0

    annual_rent_net = yr1["rent_net"]
    annual_op_costs = yr1["op_costs"]
    gross_yield = annual_rent_net / price if (s.mode == "rent" and price) else None
    net_yield = (annual_rent_net - annual_op_costs) / price if (s.mode == "rent" and price) else None
    cost_per_m2_yr = (cost_mo * 12) / s.property.living_space_m2 if s.property.living_space_m2 else 0

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

    # ---------- Pass/fail narrative strip ----------
    checks = []
    checks.append((loan_pct <= 0.30,
                   f"Loan payment is {pct(loan_pct, 1)} of income",
                   f"Loan payment is {pct(loan_pct, 1)} of income — above the 30% rule"))
    checks.append((burden_pct <= 0.30,
                   f"Net burden is {pct(burden_pct, 1)} of income",
                   f"Net burden is {pct(burden_pct, 1)} of income — above the 30% rule"))
    checks.append((down_pct >= 0.20,
                   f"Down payment is {pct(down_pct, 1)} of price (≥ 20% floor)",
                   f"Down payment is only {pct(down_pct, 1)} of price — below the 20% floor"))
    checks.append((abs(funding_gap) < 1000,
                   f"Funding plan closes: capital + loans ≈ total cost ({eur(total_cost)})",
                   (f"Under-funded by {eur(funding_gap)} — increase a loan or capital"
                    if funding_gap > 0 else
                    f"Over-funded by {eur(-funding_gap)} — reduce a loan")))
    checks.append((ltv <= 0.80,
                   f"LTV is {pct(ltv, 1)} (≤ 80% bank floor)",
                   f"LTV is {pct(ltv, 1)} — above the typical 80% cap, expect worse rates"))
    if s.mode == "rent":
        checks.append((gross_yield >= 0.03,
                       f"Gross yield is {pct(gross_yield, 2)} (≥ 3% rule)",
                       f"Gross yield is only {pct(gross_yield, 2)} — below the 3% rule"))
        checks.append((rent_mo >= cost_mo,
                       f"Year-1 rent {eur(rent_mo)}/mo covers all costs ({eur(cost_mo)}/mo)",
                       f"Year-1 rent {eur(rent_mo)}/mo doesn't cover costs {eur(cost_mo)}/mo"))
    else:
        current_rent_mo = s.live.current_monthly_rent_warm_eur or 0
        if current_rent_mo > 0:
            checks.append((cost_mo <= current_rent_mo,
                           f"Ownership ({eur(cost_mo)}/mo) is cheaper than current rent ({eur(current_rent_mo)}/mo)",
                           f"Ownership ({eur(cost_mo)}/mo) costs more than current rent ({eur(current_rent_mo)}/mo) — you're paying for equity instead of a landlord"))

    passed = [msg_ok for ok, msg_ok, _ in checks if ok]
    failed = [msg_bad for ok, _, msg_bad in checks if not ok]

    if failed:
        st.error("❌ " + "  \n❌ ".join(failed))
    if passed:
        st.success("✅ " + "  \n✅ ".join(passed))

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
            ("Grunderwerbsteuer", p.grunderwerbsteuer),
            ("Maklerprovision", p.maklerprovision),
            ("Notary + Grundbuch", p.notary_grundbuch),
            ("Initial renovation", p.renovation_capitalized),
            ("**Total**", p.total_cost),
        ], columns=["Item", "Amount (€)"])
        df["Amount (€)"] = df["Amount (€)"].apply(lambda x: eur(x))
        st.dataframe(df, hide_index=True, width="stretch")

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
    st.markdown("## Live vs. Rent comparison")
    st.caption("Same property, both modes computed in parallel. Pick whichever pencils out.")

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
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=chart_df["Year"], y=chart_df["Live"],
                              mode="lines", name="Live", line=dict(color="#E15759", width=3)))
    fig.add_trace(go.Scatter(x=chart_df["Year"], y=chart_df["Rent"],
                              mode="lines", name="Rent", line=dict(color="#4E79A7", width=3)))
    fig.add_hline(y=0, line_dash="dash", line_color="grey")
    fig.update_layout(height=400, hovermode="x unified",
                       xaxis_title="Year", yaxis_title="Cumulative wealth change (€)",
                       yaxis_tickformat=",.0f")
    st.plotly_chart(fig, width="stretch")

    st.markdown("### Year-1 monthly cash flow")
    cmp_df = pd.DataFrame([
        ("Loan payment",     cf_live["loan_payment"].iloc[0] / 12,  cf_rent["loan_payment"].iloc[0] / 12),
        ("Operating costs",  cf_live["op_costs"].iloc[0] / 12,      cf_rent["op_costs"].iloc[0] / 12),
        ("Tax",              cf_live["tax_owed"].iloc[0] / 12,      cf_rent["tax_owed"].iloc[0] / 12),
        ("Rent income",     -cf_live["rent_net"].iloc[0] / 12,     -cf_rent["rent_net"].iloc[0] / 12),
        ("Net cash burden", -cf_live["net_property"].iloc[0] / 12, -cf_rent["net_property"].iloc[0] / 12),
    ], columns=["Item", "Live (€/mo)", "Rent (€/mo)"])
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
    st.markdown(f"## Cash flow — {s.mode.upper()} mode")
    cf = result.cashflow

    fig = go.Figure()
    fig.add_trace(go.Bar(x=cf.index, y=cf["rent_net"], name="Rent income",
                          marker_color="#59A14F"))
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

    with st.expander("📊 Year-by-year table"):
        display = cf[["calendar_year", "rent_net", "loan_payment", "op_costs",
                       "capex", "tax_owed", "net_property", "cumulative"]].copy()
        display.columns = ["Cal yr", "Rent net", "Loan", "Op costs",
                            "Capex", "Tax", "Net property", "Cumulative"]
        st.dataframe(display.style.format({
            "Cal yr": "{:.0f}",
            "Rent net": "€{:,.0f}", "Loan": "€{:,.0f}", "Op costs": "€{:,.0f}",
            "Capex": "€{:,.0f}", "Tax": "€{:,.0f}",
            "Net property": "€{:,.0f}", "Cumulative": "€{:,.0f}",
        }), width="stretch", height=400)


def tab_costs(result, s: Scenario):
    """Operating cost breakdown."""
    st.markdown("## Operating costs (year 1)")
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
    st.markdown("## Debt amortization")
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
    st.markdown("## Capex schedule")
    st.caption("Auto-scheduled major renovations from component lifecycle table, "
               "plus any user-specified capex from the sidebar.")

    items = result.all_capex
    if not items:
        st.info("No capex scheduled.")
        return

    rows = []
    for it in items:
        offset = it.year_due - s.globals.today_year + 1
        infl_factor = (1 + s.globals.cost_inflation_annual) ** (it.year_due - s.globals.today_year)
        rows.append({
            "Year": it.year_due,
            "Yr offset": offset,
            "Item": it.name,
            "Cost today (€)": it.cost_eur,
            "Cost inflated (€)": it.cost_eur * infl_factor,
            "Capitalized": "AfA" if it.is_capitalized else "Deductible",
        })
    df = pd.DataFrame(rows).sort_values("Year")

    # Timeline chart (Gantt-like)
    fig = px.scatter(df, x="Year", y="Item", size="Cost inflated (€)",
                      color="Capitalized", hover_data=["Cost today (€)"],
                      title="Capex timeline (bubble size = inflated cost)")
    fig.update_layout(height=max(400, 30 * len(df)))
    st.plotly_chart(fig, width="stretch")

    # Annual aggregate
    annual = df.groupby("Year")["Cost inflated (€)"].sum().reset_index()
    fig2 = px.bar(annual, x="Year", y="Cost inflated (€)",
                   title="Annual capex spending")
    fig2.update_layout(height=300, yaxis_tickformat=",.0f")
    st.plotly_chart(fig2, width="stretch")

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
    st.markdown("## Tax detail")
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

    st.markdown(f"**Total tax over {s.globals.horizon_years} years:** "
                 f"{eur(float(tx['tax_owed'].sum()))}")
    st.markdown(f"**Marginal rate applied:** {pct(s.globals.marginal_tax_rate)}")
    st.markdown("⚠️ Simplification: this floors annual tax at €0 even in loss years. "
                 "Real German rules let rental losses offset other income — "
                 "saving more tax in early years than this model shows.")

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
            "- **Initial capital deployed**: cash at closing, including any "
            "Bauspar payout and family-loan proceeds used up front.\n"
            "- **Total monthly debt budget**: only matters if at least one "
            "loan is flagged *Adaptive* (see below). Leave it inert "
            "otherwise.\n"
            "- **Loans table**: one row per tranche. For each row:\n"
            "  - *Annuity?* check for German Annuitätendarlehen (constant "
            "monthly payment; typical for bank loans). Uncheck for "
            "fixed-payment loans like LBS Bausparverträge or family loans.\n"
            "  - *Adaptive?* check if this loan should absorb freed-up debt "
            "capacity once the others clear (typical for low-priority family "
            "/ 0%-interest loans you want to retire faster over time). The "
            "*Monthly (€)* field then becomes the **minimum**; the engine "
            "lifts it up to the total monthly debt budget after other loans "
            "fall away.\n"
            "- The sidebar shows a **Suggested Bank principal** "
            "(= total purchase cost − initial capital). If your actual bank "
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

    st.markdown("### What to read after this")
    st.markdown(
        "- **📋 Summary** — the headline numbers: price, debt, AfA, "
        "year-1 burden on salary.\n"
        "- **⚖ Live vs Rent** — the core comparison. 50-year wealth chart "
        "with both modes overlaid.\n"
        "- **🏦 Debt** — stacked balance chart; see how each loan amortizes.\n"
        "- **🧾 Tax** (rent mode only) — AfA, deductions, taxable income.\n"
        "- **📚 Methodology** — citations and the rules encoded in "
        "`immokalkul/rules_de.py`."
    )


def tab_methodology():
    st.markdown("## Methodology")
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
- **Loss carryforward against other income** — German rules let rental losses reduce overall tax bill in early years; this model floors tax at €0.
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
        st.error(f"Engine error: {e}")
        st.exception(e)
        return

    result_current = result_live if s.mode == "live" else result_rent
    result_other = result_rent if s.mode == "live" else result_live

    render_header(result_current, result_other, s)

    tabs = st.tabs([
        "🚀 Start here",
        "📋 Summary",
        "⚖ Live vs Rent",
        "💸 Cash flow",
        "💡 Costs",
        "🏦 Debt",
        "🔨 Capex",
        "🧾 Tax",
        "📚 Methodology",
    ])
    with tabs[0]: tab_getting_started()
    with tabs[1]: tab_summary(result_current, s)
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
        "padding: 0.5rem 0;'>"
        "Made by <a href='http://nicolobrandizzi.com/' target='_blank' "
        "style='color: #4E79A7; text-decoration: none;'>Nicolo' Brandizzi</a>"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
