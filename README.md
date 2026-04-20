# immokalkul

A small Python program for evaluating German property purchases. Models both **live** (owner-occupied) and **rent** (buy-to-let) modes from a single scenario, with proper German rules baked in.

---

## What this is for

Deciding whether to buy a property — and if so, whether to live in it or rent it out — requires answering questions that an Excel sheet handles badly:

- *What's my actual monthly burden after Hausgeld, maintenance reserve, vacancy risk, and tax?*
- *What's the cumulative wealth picture over 50 years in each mode?*
- *When is the next big capex due, and how much should I budget?*
- *How does this property compare to another one I'm also considering?*

This tool answers those questions with German specifics applied correctly: AfA at the right rate for your build year, Petersche Formel for maintenance reserve, Anschaffungsnaher Aufwand check on early renovations, building/land split via Bodenrichtwert, and Annuitätendarlehen amortization for the bank loan.

---

## Setup

You need Python 3.10+ installed.

**With uv (recommended):**

```bash
cd immokalkul
uv sync
```

This creates `.venv/` and installs the pinned versions from `uv.lock`.

**With pip:**

```bash
cd immokalkul
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Either way you get: streamlit, pandas, plotly, pyyaml.

---

## Running

```bash
uv run streamlit run app.py
# or, if using pip + activated venv:
streamlit run app.py
```

This opens the app in your default browser at `http://localhost:8501`. The sample scenario (Bonn-Poppelsdorf 3-Zimmer) loads automatically. Any change you make in the sidebar updates the main area immediately — no save button needed for what-if exploration. The save button is only for persisting to a YAML file.

To stop the app: Ctrl-C in the terminal where you ran `streamlit run`.

---

## How to use it: a typical workflow

### Step 1: Load or create a scenario

When you open the app, the Bonn property is loaded as a starting point. To analyze a different property:

- **Copy the sample YAML**: open `data/bonn_poppelsdorf.yaml`, save a copy as `data/<your_property>.yaml`, edit the values, and pick it from the **📂 Scenarios** dropdown in the sidebar.
- **Edit live in the sidebar**: any field can be changed via the widgets. Click ⬇ Download to save the current state as a YAML file.
- **Upload an existing YAML**: drag a file into the uploader.

### Step 2: Set up the property facts

In the sidebar, expand **🏘 Property** and enter:

- **Purchase price** — what's on the contract
- **Living space (m²)** — Wohnfläche
- **Plot size (m²)** — for an apartment, your share of the WEG plot (often equal to living space); for a house, the full Grundstück
- **Year built** — drives AfA rate and component lifecycle scheduling. Pre-1925 gets 2.5% AfA, 1925-2022 gets 2%, 2023+ gets 3%
- **Year last renovated** — set to 0 if never. Resets the component lifecycle clock for things like heating, bathroom, electrics
- **Bodenrichtwert (€/m²)** — land value per m². For Bonn-Poppelsdorf, currently €1,000-1,600 per m² per BORIS NRW (2024). Look yours up at [boris.nrw.de](https://www.boris.nrw.de/). This drives the AfA building/land split — getting it right matters for the tax calculation
- **Energy demand (kWh/m²/yr)** — from the Energieausweis. <100 = good, 100-150 = average, 150+ = poor
- **Type** (apartment vs house), **elevator**, **listed building (Denkmal)**

### Step 3: Set up the financing

Expand **💰 Financing**:

- **Initial capital deployed (€)** — total cash put down at closing, *including* any Bauspar payout and family-loan proceeds used up front
- **Total monthly debt budget** — ceiling for total monthly debt service. Only used when at least one loan has *Adaptive* checked in the loans table.
- **Loans table** — edit principal, interest rate, monthly payment, *Annuity?* (German Annuitätendarlehen), and *Adaptive?* (absorbs freed-up debt capacity once other loans clear, up to the budget above). Hover any column header in the table for a full explanation.

The sidebar shows a **💡 Suggested Bank principal** based on `total purchase cost − initial capital`. If your bank loan in the table doesn't match that, it usually means you over- or under-financed something, or the initial capital figure is off.

### Step 4: Pick your mode and read the result

The **Mode** radio at the top of the sidebar switches between live and rent. The header at the top of the page shows:

- **Year-1 monthly burden on salary** — what comes out of your pocket every month
- **% of income** — green if under 30%, red if over (the German bank rule of thumb)
- **Years until debt-free** — when all loans are paid off
- **50-year cumulative wealth change** — net of property cash flows + other savings

That's enough for the headline answer. For depth, use the tabs.

---

## What each tab tells you

### 📋 Summary

Property facts, full purchase cost breakdown, per-loan financing summary, AfA calculation (rent mode), and affordability checks. Start here.

### ⚖ Live vs Rent

The most useful tab. Shows both modes side-by-side: 50-year cumulative wealth chart with both lines, year-1 monthly cash flow comparison, and per-mode KPIs. Lets you answer "should I move into this place or rent it out?" at a glance.

### 💸 Cash flow

50-year annual cash flow waterfall for the **current** mode. Bars show rent income (positive), and loan, op costs, capex, tax (negative). Black line is net property cash flow. Below it: the cumulative wealth chart for that mode alone, and a year-by-year table.

In **rent mode**, expect early years to be slightly negative (high interest deduction → low taxable income → low tax → small positive cash; but capex spikes drag some years down). After year 30 when bank clears, the picture flips dramatically positive.

In **live mode**, expect every year to be negative (you're paying for everything with no rental income to offset). The "wealth" picture only makes sense if you also account for not paying rent yourself — which this model doesn't (yet). See the caveat at the bottom.

### 💡 Costs

All operating cost lines for year 1, with mode flags. Each line shows monthly + annual amounts and whether it's deductible against rental income. Pie chart at the bottom shows composition.

This is also where you sanity-check what's being modeled: did I include the chimney sweep? Heating maintenance? Vermieter-Rechtsschutz?

### 🏦 Debt

Stacked balance chart showing how each loan amortizes over 50 years. Below it, annual payment breakdown by loan. The summary table shows total interest paid per loan. If a loan is flagged *Adaptive*, you'll see its annual payment jump up after the non-adaptive loans clear — that's the freed capacity flowing to it.

### 🔨 Capex

Auto-scheduled major renovations (heating, roof, bathroom, etc.) plus your user-specified items from the sidebar. Bubble timeline shows when each item is due, sized by inflated cost. Annual aggregate bar chart shows clustering.

For older buildings, you'll see a cluster of capex around the projected next-replacement years. **Important caveat**: the model assumes the last replacement of each component happened at `year_built` (or `year_last_major_renovation`). If you know the heating was replaced in 2010, set `year_last_major_renovation` to 2010 — or add specific entries via the **🔨 User-specified renovations** sidebar editor.

### 🧾 Tax

Rent-mode-only. Shows AfA basis breakdown (building value + capitalized fees), the annual AfA, and per-year tax computation (rent income − interest − costs − AfA − capex deductions = taxable income; × marginal rate = tax owed). Stacked bar chart shows how each deduction shrinks the taxable basis.

### 📚 Methodology

Documentation of which German rules are applied, with citations. Read this before trusting any number.

---

## Tweaking inputs to test scenarios

The reactive UI makes "what if" questions cheap:

- **What if interest rates rise to 5%?** Change Bank rate in the loans table; everything updates.
- **What if rent only goes up 1%/yr instead of 2%?** Adjust the rent escalation slider.
- **What if I bring more cash to closing?** Bump initial capital; see the suggested bank principal drop, and watch the burden shrink.
- **What if I assume the heating was actually replaced in 2010?** Set `year_last_major_renovation` to 2010; the capex tab will push the next heating replacement to 2030 instead of 2024.
- **What if I do a €40k bathroom redo in year 2?** Add a row in the user capex editor with cost €40,000, year 2028, capitalized=False. Watch the Anschaffungsnaher Aufwand check — if it's > 15% of building value, the model reclassifies it to AfA.

For comparing two properties, save each as a YAML, then load them in turn. (A proper side-by-side comparison view is a possible future addition.)

---

## Adding a new property

1. Copy `data/bonn_poppelsdorf.yaml` to `data/<short_name>.yaml`
2. Edit the values in your text editor
3. Reload the app — the new file shows up in the dropdown automatically

The YAML schema is enforced by the dataclasses in `immokalkul/models.py`. Any typo in a field name gives a clear error when loading.

---

## Programmatic use (without the UI)

The engine works standalone. Useful for batch comparisons or scripted sensitivity analysis:

```python
from immokalkul import load_scenario, run

s = load_scenario("data/bonn_poppelsdorf.yaml")
s.mode = "rent"
result = run(s)

print(f"Years to debt-free: {result.years_to_debt_free}")
print(f"50yr final cumulative: €{result.cashflow['cumulative'].iloc[-1]:,.0f}")
print(f"Annual AfA: €{result.afa_basis.annual_afa:,.0f}")

# Tweak something and rerun
s.financing.loans[0].interest_rate = 0.05  # bank rate 5%
result_high_rate = run(s)
delta = result.cashflow['cumulative'].iloc[-1] - result_high_rate.cashflow['cumulative'].iloc[-1]
print(f"Cost of 1.6 percentage points higher rate: €{delta:,.0f}")
```

The `result` object has `.cashflow`, `.amort`, `.tax`, `.cost_lines`, `.purchase`, `.afa_basis`, `.all_capex`, `.years_to_debt_free` as Pandas DataFrames or dataclass objects.

---

## Key methodology decisions

**AfA depreciation rate** — automatically picked from `year_built`:
- Pre-1925: **2.5%/yr** over 40 years
- 1925-2022: 2%/yr over 50 years
- 2023+: 3%/yr over 33⅓ years

**AfA basis** — `(building_share × purchase_price) + (building_share × capitalizable_fees) + (building_share × capitalized_renovation)`. Capitalizable fees = Grunderwerbsteuer + Maklerprovision + 80% of Notar/Grundbuch (the rest is Geldbeschaffungskosten, immediately deductible).

**Building share** — derived from Bodenrichtwert if provided, otherwise property-type defaults (apartment ~80%, house ~65%). Capped at 75% (apartment) or 50% (house) to avoid silly results when Bodenrichtwert × plot exceeds the price.

**Maintenance reserve** — `max(Petersche Formel, II. BV age table)`:
- Petersche: `(construction_cost_per_m² × 1.5) / 80 × 0.7` (×0.7 only for apartments — Gemeinschaftseigentum share)
- II. BV: €7.10/m²/yr (≤22 yr), €9.00 (22-32 yr), €11.50 (>32 yr), +€1 if elevator
- For your 1904 Altbau, this gives ~€34/m²/yr — appropriate for a building this old

**Anschaffungsnaher Aufwand** — § 6 Abs. 1 Nr. 1a EStG. If user-specified capex within 3 years of purchase exceeds 15% of building value, all of it gets reclassified from Erhaltungsaufwand (immediately deductible) to Herstellungskosten (added to AfA basis, depreciated over 40-50 yr).

**Annuitätendarlehen** — annual annuity = `principal × (interest_rate + initial_repayment_rate)`. Constant payment over the loan's life; interest portion shrinks, principal portion grows.

**Adaptive loans** — any loan with `is_adaptive: true`. Its annual payment becomes `max(min_annual, (debt_budget_annual − non_adaptive_payment) / n_adaptive)`, capped at the remaining balance. This redirects freed-up debt-service capacity to the adaptive tranche(s) once non-adaptive loans clear. Typical use: a family / 0%-interest loan you want to retire faster over time. The legacy `adaptive_mamma` YAML flag is auto-migrated on load (sets `is_adaptive=true` on the loan named `Mamma`).

**Component lifecycles** — heating 20 yr, roof 40 yr, façade paint 12 yr, windows 30 yr, bathroom 28 yr, electrical 35 yr, plumbing 45 yr, etc. From paritätische Lebensdauertabelle (HEV/MV) and BKI cost data.

All German constants live in `immokalkul/rules_de.py` with citations. When a tax law changes, that's the only file to touch.

For the full bibliography of sources consulted (AfA, Petersche Formel, component lifecycles, Bodenrichtwert, etc.) with a reliability ranking and caveats, see [docs/REFERENCES.md](docs/REFERENCES.md).

---

## What this tool does NOT model

- **Property value appreciation** — equity built through amortization is shown via cumulative cash flow, but no market price growth is assumed. Historical Bonn appreciation has been ~3-5%/yr; if you want to factor it in, multiply the building value by `(1 + g)^n` mentally
- **Loss carry-back / forward caps** — the model applies full Verlustverrechnung (rental losses offset salary at the marginal rate in the same year), but doesn't enforce the annual / cumulative caps in § 10d EStG. For typical residential buy-to-let this is fine; for very large losses the real benefit is slightly smaller
- **Cost of equivalent rental in live mode** — when you live in a place you own, you save the rent you'd otherwise pay. Set `current_monthly_rent_warm_eur` on `LiveParameters` (or the "Current rent you pay now" sidebar field) and the engine credits it as imputed income in the cash flow, escalated by `cost_inflation_annual`. Leave the field at 0 to keep the legacy "no credit" behaviour
- **Sonderumlagen (WEG special assessments)** — modeled implicitly through the maintenance reserve, which assumes reserves are sufficient to cover them
- **Denkmal-AfA (§7i EStG)** — flag exists in the property model but the special 9%/7% scheme isn't yet implemented
- **§7b Sonder-AfA for new builds** — not modeled
- **VAT in any form** — German residential rentals are VAT-exempt, so this is fine for rent mode; for live mode it doesn't matter
- **Inflation of rent above the lease** — rent escalation is one rate; doesn't model index-linked vs Mietspiegel-capped vs negotiated separately

**Get a Steuerberater to verify any tax number before making decisions involving real money.** This tool is for budgeting and comparison, not legal advice.

---

## Project structure

```
immokalkul/
├── app.py                         # Streamlit UI (run with: streamlit run app.py)
├── pyproject.toml                 # uv project definition (used by Streamlit Cloud)
├── requirements.txt               # streamlit, pandas, plotly, pyyaml (pinned)
├── README.md                      # this file
├── LICENSE                        # MIT
├── .streamlit/config.toml         # theme & page defaults
├── immokalkul/                    # Engine package (~900 lines, no UI deps)
│   ├── __init__.py                # public API
│   ├── models.py                  # Dataclasses (Property, Loan, Scenario, ...)
│   ├── rules_de.py                # German constants with citations
│   ├── financing.py               # Purchase costs, building/land split, amortization
│   ├── operating_costs.py         # Petersche/II.BV maintenance, mode-aware costs
│   ├── capex.py                   # Component lifecycle scheduling
│   ├── tax.py                     # AfA + Anschaffungsnaher Aufwand
│   ├── cashflow.py                # End-to-end annual projection
│   └── io.py                      # YAML load/save
└── data/
    └── bonn_poppelsdorf.yaml      # Sample scenario (edit or copy to add yours)
```

---

## Troubleshooting

**App won't start, "ModuleNotFoundError"**: you didn't run `pip install -r requirements.txt` in the right Python environment. Check `which python3` and `which pip` match.

**Sidebar shows "Suggested Bank principal: €X" but my Bank loan in the table is different**: that's a hint, not an error. The suggested figure is `total purchase cost − initial capital`. If your actual bank loan differs, either your initial capital number includes/excludes things differently, or you're under-financing (need to bring more cash) or over-financing.

**AfA basis seems too low**: check the Bodenrichtwert. If you left it blank, the model uses property-type defaults (apartment = 80% building share). If your apartment is in a low-land-value area, the actual building share could be 90%+, which means more AfA. Look up the real Bodenrichtwert at [boris.nrw.de](https://www.boris.nrw.de/).

**Capex schedule shows everything bunched at year 19**: that's because the model assumes everything was last replaced at `year_built` (1904 in the sample). The math is `1904 + N × component_lifetime`, so for a 20-year-lifetime component the next replacement falls at 2024 → recomputed forward to 2044 → year offset 19. Set `year_last_major_renovation` if a Kernsanierung happened, or add specific entries via the user capex editor for items you have real information about.

**Live mode shows a big negative cumulative — am I really losing that much?**: only if you leave the "Current rent you pay now (warm, €/mo)" field at 0. That field is the all-in rent (Warmmiete + utilities) you avoid by owning; when set, the engine credits it as imputed income in the cash flow, escalated by `cost_inflation_annual`. With a realistic figure set, live and rent mode can be compared apples-to-apples.

**Streamlit deprecation warnings appear**: Streamlit changes API frequently. The code currently targets Streamlit 1.30+. If you upgrade Streamlit and see new deprecation warnings, they're harmless until removal — fix at leisure.

---

## Limitations and known issues

- **Single property at a time**: comparing two or more properties side-by-side requires loading each in turn. A multi-property comparison view would be a natural future addition.
- **No historical data**: doesn't pull live interest rates, Bodenrichtwerte, or Hausgeld benchmarks. You enter what you know.
- **No Excel export**: results stay in the browser. Use the Python API for batch work, or screenshot/copy for sharing.
- **Tax model is simplified** in the ways listed under Caveats. Conservative bias (over-estimates tax in some years).

If any of those bother you enough that you'd use a fix, the engine is small enough (~900 lines) that adding it is a few hours of work.

---

## Privacy

The app runs entirely in your browser session. Inputs you type into the sidebar, YAML files you upload, and scenarios you download never leave the process that's serving the app — nothing is logged, stored server-side, or sent to any analytics endpoint. The code contains no telemetry.

If you deploy this to Streamlit Community Cloud, your session state still lives only in the Streamlit process handling your request; Streamlit Inc. hosts the app but does not receive your inputs. If you want zero network dependency, run it locally with `streamlit run app.py`.

---

## Deploying to Streamlit Community Cloud

The repo is already set up for a public deployment:

- `LICENSE` — MIT
- `pyproject.toml` + `uv.lock` — Streamlit Cloud reads `uv.lock` first and installs with `uv`
- `requirements.txt` — pinned fallback for pip users
- `.streamlit/config.toml` — theme + page defaults
- `.gitignore` — excludes `.venv`, `__pycache__`, `.DS_Store`, `.streamlit/secrets.toml`
- `data/` — sample scenarios visitors can load from the sidebar dropdown (Bonn, Munich Neubau, Berlin Altbau, Köln Einfamilienhaus)

To ship:

1. Push the repo to GitHub (public or private — Streamlit can read both if you auth it).
2. Go to [share.streamlit.io](https://share.streamlit.io), click "New app", pick the repo + branch + `app.py`.
3. Deploy. Streamlit resolves dependencies from `uv.lock` and starts the app.

---

## License

MIT — see [LICENSE](LICENSE). Use it, fork it, learn from it. No warranty. Don't blame me if your Steuerberater disagrees.
