# Actionable items v2 — immokalkul

Concrete fixes derived from [`audit.md`](./audit.md), using the frameworks in [`research.md`](./research.md). Same constraint as v1: **no major restructuring** — single-file `app.py`, Streamlit primitives, no engine changes.

v1 closed the Goal-A blocker (the verdict banner). v2's items address the *next layer* — density on Summary, drift between duplicated content, residual coverage gaps, and small data-quality holes.

## How this file is organised

- **P0** — first-impression density / Summary bottleneck. Do first; cheap, high-leverage.
- **P1** — educational depth gaps + drift cleanup.
- **P2** — polish, microcopy, hygiene.

Each item carries:
- **Problem** — one-line summary with link to the audit finding
- **Fix** — concrete change (with code sketch where useful)
- **Target** — `file:line` to modify
- **Effort** — S (< 30 min), M (30-120 min), L (half-day+)
- **Frameworks** — which lenses motivate it

## Priority matrix (at-a-glance)

| # | Item | Priority | Effort | Goal |
|---|---|---|---|---|
| 1 | Mode badge on Summary + Buy-vs-Rent | P0 | S | A |
| 2 | Default `What now?` to closed; default detail tables visible | P0 | S | A |
| 3 | Sub-group Operating costs into 3 nested expanders | P0 | M | A |
| 4 | Use property name (not YAML key) in sample banner | P0 | S | A |
| 5 | Drop the duplicate live-mode warning on Buy-vs-Rent | P0 | S | A |
| 6 | Single-source the "NOT modelled" + walkthrough text | P0 | M | A+B |
| 7 | Finish the long-tooltip rewrite (Cost inflation, Hausgeld, Grundsteuer) | P0 | S | A |
| 8 | Halve the Capex smoothed-reserve caption | P0 | S | A |
| 9 | Add Solidaritätszuschlag, Sondereigentum, Grundschuld, Sanierungspflicht to Glossary | P1 | S | B |
| 10 | Move Verlustverrechnung explanation adjacent to the Tax chart caption | P1 | S | B |
| 11 | Caption the Costs pie chart and Debt payment-breakdown chart | P1 | S | B |
| 12 | Add description per scenario in the Scenarios dropdown | P1 | M | A+B |
| 13 | Caption the Year-1 monthly cash-flow table on Buy-vs-Rent | P1 | S | B |
| 14 | Add `(Notar + Grundbuch)` to the Notary purchase row | P1 | S | B |
| 15 | Echo failed rule names inside `What now?` (when ≥2 fail) | P1 | S | A+B |
| 16 | Cross-link Capex annual-reserve chart from Methodology Petersche section | P1 | S | B |
| 17 | Make `_is_scenario_modified` watch loans + capex tables | P1 | M | A |
| 18 | Add a "what each scenario teaches" caption under the dropdown | P1 | S | B |
| 19 | "Try this" nudges on Cash flow, Debt, Tax tabs | P1 | M | B |
| 20 | Use horizon variable in the "50-yr cumulative" KPI label | P2 | S | B |
| 21 | `min_value=0` on capex year and loan rate columns | P2 | S | — |
| 22 | Caption + label "Adaptive debt ceiling" instead of "Total monthly debt budget" | P2 | S | B |
| 23 | Glossary entry literal-translation pass (AfA = "write-off for wear", …) | P2 | S | B |
| 24 | Reset-section affordance for loans + capex editors | P2 | M | A |
| 25 | Footer: confirm version / last-updated line | P2 | S | B |

---

## P0 — Calm down the Summary tab and finish the v1 sweep

### P0-1. Mode badge on Summary and Buy-vs-Rent headings

- **Problem.** Per-tab mode badges (`:violet-background[RENT mode]`) shipped on detail tabs (`app.py:898, 961, 1000, 1070, 1178`), but Summary (`app.py:545`) and Buy vs Rent (`app.py:796`) — the two surfaces whose semantics flip with mode — have *no* badge. A user toggling modes can't see at a glance which they're in. Audit §2.1 (H6), §3.3, §3.4.
- **Fix.** Two one-line changes:
  - `app.py:545` — `st.markdown("## Summary")` → `st.markdown(f"## Summary  :violet-background[{s.mode.upper()} mode]")`
  - `app.py:796` — `st.markdown("## Buy vs Rent comparison")` → `st.markdown(f"## Buy vs Rent comparison  :violet-background[BOTH MODES]")` (this tab computes both, so the badge says so).
- **Target.** `tab_summary`, `tab_compare`.
- **Effort.** S.
- **Frameworks.** Nielsen H6 (recognition over recall) • H4 (consistency).

### P0-2. Default `What now?` to closed; default detail tables visible

- **Problem.** `✅ What now?` on Summary defaults `expanded=True` (`app.py:694`) — the only expander on Summary that does. It draws the eye to next-steps prose *above* the actual numerical receipts (Property/Purchase/Financing/AfA tables at `app.py:720-791`), which is what a user takes to a bank. Krug satisficer reads "What now?" and skips the receipts. Audit §2.4, §3.3.
- **Fix.** Change `expanded=True` → `expanded=False` at `app.py:694`. Optional follow-up: add a one-liner immediately before the expander, e.g. `st.markdown("**Want next-step guidance?** Open the panel below.")` so the affordance is still visible without grabbing the scroll.
- **Target.** `app.py:694`.
- **Effort.** S.
- **Frameworks.** Krug (satisficing) • Progressive Disclosure • Nielsen H8.

### P0-3. Sub-group Operating costs into 3 nested expanders

- **Problem.** Operating costs expander still has 8 inputs in a flat list (`app.py:393-443`) — same as v1 §3.1, not addressed. Opening it is still a wall of dense labels. Audit §2.1 (H8), §2.3, §3.1.
- **Fix.** Inside the Operating costs expander, group as nested expanders (mirror what Property does for Tax-relevant details):
  - `with st.expander("⚡ Utilities", expanded=False):` — gas, electricity, municipal (`app.py:399-407, 429-433`)
  - `with st.expander("🏛 Property tax & insurance", expanded=False):` — Grundsteuer, building insurance, liability (`app.py:408-415, 434-443`)
  - `with st.expander("🏘 WEG / management", expanded=False):` — Hausgeld, administration (`app.py:416-428`)
- **Sketch.** Each nested block keeps the existing `c.field = st.number_input(...)` lines verbatim; only the surrounding `with` is added. Layout is identical when opened.
- **Target.** `app.py:393-443`.
- **Effort.** M.
- **Frameworks.** Progressive Disclosure • CLT (intrinsic chunking) • Nielsen H8.

### P0-4. Use property name (not YAML key) in sample-scenario banner

- **Problem.** Sample banner shows the raw YAML basename (`bonn_poppelsdorf`) — snake_case + no umlauts — next to the polished title (`🏠 Bonn-Poppelsdorf 3-Zimmer`). Krug "real-world match" + Plain Language. Audit §2.1 (H2), §2.4, §3.2.
- **Fix.** At `app.py:506-511`, replace `source` (the YAML key) with `s.property.name` in the banner text:
  ```python
  st.info(
      f"📌 You're viewing the **{s.property.name}** sample scenario. "
      f"Edit any input on the left to try your own numbers — or pick a "
      f"different sample in the Scenarios expander.")
  ```
- **Target.** `render_header` — `app.py:506-511`.
- **Effort.** S.
- **Frameworks.** Nielsen H2 • Plain Language.

### P0-5. Drop the duplicate live-mode warning on Buy-vs-Rent

- **Problem.** The same `current_monthly_rent_warm_eur == 0` warning fires on both Summary (`app.py:547-554`) and Buy-vs-Rent (`app.py:799-804`). Same trigger, same wording. CLT redundancy + Nielsen H4 (consistency). Audit §2.1 (H4), §2.3, §3.3, §3.4.
- **Fix.** Delete the Buy-vs-Rent block (`app.py:799-804`). Keep the Summary copy — it's seen first and contains the actionable instruction. If a user lands on Buy-vs-Rent first via a URL hash someday, they'll still see the chart's red line being low; the symptom is visible without the duplicate banner.
- **Target.** `app.py:799-804`.
- **Effort.** S.
- **Frameworks.** Nielsen H4 • CLT redundancy • Progressive Disclosure.

### P0-6. Single-source the "NOT modelled" + walkthrough text

- **Problem.** Two pairs of duplicated copy already drifted:
  - "What this tool does NOT model" — Summary expander (`app.py:570-581`) vs Methodology body (`app.py:1498-1504`). Different wording for the same items.
  - 3-step walkthrough — Summary expander (`app.py:557-567`) vs "New here?" tab (`app.py:1250-1261`). Same intent, different sentences.

  Drift = trust loss; user catching the difference loses confidence in either source. Audit §2.1 (H10), §2.2 (CLT redundancy), §3.3, §3.10, §3.11.
- **Fix.** Extract each block into a module-level constant, render in both places:
  ```python
  NOT_MODELLED_MD = """
  - **Property appreciation** — …
  - **Loss carryforward** — …
  - **Sonderumlagen** (WEG special assessments) — …
  - **Denkmal-AfA** (§ 7i EStG) and **§ 7b Sonder-AfA** — not yet implemented.
  - **VAT / Kirchensteuer nuances** beyond the marginal rate.
  """
  WALKTHROUGH_MD = """1. **Pick a scenario** … 2. **Tweak inputs** … 3. **Read this tab** …"""
  ```
  Then both call sites (`app.py:570-581, 1498-1504, 557-567, 1250-1261`) reference the same constant. Stops drift; one place to update.
- **Target.** Module-level constants near `app.py:50-90` helpers; replace inline strings at the four sites.
- **Effort.** M.
- **Frameworks.** Nielsen H10 • Plain Language • Trust.

### P0-7. Finish the long-tooltip rewrite

- **Problem.** v1 P0-6 was a partial sweep. Three tooltips remain ≥ 4 sentences / ~80 words: Cost inflation (`app.py:464-470`), Hausgeld (`app.py:418-423`), Grundsteuer rate (`app.py:412-415`). Krug "halve the words" + Plain Language microcopy. Audit §2.1 (H8), §2.4, §3.1.
- **Fix.** Rewrite each to ≤ 2 sentences. Move long-form context (ECB target, Bundesmodell history, WEG explanation) into the Glossary or Methodology where a *reader* can find it.
  - Cost inflation: *"Yearly escalation applied to operating costs and capex. Default 2% = ECB target; bump to 3% if you assume the post-2022 regime persists."*
  - Hausgeld: *"Monthly WEG fee for shared common areas. Typical: €2.50–4.50 per m². Set 0 for a freestanding house."*
  - Grundsteuer rate: *"Property tax as a share of price. Since the 2025 reform, 0.15–0.35% is typical depending on Bundesland; 0.2% is a safe default."*
- **Target.** `app.py:412-415, 418-423, 464-470`.
- **Effort.** S.
- **Frameworks.** Krug • Plain Language.

### P0-8. Halve the Capex smoothed-reserve caption

- **Problem.** The caption at `app.py:1154-1162` is 6 sentences over 9 lines. The Erhaltungsrücklage / Hausgeld payoff is buried in the last 2 sentences. Audit §2.1 (H8), §2.2 (CLT — germane throttled by extraneous), §3.8.
- **Fix.** Split into two visual blocks:
  ```python
  st.caption(
      f"**Blue bars** = lumpy actual spend. **Red dashed line** = "
      f"{eur(steady_reserve_yr)}/yr — the steady reserve a prudent owner "
      f"would accrue (`Σ cost / lifetime`).")
  st.caption(
      f"💡 In a WEG, this steady amount is what the **Erhaltungsrücklage** "
      f"is for; it's funded out of your **Hausgeld** for the "
      f"Gemeinschaftseigentum portion.")
  ```
  Two short captions read better than one long one and split the *what* (chart legend) from the *why* (concept payoff).
- **Target.** `app.py:1154-1162`.
- **Effort.** S.
- **Frameworks.** Krug • Dual Coding • CLT.

---

## P1 — Educational depth + drift cleanup

### P1-9. Glossary entries for missing terms

- **Problem.** Solidaritätszuschlag, Sondereigentum, Grundschuld, Sanierungspflicht, Erhaltungsrücklage, Kirchensteuer either appear in tooltips only or are referenced without a Glossary entry. Audit §4.1, §4.2, §4.5.
- **Fix.** Add 6 rows to the Glossary table at `app.py:1380-1447`, alphabetised in place. Sketch:
  - **Erhaltungsrücklage** — WEG maintenance reserve (§ 19 WEG). Funded out of your Hausgeld; pays for shared-area capex.
  - **Grundschuld** — Land-charge registered against the property as bank collateral. Standard for German mortgages; you'll meet it at the notary.
  - **Kirchensteuer** — Church tax, 8–9% of income tax for registered members. Not modelled here.
  - **Sanierungspflicht** — Energy-renovation obligation under GEG (heating, insulation, windows). Especially relevant for Altbau buyers post-2024.
  - **Sondereigentum** — Your private apartment unit inside a WEG (vs. Gemeinschaftseigentum).
  - **Solidaritätszuschlag (Soli)** — 5.5% surcharge on income tax for high earners. Folded into the marginal-rate input.
- **Target.** `app.py:1380-1447`.
- **Effort.** S.
- **Frameworks.** Plain Language • Nielsen H10.

### P1-10. Move Verlustverrechnung explanation adjacent to the Tax chart caption

- **Problem.** The Tax bar+line chart shows the black "taxable income" line going negative in early years. The chart caption (`app.py:1216-1217`) explains colours but **not the negative line**. The Verlustverrechnung paragraph that does (`app.py:1222-1225`) is below the totals lines, separated from the chart by 4 lines of unrelated content. A scanner who reads the caption and skims down hits the totals first. Audit §1.2, §3.9.
- **Fix.** Move the Verlustverrechnung paragraph (`app.py:1222-1225`) to *immediately follow* the chart caption (`app.py:1216-1217`):
  ```python
  st.plotly_chart(fig, width="stretch")
  st.caption("Green = taxable rent income; other colours = deductions. "
             "Black line = your taxable result. **Negative values are "
             "refunds**: rental losses offset other income at your marginal "
             "rate (Verlustverrechnung, § 10d EStG), typical in early years "
             "when AfA + interest + costs exceed rent.")
  st.markdown(f"**Total tax over {s.globals.horizon_years} years:** …")
  st.markdown(f"**Marginal rate applied:** …")
  ```
- **Target.** `app.py:1215-1225`.
- **Effort.** S.
- **Frameworks.** Dual Coding • Nielsen H10 • Plain Language.

### P1-11. Caption the Costs pie chart and Debt payment-breakdown chart

- **Problem.** Two charts in the app have no `st.caption`: Costs pie (`app.py:993-995`) and Debt annual-payment-breakdown bar (`app.py:1033-1040`). Inconsistent with every other chart since v1's caption sweep. Audit §2.7, §3.6, §3.7.
- **Fix.** Add a one-sentence insight caption after each chart:
  - Costs pie (after `app.py:995`): *"The biggest slice is your single best target if you want to lower running costs — Hausgeld and Grundsteuer typically dominate for apartments."*
  - Debt payment breakdown (after `app.py:1040`): *"Each colour band is one loan's annual payment. When a loan clears, its band drops out — the remaining loans take the freed capacity if any are flagged Adaptive."*
- **Target.** `app.py:995, 1040`.
- **Effort.** S.
- **Frameworks.** Dual Coding.

### P1-12. Per-scenario description in the Scenarios dropdown

- **Problem.** Four built-in scenarios (Bonn, Munich, Berlin, Köln) span apartment-vs-house and Altbau-vs-Neubau — a *natural curriculum* for the persona. The dropdown shows snake_case keys with no hint of what each teaches. Audit §2.5, §2.8, §3.1.
- **Fix.** Define a `SCENARIO_DESCRIPTIONS` dict near the YAML loaders (`app.py:40-71`):
  ```python
  SCENARIO_DESCRIPTIONS = {
      "bonn_poppelsdorf": "🏘 Apartment in a 1990s Altbau (rent mode default).",
      "berlin_altbau":    "🏘 Pre-WWI Altbau apartment — high AfA basis, capex risk.",
      "munich_neubau":    "🏘 Post-2023 Neubau — newer 3% AfA rate, low capex.",
      "koeln_einfamilienhaus": "🏠 Freestanding house (live mode default).",
  }
  ```
  Render below the selectbox at `app.py:124-128`:
  ```python
  st.caption(SCENARIO_DESCRIPTIONS.get(scenario_key, ""))
  ```
- **Target.** Constants near `app.py:40`; new caption near `app.py:128`.
- **Effort.** M.
- **Frameworks.** Explorable Explanations (worked examples) • JTBD related-job.

### P1-13. Caption the Year-1 monthly cash-flow table on Buy-vs-Rent

- **Problem.** The table at `app.py:860-879` follows the chart's verdict + try-this nudge but carries no caption. After being told the verdict, the user lands on a 6-row table with no instruction on what comparison to make. Audit §2.7, §3.4.
- **Fix.** Add immediately before the table heading at `app.py:860`:
  ```python
  st.caption("Where the year-1 monthly burden of each mode comes from. "
             "Loan + Op costs - Rent income (- Avoided rent, in live mode) "
             "= Net cash burden.")
  ```
- **Target.** `app.py:860`.
- **Effort.** S.
- **Frameworks.** Dual Coding • Plain Language.

### P1-14. Add the German term to the Notary purchase-cost row

- **Problem.** The Purchase costs table label at `app.py:739` reads `"Notary + land registry (~2%)"` — it's the only row that *drops* the German term. Inconsistent with the row above (`Property transfer tax (Grunderwerbsteuer, 6.5% NRW)`) and breaks the term-lookup chain for *Notar + Grundbuch*. Audit §2.1 (H2), §2.6, §4.1.
- **Fix.** `app.py:739` — `("Notary + land registry (~2%)", p.notary_grundbuch)` → `("Notary + land registry (Notar + Grundbuch, ~2%)", p.notary_grundbuch)`.
- **Target.** `app.py:739`.
- **Effort.** S.
- **Frameworks.** Plain Language • Nielsen H2 • H4.

### P1-15. Echo failed rule names inside `What now?`

- **Problem.** The "What now?" expander branches on `n_fail ≤ 1` vs `≥ 2` (`app.py:694-716`), but doesn't name the *specific* failed rules. A user reading "Some rules are stretched. Try raising Initial capital or lowering Purchase price" has to scroll up to find which rules failed. Audit §2.8, §3.3.
- **Fix.** When `n_fail ≥ 2`, prefix the markdown with a bulleted list of `afford["failed"]`:
  ```python
  st.markdown(
      "Some rules are stretched. Specifically:\n"
      + "\n".join(f"- {f}" for f in afford["failed"])
      + "\n\nBefore pushing ahead:\n…")
  ```
- **Target.** `app.py:706-716`.
- **Effort.** S.
- **Frameworks.** JTBD • Nielsen H6 (recognition).

### P1-16. Cross-link the Capex annual-reserve chart from Methodology

- **Problem.** The Capex annual-bar + smoothed-reserve chart (`app.py:1139-1162`) is the strongest new explorable since v1 — it visualises the Petersche Formel concept. But the Methodology Petersche section (`app.py:1486-1488`) doesn't mention this chart. Reader of Methodology has no idea the visualisation exists. Audit §2.5, §3.8, §3.11.
- **Fix.** Add one sentence at the end of the Petersche bullet (`app.py:1488`): *"The **Capex tab** plots the resulting steady-reserve line over the lumpy actual spend so you can see the gap year-by-year."*
- **Target.** `app.py:1486-1488`.
- **Effort.** S.
- **Frameworks.** Explorable Explanations • Dual Coding.

### P1-17. Make `_is_scenario_modified` watch loans + capex tables

- **Problem.** `_is_scenario_modified()` (`app.py:73-84`) compares only key scalar fields. Editing only the loans data-editor or capex editor leaves the title showing the original scenario name without `*(modified)*` — silently wrong for the most common power-user edits. Audit §2.1 (H1), §3.2.
- **Fix.** Extend the helper to compare the loans list and user_capex list as well. Sketch:
  ```python
  def _is_scenario_modified() -> bool:
      orig = st.session_state.get("scenario_original")
      cur  = st.session_state.get("scenario")
      if not orig or not cur: return False
      if cur.property != orig.property: return True
      if cur.financing.initial_capital_eur != orig.financing.initial_capital_eur: return True
      if [(l.name, l.principal, l.interest_rate, l.monthly_payment, l.is_annuity, l.is_adaptive)
          for l in cur.financing.loans] != \
         [(l.name, l.principal, l.interest_rate, l.monthly_payment, l.is_annuity, l.is_adaptive)
          for l in orig.financing.loans]: return True
      if [(c.name, c.cost_eur, c.year_due, c.is_capitalized) for c in cur.user_capex] != \
         [(c.name, c.cost_eur, c.year_due, c.is_capitalized) for c in orig.user_capex]: return True
      return False
  ```
- **Target.** `app.py:73-84`.
- **Effort.** M.
- **Frameworks.** Nielsen H1.

### P1-18. "What each scenario teaches" caption under the dropdown

- **Problem.** Same surface as P1-12. Even after adding descriptions, a first-timer doesn't see the *why* the four scenarios were chosen as a set (apartment-vs-house, Altbau-vs-Neubau, rent-default-vs-live-default). Audit §2.5, §2.8.
- **Fix.** Below the SCENARIO_DESCRIPTIONS caption (P1-12), one extra `st.caption`: *"Together these four sample a typical German buyer's choice space — switch between them to see how Altbau vs Neubau changes AfA, and apartment vs house changes Hausgeld and capex."*
- **Target.** `app.py:128`.
- **Effort.** S.
- **Frameworks.** Explorable Explanations.

### P1-19. "Try this" nudges on Cash flow, Debt, Tax tabs

- **Problem.** Buy-vs-Rent has a "💡 Try raising the Horizon slider" caption (`app.py:857-858`) — the only counterfactual prompt in the app. The Cash flow, Debt, and Tax tabs all have explorable parameters that affect them but never invite the user to change them. Audit §2.5, §3.5, §3.7, §3.9.
- **Fix.** One `st.caption("💡 …")` per tab, immediately under the most informative chart:
  - Cash flow (after `app.py:925`): *"💡 Raise rent escalation by 1% on the sidebar — watch the green bars compound and the black net line pull above zero earlier."*
  - Debt (after `app.py:1028`): *"💡 Toggle a loan's **Adaptive?** flag in the loans editor — watch the black total-debt line bend after the first loan clears."*
  - Tax (after the new caption from P1-10): *"💡 Lower your marginal rate on the sidebar — see how the red interest deduction loses value when the rate is lower."*
- **Target.** `app.py:925, 1028, ~1218`.
- **Effort.** M (3 captions × ~10 min each, including phrasing).
- **Frameworks.** Explorable Explanations.

---

## P2 — Polish

### P2-20. Use the horizon variable in the "50-yr cumulative" KPI label

- **Problem.** Header KPI label is hardcoded "50-yr cumulative wealth" (`app.py:523`), but the engine respects `s.globals.horizon_years` (default 50, but the slider goes 10–60). User who sets horizon to 30 sees mismatched labelling. Audit §3.2.
- **Fix.** `app.py:522-527` — replace the hardcoded "50-yr" with `f"{s.globals.horizon_years}-yr cumulative wealth"`.
- **Target.** `app.py:522-527`.
- **Effort.** S.
- **Frameworks.** Nielsen H1 (status visibility).

### P2-21. `min_value=0` on capex year and loan rate columns

- **Problem.** Capex editor's Year column accepts negative offsets (silently dropped); loans editor's Rate column accepts negative rates. Audit §2.1 (H5), §3.1.
- **Fix.**
  - `app.py:466-480` — capex `column_config` for `Year due`: add `min_value=int(s.globals.today_year)` (or just `min_value=2020`).
  - `app.py:253-258` — loans `column_config` for `Rate (%)`: add `min_value=0.0`.
- **Target.** `app.py:253-258, 466-480`.
- **Effort.** S.
- **Frameworks.** Nielsen H5.

### P2-22. Rename "Total monthly debt budget" → "Adaptive debt ceiling"

- **Problem.** The label "Total monthly debt budget" (`app.py:233`) doesn't clarify that this is the **ceiling** that **adaptive loans** absorb up to. The (now correctly hidden) input only exists when an adaptive loan is flagged, but the name doesn't reflect that. Audit §3.1.
- **Fix.** `app.py:233-239` — rename label to `"Adaptive debt ceiling (€/mo, total across loans)"`. Tooltip can be shortened to one sentence: *"When any loan is flagged Adaptive, the engine increases its annuity to use up to this monthly ceiling."*
- **Target.** `app.py:233-239`.
- **Effort.** S.
- **Frameworks.** Plain Language • Nielsen H2.

### P2-23. Glossary literal-translation pass

- **Problem.** Several Glossary entries describe what a term *does* without translating what it literally *means*. The cheapest single-sentence teaching for a German term is its literal meaning (often half-revealing of the rule). Audit §2.6.
- **Fix.** Add a leading literal translation to the highest-traffic terms in the Glossary table at `app.py:1380-1447`. Examples:
  - **AfA** — *Absetzung für Abnutzung*, literally "write-off for wear". Linear depreciation of the building over 40 / 50 / 33⅓ years. Available only in rent mode.
  - **Anschaffungsnaher Aufwand** — literally "expenditure close to acquisition". Renovations …
  - **Erhaltungsaufwand** — literally "preservation expenditure". Routine maintenance …
  - **Herstellungskosten** — literally "production costs". Renovations that …
- **Target.** `app.py:1380-1447`.
- **Effort.** S.
- **Frameworks.** Plain Language • Dual Coding (verbal-channel double-tap).

### P2-24. Reset-section affordance for loans + capex editors

- **Problem.** No "reset this section to scenario defaults" affordance for the loans / capex tables. Only escape is reloading the YAML and losing every other edit. Audit §2.1 (H3), §3.1.
- **Fix.** Above each editor, add a small `st.button("↺ Reset to scenario defaults", key="reset_loans")` that sets the in-place scenario field back to a deepcopy of `st.session_state.scenario_original.financing.loans` (or `.user_capex`).
- **Target.** Above `app.py:242-291`; above `app.py:466-480`.
- **Effort.** M.
- **Frameworks.** Nielsen H3.

### P2-25. Footer: confirm version / last-updated line

- **Problem.** v1 P2-18 added disclaimer + sources link. Audit §3.12 couldn't fully verify whether a version / last-updated line is present.
- **Fix.** Inspect `_render_footer()` (around `app.py:1601-1614`); if missing, add a single line: `st.caption(f"App version: see [git history](https://github.com/nicofirst1/immokalkul/commits/main) — German rules current as of Q4 2025.")`
- **Target.** `_render_footer()`.
- **Effort.** S.
- **Frameworks.** Goal-B transparency.

---

## Sequencing recommendation

Three short waves again:

1. **Wave 1 (P0 — half a day).** Items 1–8. Reduces Summary density, finishes the v1 sweep, kills duplicate banners, fixes the YAML-key banner. Quickest payoff.
2. **Wave 2 (P1 — half a day).** Items 9–19. Closes residual coverage gaps, repairs drift, scaffolds counterfactuals on the detail tabs.
3. **Wave 3 (P2 — ~2 hours).** Items 20–25. Polish + small UX/data-quality holes.

## What's still NOT recommended

Same constraints as v1's note. Specifically v2-relevant non-recommendations:

- **Do not** turn the Glossary into a generated artifact (e.g. parsed from `rules_de.py`). The hand-written entries are the persona's plain-English layer; auto-generation would lose the voice.
- **Do not** introduce a "novice mode" toggle. The v1 fixes (collapsed expanders, nested Tax-relevant details) get the same effect without splitting the codebase.
- **Do not** redesign the tab strip into a wizard. The current tabs map cleanly onto the JTBD; a wizard would force linearity that the persona doesn't need after the verdict has landed.
- **Do not** add appreciation modelling, loss carry-back, or Denkmal-AfA to the engine just because they're listed in the "NOT modelled" expander. Those are deliberate scope choices.

## Open questions to surface before Wave 1

- **P0-6 single-source.** Should the canonical "NOT modelled" list live as a markdown asset in `data/` (loadable from both Summary and Methodology), or as a Python constant near the helpers? Constant is simpler; data file is cleaner for non-Python contributors.
- **P1-12 scenario descriptions.** Are the four built-in scenarios stable, or planned to grow? If they grow, the description dict should live alongside the YAMLs (e.g., `description: …` field in each YAML, surfaced via `load_scenario`).
- **P0-2 What-now default-closed.** If the user-base research data shows the next-steps panel is the most-clicked surface, leaving it open might be the right call. Worth checking analytics-equivalent (anecdotes) before flipping.
