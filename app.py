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
                Loan("Bank", 300000, 0.034, 1350, is_annuity=True),
            ],
            adaptive_mamma=False,
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
                help="Cash at closing INCLUDING LBS savings + Mamma proceeds.")
            s.financing.adaptive_mamma = st.checkbox(
                "Adaptive Mamma (accelerate after Bank/LBS clear)",
                s.financing.adaptive_mamma,
                help="If yes, freed-up debt-service capacity flows to Mamma.")
            if s.financing.adaptive_mamma:
                s.financing.debt_budget_monthly = st.number_input(
                    "Total monthly debt budget (€)",
                    value=float(s.financing.debt_budget_monthly), step=50.0, format="%.0f")

            st.markdown("**Loans** (edit principal/rate/payment in cells below)")
            loans_df = pd.DataFrame([{
                "Name": l.name,
                "Principal (€)": l.principal,
                "Rate": l.interest_rate,
                "Monthly (€)": l.monthly_payment,
                "Annuity?": l.is_annuity,
            } for l in s.financing.loans])
            edited = st.data_editor(
                loans_df, num_rows="dynamic", key="loans_editor",
                column_config={
                    "Rate": st.column_config.NumberColumn(format="%.4f", step=0.001),
                    "Principal (€)": st.column_config.NumberColumn(format="%.0f"),
                    "Monthly (€)": st.column_config.NumberColumn(format="%.2f"),
                    "Annuity?": st.column_config.CheckboxColumn(),
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
            s.rent.monthly_rent = st.number_input(
                "Monthly rent (Kaltmiete, €)",
                value=float(s.rent.monthly_rent), step=50.0, format="%.0f")
            s.rent.monthly_parking = st.number_input(
                "Monthly parking (€)",
                value=float(s.rent.monthly_parking), step=10.0, format="%.0f")
            s.rent.annual_rent_escalation = st.slider(
                "Annual rent escalation", 0.0, 0.05,
                value=float(s.rent.annual_rent_escalation), step=0.005, format="%.1f%%")
            s.rent.expected_vacancy_months_per_year = st.slider(
                "Vacancy (months/year)", 0.0, 3.0,
                value=float(s.rent.expected_vacancy_months_per_year), step=0.05)
            s.rent.has_property_manager = st.checkbox(
                "Use property manager?", s.rent.has_property_manager)
            if s.rent.has_property_manager:
                s.rent.property_manager_pct_of_rent = st.slider(
                    "Manager fee (% of rent)", 0.0, 0.10,
                    value=float(s.rent.property_manager_pct_of_rent), step=0.005, format="%.1f%%")

        # --- Live params ---
        with st.expander("🛏 Live parameters", expanded=(s.mode == "live")):
            s.live.people_in_household = int(st.number_input(
                "People in household", value=int(s.live.people_in_household),
                min_value=1, max_value=10, step=1))
            s.live.large_appliances = int(st.number_input(
                "Large appliances", value=int(s.live.large_appliances),
                min_value=0, max_value=20, step=1))

        # --- Costs ---
        with st.expander("⚡ Operating costs", expanded=False):
            c = s.costs
            c.gas_price_eur_per_kwh = st.number_input("Gas €/kWh",
                value=float(c.gas_price_eur_per_kwh), step=0.01, format="%.3f")
            c.electricity_price_eur_per_kwh = st.number_input("Electricity €/kWh",
                value=float(c.electricity_price_eur_per_kwh), step=0.01, format="%.3f")
            c.grundsteuer_rate_of_price = st.number_input("Grundsteuer rate (% of price)",
                value=float(c.grundsteuer_rate_of_price), step=0.0001, format="%.4f")
            c.hausgeld_monthly_for_rent = st.number_input("Hausgeld (€/mo, rent mode)",
                value=float(c.hausgeld_monthly_for_rent), step=10.0, format="%.0f")
            c.administration_monthly = st.number_input("Administration (€/mo)",
                value=float(c.administration_monthly), step=5.0, format="%.0f")
            c.municipal_charges_eur_per_m2_month = st.number_input("Municipal €/m²/mo",
                value=float(c.municipal_charges_eur_per_m2_month), step=0.05, format="%.2f")
            c.building_insurance_eur_per_m2_year = st.number_input("Building insurance €/m²/yr",
                value=float(c.building_insurance_eur_per_m2_year), step=0.5, format="%.1f")
            c.liability_insurance_annual = st.number_input("Liability insurance €/yr",
                value=float(c.liability_insurance_annual), step=10.0, format="%.0f")

        # --- Globals ---
        with st.expander("🌍 Global assumptions", expanded=False):
            g = s.globals
            g.monthly_household_income = st.number_input(
                "Monthly household net income (€)",
                value=float(g.monthly_household_income), step=100.0, format="%.0f")
            g.additional_monthly_savings = st.number_input(
                "Other monthly savings (€)",
                value=float(g.additional_monthly_savings), step=50.0, format="%.0f")
            g.cost_inflation_annual = st.slider(
                "Cost inflation (annual)", 0.0, 0.06,
                value=float(g.cost_inflation_annual), step=0.005, format="%.1f%%")
            g.marginal_tax_rate = st.slider(
                "Marginal tax rate (rent mode)", 0.20, 0.50,
                value=float(g.marginal_tax_rate), step=0.01, format="%.0f%%")
            g.horizon_years = int(st.slider("Horizon (years)",
                10, 60, value=int(g.horizon_years)))

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
    """High-level dashboard. Lists every key number with explanation."""
    st.markdown("## Summary")

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

        total_debt = sum(l.principal for l in s.financing.loans)
        total_monthly = sum(l.monthly_payment for l in s.financing.loans)
        st.write(f"**Total debt:** {eur(total_debt)} "
                  f"({pct(total_debt / s.property.purchase_price)} of price)")
        st.write(f"**Total monthly payment:** {eur(total_monthly)}")
        st.write(f"**Initial capital:** {eur(s.financing.initial_capital)}")
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

    st.markdown("---")
    st.markdown("### Affordability checks")
    yr1 = result.cashflow.iloc[0]
    income_mo = s.globals.monthly_household_income
    cost_mo = (yr1["loan_payment"] + yr1["op_costs"]) / 12
    rent_mo = yr1["rent_net"] / 12 if s.mode == "rent" else 0
    burden_mo = max(0, cost_mo - rent_mo)

    a, b, c = st.columns(3)
    a.metric("Monthly cost", eur(cost_mo, 0))
    b.metric("Monthly rent (net)", eur(rent_mo, 0))
    c.metric("Net burden on salary", eur(burden_mo, 0),
              delta=f"{pct(burden_mo / income_mo, 1)} of income",
              delta_color="inverse" if burden_mo / income_mo > 0.30 else "normal")

    if burden_mo / income_mo > 0.30:
        st.warning(f"⚠️ Year-1 burden is {pct(burden_mo / income_mo, 1)} of income, "
                    f"above the 30% rule of thumb.")
    elif s.mode == "rent" and rent_mo >= cost_mo:
        st.success("✅ Rent covers all year-1 costs.")
    else:
        st.info(f"Year-1 burden is {pct(burden_mo / income_mo, 1)} of income.")


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
               "Bank uses German Annuitätendarlehen logic (constant annuity = principal × (rate + Tilgung)). "
               "LBS and Mamma use fixed monthly payments.")

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
All German constants live in `immokalkul/rules_de.py` with citations to source. AfA rates from § 7 Abs. 4 EStG and Finanzamt NRW. Petersche Formel from Heinz Peters (1984). Bonn Bodenrichtwert range from BORIS NRW 2024.
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
        "📋 Summary",
        "⚖ Live vs Rent",
        "💸 Cash flow",
        "💡 Costs",
        "🏦 Debt",
        "🔨 Capex",
        "🧾 Tax",
        "📚 Methodology",
    ])
    with tabs[0]: tab_summary(result_current, s)
    with tabs[1]: tab_compare(result_live, result_rent, s)
    with tabs[2]: tab_cashflow(result_current, s)
    with tabs[3]: tab_costs(result_current, s)
    with tabs[4]: tab_debt(result_current, s)
    with tabs[5]: tab_capex(result_current, s)
    with tabs[6]: tab_tax(result_current, s)
    with tabs[7]: tab_methodology()


if __name__ == "__main__":
    main()
