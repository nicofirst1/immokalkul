# Actionable items — immokalkul

Concrete fixes derived from [`audit.md`](./audit.md), using the frameworks in [`research.md`](./research.md). All items respect the constraint **no major restructuring** — single-file `app.py`, Streamlit primitives, no engine changes.

## How this file is organised

- **P0** — Goal-A blockers. First-open disengagement risks. Do first.
- **P1** — Goal-B wins. Educational depth. In-context transparency.
- **P2** — Polish. Microcopy, consistency, hygiene.

Each item carries:
- **Problem** — one-line summary with link to the audit finding
- **Fix** — concrete change (often with a small code sketch)
- **Target** — `file:line` or function to modify
- **Effort** — S (< 30 min), M (30-120 min), L (half-day+)
- **Frameworks** — which lenses from `research.md` motivate it

## Priority matrix (at-a-glance)

| # | Item | Priority | Effort | Goal |
|---|---|---|---|---|
| 1 | Top-of-page verdict banner | P0 | M | A |
| 2 | Collapse Property + Financing; default-open Scenarios | P0 | S | A |
| 3 | Hide "Total monthly debt budget" when no adaptive loan | P0 | S | A |
| 4 | Split Property expander into Basics + Tax details | P0 | S | A |
| 5 | Drop Mode KPI; slim header to 4 tiles | P0 | S | A |
| 6 | Rewrite long tooltips to ≤ 2 sentences | P0 | M | A |
| 7 | "This is a sample scenario" framing banner | P0 | S | A |
| 8 | Summary first, Start-here as expander on Summary | P0 | M | A |
| 9 | Show rates in Purchase costs table labels | P1 | S | B |
| 10 | In-context gloss under Purchase costs table | P1 | M | B |
| 11 | Glossary expander in Start-here tab | P1 | M | B |
| 12 | Chart captions with insight sentences | P1 | M | B |
| 13 | Cross-mode verdict on Live-vs-Rent tab | P1 | S | B |
| 14 | "Next steps" panel on Summary | P1 | M | A+B |
| 15 | "Try this" nudge under Live-vs-Rent chart | P1 | S | B |
| 16 | Rewrite jargon labels to plain language + term | P1 | S | B |
| 17 | Elevate "NOT modelled" limitations block | P1 | S | B |
| 18 | Footer: disclaimer + sources link | P2 | S | B |
| 19 | Friendlier error fallback (no raw traceback) | P2 | S | A |
| 20 | Mode indicator on per-tab sub-headers | P2 | S | A |
| 21 | Widen marginal tax slider (10 % – 55 %) | P2 | S | B |
| 22 | `min_value=0` on capex cost column | P2 | S | — |
| 23 | TOC inside Methodology tab | P2 | S | B |
| 24 | Legend key + colour-blind affordance on 50-year chart | P2 | S | — |
| 25 | Mark modified scenario in header title | P2 | S | A |

---

## P0 — Don't lose users at open

### P0-1. Top-of-page verdict banner

- **Problem.** The landing view shows 5 metric tiles and no sentence-form answer. First-time user fails the 5-second test — can't state the verdict for the scenario. Audit §1.1, §2.4, §2.8 (JTBD top risk).
- **Fix.** Before `render_header`, render a single full-width banner that synthesises the existing `checks` list (`app.py:630-664`) into one sentence. Use `st.success` / `st.warning` / `st.error` depending on how many checks pass. Example output: *"✅ Looks affordable — meets 4 of 5 rules; one watch-out: your down payment is 19 % (target 20 %)."*
- **Sketch.** Extract the `checks` computation from `tab_summary` into a helper `_compute_affordability_verdict(result, s) -> (level, sentence)`; call it once in `main()` right before `render_header(...)`. Keep the existing ✅/❌ strip inside the Summary tab (it provides the per-rule detail). This keeps the engine untouched.
- **Target.** New helper + call in `main()` (`app.py:1281-1325`); source logic from `tab_summary` (`app.py:629-668`).
- **Effort.** M.
- **Frameworks.** Krug 5s • Nielsen H1, H8 • JTBD • CLT (germane / verdict framing).

### P0-2. Collapse Property + Financing; default-open Scenarios

- **Problem.** Three sidebar expanders are open on load (Property + Financing + Rent-parameters via `expanded=(s.mode=="rent")`). The highest-leverage onboarding expander — Scenarios — is closed. Audit §2.3, §3.1.
- **Fix.** Change three expander defaults:
  - Scenarios: `expanded=False` → `expanded=True` (`app.py:103`)
  - Property: `expanded=True` → `expanded=False` (`app.py:139`)
  - Financing: `expanded=True` → `expanded=False` (`app.py:180`)
  - Rent parameters: `expanded=(s.mode=="rent")` → `expanded=False` (`app.py:266`)
  - Live parameters: `expanded=(s.mode=="live")` → `expanded=False` (`app.py:312`)
- **Result.** On first load, user sees the scenario picker (invitation to explore) — not a wall of inputs. The verdict banner + header tiles deliver the answer; sidebar expanders are available when the user wants to tweak.
- **Target.** `sidebar_inputs()` — `app.py:94-462`.
- **Effort.** S.
- **Frameworks.** Progressive Disclosure • CLT (extraneous) • Nielsen H8.

### P0-3. Hide "Total monthly debt budget" when no adaptive loan

- **Problem.** The tooltip itself admits "No adaptive loan set, so this value is inert." — yet the input is always visible (`app.py:189-198`). Default Bonn scenario has one adaptive loan, but users loading other scenarios or starting blank do not — the input shows as inert clutter. Audit §2.3.
- **Fix.** Wrap the `debt_budget_monthly` input in `if any_adaptive:` (the variable already exists at `app.py:188`). When hidden, leave the underlying scenario value untouched.
- **Target.** `app.py:188-198`.
- **Effort.** S.
- **Frameworks.** Progressive Disclosure • Nielsen H8.

### P0-4. Split Property expander into Basics + Tax details

- **Problem.** 11 fields in two columns mix physical facts (price, m², year) with tax-relevant flags (Bodenrichtwert override, Denkmal, year_last_major_renovation). Novice meets Bodenrichtwert and Denkmal before reading anything about what AfA is. Audit §2.3, §3.1.
- **Fix.** Inside the Property expander, keep column 1 (price, living space, year built, type, elevator) visible. Move Bodenrichtwert + Denkmal + year_last_major_renovation + energy demand into a nested `st.expander("🔬 Tax-relevant details (can skip for first pass)")` closed by default.
- **Target.** `app.py:139-178`.
- **Effort.** S.
- **Frameworks.** Progressive Disclosure • CLT (manage intrinsic) • Nielsen H7 (novice/expert).

### P0-5. Drop Mode KPI; slim header to 4 tiles

- **Problem.** `Mode: RENT` is a *state*, not a measurement. Costs a tile slot at the top of the page for no information gain. Combined with "Year-1 monthly burden" which repeats in Summary (`Net burden / income`), the header carries redundancy. Audit §3.2.
- **Fix.**
  - Remove the Mode tile (`app.py:483-484`) and the Year-1 burden tile (`app.py:486-491`).
  - Keep: Total purchase cost, Years to debt-free, 50yr cumulative. Add one new tile: the *verdict level* from P0-1 (e.g. "✅ Within rules (4/5)").
- **Target.** `render_header()` — `app.py:468-497`.
- **Effort.** S.
- **Frameworks.** Nielsen H8 • CLT (redundancy).

### P0-6. Rewrite long tooltips to ≤ 2 sentences

- **Problem.** Tooltips exceed 80 words in several places — users scan, they don't read. Audit §2.4, §2.6, §3.1.
- **Fix.** Rewrite the following tooltips to ≤ 2 sentences each. Move the citation-style detail (e.g. "German long-run CPI anchors around 2%") into the Methodology tab or a new glossary.
  - `annual_rent_escalation` — `app.py:284-288`. Target: *"Assumed yearly rent growth. German rents are capped by Mietspiegel/Mietpreisbremse — 1.5–2.5 % is typical."*
  - `expected_vacancy_months_per_year` — `app.py:292-296`. Target: *"Months per year the flat is empty between tenants. 0.15 = hot city, 1.0+ = rural."*
  - `current_monthly_rent_warm_eur` — `app.py:331-336`. Target: *"What you currently pay in all-inclusive rent (Warmmiete + utilities). Buying replaces this cost — the Summary uses it to compare."*
  - `marginal_tax_rate` — `app.py:413-420`. Target: *"Your top German income-tax rate (Grenzsteuersatz). Roughly 30 % at €35k, 42 % above €68k single."*
- **Target.** Multiple sidebar inputs.
- **Effort.** M (word-by-word).
- **Frameworks.** Krug ("halve the words") • Plain Language.

### P0-7. "This is a sample scenario" framing banner

- **Problem.** The Bonn scenario is a worked example but isn't labelled as one — first-time user may think it's presenting *their* numbers. Audit §2.2, §2.5.
- **Fix.** Above the verdict banner (or immediately below it), render an `st.info` or a dismissible caption: *"📌 You're viewing our **Bonn-Poppelsdorf** sample. Edit any input on the left to try your own numbers — or pick a different sample in the Scenarios expander."*
- **Target.** New call in `main()` before/after `render_header` — `app.py:1302`.
- **Effort.** S.
- **Frameworks.** Explorable Explanations (worked example framing) • CLT.

### P0-8. Summary first; Start-here as a collapsed expander on top of Summary

- **Problem.** The user lands on "🚀 Start here" — onboarding prose — but has already seen the header KPIs. The onboarding is hit-or-miss depending on whether the user scrolls past the header tiles. Audit §3.7.
- **Fix.** Two changes:
  1. Reorder the tab list so Summary is first: `["📋 Summary", "🚀 New here?", "⚖ Buy vs Rent", …]`. Streamlit defaults to the first tab, so returning users land on the answer.
  2. At the top of Summary, add a collapsed expander: `st.expander("🚀 New here? 2-minute walkthrough", expanded=False)` whose body is the 3-step walkthrough (cloned from `tab_getting_started`, `app.py:1069-1081`). The full Start-here page stays as tab 2 for deep reference.
- **Target.** `main()` — `app.py:1304-1315`; `tab_summary` — `app.py:503` top.
- **Effort.** M.
- **Frameworks.** Nielsen H10 (help in-context) • Krug (first-plausible-click) • JTBD.

---

## P1 — Educational depth (Goal B)

### P1-9. Show rates in Purchase costs table labels

- **Problem.** The Summary's Purchase costs table shows EUR values without revealing the underlying rate — user can't check or learn. All three rates are in `rules_de.py` (6.5 % NRW Grunderwerbsteuer, 3.57 % Maklerprovision, 2 % Notary + Grundbuch). Audit §4.1, §4.6.
- **Fix.** Change row labels in `tab_summary` to include the rate:
  - `"Purchase price"` → `"Purchase price"`
  - `"Grunderwerbsteuer"` → `"Grunderwerbsteuer (6.5 % NRW — property transfer tax)"`
  - `"Maklerprovision"` → `"Maklerprovision (3.57 % — buyer's share of agent fee)"`
  - `"Notary + Grundbuch"` → `"Notar + Grundbuch (~2 % — closing fees)"`
  - `"Initial renovation"` → `"Initial renovation (capitalized, depreciated via AfA)"`
- **Target.** `app.py:687-694`.
- **Effort.** S.
- **Frameworks.** Plain Language • Nielsen H2 (real-world match) • Dual Coding.

### P1-10. In-context gloss under Purchase costs table

- **Problem.** Even with P1-9, a non-German user may want a one-line gloss on what each item is *for*. Audit §1.2, §2.1, §3.3.
- **Fix.** Immediately below the table, add an `st.expander("What are these fees?", expanded=False)` containing a 4-bullet list:
  - *Grunderwerbsteuer* — one-time property-transfer tax. Varies by Bundesland; NRW is currently 6.5 %.
  - *Maklerprovision* — estate-agent commission. Since 2020, the buyer covers ~half (≈3.57 % incl. VAT in NRW).
  - *Notar + Grundbuch* — notary and land-registry fees. Legally required for any property transfer; roughly 2 % of price combined.
  - *Initial renovation* — if you're doing major work in the first 3 years after purchase, it may be treated as *Herstellungskosten* (added to the depreciation basis) rather than immediately deductible (*Erhaltungsaufwand*).
- **Target.** `app.py:696`, after the `st.dataframe(df, …)`.
- **Effort.** M.
- **Frameworks.** Plain Language • Nielsen H10 • Dual Coding (text + table).

### P1-11. Glossary expander in Start-here tab

- **Problem.** The Start-here tab walks through each sidebar section but offers no alphabetical lookup — a user who sees "Hausgeld" in the table can't find its definition quickly. Audit §2.1 (H10), §4.6.
- **Fix.** At the bottom of `tab_getting_started` (before "What to read after this"), add a new `st.expander("📖 Glossary of German terms (A–Z)", expanded=False)`. Contents are every term flagged **⚠ marginal** or **❌ gap** in the audit's coverage matrix (§4), rendered as a two-column markdown table: *Term* | *One-line definition*. Around 25 entries.
- **Sketch.**
  ```markdown
  | Term | Plain meaning |
  | AfA | Linear depreciation of the building over 40 / 50 / 33⅓ years. Available only in rent mode. |
  | Anschaffungsnaher Aufwand | Renovations in the first 3 years >15 % of building value get reclassified as capital spend, not expense. |
  | Bodenrichtwert | Official land value per m² in your area. Look up on BORIS NRW. |
  | Grunderwerbsteuer | One-off property-transfer tax. 6.5 % in NRW; 3.5 – 6.5 % elsewhere. |
  ...
  ```
- **Target.** `tab_getting_started()` — `app.py:1050-1204`.
- **Effort.** M.
- **Frameworks.** Nielsen H10 • Plain Language • Dual Coding.

### P1-12. Chart captions with insight sentences

- **Problem.** Most charts have a title but no caption stating what to look at. Dual-channel learning is broken — visual served alone. Audit §2.7, §3.5, §3.6.
- **Fix.** After each `st.plotly_chart(...)` call, add an `st.caption(...)` with an insight-oriented sentence. Examples:
  - Cash flow bar chart (`app.py:815`): *"Red/orange = money out; green = money in; black line = net per year. Where the black line crosses zero, rent income starts covering all costs."*
  - Cumulative position chart (`app.py:826`): *"Total wealth change from this property. Positive means it pays back; negative means it costs more than it earns, cumulatively."*
  - Debt balance stack (`app.py:907`): *"Each colour band is one loan. The black dashed line shows total debt — the steeper it falls, the faster you're deleveraging."*
  - Capex timeline bubbles (`app.py:977`): *"Each bubble is a scheduled renovation; bigger = more expensive. Purple = capitalised (depreciated via AfA); blue = immediately deductible."*
  - Tax bars (`app.py:1037`): *"Green = taxable rent income; other colours = deductions that shrink it. Black line = your taxable result — if it's below the green bar, deductions are doing their job."*
- **Target.** All `tab_*` functions that call `st.plotly_chart`.
- **Effort.** M (~10 charts × 5 min each).
- **Frameworks.** Dual Coding • Explorable Explanations.

### P1-13. Cross-mode verdict on Live-vs-Rent tab

- **Problem.** The tab shows two mode summaries side-by-side plus a 50-year chart, leaving the user to compare 13 numbers across two columns. No explicit winner sentence. Audit §3.4.
- **Fix.** Just below the tab heading (`app.py:732`), render a one-sentence verdict computed from the two `result` objects. Template:
  - If `result_rent.cashflow['cumulative'].iloc[-1] > result_live.cashflow['cumulative'].iloc[-1]`: *"Over 50 years, **rent mode** ends ahead by €X. **Live mode** costs less in year 1 by €Y / month."*
  - Else: *"Over 50 years, **live mode** ends ahead by €X. **Rent mode** costs less in year 1 by €Y / month."*
- **Target.** `tab_compare()` — `app.py:730-776`.
- **Effort.** S.
- **Frameworks.** JTBD • Dual Coding • Krug.

### P1-14. "Next steps" panel on Summary

- **Problem.** After the verdict, there's no guidance on what to do next. JTBD related-job gap. Audit §2.8.
- **Fix.** After the pass/fail strip in `tab_summary` (`app.py:670` `st.markdown("---")`), add a `st.expander("✅ What now?", expanded=True)` that branches on the number of failed checks:
  - **0–1 failures** → *"Looks affordable. Next steps: (1) ask your bank for a Finanzierungszusage with these numbers, (2) verify the Bodenrichtwert on [BORIS NRW](https://www.boris.nrw.de/), (3) request the Energieausweis from the seller. Not financial advice — confirm with a Steuerberater if this is a rental."*
  - **2+ failures** → *"Some rules are stretched. Before pushing ahead: (1) try raising initial capital or lowering the price on the sidebar, (2) read the failed rules above — each links to what to adjust, (3) if it still doesn't pencil out, consider waiting or looking at a cheaper market."*
- **Target.** `tab_summary` — `app.py:670`.
- **Effort.** M.
- **Frameworks.** JTBD (next-step) • Nielsen H10 • Plain Language.

### P1-15. "Try this" nudge under Live-vs-Rent chart

- **Problem.** The app is a reactive document but never invites the user to try a what-if. Audit §2.5.
- **Fix.** Under the 50-year chart in `tab_compare` (after `st.plotly_chart(fig, …)` at `app.py:763`), add `st.caption("💡 Try raising the Horizon slider in Global assumptions — watch where the two lines cross over.")`.
- **Target.** `app.py:763`.
- **Effort.** S.
- **Frameworks.** Explorable Explanations (guided counterfactual) • Dual Coding.

### P1-16. Rewrite jargon labels to plain language + term

- **Problem.** Several sidebar labels use raw German or financial jargon the target persona doesn't share. Audit §2.6, §3.1.
- **Fix.** Adopt the same pattern already used for *Monthly rent (Kaltmiete, €)* — English first, German in parentheses:
  - `Hausgeld (€/mo, rent mode)` → `Building fee (Hausgeld) — €/mo, rent mode` (`app.py:360`)
  - `Grundsteuer rate (% of price)` → `Property tax rate (Grundsteuer, % of price)` (`app.py:354`)
  - `Schornsteinfeger` / `Betriebskostenabrechnung` in tooltips — introduce with English first
  - `Year-1 monthly burden on salary` → `Year-1 monthly net cost` (`app.py:488`, still in header only if kept)
  - Mode radio labels `live` / `rent` → `Live in it` / `Rent it out` (`app.py:132`)
  - Live-vs-Rent tab label: `⚖ Live vs Rent` → `⚖ Buy vs Rent` — reads more naturally to an English speaker (`app.py:1307`)
- **Target.** Multiple.
- **Effort.** S.
- **Frameworks.** Plain Language • Nielsen H2.

### P1-17. Elevate "NOT modelled" limitations block

- **Problem.** The "What this tool does NOT model" block is one of the strongest transparency surfaces in the app — but it sits mid-Methodology-tab. A user who trusts the app without reading it gets over-confident numbers. Audit §3.8.
- **Fix.** Duplicate or move the block into a `st.expander("⚠ What this tool does NOT model", expanded=False)` at the *top* of the Summary tab (between the verdict and the detail tables). Keep the copy in Methodology too for reference.
- **Target.** `app.py:1236-1242` → duplicated near `app.py:670`.
- **Effort.** S.
- **Frameworks.** Goal-B transparency • Nielsen H10 • JTBD.

---

## P2 — Polish

### P2-18. Footer: disclaimer + sources link

- **Problem.** The footer is attribution only. No disclaimer, no "not financial advice", no link to `REFERENCES.md`. Audit §3.9.
- **Fix.** Replace the footer body with three lines: attribution (existing) + *"Not financial advice — verify with a Steuerberater or your bank. See [REFERENCES.md](…) for sources."* + current model version / last-updated date.
- **Target.** `_render_footer()` — `app.py:1328-1337`.
- **Effort.** S.
- **Frameworks.** Goal-B transparency.

### P2-19. Friendlier error fallback (no raw traceback)

- **Problem.** A runtime error shows `st.exception(e)` — Python traceback visible to non-developers. Audit §2.1 (H9).
- **Fix.** Replace `st.exception(e)` with `st.caption(f"Internal detail: {type(e).__name__}: {e}")` and a recovery nudge *"Try reloading the default scenario from the Scenarios expander in the sidebar."* Log the full exception to the console via `import traceback; traceback.print_exc()`.
- **Target.** `app.py:1294-1297`.
- **Effort.** S.
- **Frameworks.** Nielsen H9.

### P2-20. Mode indicator on per-tab sub-headers

- **Problem.** Per-tab subtitle only says `Cash flow — RENT mode` (`app.py:795`). Easy to miss at a glance. Audit §2.1 (H6).
- **Fix.** Prefix each detail tab's heading with a coloured pill: `st.markdown(f"## Cash flow  :violet-background[{s.mode.upper()} mode]")`. Streamlit supports `:color-background[…]` markup as of 1.30+.
- **Target.** `tab_cashflow`, `tab_costs`, `tab_debt`, `tab_capex`, `tab_tax`.
- **Effort.** S.
- **Frameworks.** Nielsen H6 (recognition).

### P2-21. Widen marginal tax slider to 10 % – 55 %

- **Problem.** The slider clamps 20 % – 50 %, excluding low earners (part-time, parental leave) and high earners (Kirchensteuer above Reichensteuersatz). Audit §2.1 (H5).
- **Fix.** Change `st.slider("Marginal tax rate (rent mode)", 0.20, 0.50, …)` to `st.slider("Marginal tax rate (Grenzsteuersatz)", 0.10, 0.55, …)`.
- **Target.** `app.py:412-420`.
- **Effort.** S.
- **Frameworks.** Nielsen H5.

### P2-22. `min_value=0` on capex cost column

- **Problem.** Capex editor accepts negative costs; would break sums downstream.
- **Fix.** In the `column_config` dict (`app.py:445`), change `"Cost (€)": st.column_config.NumberColumn(format="%.0f")` → `st.column_config.NumberColumn(format="%.0f", min_value=0)`.
- **Target.** `app.py:445`.
- **Effort.** S.
- **Frameworks.** Nielsen H5.

### P2-23. Table of contents inside Methodology tab

- **Problem.** Methodology is a long markdown block with no in-tab nav. Audit §3.8.
- **Fix.** Add 4 markdown anchor links at the top of `tab_methodology`: *Key German rules • Component lifecycles • What this tool does NOT model • Citations.* Use `[Key rules](#key-german-rules)` anchor syntax (works in Streamlit markdown).
- **Target.** `app.py:1207-1262`.
- **Effort.** S.
- **Frameworks.** Nielsen H10.

### P2-24. Legend key + colour-blind affordance on 50-year chart

- **Problem.** Live/Rent colours (red/blue) are fine for most users, but no visible legend key; Plotly's auto-legend is a small element at chart's top-right. Audit §3.4.
- **Fix.** Add `line=dict(color="#E15759", width=3, dash="solid")` for Live and `line=dict(color="#4E79A7", width=3, dash="dash")` for Rent. Add a caption above the chart: *"Red solid = live; blue dashed = rent."*
- **Target.** `tab_compare` — `app.py:754-763`.
- **Effort.** S.
- **Frameworks.** Accessibility • Dual Coding.

### P2-25. Mark modified scenario in header title

- **Problem.** After editing inputs, the title still reads the scenario's original name — user can lose track of whether they're looking at "Bonn sample" or "Bonn with my edits." Audit §2.1 (H1), §3.2.
- **Fix.** Track a snapshot of the loaded scenario (e.g., `st.session_state.scenario_original = deepcopy(load_scenario(...))` on load) and compare via a hash of key fields. If different, render the title as `🏠 {name} *(modified)*`.
- **Target.** `init_scenario` + `render_header` — `app.py:62-68, 470`.
- **Effort.** S.
- **Frameworks.** Nielsen H1 (visibility of status).

---

## Sequencing recommendation

Ship in three waves:

1. **Wave 1 (P0 only, ~half-day total).** Items 1–8. Ship before anything else — they address the Goal-A blocker: first-open disengagement. Test by asking a non-German friend to open the app and state, in five seconds, what the verdict is.
2. **Wave 2 (P1, ~half-day).** Items 9–17. These turn the app from "a calculator with tooltips" into "a calculator that teaches." Test by asking the same friend: "without leaving the app, can you tell me what Grunderwerbsteuer is?"
3. **Wave 3 (P2, ~2 hours).** Items 18–25. Polish pass; no single one is critical, but together they lift trust and consistency.

## What's explicitly NOT recommended

Keeping the "no major restructuring" constraint honest:

- **Do not** split `app.py` into multi-page. The app is coherent; splitting would move complexity to session-state plumbing and lose the reactive single-file benefit.
- **Do not** swap Streamlit for Dash / Gradio / custom React. The Streamlit auto-rerun loop is the explorable-explanation foundation; it would take weeks to rebuild.
- **Do not** redesign the calculation engine to add "quick mode" simplifications. Goal B requires the real German rules; simplifying the engine would break transparency.
- **Do not** add telemetry to measure these changes. The privacy note at `app.py:1063-1067` is an explicit product commitment — don't trade it for analytics.
