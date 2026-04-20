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

APP_VERSION = "1.7.4"


@st.cache_data(show_spinner=False)
def _scenario_label(yaml_path: str) -> str:
    """Polished property.name for selectbox display; falls back to stem."""
    try:
        return load_scenario(Path(yaml_path)).property.name
    except Exception:
        return Path(yaml_path).stem

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


# Widget keys include a generation suffix. Bumping widget_generation
# invalidates every keyed widget so Streamlit re-seeds them from the
# current scenario on next render. Without this, a widget's cached
# value silently overrides any programmatic write to its backing field
# (scenario load, reset, etc.) — see audit v1 [C1].
def wk(base: str) -> str:
    gen = st.session_state.get("widget_generation", 0)
    return f"{base}__g{gen}"


def _bump_widget_generation() -> None:
    st.session_state.widget_generation = (
        st.session_state.get("widget_generation", 0) + 1)


def afa_useful_life_label(year_built: int, useful_life_years: int) -> str:
    """Display useful life with the statute's literal fraction for 2023+
    builds. § 7 Abs. 4 EStG (post-JStG-2022) reads "33⅓ Jahre" — the engine
    stores 33 (integer), so the display layer reconstructs the fraction."""
    if year_built >= 2023:
        return "33⅓"
    return str(useful_life_years)


# -----------------------------------------------------------------------------
# Shared copy — single-sourced so Summary and Methodology can't drift
# -----------------------------------------------------------------------------
NOT_MODELLED_MD = """\
- **Property appreciation** — no market-price growth assumed. Equity is built purely through amortization.
- **Loss carryforward caps** — the model applies full Verlustverrechnung at the marginal rate, but real § 10d EStG rules have annual and cumulative caps for very large losses. Fine for typical residential buy-to-let.
- **Sonderumlagen** (WEG special assessments) — baked into the maintenance reserve rather than modelled separately.
- **Denkmal-AfA** (§ 7i / § 7h EStG, 9 %/yr in years 1–8 then 7 %/yr in years 9–12 on the qualifying portion) — the `is_denkmal` flag exists but the engine doesn't apply the elevated AfA. New-build **§ 7b Sonder-AfA** (extra 5 %/yr in years 1–5 on qualifying post-2023 residential builds) — also not implemented; new-build buyers see understated tax benefit.
- **Tax decomposition** — `marginal_tax_rate` is a single blended figure. Real tax = Einkommensteuer × (1 + Soli + Kirchensteuer); a user who enters only their Einkommensteuersatz understates effective rate by 1–3 pp.
- **Mietpreisbremse / Kappungsgrenze** — `annual_rent_escalation` is unconstrained. §§ 556d, 558 BGB cap real-world increases (max 10 % over 3 yr in regulated markets). Honour the cap manually if your unit qualifies.
"""

WALKTHROUGH_MD = """\
1. **Pick a scenario** from the 📂 Scenarios expander in the sidebar — Bonn-Poppelsdorf, Munich Neubau, Berlin Altbau, or Köln Einfamilienhaus. Or upload your own YAML.
2. **Tweak inputs** in the sidebar. Every field updates the results instantly — no save button needed for what-if exploration. Hover the ❓ icon next to any field for an explanation.
3. **Read the tabs** above: Summary for the headline, Live vs Rent for the big comparison, then Cash flow / Debt / Tax / Capex for depth.
"""

SCENARIO_DESCRIPTIONS = {
    "bonn_poppelsdorf":      "🏘 Apartment in a 1990s Altbau (rent-mode default).",
    "berlin_altbau":         "🏘 Pre-WWI Altbau apartment — high AfA basis, capex risk.",
    "munich_neubau":         "🏘 Post-2023 Neubau — newer 3% AfA rate, low capex.",
    "koeln_einfamilienhaus": "🏠 Freestanding house (live-mode default).",
}


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
    if "widget_generation" not in st.session_state:
        st.session_state.widget_generation = 0


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
                labels = {f.stem: _scenario_label(str(f)) for f in available}
                picked = st.selectbox(
                    "Load scenario", names, index=default_idx,
                    format_func=lambda k: labels.get(k, k),
                    key=wk("scenario_picker"))
                desc = SCENARIO_DESCRIPTIONS.get(picked, "")
                if desc:
                    st.caption(desc)
                st.caption("Together these four sample a typical German "
                           "buyer's choice space — switch between them to see "
                           "how Altbau vs Neubau changes AfA, and apartment "
                           "vs house changes Hausgeld and capex.")
                if st.button("Load selected"):
                    st.session_state.scenario = load_scenario(DATA_DIR / f"{picked}.yaml")
                    st.session_state.scenario_original = deepcopy(st.session_state.scenario)
                    st.session_state.scenario_source = picked
                    _bump_widget_generation()
                    st.rerun()

            uploaded = st.file_uploader(
                "Upload YAML scenario", type=["yaml", "yml"],
                key=wk("yaml_uploader"))
            if uploaded:
                tmp_path = Path("/tmp") / uploaded.name
                tmp_path.write_bytes(uploaded.getvalue())
                st.session_state.scenario = load_scenario(tmp_path)
                st.session_state.scenario_original = deepcopy(st.session_state.scenario)
                st.session_state.scenario_source = uploaded.name
                st.success(f"Loaded {uploaded.name}")
                _bump_widget_generation()
                st.rerun()

            # --- Build from a listing via LLM ---
            with st.expander("🤖 Build YAML from a listing via LLM",
                              expanded=False):
                st.caption(
                    "No YAML to hand? Paste a listing URL or Exposé below, "
                    "copy the generated prompt into ChatGPT / Claude / "
                    "Gemini, and it'll return a YAML you can upload above.")
                listing_ctx = st.text_area(
                    "Listing URL or Exposé text",
                    height=100,
                    placeholder=("https://www.immobilienscout24.de/expose/..."
                                  "  — or paste the full Exposé text"),
                    key=wk("llm_listing_context"))
                st.markdown(
                    "**How to use:** copy the prompt below (📋 icon, top-"
                    "right of the code block) → paste into your LLM → save "
                    "its YAML reply as a file → upload it above.")
                st.code(
                    _build_llm_prompt(listing_ctx.strip() or
                                       "(paste the listing URL or text here)"),
                    language="markdown")

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
                          key=wk("mode_radio"),
                          help="Live in it: you occupy it (your costs only). "
                               "Rent it out: **buy-to-let** — you buy the "
                               "property and rent it to a tenant "
                               "(Vermietung / Kapitalanlage). Rental income, "
                               "taxes and vacancy are modelled.")

        # --- Property ---
        with st.expander("🏘 Property", expanded=False):
            s.property.name = st.text_input(
                "Name", s.property.name, key=wk("property_name"))
            c1, c2 = st.columns(2)
            with c1:
                s.property.purchase_price = st.number_input(
                    "Purchase price (€)", value=float(s.property.purchase_price),
                    step=5000.0, format="%.0f",
                    key=wk("purchase_price"))
                s.property.living_space_m2 = st.number_input(
                    "Living space (m²)", value=float(s.property.living_space_m2),
                    step=1.0, format="%.2f",
                    key=wk("living_space_m2"))
                s.property.year_built = int(st.number_input(
                    "Year built", value=int(s.property.year_built),
                    min_value=1700, max_value=2030, step=1,
                    key=wk("year_built")))
                s.property.plot_size_m2 = st.number_input(
                    "Plot size (m²)", value=float(s.property.plot_size_m2),
                    step=1.0, format="%.2f",
                    key=wk("plot_size_m2"),
                    help="**WEG** = *Wohnungseigentümergemeinschaft*, the "
                         "owners' association every Eigentumswohnung belongs "
                         "to. For an apartment you enter your pro-rata share "
                         "of the shared plot (shown on the Teilungserklärung). "
                         "For a house, enter the full plot.")
            with c2:
                s.property.property_type = st.selectbox(
                    "Type", ["apartment", "house"],
                    index=0 if s.property.property_type == "apartment" else 1,
                    key=wk("property_type"))
                s.property.has_elevator = st.checkbox(
                    "Has elevator", s.property.has_elevator,
                    key=wk("has_elevator"),
                    help="Adds +€1/m²/yr to the II. BV maintenance reserve "
                         "(service contracts + eventual renewal). Only "
                         "applies when the II. BV table beats the Petersche "
                         "Formel — typically older buildings.")

            with st.expander("🔬 Tax-relevant details (can skip for first pass)", expanded=False):
                lr = s.property.year_last_major_renovation
                s.property.year_last_major_renovation = int(st.number_input(
                    "Year last renovated (0 = never)",
                    value=int(lr) if lr else 0, min_value=0, max_value=2030, step=1,
                    key=wk("year_last_renovation"),
                    help="The 4-digit calendar year of the last Kernsanierung "
                         "(e.g. **1995** if heating + bathroom + electrics "
                         "were redone in 1995). Resets the component "
                         "lifecycle clock from that year. Set **0** if no "
                         "major renovation has happened since the build "
                         "year.")) or None
                s.property.energy_demand_kwh_per_m2_year = st.number_input(
                    "Energy demand (kWh/m²/yr)",
                    value=float(s.property.energy_demand_kwh_per_m2_year),
                    step=5.0, format="%.0f",
                    key=wk("energy_demand"),
                    help="From the Energieausweis. German efficiency classes "
                         "(§ 16 GEG):\n"
                         "- **A+**: < 30\n"
                         "- **A**: 30–50\n"
                         "- **B**: 50–75\n"
                         "- **C**: 75–100\n"
                         "- **D**: 100–130\n"
                         "- **E**: 130–160\n"
                         "- **F**: 160–200\n"
                         "- **G**: 200–250\n"
                         "- **H**: > 250")
                s.property.bodenrichtwert_eur_per_m2 = st.number_input(
                    "Bodenrichtwert (€/m²)",
                    value=float(s.property.bodenrichtwert_eur_per_m2 or 0),
                    step=10.0, format="%.0f",
                    key=wk("bodenrichtwert"),
                    help="**Official land reference value (€/m²)** published "
                         "by the municipal Gutachterausschuss and refreshed "
                         "every 1–2 years. Used here to split purchase price "
                         "into land (not depreciable) and building "
                         "(AfA-eligible); also drives the Grundsteuer base "
                         "under the post-2025 Bundesmodell. Lookup: BORIS NRW "
                         "for NRW, BORIS.NI for Lower Saxony, BayernAtlas for "
                         "Bavaria, etc. — every Bundesland runs its own "
                         "portal. Leave 0 to use property-type defaults.") or None
                s.property.is_denkmal = st.checkbox(
                    "Listed building (Denkmal)", s.property.is_denkmal,
                    key=wk("is_denkmal"),
                    help="**Flag only — not yet consumed by the engine.** "
                         "Real Denkmal AfA (§ 7i / § 7h EStG): 9 %/yr in "
                         "years 1–8, then 7 %/yr in years 9–12 on the "
                         "qualifying portion. Not modelled here; consult a "
                         "Steuerberater for an accurate tax projection.")

        # --- Financing ---
        with st.expander("💰 Financing", expanded=False):
            with st.expander("❓ Initial capital vs. loans — what's the difference?",
                              expanded=False):
                st.markdown(
                    "**Initial capital** is *your own money* at closing — "
                    "savings, a gift, a Bauspar payout. *Closing* = the "
                    "notary signing day (**Beurkundungstermin**) when the "
                    "contract is executed and funds move. No repayment, no "
                    "interest.\n\n"
                    "**Loans** are money a third party fronts; you pay them "
                    "back over time.\n\n"
                    "**Closing identity:** \n"
                    "`price + fees = your own capital + Σ loan principals`. \n"
                    "Whatever is left once your own capital and the other "
                    "loans are subtracted from *price + fees* is the "
                    "residual the bank loan has to cover — that's the "
                    "*Suggested Bank principal* hint below.\n\n"
                    "**Family / Bauspar loans.** If a family loan's cash is "
                    "already inside *Initial capital* at closing, add the "
                    "loan as a **non-annuity** row below to track the "
                    "repayment only — don't double-count it at closing. "
                    "Flag it *Adaptive* if you want freed-up capacity to "
                    "flow into it once other loans clear.")
            s.financing.initial_capital = st.number_input(
                "Initial capital deployed (€)",
                value=float(s.financing.initial_capital), step=5000.0, format="%.0f",
                key=wk("initial_capital"),
                help="Your own money at **closing** (notary signing / "
                     "Beurkundungstermin) — savings, gifts, Bauspar "
                     "payouts. No repayment. Contrast with Loans (below) = "
                     "third-party money you repay over time.")

            any_adaptive = any(l.is_adaptive for l in s.financing.loans)
            if any_adaptive:
                s.financing.debt_budget_monthly = st.number_input(
                    "Monthly loan budget [adaptive] (€/mo, all loans)",
                    value=float(s.financing.debt_budget_monthly),
                    step=50.0, format="%.0f",
                    key=wk("debt_budget_monthly"),
                    help="**What does this number constrain?** The total "
                         "monthly payment across all loans flagged "
                         "`[adaptive]`. Covers loan principal + interest "
                         "only — NOT Hausgeld, insurance, property tax or "
                         "maintenance. When an `[adaptive]` loan is free "
                         "of peers, its payment is lifted up to this "
                         "ceiling.")

            s.financing.monthly_total_housing_budget_eur = st.number_input(
                "Monthly housing ceiling [total] (€/mo) — 0 = unset",
                value=float(s.financing.monthly_total_housing_budget_eur),
                step=50.0, format="%.0f", min_value=0.0,
                key=wk("housing_ceiling"),
                help="**What does this cap?** Total monthly housing spend "
                     "— loan payments **plus** operating costs (Hausgeld, "
                     "insurance, Grundsteuer, maintenance). \n\n"
                     "**How is this different from the `[adaptive]` "
                     "budget above?** The `[adaptive]` budget is an "
                     "*engine knob* — it drives how adaptive loans "
                     "scale and covers **loans only**. This ceiling is "
                     "an *affordability check* — it triggers a warning "
                     "on Summary when total housing spend exceeds it. "
                     "Set to **0** to disable the check.")

            with st.expander("🔧 Advanced: closing-fee rates", expanded=False):
                st.caption(
                    "Overrides for *Notar* + *Grundbuch*. Leave at the "
                    "defaults unless your closing statement shows a "
                    "different split. Rates apply as a fraction of "
                    "purchase price.")
                from immokalkul import rules_de as _rules_de_for_advanced
                notary_default = _rules_de_for_advanced.NOTARY_FEE * 100
                grundbuch_default = _rules_de_for_advanced.GRUNDBUCH_FEE * 100
                notary_cur = (s.financing.notary_pct * 100
                              if s.financing.notary_pct is not None
                              else notary_default)
                grundbuch_cur = (s.financing.grundbuch_pct * 100
                                  if s.financing.grundbuch_pct is not None
                                  else grundbuch_default)
                new_notary = st.number_input(
                    f"Notar rate (%) — default {notary_default:.2f}%",
                    value=float(notary_cur), step=0.05, format="%.2f",
                    min_value=0.0, max_value=5.0,
                    key=wk("notary_rate"),
                    help="Notary fees follow the GNotKG schedule. The "
                         "~1.5 % figure is a price-weighted average; "
                         "small properties skew higher, large ones "
                         "lower.")
                new_grundbuch = st.number_input(
                    f"Grundbuch rate (%) — default {grundbuch_default:.2f}%",
                    value=float(grundbuch_cur), step=0.05, format="%.2f",
                    min_value=0.0, max_value=3.0,
                    key=wk("grundbuch_rate"),
                    help="Land-registry fees for ownership transfer "
                         "(Auflassung) and any Grundschuld entry. "
                         "Typically 0.3 – 0.8 % depending on whether "
                         "the purchase is leveraged.")
                # Persist as override only if the user moved away from defaults.
                s.financing.notary_pct = (new_notary / 100
                                           if abs(new_notary - notary_default) > 1e-6
                                           else None)
                s.financing.grundbuch_pct = (new_grundbuch / 100
                                              if abs(new_grundbuch - grundbuch_default) > 1e-6
                                              else None)

            st.markdown("**Loans** — one row per tranche. Add / remove rows freely.")
            if st.button("↺ Reset loans to scenario defaults", key="reset_loans"):
                s.financing.loans = deepcopy(
                    st.session_state.scenario_original.financing.loans)
                _bump_widget_generation()
                st.rerun()
            loans_df = pd.DataFrame([{
                "Name": l.name,
                "Principal (€)": l.principal,
                "Rate (%)": l.interest_rate * 100,
                "Monthly (€)": l.monthly_payment,
                "Annuity?": l.is_annuity,
                "Adaptive?": l.is_adaptive,
            } for l in s.financing.loans])
            edited = st.data_editor(
                loans_df, num_rows="dynamic", key=wk("loans_editor"),
                column_config={
                    "Principal (€)": st.column_config.NumberColumn(format="%.0f", min_value=0),
                    "Rate (%)": st.column_config.NumberColumn(format="%.3f", step=0.1, min_value=0.0),
                    "Monthly (€)": st.column_config.NumberColumn(format="%.2f", min_value=0),
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
                    "capacity once other loans clear, up to the *Monthly "
                    "loan budget [adaptive]* ceiling above. Typical for "
                    "low-priority family / 0 %-interest loans you want to "
                    "retire faster.")
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
            from immokalkul import rules_de as _rules_de
            try:
                pc = compute_purchase_costs(
                    s.property,
                    notary_rate=(s.financing.notary_pct
                                 if s.financing.notary_pct is not None
                                 else _rules_de.NOTARY_FEE),
                    grundbuch_rate=(s.financing.grundbuch_pct
                                     if s.financing.grundbuch_pct is not None
                                     else _rules_de.GRUNDBUCH_FEE),
                )
                residual = pc.total_cost - s.financing.initial_capital
                st.caption(f"💡 Suggested Bank principal "
                           f"(total cost − initial capital): **{eur(residual)}**")
            except Exception:
                pass

        # --- Rent params ---
        with st.expander("🏘 Rent parameters", expanded=False):
            st.caption("These fields are **only used in rent mode** "
                       "(buy-to-let — you let the property to a tenant). "
                       "Live mode ignores them. Safe to leave at defaults if "
                       "you only care about living in the place.")
            st.caption("📍 Look up realistic rents: "
                       "[ImmoScout24](https://www.immobilienscout24.de/) · "
                       "[mietspiegeltabelle.de](https://www.mietspiegeltabelle.de/)")
            s.rent.monthly_rent = st.number_input(
                "Monthly rent (Kaltmiete, €)",
                value=float(s.rent.monthly_rent), step=50.0, format="%.0f",
                key=wk("monthly_rent"),
                help="Net cold rent you expect to charge (Kaltmiete, no utilities). "
                     "For a realistic number, look up Mietspiegel or comparable "
                     "listings on ImmoScout24 for your postcode.")
            s.rent.monthly_parking = st.number_input(
                "Monthly parking (€)",
                value=float(s.rent.monthly_parking), step=10.0, format="%.0f",
                key=wk("monthly_parking"),
                help="Separate rent for a parking spot / Tiefgarage, if any. "
                     "Leave 0 if parking isn't part of the lease.")
            s.rent.annual_rent_escalation = st.slider(
                "Annual rent escalation", 0.0, 5.0,
                value=float(s.rent.annual_rent_escalation) * 100,
                step=0.1, format="%.1f%%",
                key=wk("annual_rent_escalation"),
                help="Assumed yearly rent growth. German rents are capped by "
                     "Mietspiegel / Mietpreisbremse — 1.5-2.5% is typical.") / 100
            if s.rent.annual_rent_escalation * 3 > 0.10:
                st.caption(
                    "⚠ Implied 3-yr increase exceeds 10 % — over the "
                    "Kappungsgrenze (§ 558 BGB) for regulated markets. "
                    "Honour the cap manually if your unit qualifies for "
                    "Mietpreisbremse.")
            s.rent.expected_vacancy_months_per_year = float(st.slider(
                "Vacancy (months/year)", 0, 6,
                value=int(round(float(s.rent.expected_vacancy_months_per_year))),
                step=1,
                key=wk("vacancy_months"),
                help="Whole months per year the flat is empty between "
                     "tenants. 0–1 = hot city, 2–3 = average, 4+ implies "
                     "renovation gaps or persistent vacancy."))
            s.rent.has_property_manager = st.checkbox(
                "Use property manager?", s.rent.has_property_manager,
                key=wk("has_property_manager"),
                help="Check if you'll outsource tenant handling / rent "
                     "collection / minor repairs to a Hausverwaltung. Typical "
                     "in buy-to-let across cities; waive it if you self-manage "
                     "a single unit you know well.")
            if s.rent.has_property_manager:
                s.rent.property_manager_pct_of_rent = st.slider(
                    "Manager fee (% of rent)", 0.0, 10.0,
                    value=float(s.rent.property_manager_pct_of_rent) * 100,
                    step=0.1, format="%.1f%%",
                    key=wk("manager_fee_pct"),
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
                key=wk("people_in_household"),
                help="Drives heating and electricity consumption. Adults and "
                     "children count the same here — the model uses a per-head "
                     "kWh adjustment."))
            s.live.large_appliances = int(st.number_input(
                "Large appliances", value=int(s.live.large_appliances),
                min_value=0, max_value=20, step=1,
                key=wk("large_appliances"),
                help="Count of large electric appliances (fridge, freezer, "
                     "washer, dryer, dishwasher, oven). Proxy for electricity "
                     "base load."))
            s.live.current_monthly_rent_warm_eur = st.number_input(
                "Current rent you pay now (warm, €/mo)",
                value=float(s.live.current_monthly_rent_warm_eur),
                step=50.0, format="%.0f",
                key=wk("current_rent_warm"),
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
            with st.expander("⚡ Utilities", expanded=False):
                c.gas_price_eur_per_kwh = st.number_input("Gas €/kWh",
                    value=float(c.gas_price_eur_per_kwh), step=0.01, format="%.3f",
                    key=wk("gas_price"),
                    help="Retail gas price per kWh for heating. Typical 2024-2026 "
                         "German range: €0.10-0.14. Check your Energieversorger bill.")
                c.electricity_price_eur_per_kwh = st.number_input("Electricity €/kWh",
                    value=float(c.electricity_price_eur_per_kwh), step=0.01, format="%.3f",
                    key=wk("electricity_price"),
                    help="Retail electricity price per kWh. Typical 2025 German "
                         "Grundversorger rate: €0.32-0.40 (Ökostrom tariffs "
                         "€0.28-0.35). Only used in live mode for Nebenkosten.")
                c.municipal_charges_eur_per_m2_month = st.number_input("Municipal €/m²/mo",
                    value=float(c.municipal_charges_eur_per_m2_month), step=0.05, format="%.2f",
                    key=wk("municipal_charges"),
                    help="City-level charges: trash, water, sewage, street cleaning, "
                         "chimney sweep. Typical range: €0.40-0.80/m²/month "
                         "depending on Kommune.")
            with st.expander("🏛 Property tax & insurance", expanded=False):
                c.grundsteuer_land_rate = st.slider(
                    "Grundsteuer rate (% of land value)", 0.0, 1.0,
                    value=float(c.grundsteuer_land_rate) * 100,
                    step=0.01, format="%.2f%%",
                    key=wk("grundsteuer_rate"),
                    help="Post-2025 Bundesmodell: tax base is the "
                         "Grundstückswert (land value), not the whole price. "
                         "Engine uses Bodenrichtwert × plot when available. "
                         "0.20–0.50 % typical depending on Bundesland + "
                         "Hebesatz; 0.34 % is a safe default.") / 100
                c.building_insurance_eur_per_m2_year = st.number_input("Building insurance €/m²/yr",
                    value=float(c.building_insurance_eur_per_m2_year), step=0.5, format="%.1f",
                    key=wk("building_insurance"),
                    help="Wohngebäudeversicherung — covers fire, storm, water "
                         "damage to the building shell. Typical: €3-6 per m²/yr "
                         "depending on region and flood zone.")
                c.liability_insurance_annual = st.number_input("Liability insurance €/yr",
                    value=float(c.liability_insurance_annual), step=10.0, format="%.0f",
                    key=wk("liability_insurance"),
                    help="Haus- und Grundbesitzerhaftpflicht (owner's liability). "
                         "Typical: €80-200/yr. Sometimes bundled into private "
                         "liability insurance — leave 0 if already covered there.")
            with st.expander("🏘 WEG / management", expanded=False):
                c.hausgeld_monthly_for_rent = st.number_input("Building fee (Hausgeld) — €/mo, rent mode",
                    value=float(c.hausgeld_monthly_for_rent), step=10.0, format="%.0f",
                    key=wk("hausgeld_monthly"),
                    help="Monthly WEG fee for shared common areas. Typical: "
                         "€2.50–4.50 per m². Set 0 for a freestanding house.")
                c.hausgeld_reserve_share = st.slider(
                    "Hausgeld reserve share (Erhaltungsrücklage portion)",
                    0.0, 100.0,
                    value=float(c.hausgeld_reserve_share) * 100,
                    step=5.0, format="%.0f%%",
                    key=wk("hausgeld_reserve_share"),
                    help="Share of Hausgeld funding the Erhaltungsrücklage "
                         "(§ 19 WEG). Not deductible against rental income "
                         "until actually spent on repairs. The remainder is "
                         "the operating portion (Werbungskosten, deductible). "
                         "30–50 % typical; 40 % default.") / 100
                c.administration_monthly = st.number_input("Administration (€/mo)",
                    value=float(c.administration_monthly), step=5.0, format="%.0f",
                    key=wk("administration_monthly"),
                    help="Verwalterhonorar or self-landlord admin costs (accounting, "
                         "Steuerberater share). Typical: €25-40/month for a single "
                         "unit. Set 0 for a freestanding house you manage yourself.")

        # --- Globals ---
        with st.expander("🌍 Global assumptions", expanded=False):
            g = s.globals
            g.monthly_household_income = st.number_input(
                "Monthly household net income (€)",
                value=float(g.monthly_household_income), step=100.0, format="%.0f",
                key=wk("household_income"),
                help="**How much does this income figure actually drive?** "
                     "It feeds the **affordability ratios** only "
                     "(loan/income, net burden/income, price/annual "
                     "income). It is *not* added to any cashflow total — "
                     "so this is the 'can you afford this?' input, not a "
                     "'how rich will you be?' input.")
            g.additional_monthly_savings = st.number_input(
                "Other monthly savings (€)",
                value=float(g.additional_monthly_savings), step=50.0, format="%.0f",
                key=wk("additional_savings"),
                help="**Why is this separate from the property cash "
                     "flow?** Because it represents savings set aside "
                     "independently of the property — it feeds the "
                     "cumulative-wealth line (property vs total household "
                     "wealth) but does *not* affect the affordability "
                     "ratios. Think of it as the 'what if I also save on "
                     "the side?' input.")
            g.cost_inflation_annual = st.slider(
                "Cost inflation (annual)", 0.0, 6.0,
                value=float(g.cost_inflation_annual) * 100,
                step=0.1, format="%.1f%%",
                key=wk("cost_inflation"),
                help="Yearly escalation applied to operating costs and capex. "
                     "Default 2% = ECB target; bump to 3% if you assume the "
                     "post-2022 regime persists.") / 100
            g.marginal_tax_rate = st.slider(
                "Marginal tax rate (Grenzsteuersatz)", 10.0, 55.0,
                value=float(g.marginal_tax_rate) * 100,
                step=1.0, format="%.0f%%",
                key=wk("marginal_tax_rate"),
                help="Blended top tax rate. Roughly 30 % at €35k, 42 % above "
                     "€68k single. **Enter the effective rate** = "
                     "Einkommensteuer × (1 + Soli + Kirchensteuer): for a "
                     "42 % ESt + 5.5 % Soli + 9 % Kirche, the effective "
                     "marginal rate is ~48 %. The engine doesn't decompose; "
                     "a single blended number is enough.") / 100
            g.horizon_years = int(st.slider(
                "Horizon (years)", 10, 60, value=int(g.horizon_years),
                key=wk("horizon_years"),
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
            if st.button("↺ Reset capex to scenario defaults", key="reset_capex"):
                s.user_capex = deepcopy(
                    st.session_state.scenario_original.user_capex)
                _bump_widget_generation()
                st.rerun()
            capex_df = pd.DataFrame([{
                "Name": c.name, "Cost (€)": c.cost_eur,
                "Year due": c.year_due, "Capitalized?": c.is_capitalized,
            } for c in s.user_capex])
            if capex_df.empty:
                capex_df = pd.DataFrame([{
                    "Name": "", "Cost (€)": 0, "Year due": s.globals.today_year,
                    "Capitalized?": False}])
            edited_cx = st.data_editor(
                capex_df, num_rows="dynamic", key=wk("capex_editor"),
                column_config={
                    "Cost (€)": st.column_config.NumberColumn(format="%.0f", min_value=0),
                    "Year due": st.column_config.NumberColumn(format="%d", step=1,
                                                               min_value=int(s.globals.today_year)),
                    "Capitalized?": st.column_config.CheckboxColumn(),
                })
            new_cx = []
            incomplete_rows: list[str] = []
            for _, row in edited_cx.iterrows():
                name_ok = pd.notna(row["Name"]) and bool(row["Name"])
                cost_ok = pd.notna(row["Cost (€)"]) and float(row["Cost (€)"] or 0) > 0
                year_ok = pd.notna(row["Year due"])
                if name_ok and cost_ok and year_ok:
                    new_cx.append(CapexItem(
                        name=str(row["Name"]),
                        cost_eur=float(row["Cost (€)"]),
                        year_due=int(row["Year due"]),
                        is_capitalized=bool(row["Capitalized?"]),
                    ))
                elif name_ok and (not cost_ok or not year_ok):
                    missing = []
                    if not cost_ok: missing.append("cost")
                    if not year_ok: missing.append("year")
                    incomplete_rows.append(f"{row['Name']} (missing {', '.join(missing)})")
            if incomplete_rows:
                st.warning(
                    "Skipped incomplete capex rows: "
                    + "; ".join(incomplete_rows)
                    + ". Fill in cost **and** year to include them.")
            s.user_capex = new_cx
            s.auto_schedule_capex = st.checkbox(
                "Auto-schedule component capex (heating, roof, etc.)",
                s.auto_schedule_capex,
                key=wk("auto_schedule_capex"),
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
            f"📌 You're viewing the **{s.property.name}** sample scenario. "
            f"Edit any input on the left to try your own numbers — or pick a "
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
        f"{s.globals.horizon_years}-yr cumulative wealth",
        eur(final),
        delta_color="normal" if final > 0 else "inverse",
        help=(f"**Does this property pay back over {s.globals.horizon_years} "
              f"years?** Net {s.globals.horizon_years}-year change in "
              "wealth from owning it. Positive = pays back; negative = "
              "costs more than it earns. *The horizon is configurable "
              "— set it in Global assumptions in the sidebar (range "
              "10–60 years, default 50).*"))
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
    st.markdown(f"## Summary  :violet-background[{s.mode.upper()} mode]")

    if s.mode == "live" and (s.live.current_monthly_rent_warm_eur or 0) == 0:
        st.warning(
            "⚠ **Set 'Current rent you pay now (warm, €/mo)' in the "
            "🛏 Live parameters sidebar.** Without it, the cumulative wealth "
            "chart treats ownership as 100 % pure outflow and doesn't credit "
            "the rent you'd otherwise pay — so live mode looks artificially "
            "hundreds of thousands of euros worse than reality."
        )

    # ---------- Year-1 monthly: the "what do I pay every month?" view ----------
    loan_mo = afford["loan_mo"]
    opex_mo = afford["cost_mo"] - loan_mo
    yr1 = result.cashflow.iloc[0]
    tax_mo = float(yr1["tax_owed"]) / 12
    rent_income_mo = afford["rent_mo"]  # rent mode: non-zero; live mode: 0
    avoided_mo = (float(yr1.get("avoided_rent", 0.0)) / 12
                  if s.mode == "live" else 0.0)

    ownership_mo = loan_mo + opex_mo + max(0.0, tax_mo)
    tax_savings_mo = max(0.0, -tax_mo)  # rent-mode refund from Verlustverrechnung
    offsets_mo = rent_income_mo + avoided_mo + tax_savings_mo
    net_mo = ownership_mo - offsets_mo

    st.markdown("### Monthly cost (year 1)")
    m1, m2, m3 = st.columns(3)
    m1.metric(
        "Ownership cost / mo",
        eur(ownership_mo, 0),
        help=(
            f"Year-1 monthly cost of owning: loan {eur(loan_mo)} + "
            f"operating costs {eur(opex_mo)}" +
            (f" + tax {eur(max(0.0, tax_mo))}" if tax_mo > 0 else "") +
            "."))
    offset_delta = []
    if rent_income_mo > 0:
        offset_delta.append(f"{eur(rent_income_mo)} rent")
    if avoided_mo > 0:
        offset_delta.append(f"{eur(avoided_mo)} avoided rent")
    if tax_savings_mo > 0:
        offset_delta.append(f"{eur(tax_savings_mo)} tax refund")
    m2.metric(
        "Offsets / mo",
        eur(offsets_mo, 0),
        delta=" + ".join(offset_delta) if offset_delta else "none",
        delta_color="normal" if offsets_mo > 0 else "off",
        help="Monthly credits that reduce the ownership cost: rental "
             "income (rent mode), avoided rent (live mode when current "
             "warm rent is set), and tax refund from Verlustverrechnung "
             "in loss years (rent mode).")
    income_mo = s.globals.monthly_household_income
    m3.metric(
        "Net out of pocket / mo",
        eur(net_mo, 0),
        delta=f"{pct(net_mo / income_mo, 1)} of income" if income_mo else None,
        delta_color=("inverse" if net_mo > 0 and net_mo / income_mo > 0.30
                     else "normal"),
        help="**What actually leaves your wallet each month in year 1?** "
             "Ownership cost (loan + operating costs + tax owed) minus "
             "offsets (rent income, avoided rent, tax refund). Negative "
             "means the property pays for itself. **What's NOT in this "
             "number:** the rent you still pay as a tenant (in rent "
             "mode) — that only shows up in the *Net burden / income* "
             "affordability ratio below.")

    with st.expander("📋 Line-by-line monthly breakdown"):
        rows = [
            ("Loan payment", loan_mo, "out"),
            ("Operating costs", opex_mo, "out"),
        ]
        if tax_mo > 0:
            rows.append(("Tax owed (rental profit)", tax_mo, "out"))
        if tax_mo < 0:
            rows.append(("Tax refund (Verlustverrechnung)", -tax_mo, "in"))
        if rent_income_mo > 0:
            rows.append(("Rent income (net of vacancy)", rent_income_mo, "in"))
        if avoided_mo > 0:
            rows.append(("Avoided rent (imputed)", avoided_mo, "in"))
        rows.append(("Net out of pocket", net_mo, "net"))

        df_mo = pd.DataFrame([
            {"Item": name,
             "€ / month": ("− " + eur(amt, 0)) if direction == "out" and amt != 0
                          else eur(amt, 0),
             "Effect": "income" if direction == "in"
                       else "outflow" if direction == "out"
                       else "balance"}
            for name, amt, direction in rows
        ])

        def _style_monthly_row(row):
            if row["Effect"] == "outflow":
                return ["color: #c0392b"] * len(row)      # red
            if row["Effect"] == "income":
                return ["color: #27ae60"] * len(row)      # green
            return ["font-weight: bold; border-top: 1px solid #888"] * len(row)

        styler = df_mo.style.apply(_style_monthly_row, axis=1).hide(axis="index")
        st.dataframe(styler, width="stretch")

    # ---------- In-context on-ramp: collapsed walkthrough ----------
    with st.expander("🚀 New here? 2-minute walkthrough", expanded=False):
        st.markdown(WALKTHROUGH_MD
                    + "\nFull guided tour of every sidebar section is on the "
                      "**New here?** tab.")

    # ---------- Limitations — elevated for transparency ----------
    with st.expander("⚠ What this tool does NOT model", expanded=False):
        st.markdown(NOT_MODELLED_MD
                    + "\nFor anything affecting a tax filing, verify with a "
                      "Steuerberater.")

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
        help="**How strained is your salary by loan repayments alone?** "
             "Monthly loan payments ÷ net monthly income. Gross number, "
             "no offsets. German banks typically want this under 30–35 %.")
    a2.metric(
        "Net burden / income",
        pct(burden_pct, 1),
        delta=("within 30%" if burden_pct <= 0.30 else f"+{pct(burden_pct - 0.30, 1)} over"),
        delta_color="normal" if burden_pct <= 0.30 else "inverse",
        help="**And how strained once operating costs and offsets are "
             "counted?** \n\n"
             "`(loan + operating costs − rent income − avoided rent) ÷ "
             "income` — the true monthly drain on your salary after "
             "everything the property gives back.\n\n"
             "**Why can this be *smaller* than Loan / income?** Because "
             "the offsets *subtract*. In rent mode the rental income can "
             "more than cover operating costs, so burden < loan. In live "
             "mode the avoided rent (warm rent you'd otherwise pay — set "
             "it in Live parameters) offsets part of the loan. If there "
             "are no offsets, burden ≥ loan.")
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
        help="**How many years of net income does this property cost?** "
             "Purchase price ÷ annual household net income. 5–8× is the "
             "traditional safe range; 8–10× is stretched; 10×+ is "
             "typical only in top cities and implies long horizons.")

    if afford.get("loan_pct_warn"):
        loan_thr = afford["loan_pct_warn_threshold"]
        st.warning(
            f"**Loan / income is {pct(loan_pct, 1)}** — beyond the "
            f"{pct(loan_thr, 0)} level where German banks typically "
            "tighten lending standards or decline. Consider a larger "
            "down payment, a longer term, or a lower price.")
    if afford.get("burden_pct_warn"):
        burden_thr = afford["burden_pct_warn_threshold"]
        st.warning(
            f"**Net burden / income is {pct(burden_pct, 1)}** — even "
            f"after rent income and avoided rent, more than {pct(burden_thr, 0)} "
            "of salary goes to this property. That leaves little room "
            "for savings, vacancies, or rate resets.")
    if afford.get("housing_budget_set"):
        housing_mo = afford["total_housing_mo"]
        housing_cap = afford["housing_budget"]
        if afford.get("housing_budget_exceeded"):
            overage = housing_mo - housing_cap
            st.warning(
                f"**Total housing is {eur(housing_mo, 0)} / mo — "
                f"{eur(overage, 0)} over your {eur(housing_cap, 0)} "
                "ceiling.** That's loan payments plus operating costs "
                "(Hausgeld, insurance, Grundsteuer, maintenance). Either "
                "raise the ceiling, trim the scenario, or accept the "
                "overshoot knowingly.")
        else:
            headroom = housing_cap - housing_mo
            st.caption(
                f"Total housing: **{eur(housing_mo, 0)} / mo** · "
                f"ceiling {eur(housing_cap, 0)} · "
                f"headroom {eur(headroom, 0)}.")

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
    st.markdown("**Want next-step guidance?** Open the panel below.")
    with st.expander("✅ What now?", expanded=False):
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
            failed_md = "\n".join(f"- {f}" for f in afford["failed"])
            st.markdown(
                "Some rules are stretched. Specifically:\n"
                f"{failed_md}\n\n"
                "Before pushing ahead:\n"
                "1. Try raising **Initial capital** or lowering **Purchase "
                "price** on the sidebar and watch the checks above update.\n"
                "2. Read each failed rule — the headline names the lever to "
                "adjust.\n"
                "3. If it still doesn't pencil out, consider waiting or "
                "looking at a cheaper market.\n\n"
                "*Not financial advice — verify with a Steuerberater or your "
                "bank.*")

    st.markdown("---")
    st.markdown("## Scenario detail")
    st.caption(
        "Everything that went *into* the numbers above, grouped: "
        "**Property** (physical facts) and **Purchase costs** on the left; "
        "**Financing** and **AfA** (rent mode) on the right. Each section "
        "is a standalone card.")

    # ---------- Detail: property / purchase / financing / AfA ----------
    c1, c2 = st.columns(2)

    with c1:
        with st.container(border=True):
            st.markdown("### Property")
            prop = s.property
            prop_rows = [
                ("Built", f"{prop.year_built} ({2026 - prop.year_built} yr old)"),
                ("Living space", f"{prop.living_space_m2:.2f} m²"),
                ("Price per m²", eur(prop.purchase_price / prop.living_space_m2)),
                ("Type", prop.property_type.capitalize()),
            ]
            if prop.year_last_major_renovation:
                prop_rows.append(("Last renovated", str(prop.year_last_major_renovation)))
            prop_md = ["| Field | Value |", "| --- | --- |"]
            for k, v in prop_rows:
                prop_md.append(f"| {k} | {v} |")
            st.markdown("\n".join(prop_md))

        with st.container(border=True):
            st.markdown("### Purchase costs")
            p = result.purchase
            df = pd.DataFrame([
                ("Purchase price", p.purchase_price),
                ("Property transfer tax (Grunderwerbsteuer, 6.5% NRW)", p.grunderwerbsteuer),
                ("Agent fee (Maklerprovision, ~3.57% buyer share)", p.maklerprovision),
                ("Notary (Notar, ~1.5%)", p.notary_fee),
                ("Land registry (Grundbuch, ~0.5%)", p.grundbuch_fee),
                ("Initial renovation (capitalized, AfA)", p.renovation_capitalized),
                ("Total", p.total_cost),
            ], columns=["Item", "Amount (€)"])
            df["Amount (€)"] = df["Amount (€)"].apply(lambda x: eur(x))
            total_idx = len(df) - 1
            styler_pc = (df.style
                           .apply(lambda row: ["font-weight: bold; border-top: 1px solid #888"] * len(row)
                                               if row.name == total_idx else [""] * len(row),
                                  axis=1)
                           .hide(axis="index"))
            st.dataframe(styler_pc, width="stretch")

            with st.expander("What are these fees?", expanded=False):
                st.markdown(
                    "- **Grunderwerbsteuer** — one-time property-transfer "
                    "tax. Varies by Bundesland; NRW is 6.5%. Goes to the "
                    "state, not deductible.\n"
                    "- **Maklerprovision** — estate-agent commission. Since "
                    "2020 the buyer covers ~half (~3.57% incl. VAT in NRW).\n"
                    "- **Notar (notary)** — the notary is legally required "
                    "to authenticate the sale and register the Auflassung. "
                    "Fees follow the GNotKG schedule (≈ 1.5 % of price).\n"
                    "- **Grundbuch (land registry)** — fees charged by the "
                    "Grundbuchamt to record ownership transfer and any "
                    "Grundschuld. Typically ≈ 0.5 % of price. You can "
                    "override both rates in **Financing → Advanced** if your "
                    "closing statement differs.\n"
                    "- **Initial renovation** — major work in the first 3 "
                    "years may be treated as *Herstellungskosten* (added to "
                    "the AfA basis and depreciated) rather than immediately "
                    "deductible *Erhaltungsaufwand* — the "
                    "Anschaffungsnaher-Aufwand rule (§ 6 Abs. 1 Nr. 1a EStG).")

    with c2:
        with st.container(border=True):
            st.markdown("### Financing")
            fin_rows = [{
                "Loan": l.name,
                "Principal (€)": eur(l.principal),
                "Rate": pct(l.interest_rate, 2),
                "Monthly (€)": eur(l.monthly_payment),
                "Annual (€)": eur(l.monthly_payment * 12),
                "Cleared": _years_until_clear(result, l.name),
            } for l in s.financing.loans]
            total_monthly = sum(l.monthly_payment for l in s.financing.loans)
            fin_rows.append({
                "Loan": "Total",
                "Principal (€)": eur(total_debt),
                "Rate": "—",
                "Monthly (€)": eur(total_monthly),
                "Annual (€)": eur(total_monthly * 12),
                "Cleared": f"{result.years_to_debt_free} yr",
            })
            fin_df = pd.DataFrame(fin_rows)
            total_idx_f = len(fin_df) - 1
            styler_fin = (fin_df.style
                                .apply(lambda row: ["font-weight: bold; border-top: 1px solid #888"] * len(row)
                                                    if row.name == total_idx_f else [""] * len(row),
                                       axis=1)
                                .hide(axis="index"))
            st.dataframe(styler_fin, width="stretch")

            st.caption(
                f"**Debt load:** {eur(total_debt)} "
                f"({pct(total_debt / price)} of price) · "
                f"**Initial capital:** {eur(initial_cap)} · "
                f"**Years until all debt cleared:** {result.years_to_debt_free}")

        if s.mode == "rent" and result.afa_basis:
            with st.container(border=True):
                st.markdown("### AfA (annual depreciation)")
                a = result.afa_basis
                afa_md = ["| Step | Amount |", "| --- | ---: |"]
                afa_md.append(f"| Building value | {eur(a.building_value)} |")
                afa_md.append(f"| + Capitalized fees | {eur(a.capitalized_fees)} |")
                afa_md.append(f"| **= AfA basis** | **{eur(a.total_basis)}** |")
                useful = afa_useful_life_label(s.property.year_built, a.useful_life_years)
                cohort = 'pre-1925 Altbau' if s.property.year_built < 1925 else 'post-1925'
                afa_md.append(f"| × Rate | {pct(a.afa_rate, 2)} "
                               f"({useful}-year life — {cohort}) |")
                afa_md.append(f"| **= Annual AfA** | **{eur(a.annual_afa)}** |")
                st.markdown("\n".join(afa_md))


def tab_compare(result_live, result_rent, s: Scenario):
    """Side-by-side live vs rent comparison."""
    st.markdown("## Buy vs Rent comparison  :violet-background[BOTH MODES]")
    st.caption("Same property, both modes computed in parallel. Pick whichever pencils out.")

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

    st.markdown(f"---\n### {s.globals.horizon_years}-year cumulative wealth change")
    chart_df = pd.DataFrame({
        "Year": cf_live.index,
        "Live": cf_live["cumulative"],
        "Rent": cf_rent["cumulative"],
    })
    st.caption("Red solid = live in it; blue dashed = rent it out. "
               "Hover any line — the top-left value is the **Year**.")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=chart_df["Year"], y=chart_df["Live"],
                              mode="lines", name="Live in it",
                              line=dict(color="#E15759", width=3, dash="solid"),
                              hovertemplate="Live: €%{y:,.0f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=chart_df["Year"], y=chart_df["Rent"],
                              mode="lines", name="Rent it out",
                              line=dict(color="#4E79A7", width=3, dash="dash"),
                              hovertemplate="Rent: €%{y:,.0f}<extra></extra>"))
    fig.add_hline(y=0, line_dash="dash", line_color="grey")
    fig.update_layout(height=400, hovermode="x unified",
                       xaxis_title="Year", yaxis_title="Cumulative wealth change (€)",
                       yaxis_tickformat=",.0f")
    st.plotly_chart(fig, width="stretch")
    st.caption("💡 Try raising the Horizon slider in Global assumptions — "
               "watch where the two lines cross over.")

    st.markdown("### Year-1 monthly cash flow")
    st.caption("Where the year-1 monthly burden of each mode comes from. "
               "Loan + Op costs − Rent income (− Avoided rent, in live mode) "
               "= Net cash burden.")
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
    # Treat sub-euro values as zero so live-mode "rent income" doesn't show
    # up as "−€0" tinted green.
    def _fmt_or_dash(x):
        if abs(float(x)) < 0.5:
            return "—"
        return eur(float(x), 0)
    cmp_df_display = cmp_df.copy()
    for col in ["Live (€/mo)", "Rent (€/mo)"]:
        cmp_df_display[col] = cmp_df_display[col].apply(_fmt_or_dash)

    total_idx_cmp = len(cmp_df_display) - 1  # "Net cash burden" row
    value_cols = ["Live (€/mo)", "Rent (€/mo)"]
    col_positions = {c: cmp_df.columns.get_loc(c) for c in value_cols}

    def _style_cmp(row):
        styles = [""] * len(row)
        if row.name == total_idx_cmp:
            return ["font-weight: bold; border-top: 1px solid #888"] * len(row)
        for col, pos in col_positions.items():
            try:
                val = float(cmp_df.iloc[row.name][col])
            except (ValueError, TypeError):
                continue
            if abs(val) < 0.5:
                continue                       # leave neutral (dash)
            if val > 0:
                styles[pos] = "color: #c0392b" # outflow red
            else:
                styles[pos] = "color: #27ae60" # inflow / offset green
        return styles

    styler_cmp = cmp_df_display.style.apply(_style_cmp, axis=1).hide(axis="index")
    st.dataframe(styler_cmp, width="stretch")


def _mode_summary_block(result, s: Scenario):
    cf = result.cashflow
    yr1 = cf.iloc[0]
    final = cf["cumulative"].iloc[-1]
    monthly_burden = max(0, (yr1["loan_payment"] + yr1["op_costs"] - yr1["rent_net"]) / 12)
    st.metric("Year-1 monthly burden", eur(monthly_burden))
    st.metric("Total interest paid (50 yr)",
               eur(float(result.amort["total_interest"].sum())))
    st.metric("Total tax paid (50 yr)", eur(float(cf["tax_owed"].sum())))
    st.metric(f"Total capex ({s.globals.horizon_years} yr)",
               eur(float(cf["capex"].sum())),
               help="**How much renovation spend is baked into this "
                    "projection?** Sum of all scheduled + user-added "
                    "renovation costs across the "
                    f"{s.globals.horizon_years}-year horizon, in nominal "
                    "€ (inflation is already applied inside each year's "
                    "figure).")
    st.metric("Final cumulative wealth change", eur(final),
               delta_color="normal" if final > 0 else "inverse",
               help="**Are you richer or poorer after the full horizon?** "
                    "Net change in net worth = equity built + cumulative "
                    "rent income + tax effects − all cash outflows (loan, "
                    "operating, capex, tax). Positive = property pays "
                    "back; negative = it costs more than it earns over "
                    "the horizon.")


def tab_cashflow(result, s: Scenario):
    """50-year cashflow detail."""
    st.markdown(f"## Cash flow  :violet-background[{s.mode.upper()} mode]")
    st.caption("All flows are aggregated **at year-end** (Dec 31). A bank "
               "statement breaks them out monthly — sub-year timing "
               "differences are by design.")
    cf = result.cashflow

    fig = go.Figure()
    bar_ht = "%{fullData.name}: €%{y:,.0f}<extra></extra>"
    fig.add_trace(go.Bar(x=cf.index, y=cf["rent_net"], name="Rent income",
                          marker_color="#59A14F",
                          hovertemplate=bar_ht))
    if s.mode == "live" and "avoided_rent" in cf.columns and cf["avoided_rent"].sum() > 0:
        fig.add_trace(go.Bar(x=cf.index, y=cf["avoided_rent"],
                              name="Avoided rent (imputed)",
                              marker_color="#8CD17D",
                              hovertemplate=bar_ht))
    fig.add_trace(go.Bar(x=cf.index, y=-cf["loan_payment"], name="Loan payment",
                          marker_color="#E15759",
                          hovertemplate=bar_ht))
    fig.add_trace(go.Bar(x=cf.index, y=-cf["op_costs"], name="Operating costs",
                          marker_color="#F28E2B",
                          hovertemplate=bar_ht))
    fig.add_trace(go.Bar(x=cf.index, y=-cf["capex"], name="Capex",
                          marker_color="#B07AA1",
                          hovertemplate=bar_ht))
    if s.mode == "rent":
        fig.add_trace(go.Bar(x=cf.index, y=-cf["tax_owed"], name="Tax",
                              marker_color="#76B7B2",
                              hovertemplate=bar_ht))
    fig.add_trace(go.Scatter(x=cf.index, y=cf["net_property"], mode="lines+markers",
                              name="Net property cashflow",
                              line=dict(color="black", width=3),
                              hovertemplate=bar_ht))
    fig.update_layout(barmode="relative", height=500, hovermode="x unified",
                       xaxis_title="Year", yaxis_title="€ per year",
                       yaxis_tickformat=",.0f")
    st.plotly_chart(fig, width="stretch")
    st.caption("Red / orange / purple / teal = money out; green = money in; "
               "black line = net per year. Where the black line crosses zero, "
               "rent income starts covering all costs.")
    st.caption("💡 Raise *Annual rent escalation* in the sidebar's **Rent "
               "parameters** expander by 1 % — watch the green bars compound "
               "and the black net line pull above zero earlier.")

    st.markdown("### Cumulative position")
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=cf.index, y=cf["cumulative"], fill="tozeroy",
                                name="Cumulative wealth change",
                                line=dict(color="#4E79A7", width=2),
                                hovertemplate="Cumulative: €%{y:,.0f}<extra></extra>"))
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

        inflow_cols = {"Rent net", "Avoided rent"}
        outflow_cols = {"Loan", "Op costs", "Capex"}
        signed_cols = {"Tax", "Net property", "Cumulative"}
        RED = "color: #c0392b"
        GREEN = "color: #27ae60"

        def _style_cashflow(col):
            name = col.name
            if name in inflow_cols:
                return [GREEN] * len(col)
            if name in outflow_cols:
                return [RED] * len(col)
            if name in signed_cols:
                # positive (cost/outflow) → red, negative (refund/inflow) → green
                return [RED if v > 0 else GREEN if v < 0 else "" for v in col]
            return [""] * len(col)

        styled = (display.style.format(fmt)
                               .apply(_style_cashflow, axis=0))
        st.dataframe(styled, width="stretch", height=400)
        st.markdown(
            "**Column legend**\n\n"
            "- **Cal yr** — calendar year.\n"
            "- **Rent net** — rent income after vacancy (rent mode only).\n"
            "- **Avoided rent** — warm rent you would otherwise pay (live mode only).\n"
            "- **Loan** — principal + interest paid that year.\n"
            "- **Op costs** — Hausgeld + insurance + maintenance + property tax.\n"
            "- **Capex** — scheduled + user renovations.\n"
            "- **Tax** — income tax effect. "
            "**Negative = refund** (Verlustverrechnung: Werbungskosten + "
            "AfA + interest > rent, so the loss offsets other income at "
            "your marginal rate).\n"
            "- **Net property** — the year's net cashflow.\n"
            "- **Cumulative** — running total so far.\n\n"
            "Green = inflow / positive effect, red = outflow / cost."
        )


def tab_costs(result, s: Scenario):
    """Operating cost breakdown."""
    st.markdown(f"## Operating costs (year 1)  :violet-background[{s.mode.upper()} mode]")
    st.caption(f"Showing all cost lines. **{s.mode.upper()} mode** uses only the lines flagged for that mode. Costs escalate by {pct(s.globals.cost_inflation_annual)} per year on the cash flow tab.")

    with st.expander("ℹ How Hausgeld is split — [operating] vs [reserve]",
                      expanded=False):
        st.markdown(
            "The monthly **Hausgeld** that every Eigentumswohnung pays to "
            "its `[WEG]` (*Wohnungseigentümergemeinschaft* — the owners' "
            "association) is split by the Verwalter into:\n\n"
            "- **`[operating]` (Umlagen)** — running shared costs "
            "(heating, water, cleaning, Hausmeister, Verwalter fee, "
            "common-area electricity). On the tax side, deductible as "
            "Werbungskosten on payment (accrual) basis.\n\n"
            "- **`[reserve]` (Erhaltungsrücklage, § 19 WEG)** — savings "
            "pot for future major works (roof, façade, lift). Per "
            "*Trennungstheorie* the paid-in portion is **not** "
            "deductible — only the amount the `[WEG]` actually spends in "
            "a given year is.\n\n"
            "The *Hausgeld reserve share* slider in the sidebar "
            "(%) controls the split (default 40 %).")

    # Pie chart (moved above the table — shows the big picture first).
    active_lines = [cl for cl in result.cost_lines
                    if (s.mode == "live" and cl.in_live) or (s.mode == "rent" and cl.in_rent)]
    total_active = sum(cl.annual_eur for cl in active_lines)
    if active_lines:
        st.markdown("### Cost composition")
        pie = pd.DataFrame([{"Item": cl.name, "€/yr": cl.annual_eur} for cl in active_lines])
        fig = px.pie(pie, values="€/yr", names="Item")
        fig.update_traces(
            textposition="outside", textinfo="percent+label",
            hovertemplate="%{label}<br>€%{value:,.0f} / yr (%{percent})<extra></extra>",
        )
        fig.update_layout(height=600, font=dict(size=13),
                           showlegend=True,
                           uniformtext=dict(minsize=10, mode="hide"),
                           margin=dict(l=80, r=80, t=20, b=40))
        st.plotly_chart(fig, width="stretch")
        st.caption("The biggest slice is your single best target if you want "
                   "to lower running costs — Hausgeld and Grundsteuer "
                   "typically dominate for apartments. Labels for tiny "
                   "slices are hidden; see the legend for small items.")

    st.metric(
        f"Total active in {s.mode.upper()} mode",
        f"{eur(total_active)} / yr",
        delta=f"{eur(total_active / 12)} / mo",
        delta_color="off",
    )

    # Full line-by-line table
    st.markdown("### All cost lines")
    NOTE_PREVIEW_CHARS = 90
    md_lines = [
        "| Item | Annual (€) | Monthly (€) | Live | Rent | Active | Deductible (rent) | Note |",
        "| --- | ---: | ---: | :---: | :---: | :---: | :---: | --- |",
    ]
    for cl in result.cost_lines:
        active = (s.mode == "live" and cl.in_live) or (s.mode == "rent" and cl.in_rent)
        raw_note = (cl.note or "").replace("|", "\\|").replace("\n", " ")
        if len(raw_note) > NOTE_PREVIEW_CHARS:
            preview = raw_note[:NOTE_PREVIEW_CHARS].rstrip() + "…"
            note_cell = (
                f"<details><summary>{preview}</summary>{raw_note}</details>"
            )
        else:
            note_cell = raw_note
        md_lines.append(
            f"| {cl.name} "
            f"| {eur(cl.annual_eur)} "
            f"| {eur(cl.annual_eur / 12)} "
            f"| {'✓' if cl.in_live else '—'} "
            f"| {'✓' if cl.in_rent else '—'} "
            f"| {'✓' if active else '—'} "
            f"| {'✓' if (cl.in_rent and cl.deductible_in_rent) else '—'} "
            f"| {note_cell} |"
        )
    st.markdown("\n".join(md_lines), unsafe_allow_html=True)
    st.caption(
        "Column legend — "
        "**Live / Rent** = whether the line is modelled in that mode. "
        "**Active** = whether it is summed into *this* mode's total above "
        "(✓ = current mode, — = reference only). "
        "**Deductible (rent)** = counts as Werbungskosten against rental "
        "income; only relevant in rent mode. "
        "**Note** — long notes collapse to a preview; click ▸ to expand.")


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
    st.caption("💡 Toggle a loan's **Adaptive?** flag in the loans editor — "
               "watch the black total-debt line bend after the first loan "
               "clears.")

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
    st.caption("Each colour band is one loan's annual payment. When a loan "
               "clears, its band drops out — the remaining loans take the "
               "freed capacity if any are flagged Adaptive.")

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
    st.dataframe(
        pd.DataFrame(summary_rows), hide_index=True, width="stretch",
        column_config={
            "Principal (€)": st.column_config.TextColumn(
                "Principal (€)",
                help="Amount borrowed at closing."),
            "Rate": st.column_config.TextColumn(
                "Rate",
                help="Annual interest rate."),
            "Years to clear": st.column_config.TextColumn(
                "Years to clear",
                help="Year in which the balance reaches 0 within the "
                     "horizon. ≥N means the loan is still outstanding at "
                     "the end of the projection."),
            "Total payments (€)": st.column_config.TextColumn(
                "Total payments (€)",
                help="Principal + interest paid across the horizon "
                     "(not present-valued)."),
            "Total interest (€)": st.column_config.TextColumn(
                "Total interest (€)",
                help="Cumulative interest portion over the horizon — the "
                     "true cost of the loan on top of principal."),
            "Interest %": st.column_config.TextColumn(
                "Interest %",
                help="Total interest ÷ original principal. Useful for "
                     "comparing Gesamtkosten across loans with different "
                     "rates and durations."),
        })

    with st.expander("📊 Year-by-year amortization table"):
        st.dataframe(am.style.format("€{:,.0f}"),
                      width="stretch", height=400)
        st.caption(
            "**Columns** — `*_balance`: outstanding principal at end of "
            "year. `*_payment`: principal + interest paid that year. "
            "`*_interest`: interest portion only. Principal portion = "
            "`*_payment` − `*_interest`. Totals aggregate across all "
            "loans.")


def tab_capex(result, s: Scenario):
    """Capex schedule."""
    st.markdown(f"## Capex schedule  :violet-background[{s.mode.upper()} mode]")

    auto_on = s.auto_schedule_capex
    n_auto = len(result.auto_capex) if auto_on else 0
    n_user = len(s.user_capex)

    st.caption(f"**{n_auto} auto-scheduled** + **{n_user} user-specified** items.")
    st.caption(
        "Auto-scheduled items come from the German component lifecycle "
        "table (heating ~20 yr, roof ~40 yr, façade paint ~12 yr, …) "
        "projected forward from the last Kernsanierung (or year built). "
        "Turn them off with the **Auto-schedule component capex** "
        "checkbox in the 🔨 sidebar expander."
        if auto_on else
        "Auto-scheduling is **off** — only user-specified items below. "
        "Enable it in the 🔨 sidebar expander to project component "
        "replacements from the German lifecycle table.")
    st.caption(
        "ℹ️ **Capex is identical in live and rent modes** — the physical "
        "work on roof / heating / windows happens regardless of who "
        "lives there. What changes between modes is the **tax treatment** "
        "(in rent mode, capex is either immediately deductible — "
        "Erhaltungsaufwand — or capitalized into AfA as Herstellungsaufwand; "
        "in live mode nothing is deductible).")

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
    st.markdown("### Capex timeline")
    st.caption("Bubble size = inflated cost in the year due.")
    fig = px.scatter(df, x="Year", y="Item", size="Cost inflated (€)",
                      color="Source",
                      hover_data={
                          "Year": True,
                          "Item": True,
                          "Source": True,
                          "Cost today (€)": ":,.0f",
                          "Cost inflated (€)": ":,.0f",
                          "Capitalized": True,
                      })
    fig.update_layout(height=max(420, 32 * len(df)),
                       font=dict(size=13),
                       margin=dict(l=10, r=10, t=10, b=10))
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
    st.markdown("### Annual capex — lumpy actual vs. smoothed reserve")
    fig2.update_layout(height=340, yaxis_tickformat=",.0f",
                        hovermode="x unified",
                        font=dict(size=13),
                        xaxis_title="Year", yaxis_title="€ per year",
                        margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig2, width="stretch")
    st.caption(
        f"**Blue bars** = lumpy actual spend. **Red dashed line** = "
        f"{eur(steady_reserve_yr)}/yr — the steady reserve a prudent owner "
        f"would accrue (`Σ cost / lifetime`).")
    st.caption(
        "💡 In a WEG, this steady amount is what the **Erhaltungsrücklage** "
        "is for; it's funded out of your **Hausgeld** for the "
        "Gemeinschaftseigentum portion.")

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
    afa_rate_label = (f"{pct(a.afa_rate, 2)} "
                       f"({afa_useful_life_label(s.property.year_built, a.useful_life_years)}"
                       "-year useful life)")
    afa_rows = [
        ("Building share of price",
         pct(a.building_value / s.property.purchase_price, 1),
         "Share of the purchase price attributed to the building "
         "(AfA-eligible); the rest is land (not depreciable). Driven by "
         "Bodenrichtwert × plot when set, else property-type defaults "
         "(apartment 80 %, house 65 %)."),
        ("Building value", eur(a.building_value),
         "Purchase price × building share. The capital portion that can "
         "be written off as AfA."),
        ("Capitalized purchase fees", eur(a.capitalized_fees),
         "Grunderwerbsteuer + Maklerprovision + 80 % of Notar & Grundbuch, "
         "scaled by the building share. Added to the AfA basis."),
        ("Capitalized renovation", eur(a.capitalized_renovation),
         "User-specified renovations marked as Capitalized "
         "(Herstellungskosten) plus any Anschaffungsnaher Aufwand "
         "reclassified from first-3-year spend."),
        ("**Total AfA basis**", f"**{eur(a.total_basis)}**",
         "Sum of the three lines above. The denominator for annual AfA."),
        ("AfA rate", afa_rate_label,
         "2 % for 1925-2022 builds (50-yr life); 2.5 % for pre-1925 Altbau "
         "(40 yr); 3 % for post-2023 Neubau (33⅓ yr) under § 7 Abs. 4 EStG."),
        ("**Annual AfA deduction**", f"**{eur(a.annual_afa)}**",
         "Total basis × rate. The yearly amount subtracted from taxable "
         "rental income."),
    ]
    md = ["| Component | Value | What it means |",
           "| --- | ---: | --- |"]
    for comp, val, explainer in afa_rows:
        explainer_clean = explainer.replace("|", "\\|")
        md.append(f"| {comp} | {val} | {explainer_clean} |")
    st.markdown("\n".join(md))

    if s.globals.horizon_years > a.useful_life_years:
        st.info(
            f"**AfA stops at year {a.useful_life_years}** — the statutory "
            f"useful life for this build cohort (§ 7 Abs. 4 EStG). From "
            f"year {a.useful_life_years + 1} onward the depreciation "
            f"shield is exhausted, so taxable rental income rises and "
            f"tax owed jumps. This is the correct legal treatment, not a "
            f"model glitch.")

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
    # Actual tax owed = taxable × marginal rate. Drawn as a second line so
    # users immediately see it move when they drag the marginal-rate slider.
    fig.add_trace(go.Scatter(
        x=tx.index, y=tx["tax_owed"],
        mode="lines+markers", name=f"Tax owed @ {pct(s.globals.marginal_tax_rate)}",
        line=dict(color="#FF9DA7", width=3, dash="dot")))
    fig.update_layout(barmode="relative", height=440, hovermode="x unified",
                       xaxis_title="Year",
                       yaxis_title="Taxable income / deductions / tax (€)",
                       yaxis_tickformat=",.0f")
    st.plotly_chart(fig, width="stretch")
    st.caption("Green bar = taxable rent income; red/orange/teal/purple bars "
               "= deductions. **Black line** = taxable result (rent income − "
               "deductions). **Pink dotted line** = tax actually owed "
               "(taxable × marginal rate). "
               "Negative values are **refunds** (Verlustverrechnung, "
               "§ 10d EStG) — losses offset other income at your marginal "
               "rate, typical in early years when AfA + interest + costs "
               "exceed rent.")
    st.caption("💡 Drag the **Marginal tax rate** slider in the sidebar's "
               "🌍 **Global assumptions** expander — the pink dotted **Tax "
               "owed** line rescales immediately (the bars and black line "
               "are pre-rate, so they don't move).")

    st.markdown(f"**Total tax over {s.globals.horizon_years} years:** "
                 f"{eur(float(tx['tax_owed'].sum()))}")
    st.markdown(f"**Marginal rate applied:** {pct(s.globals.marginal_tax_rate)}")

    if s.globals.horizon_years > a.useful_life_years:
        st.caption(
            f"⚠ Real § 7 EStG stops AfA after the "
            f"{a.useful_life_years}-year useful life — total deduction "
            "should equal the full basis exactly once. **This model keeps "
            f"deducting AfA for the full {s.globals.horizon_years}-year "
            f"horizon**, which over-depreciates the basis by "
            f"{(s.globals.horizon_years - a.useful_life_years) * a.afa_rate * 100:.0f}% "
            "across the residual years and understates late-year tax. "
            "Tighten the horizon to the useful life for an exact match.")

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
    st.caption("📖 **Hit a German term you don't recognise?** Jump to the "
               "**💬 Glossary** tab — every term used anywhere in the app "
               "is defined there in plain English, with an A–Z index.")

    st.markdown("### 3-step walkthrough")
    st.markdown(WALKTHROUGH_MD)

    st.markdown("### Sidebar sections, in plain terms")

    with st.expander("🏘 Property — physical facts about the unit", expanded=False):
        st.markdown(
            "- **Purchase price**: what's on the contract.\n"
            "- **Living space / plot size**: Wohnfläche in m²; plot is your "
            "share of the WEG (Wohnungseigentümergemeinschaft — the owners' "
            "association) plot for an apartment, the full Grundstück for a "
            "house.\n"
            "- **Year built / last renovated**: drives AfA rate and capex "
            "scheduling. Leave year-last-renovated at 0 if nothing major "
            "happened.\n"
            "- **Bodenrichtwert (€/m²)**: official land reference value "
            "published by the municipal Gutachterausschuss. Look up on "
            "[boris.nrw.de](https://www.boris.nrw.de/) (NRW) or your "
            "Bundesland's equivalent. **Can be left blank** — the engine "
            "then uses property-type defaults (apartment = 80% building "
            "share, house = 65%).\n"
            "- **Energy demand (kWh/m²/yr)**: from the Energieausweis. "
            "Roughly: <100 ≈ new or KfW; 100-150 ≈ typical 1990–2010 "
            "stock; 150+ ≈ unrenovated pre-1990. See the full "
            "A+–H class table in the sidebar tooltip.\n"
            "- **Type**: *apartment* (Eigentumswohnung, a share in a WEG) "
            "or *house* (detached, full plot). Apartment scenarios pay "
            "Hausgeld; houses don't.\n"
            "- **Elevator**: lift flag. Raises Hausgeld (service contract "
            "+ eventual renewal) and the II. BV maintenance-reserve "
            "estimate. Usually absent in small houses.\n"
            "- **Denkmal**: listed-building flag (§ 7i / § 7h EStG). "
            "Enhanced AfA (9 %/yr years 1–8, 7 %/yr years 9–12) on the "
            "qualifying renovation portion — **flag only, engine does "
            "not yet apply the elevated AfA.**"
        )

    with st.expander("💰 Financing — initial capital and loans", expanded=False):
        st.markdown(
            "**Mental model / closing identity:** \n"
            "`price + fees = your own capital + Σ loan principals`. \n"
            "Fees are the Nebenkosten (notary, Grundbuch, Grunderwerbsteuer, "
            "Makler). Whatever is left once you subtract your own capital "
            "and the other loans from *price + fees* is the bank loan you "
            "still need — the *Suggested Bank principal* hint below.\n\n"
            "- **Initial capital deployed** = your own money at closing "
            "(*closing* = notary signing / Beurkundungstermin). Savings, "
            "gifts, Bauspar payouts. No repayment, no interest. This "
            "shrinks what the bank has to finance.\n"
            "- **Loans table** = third-party money you pay back over time. "
            "One row per tranche. Columns:\n"
            "  - *Annuity?* → German Annuitätendarlehen (constant monthly "
            "payment). Uncheck for fixed-payment loans (LBS Bausparverträge, "
            "family loans).\n"
            "  - *Adaptive?* → this loan absorbs freed-up debt capacity "
            "once the others clear. The *Monthly (€)* field then becomes "
            "the **minimum** payment; the engine lifts it up to the "
            "*Monthly loan budget [adaptive]* ceiling. Typical for "
            "low-priority family / 0 %-interest loans you want to retire "
            "faster.\n"
            "- **Family / Bauspar loans.** If the family cash arrives at "
            "closing, fold it into *Initial capital* and add a non-annuity "
            "row here to track the ongoing repayment — don't double-count.\n"
            "- **Monthly loan budget [adaptive]** — only used when ≥ 1 loan "
            "is flagged Adaptive. Otherwise inert and hidden. Covers loan "
            "payments only (principal + interest), *not* Hausgeld / "
            "insurance / maintenance.\n"
            "- **Suggested Bank principal hint** in the sidebar is "
            "`total purchase cost − initial capital − Σ other loan "
            "principals`. If your actual bank loan differs, one of the "
            "numbers is probably off."
        )

    with st.expander("🏘 Rent parameters — rent-mode only", expanded=False):
        st.markdown(
            "Used **only** when the mode radio is set to *rent*. Safe to "
            "leave at defaults if you only care about living in the place.\n"
            "- **Monthly rent (Kaltmiete)**: expected net cold rent. Look "
            "up realistic numbers at "
            "[ImmoScout24](https://www.immobilienscout24.de/) or "
            "[mietspiegeltabelle.de](https://www.mietspiegeltabelle.de/) "
            "for your postcode.\n"
            "- **Annual rent escalation**: 1.5-2.5% for regulated markets "
            "(Berlin, Munich, Hamburg Mietpreisbremse); up to 3% outside "
            "the cap. Long-run German CPI anchors around 2% "
            "([ECB target](https://www.ecb.europa.eu/mopo/strategy/pricestab/html/index.en.html)).\n"
            "- **Vacancy (months/year)**: whole months per year the flat "
            "sits empty between tenants. 0–1 (hot city) to 4+ (renovation "
            "gaps / problem asset). Engine multiplies rent by "
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
            "- **Monthly household net income**: Netto take-home. Drives "
            "the affordability ratios (loan/income, net burden/income, "
            "price/annual income). Does *not* enter the cashflow.\n"
            "- **Other monthly savings**: savings unrelated to the "
            "property. Feeds the cumulative-wealth chart, *not* the "
            "affordability ratios.\n"
            "- **Cost inflation**: **2% default** (Destatis long-run; "
            "[ECB target](https://www.ecb.europa.eu/mopo/strategy/pricestab/html/index.en.html)). "
            "Bump to 3% if you think the 2022+ regime persists.\n"
            "- **Marginal tax rate**: your Grenzsteuersatz (§ 32a EStG). "
            "Roughly 30% around €35k single / €70k couple, 38% around "
            "€60k / €120k, 42% at the €68k single / €136k couple "
            "Reichensteuer threshold.\n"
            "- **Horizon**: **50 years default** (matches German AfA useful "
            "life for 1925-2022 builds). The slider lets you shorten or "
            "extend between 10 and 60 years. Shorter horizons miss "
            "post-debt-free years; longer ones compound more model error."
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

    st.caption("German terms are collected in the **💬 Glossary** tab — "
               "one click to the top of the tab strip.")

    st.markdown("### What to read after this")
    st.markdown(
        "- **📋 Summary** — the headline numbers: price, debt, AfA, "
        "year-1 burden on salary.\n"
        "- **⚖ Buy vs Rent** — the core comparison. 50-year wealth chart "
        "with both modes overlaid.\n"
        "- **🏦 Debt** — stacked balance chart; see how each loan amortizes.\n"
        "- **🧾 Tax** (rent mode only) — AfA, deductions, taxable income.\n"
        "- **📚 Methodology** — citations and the rules encoded in "
        "`immokalkul/rules_de.py`.\n"
        "- **💬 Glossary** — A–Z of every German term used in the app."
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
    st.caption("German terms used below are defined in the "
               "**💬 Glossary** tab (A–Z).")
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
- The **Capex tab** plots the resulting steady-reserve line over the lumpy actual spend so you can see the gap year-by-year.

**Bank loan** — German Annuitätendarlehen logic:
- Annual annuity = principal × (interest rate + initial repayment rate)
- Constant payment; principal portion grows over time as interest portion shrinks
- Interest compounds **annually** (matching § 488 BGB convention) — interest is credited once per year on the opening balance even though payments arrive monthly. A monthly-compounding model would show ~0.5–1 % more total interest over a 30-year loan.
- Negative loan rates are clamped to 0 with a runtime warning (subsidized-loan realism).

**Component lifecycles** — based on paritätische Lebensdauertabelle (HEV/MV) and Sparkasse references:
- Heating: 20 yr; Roof: 40 yr; Façade paint: 12 yr; Windows: 30 yr; Bathroom: 28 yr; Electrical: 35 yr; Plumbing: 45 yr; etc.
- Costs from Baukosteninformationszentrum BKI Q4/2025

### What this tool does NOT model
""")
    st.markdown(NOT_MODELLED_MD)
    st.markdown("""
### Citations

All German constants live in `immokalkul/rules_de.py` with citations to source. Key links below; the [docs/REFERENCES.md](https://github.com/nicofirst1/immokalkul/blob/main/docs/REFERENCES.md) file in the repo has the full bibliography with a reliability ranking.

**Primary / official sources**
- [Finanzamt NRW — Abschreibung für Vermietungsobjekte](https://www.finanzamt.nrw.de/steuerinfos/privatpersonen/haus-und-grund/so-ermitteln-sie-die-abschreibung-fuer-ihr) — AfA rates (2.5% / 2% / 3%) and capitalizable fees
- [BORIS NRW](https://www.boris.nrw.de/) — official Bodenrichtwert for North Rhine-Westphalia
- [Wikipedia — Peterssche Formel](https://de.wikipedia.org/wiki/Peterssche_Formel) — canonical derivation of the maintenance-reserve formula
- [Gesetze im Internet — § 7 EStG](https://www.gesetze-im-internet.de/estg/__7.html) — depreciation rules
- [Gesetze im Internet — § 6 EStG](https://www.gesetze-im-internet.de/estg/__6.html) — Anschaffungsnaher Aufwand (§ 6 Abs. 1 Nr. 1a)
- [Gesetze im Internet — § 19 WEG](https://www.gesetze-im-internet.de/woeigg/__19.html) — Erhaltungsrücklage (post-WEG-Reform 2020)
- [Gesetze im Internet — § 28 II. BV](https://www.gesetze-im-internet.de/bv_2/__28.html) — age-based maintenance reserve table

**Reputable professional / institutional** — Rosepartner, Pandotax, Schiffer, Sparkasse, Wüstenrot, Interhyp, Hypofriend (see docs/REFERENCES.md).

**Aggregators / content marketing** — Immowelt, Homeday, Techem, Effi, LPE, private Bodenrichtwert portals. Use only for cross-checking.

For anything affecting an actual tax filing, verify with a Steuerberater. For Bodenrichtwert, always use BORIS NRW directly — it's free and authoritative.
    """)


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _build_llm_prompt(listing_context: str) -> str:
    """Prompt template the user pastes into an LLM to extract a listing into
    the immokalkul YAML schema.

    The embedded schema mirrors `immokalkul.models` and the bundled samples —
    if the models change, update this function in the same PR.
    """
    return f"""You are an assistant that extracts German real-estate listing data into a
YAML scenario for the "immokalkul" property finance calculator.

OUTPUT: only valid YAML matching the schema below. No Markdown, no commentary,
no code fences. If the listing doesn't state a value, use a sensible German-
market default (not a placeholder string). Never invent details — if something
is genuinely unknowable from the input, fall back to the default shown.

USER-PROVIDED LISTING INFORMATION (URL, Exposé text, or free-text description):

<<<
{listing_context}
>>>

SCHEMA — mirror this structure exactly, filling in values from the listing:

mode: rent                              # "live" (owner-occupied) or "rent" (buy-to-let)

property:
  name: "City — short description"      # e.g. "Köln Altbau 3-Zimmer"
  purchase_price: 400000                # EUR, Kaufpreis on the contract (not Gesamtpreis)
  living_space_m2: 80.0                 # Wohnfläche
  plot_size_m2: 80.0                    # apartment: your share of WEG plot (≈ Wohnfläche)
                                        # house: full Grundstück
  year_built: 2000                      # Baujahr
  year_last_major_renovation: null      # int year, or null if never
  property_type: apartment              # "apartment" or "house"
  heating_type: gas                     # gas | oil | heat_pump | district | electric | wood
  energy_demand_kwh_per_m2_year: 100    # from the Energieausweis; <100 good, 100-150 avg, 150+ poor
  has_elevator: false
  bodenrichtwert_eur_per_m2: null       # €/m² from BORIS NRW; null if unknown (engine falls back)
  is_denkmal: false
  notes: "Short free-text note (Altbau, recent Kernsanierung, etc.)"
  listing_url: "https://..."            # paste the original URL if available

financing:
  initial_capital: 100000               # your own cash at closing (savings, gifts, Bauspar payout)
  debt_budget_monthly: 1800             # only used when a loan is flagged adaptive
  loans:
    - name: Bank
      principal: 350000                 # ≈ total_cost (price × 1.12) − initial_capital
      interest_rate: 0.035               # annual decimal; 0.035 = 3.5 %
      monthly_payment: 1604             # principal × (rate + 0.015) / 12 for 1.5 % Tilgung
      is_annuity: true
      is_adaptive: false

costs:
  gas_price_eur_per_kwh: 0.11
  electricity_price_eur_per_kwh: 0.35
  grundsteuer_rate_of_price: 0.002      # legacy proxy, kept for back-compat
  grundsteuer_land_rate: 0.0034         # 0.20-0.50 % typical post-2025 reform
  building_insurance_eur_per_m2_year: 4.0
  liability_insurance_annual: 150.0
  administration_monthly: 30.0
  municipal_charges_eur_per_m2_month: 0.60
  hausgeld_monthly_for_rent: 350        # apartments only; set 0 for freestanding houses
  hausgeld_reserve_share: 0.40          # § 19 WEG portion; not deductible until spent

rent:
  monthly_rent: 1500                    # expected Kaltmiete
  monthly_parking: 0
  annual_rent_escalation: 0.02          # 1.5-2.5 % typical under Mietspiegel
  expected_vacancy_months_per_year: 0.25
  landlord_legal_insurance_annual: 300
  has_property_manager: false
  property_manager_pct_of_rent: 0.06

live:
  people_in_household: 2
  large_appliances: 4
  needs_kitchen_replacement: false
  current_monthly_rent_warm_eur: 0      # what the household pays today all-in

globals:
  monthly_household_income: 6000        # household Netto
  additional_monthly_savings: 500
  cost_inflation_annual: 0.02           # ECB target
  marginal_tax_rate: 0.38               # Grenzsteuersatz
  horizon_years: 50
  today_year: {GlobalParameters().today_year}

user_capex: []
auto_schedule_capex: true

EXTRACTION GUIDANCE:
- Baujahr → property.year_built. "Teilsaniert 2010" → year_last_major_renovation: 2010.
- Wohnfläche → living_space_m2. Zimmer count alone is not enough — find the m².
- Immobilienscout / Exposé pages list Hausgeld separately; use it if present,
  otherwise estimate as 3 €/m²/month for apartments, 0 for houses.
- If Denkmalgeschützt is mentioned → is_denkmal: true.
- If the listing is a Mehrfamilienhaus apartment, set property_type: apartment
  and plot_size_m2 ≈ living_space_m2 (WEG share). For a freestanding house,
  use the actual Grundstücksgröße.
- Compute Bank loan: principal ≈ purchase_price × 1.12 − initial_capital; if
  no initial_capital signal, leave the default at 100000 and recompute.
  monthly_payment ≈ principal × (interest_rate + 0.015) / 12 (1.5 % Tilgung).
- Produce ONLY the YAML. No heading, no explanation, no code fence."""


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
        "💬 Glossary",
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
    with tabs[9]: tab_glossary()

    _render_footer()


GLOSSARY_TERMS: list[tuple[str, str, str]] = [
    # (anchor slug, display label, definition)
    ("afa",
     "AfA *(Absetzung für Abnutzung)*",
     "Literally *write-off for wear*. Linear depreciation of the building "
     "over 40 / 50 / 33⅓ years. Available only in rent mode."),
    ("annuitaetendarlehen",
     "Annuitätendarlehen",
     "Loan with a constant monthly payment; interest portion shrinks, "
     "principal portion grows. The typical German mortgage structure."),
    ("anschaffungsnaher-aufwand",
     "Anschaffungsnaher Aufwand",
     "Literally *expenditure close to acquisition*. Renovations in the "
     "first 3 years exceeding 15 % of building value get reclassified from "
     "expense to capital spend (§ 6 Abs. 1 Nr. 1a EStG)."),
    ("bausparvertrag",
     "Bausparvertrag (LBS)",
     "Savings-plus-loan hybrid. Fixed monthly payment on both sides."),
    ("betriebskostenabrechnung",
     "Betriebskostenabrechnung",
     "Annual reconciliation of utility costs between landlord and tenant."),
    ("bodenrichtwert",
     "Bodenrichtwert",
     "Official land value per m² in your area. Look up on BORIS NRW (or "
     "your state's equivalent)."),
    ("denkmal",
     "Denkmal",
     "Listed building. Qualifies for special AfA (§ 7i EStG, not yet "
     "modelled here)."),
    ("energieausweis",
     "Energieausweis",
     "Legally required energy-efficiency certificate. Gives the kWh/m²/yr "
     "figure."),
    ("erhaltungsaufwand",
     "Erhaltungsaufwand",
     "Literally *preservation expenditure*. Ordinary maintenance — "
     "immediately deductible in rent mode."),
    ("erhaltungsruecklage",
     "Erhaltungsrücklage",
     "WEG maintenance reserve (§ 19 WEG, post-2020 rename of "
     "*Instandhaltungsrücklage*). Funded out of your Hausgeld; pays for "
     "shared-area capex."),
    ("finanzierungszusage",
     "Finanzierungszusage",
     "Written bank commitment to fund the loan at stated terms. Ask for "
     "this early."),
    ("gemeinschaftseigentum",
     "Gemeinschaftseigentum",
     "Shared portions of a WEG building (roof, façade, stairs). Covered "
     "by Hausgeld."),
    ("grenzsteuersatz",
     "Grenzsteuersatz",
     "Marginal income-tax rate — applies to each extra euro of income."),
    ("grundbuch",
     "Grundbuch",
     "Land registry. Ownership and encumbrances are recorded here; "
     "updates cost ~0.5 % of price."),
    ("grundschuld",
     "Grundschuld",
     "Land-charge registered against the property as bank collateral. "
     "Standard for German mortgages; you'll meet it at the notary."),
    ("grunderwerbsteuer",
     "Grunderwerbsteuer",
     "One-off property-transfer tax. 6.5 % in NRW; 3.5–6.5 % elsewhere."),
    ("grundsteuer",
     "Grundsteuer",
     "Annual property tax paid to the Kommune. Typically 0.15–0.35 % of "
     "price post-2025 reform."),
    ("hausgeld",
     "Hausgeld",
     "Monthly WEG fee for common-area costs, admin, shared insurance — "
     "for apartments only."),
    ("hausverwaltung",
     "Hausverwaltung",
     "Property management company. 4–8 % of gross rent typical."),
    ("herstellungskosten",
     "Herstellungskosten",
     "Literally *production costs*. Capital spend that adds to the AfA "
     "basis and is depreciated over the building's useful life."),
    ("kaltmiete",
     "Kaltmiete",
     "Net cold rent — rent only, no utilities."),
    ("kernsanierung",
     "Kernsanierung",
     "Full-gut renovation. Resets component-lifecycle clocks."),
    ("kirchensteuer",
     "Kirchensteuer",
     "Church tax, 8–9 % of income tax for registered members. Not "
     "modelled here."),
    ("kommune",
     "Kommune",
     "Municipality. Sets the Grundsteuer Hebesatz."),
    ("maklerprovision",
     "Maklerprovision",
     "Estate-agent commission. Since 2020 the buyer covers ~3.57 % in "
     "most Bundesländer."),
    ("mietpreisbremse",
     "Mietpreisbremse",
     "Rent cap in tight markets — limits new leases to ~10 % above local "
     "Mietspiegel."),
    ("mietspiegel",
     "Mietspiegel",
     "Official city rent-comparison table."),
    ("nebenkosten",
     "Nebenkosten",
     "Warm-side utilities (heating, water, etc.) on top of Kaltmiete. "
     "Nebenkosten + Kaltmiete = Warmmiete."),
    ("notar",
     "Notar",
     "Notary. German property transfers require a notarised deed; fees "
     "~1.5 % of price."),
    ("petersche-formel",
     "Petersche Formel",
     "1984 formula for the maintenance reserve: "
     "`(build cost/m² × 1.5) / 80 × 0.7`."),
    ("sanierungspflicht",
     "Sanierungspflicht",
     "Energy-renovation obligation under GEG (heating, insulation, "
     "windows). Especially relevant for Altbau buyers post-2024."),
    ("sondereigentum",
     "Sondereigentum",
     "Your private apartment unit inside a WEG (vs. Gemeinschaftseigentum)."),
    ("sonderumlage",
     "Sonderumlage",
     "Special one-off WEG assessment when the reserve isn't enough."),
    ("solidaritaetszuschlag",
     "Solidaritätszuschlag (Soli)",
     "5.5 % surcharge on income tax for high earners. Folded into the "
     "marginal-rate input."),
    ("steuerberater",
     "Steuerberater",
     "Tax advisor. Required reading for anything sensitive to §7 or §6 "
     "EStG interpretation."),
    ("tilgung",
     "Tilgung",
     "Repayment rate on an annuity loan — the % of principal you pay "
     "down per year at the start."),
    ("warmmiete",
     "Warmmiete",
     "All-in rent: Kaltmiete + Nebenkosten."),
    ("weg",
     "WEG *(Wohnungseigentümergemeinschaft)*",
     "Owners' association for an apartment building."),
    ("werbungskosten",
     "Werbungskosten",
     "Income-related expenses deductible against rental income — "
     "interest, operating costs, maintenance, management fees, AfA."),
]


def tab_glossary() -> None:
    """Dedicated glossary tab — A-Z index + anchored term list.

    Intra-tab markdown anchors (`<a id="...">` + `[link](#...)`) work
    reliably inside a single Streamlit tab. Cross-tab anchors do not,
    which is why the glossary lives in its own tab rather than linked
    from Methodology / Getting-started."""
    st.markdown("## 💬 Glossary of German terms")
    st.caption(
        "Every German term that shows up in the sidebar, tooltips, or "
        "tables is defined here in plain English. Click a letter to jump; "
        "click the ↑ next to any term to come back up.")

    # A-Z jump index. Groups by first letter; letters without any term
    # are skipped so the index stays tight.
    by_letter: dict[str, list[tuple[str, str, str]]] = {}
    for slug, label, _ in GLOSSARY_TERMS:
        letter = label[0].upper()
        by_letter.setdefault(letter, []).append((slug, label, _))
    az_links = [
        f"[{letter}](#glossary-letter-{letter.lower()})"
        for letter in sorted(by_letter.keys())
    ]
    st.markdown(" · ".join(az_links))

    # Render each letter section with a letter anchor + all terms under it.
    md_lines: list[str] = []
    for letter in sorted(by_letter.keys()):
        md_lines.append(
            f'<a id="glossary-letter-{letter.lower()}"></a>')
        md_lines.append(f"### {letter}")
        for slug, label, definition in by_letter[letter]:
            md_lines.append(f'<a id="glossary-{slug}"></a>')
            md_lines.append(f"**{label}** — {definition} "
                             "[↑ back to top](#glossary-of-german-terms)")
            md_lines.append("")  # blank line between terms
    st.markdown("\n".join(md_lines), unsafe_allow_html=True)


def _render_footer():
    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #6b7280; font-size: 0.85rem; "
        "padding: 0.5rem 0; line-height: 1.6;'>"
        "Made by <a href='http://nicolobrandizzi.com/' target='_blank' "
        "style='color: #4E79A7; text-decoration: none;'>Nicolo' Brandizzi</a>"
        "<br>"
        "Not financial advice — verify with a Steuerberater or your bank. "
        "See <a href='https://github.com/nicofirst1/immokalkul/blob/main/docs/REFERENCES.md' "
        "target='_blank' style='color: #4E79A7; text-decoration: none;'>"
        "docs/REFERENCES.md</a> for sources."
        "<br>"
        f"App version {APP_VERSION} · "
        "<a href='https://github.com/nicofirst1/immokalkul' "
        "target='_blank' style='color: #4E79A7; text-decoration: none;'>"
        "🔓 open source on GitHub</a> · "
        "<a href='https://github.com/nicofirst1/immokalkul/commits/main' "
        "target='_blank' style='color: #4E79A7; text-decoration: none;'>git "
        "history</a> — German rules current as of Q1 2026."
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
