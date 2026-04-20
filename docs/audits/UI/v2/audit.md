# Audit v2 — immokalkul UX + educational review

Applies the eight frameworks from [`research.md`](./research.md) to `app.py` at its current state (**1618 lines**, up from 1341 at v1). Most of v1's 25 actionable items have shipped — this v2 is a fresh look at the *current* state, not a re-litigation of v1.

All findings cite `file:line`. Severity scale: **1 cosmetic** / **2 minor** / **3 major** / **4 blocker**.

Persona lens unchanged: **first-time buyer living in Germany, not assumed to be German-native**. Goal A = don't overwhelm at first open. Goal B = teach transparently in-context.

---

## 0. What v1 shipped (sets the new baseline)

The changes between v1 and the current head are visible across the file:

- **Verdict banner** before the KPI strip (`app.py:514-515`) — the single biggest landing-experience gain.
- **Sample-scenario framing banner** (`app.py:506-511`) — labels the Bonn scenario as illustrative.
- **Header slimmed** to four KPI tiles (`app.py:519-537`); Mode tile dropped, "Year-1 burden" removed.
- **All sidebar expanders default-collapsed** except Scenarios (`app.py:118` `expanded=True`; Property `app.py:160`, Financing `app.py:207`, Rent params `app.py:305`, Live params `app.py:347`, Op costs `app.py:371`, Globals `app.py:446`, User capex `app.py:462` — all `expanded=False`).
- **Property expander split** into Basics + nested "🔬 Tax-relevant details" (`app.py:183`).
- **Adaptive debt-budget input gated** on `any_adaptive` (`app.py:233-239`).
- **Tab order** now Summary first (`app.py:1576+`).
- **Purchase-cost rows show rates inline** (`app.py:737-740`) and a "What are these fees?" gloss expander (`app.py:746-760`).
- **Cross-mode verdict sentence** on Buy vs Rent (`app.py:821-823`).
- **"What now?" branching expander** on Summary (`app.py:694-716`).
- **"What this tool does NOT model" expander** elevated to Summary (`app.py:570-581`) and kept on Methodology.
- **Glossary table A–Z** in "New here?" tab (`app.py:1380-1447`).
- **Insight captions** under most charts.
- **Mode badges** (`:violet-background[…]`) on per-tab headings (`app.py:898, 961, 1000, 1070, 1178`).
- **Methodology TOC anchors** (`app.py:1465-1469`).
- **Modified-scenario badge** in title (`app.py:502-503`).
- **Friendly error fallback** + traceback to console (`app.py:1567`).

The result is a substantially better app. v2 finds *new* failure modes the v1 fixes have introduced (mostly density / hierarchy on Summary), plus residual gaps the v1 plan deliberately left open.

---

## 1. Goal audit

### 1.1 5-second test (Goal A — "don't overwhelm")

**Scenario.** First load. Sidebar default-collapsed except 📂 Scenarios. Title `🏠 Bonn-Poppelsdorf 3-Zimmer` (`app.py:503`), then a sample-scenario `st.info` banner (`app.py:506-511`), then a verdict `st.success`/`warning`/`error` banner (`app.py:514-515`), then 4 KPI tiles (`app.py:519-537`), then 9 tabs starting on **📋 Summary**.

**What a 5-second scanner sees on Summary:**

| # | Surface | Visible content | Verdict |
|---|---|---|---|
| 1 | Title | `🏠 Bonn-Poppelsdorf 3-Zimmer` | ✅ |
| 2 | Sample banner (`app.py:506-511`) | "📌 You're viewing the **bonn_poppelsdorf** sample…" | ✅ — but uses raw filename, not friendly name |
| 3 | Verdict banner (`app.py:514-515`) | One sentence, coloured | ✅ — **the v1 win** |
| 4 | 4 KPI tiles | Total purchase cost / Years until debt-free / 50-yr cumulative / Affordability rules | ⚠ — "50-yr cumulative" still requires three sub-concepts to interpret |
| 5 | Tab strip | 9 tabs | ⚠ — same density as v1 |
| 6 | Summary heading + 4 stacked expanders | "## Summary" → `🚀 New here?` (`app.py:557`) → `⚠ NOT modelled` (`app.py:570`) → 4 affordability tiles → 4 returns tiles → pass/fail strip → `✅ What now?` (`app.py:694`, **expanded=True**) → property+purchase tables → "What are these fees?" expander | ❌ **Summary is now the bottleneck** |

**Scorecard.** The three Krug questions:

- *What is this page?* — **yes**, immediately.
- *What is the headline answer?* — **yes**, in the verdict banner. **v1 fix landed.**
- *What do I do next?* — **partially, but contradicted.** The verdict says one thing, the sample banner says "edit any input on the left", the `🚀 New here?` collapsed expander offers a 3-step walkthrough, and the `✅ What now?` expander (open) offers a different 3-step plan. **Three competing "next step" prompts on one page.**

**New finding (v2):** the *first-open verdict* problem is solved. The new bottleneck is the **Summary tab itself**, which now stacks: 1 sample banner + 1 verdict banner + 1 walkthrough expander + 1 limitations expander + 8 metric tiles + 1 narrative strip + 1 next-steps expander (open) + 1 horizontal rule + 2 detail tables + 1 fees expander + 1 AfA block. **That's 12 distinct semantic blocks above the Buy-vs-Rent comparison the user actually came for.** The page is no longer overwhelming *at the title-bar* — it's overwhelming *one scroll down*.

**Severity-3 finding.** Summary stacks too many onboarding/educational/limitation surfaces between the verdict and the actual numerical detail. CLT extraneous load and Krug "halve the words" both apply.

### 1.2 First-click test (Goal B — "teach transparently")

**Prompt.** User reads the Summary verdict, sees `Total purchase cost €66,560`, scrolls to Purchase costs and reads `Property transfer tax (Grunderwerbsteuer, 6.5% NRW) — €X`. They want to know *what Bundesland-by-Bundesland means* — is 6.5% high or low?

**Expected path now.** Click "What are these fees?" expander (`app.py:746-760`). Definition is one sentence: *"Varies by Bundesland; NRW is 6.5%."* That's an improvement over v1, but it doesn't show the range (3.5–6.5%) and doesn't tell the user that NRW is on the **high end** (only Brandenburg, Saarland, Schleswig-Holstein and Thuringia match it). To learn the comparison, the user has to leave the app.

**Severity-2 finding.** The in-context gloss landed (v1 win) but stops one fact short of a complete teaching moment — the **comparison** is missing. Same pattern recurs for Maklerprovision (the 3.57% figure is given without saying "this is the *new* post-2020 split — before then it was 100% buyer", which is exactly the teaching the persona needs).

**Second prompt.** User in rent mode reads the Tax tab and sees `Annual tax computation` with five bars + a black "taxable income" line (`app.py:1199-1217`). The caption (`app.py:1216-1217`) explains colours but doesn't explain the **negative-tax = refund** mechanic that's actually displayed; that explanation is a sentence below at `app.py:1222-1225`, separated from the chart by the total-tax line.

**Severity-2 finding.** The chart-caption-immediately-below pattern is good (v1 fix), but on the Tax tab the *interesting* feature of the chart — bars going below zero, line going negative, refund regime — has its explanation **after** the totals, where a scanner who looks at the chart and skims the caption will miss it.

---

## 2. Heuristic findings (by framework)

### 2.1 Nielsen's 10 Heuristics

| # | Heuristic | Finding | Sev | Loc |
|---|---|---|---|---|
| H1 | Visibility of system status | `_is_scenario_modified()` (`app.py:73-84`) compares the live `Scenario` object to the deepcopy at load. It only checks key scalar fields — **not the loans table or capex table**. Editing only loans / capex leaves the title showing the original name with no "(modified)" badge. | 2 | `app.py:73-84, 502` |
| H2 | Match real world | "Property transfer tax (Grunderwerbsteuer, 6.5% NRW)" is the right pattern (English first, German in parens, rate visible). But on the same row, "Notary + land registry (~2%)" drops the German entirely — *Notar + Grundbuch* never appears on this row. The user can't tie the EUR figure to the German term they'll hear at the bank. | 2 | `app.py:739` |
| H2 | Match real world | The sample-scenario banner shows the **raw YAML basename** (`bonn_poppelsdorf`) instead of the property name (`Bonn-Poppelsdorf 3-Zimmer`). Snake-case + underscores + no umlauts is jarring next to the polished title above it. | 2 | `app.py:506-511, 124-128` |
| H3 | User control / freedom | Loans data-editor and capex editor still have no "reset this section to scenario defaults" affordance; user must reload the YAML and lose all other edits. | 2 | `app.py:242-291, 466-490` |
| H4 | Consistency | Three different st.info / success / warning banner usages stack at the top: **sample-scenario** (`st.info`, `app.py:508`), **verdict** (`st.success/warning/error`, `app.py:514`), **live-mode warning** (`st.warning`, `app.py:548`) on Summary. They use the same colour family and visual weight; users have to read each to know which is feedback vs. branding vs. critical. | 2 | `app.py:506-511, 514-515, 547-554` |
| H4 | Consistency | "Buy vs Rent" tab has **its own** st.warning (`app.py:799-804`) about the same `current_monthly_rent_warm_eur=0` condition that Summary already warns about (`app.py:547-554`). Same wording, same trigger, twice on the same scroll. | 2 | `app.py:547-554, 799-804` |
| H4 | Consistency | Summary "What now?" expander defaults `expanded=True` (`app.py:694`); every other expander on the same tab defaults `expanded=False` (`app.py:557, 570, 746`). Visual rhythm is "open by default" only here, drawing the eye disproportionately. | 1 | `app.py:694` |
| H5 | Error prevention | The capex editor has `min_value=0` on cost (v1 fix landed, `app.py:477`), but **no `min_value` on the year column**. A user can enter a year before `today_year` and the cashflow projection silently drops it. | 2 | `app.py:466-480` |
| H5 | Error prevention | Loans data-editor `Rate (%)` column accepts negative rates (no `min_value`, `app.py:255`). | 1 | `app.py:253-258` |
| H6 | Recognition over recall | Mode badges (`:violet-background[RENT mode]`) are present on detail tabs (`app.py:898, 961, 1000, 1070, 1178`) — v1 fix. But they're **missing on Summary** (`app.py:545`) and **missing on Buy vs Rent** (`app.py:796`). Summary actually *depends* on mode (the Returns tiles flip between gross/net yield in rent mode and ownership-vs-rent metrics in live mode, `app.py:629-685`). User can't see the mode at the spot it changes the meaning. | **3** | `app.py:545, 796` |
| H6 | Recognition over recall | The sample-scenario banner says "edit any input on the left", but the **Mode radio** at `app.py:152-156` is the single most consequential input — it changes which Returns tiles render, which charts appear, what the Tax tab does — and isn't called out as "the most important toggle." | 2 | `app.py:152-156, 506-511` |
| H7 | Flexibility / efficiency | No novice / expert toggle. Adaptive loans, Bodenrichtwert override, Denkmal flag, Anschaffungsnaher window, auto-schedule capex remain visible to the novice — the v1 fix moved Bodenrichtwert/Denkmal into a *nested* expander inside Property (`app.py:183`), but Adaptive (`app.py:258`), auto-schedule capex (`app.py:491-494`), and Manager-fee-conditional (`app.py:337-344`) are still inline. | 2 | `app.py:258, 491-494` |
| H8 | Aesthetic and minimalist | Header is now slim (4 tiles, v1 win). But the Summary tab itself has **8 metric tiles** in two rows + a 2-column property/purchase/financing/AfA block + 4 expanders. Above Miller's 7±2 *within one tab*. | 3 | `app.py:593-685, 720-791` |
| H8 | Aesthetic and minimalist | Operating costs expander is unchanged from v1: 8 inputs (`app.py:399-443`) in a flat list, no sub-grouping. Same finding as v1 §3.1; not addressed. Should split: *Utilities* (gas, electricity, municipal) vs. *Property-tax & insurance* (Grundsteuer, building, liability) vs. *WEG / management* (Hausgeld, administration). | 2 | `app.py:393-443` |
| H8 | Aesthetic and minimalist | Capex tab now has **two charts back-to-back** (timeline bubble at `app.py:1119-1123` + annual bar+reserve at `app.py:1139-1153`), each with a *long* multi-sentence caption (`app.py:1124-1128`, `app.py:1154-1162`). The second caption alone is 6 sentences over 9 lines. Krug "halve the words" violation. | 2 | `app.py:1124-1162` |
| H9 | Error recovery | Friendly error fallback shipped (`app.py:1567`); good. No further finding here. | — | — |
| H10 | Help and documentation | The Glossary table (`app.py:1380-1447`) lives at the **bottom of "New here?" tab** (tab index 1). A user reading Summary's Purchase-costs table can't reach it without leaving the page. The Methodology tab's TOC anchors (v1 fix at `app.py:1465-1469`) help inside Methodology, but there's no cross-tab "jump to glossary entry for *Hausgeld*" affordance. | 3 | `app.py:1380-1447` |
| H10 | Help and documentation | "What this tool does NOT model" appears **twice** verbatim (Summary expander `app.py:570-581` + Methodology body `app.py:1498-1504`). v1 ordered the duplication intentionally — but the two copies have already drifted: Summary lists 5 items, Methodology lists 5 items, but the wording differs. ("Loss carryforward" vs "Loss carry-back limits"; "Sonderumlagen baked into the maintenance reserve" vs "modeled implicitly through the maintenance reserve.") | 2 | `app.py:570-581, 1498-1504` |

### 2.2 Cognitive Load Theory (CLT)

| Finding | Type | Sev | Loc |
|---|---|---|---|
| Three coloured banners stack on Summary load (sample-scenario blue + verdict colour + live-mode warning if applicable). Same shape, similar palette — the user's eye must parse three boxes before reaching the verdict text. | Extraneous | 2 | `app.py:506-554` |
| Summary tab: 4 expanders + 8 tiles + 2 detail tables + AfA block. The walkthrough + limitations + next-steps + fees expanders are each *useful*, but **collectively** they push the actual property/financing detail block out of the first scroll on a 13" screen. | Extraneous | **3** | `app.py:545-791` |
| The Capex tab's annual bar + smoothed reserve line (`app.py:1139-1162`) is a *germane*-load win — it shows the lumpy-vs-smoothed reserve concept visually (Erhaltungsrücklage, II. BV) that no other surface explains. **This is the strongest new explorable-explanation surface in the app since v1.** | Germane (positive) | — | `app.py:1130-1162` |
| But its caption is 9 lines + 6 sentences (`app.py:1154-1162`). A novice has to read all of it to catch that the red dashed line is the *Erhaltungsrücklage equivalent*. The germane gain is throttled by extraneous prose density. | Extraneous | 2 | `app.py:1154-1162` |
| Two onboarding surfaces: the collapsed "🚀 New here? 2-minute walkthrough" expander on Summary (`app.py:557-567`) plus the full "🚀 New here?" tab (`app.py:1231-1459`). The two have **different** 3-step walkthroughs (`app.py:559-565` vs `app.py:1251-1261`). User who hits both gets the same content twice with subtle differences — classic redundancy effect. | Extraneous (redundancy) | 2 | `app.py:557-567, 1250-1261` |
| Buy-vs-Rent tab now has a verdict sentence (v1 win, `app.py:821-823`) **and** two side-by-side mode summary blocks of 5 metrics each (`app.py:828-835` → `_mode_summary_block` `app.py:882-893`) **and** a 50-year chart **and** a year-1 monthly cash flow table. The verdict already states the headline; the 10 metrics + chart + table are now *post-verdict detail*, but they're not labelled as such. The user is invited to compare 10 numbers across two columns *after* being told the answer. | Intrinsic unmanaged | 2 | `app.py:794-879` |

### 2.3 Progressive Disclosure

| Finding | Sev | Loc |
|---|---|---|
| Sidebar default state is now correct (Scenarios open, everything else collapsed) — v1 fix landed. | — (positive) | `app.py:118-462` |
| But disclosure depth is uneven. Property has a *nested* expander "🔬 Tax-relevant details" (`app.py:183`); Financing has a *nested* `❓ Initial capital vs loans` explainer (`app.py:208-224`); Operating costs is **flat with 8 fields**; Globals is **flat with 5 fields**. Two patterns coexist — user can't predict whether expanding will reveal nested options. | 2 | `app.py:160-459` |
| Summary tab: of 4 expanders, 1 defaults open (`✅ What now?`, `app.py:694`) and 3 default closed. NN/g convention is "two disclosure levels max"; here we have header → tab → 4 expanders, of which one nests further (`What are these fees?`, `app.py:746`) — that's 4 levels deep. | 2 | `app.py:557-760` |
| The "Buy vs Rent" verdict sentence is a *summary* but the year-1 monthly cash flow table immediately below (`app.py:860-879`) and the two `_mode_summary_block`s are not behind expanders — they're the default visible content. A user with a clear verdict has no way to "collapse the detail." | 2 | `app.py:828-879` |
| Live-mode warning banner about `current_monthly_rent_warm_eur=0` fires on **both** Summary (`app.py:547-554`) and Buy-vs-Rent (`app.py:799-804`). If the user dismisses one mentally, the other re-asserts. Should fire once (closer to the input that fixes it). | 2 | `app.py:547-554, 799-804` |

### 2.4 Krug — "Don't Make Me Think"

| Finding | Sev | Loc |
|---|---|---|
| Verdict banner at the top is the *single most scannable surface in the app now*. Protect at all costs. | — (positive) | `app.py:514-515` |
| Sample-scenario banner uses the YAML key (`bonn_poppelsdorf`) — Krug "halve the words" applies *and* the underscored slug fails the "real world" match. A 5-second scanner reads "bonn_poppelsdorf" and registers it as machine output, not a friendly label. | 2 | `app.py:506-511` |
| Capex tab smoothed-reserve caption (`app.py:1154-1162`) is 6 sentences over 9 lines. Halve, then halve again. | 2 | `app.py:1154-1162` |
| Several v1 tooltips not yet shortened: Cost inflation (`app.py:464-470`, ~80 words, 4 sentences), Hausgeld (`app.py:418-423`, 5 sentences), Grundsteuer rate (`app.py:412-415`, 4 sentences). | 2 | `app.py:412-470` |
| Tab labels mix metaphors: 📋 Summary (data) / 🚀 New here? (rocket = launch?) / ⚖ Buy vs Rent (scales = comparison) / 💸 (money flying away) / 💡 (insight?) / 🏦 (bank) / 🔨 (tool) / 🧾 (receipt) / 📚 (reference). Six glyph categories on one tab strip; satisficing scanner picks whichever feels familiar. | 1 | `app.py:1576-1595` |
| The "✅ What now?" expander is `expanded=True` (`app.py:694`) right below the pass/fail strip. A satisficer who reads the verdict + sees a prominent ✅ checkbox will click into the next-steps and skip the property/purchase/financing tables below — which contain *the actual numbers the bank will ask about*. Defaulting "What now?" closed (and "Property/Purchase/Financing" tables open as today) might better match scan order. | 2 | `app.py:694-716, 720-791` |

### 2.5 Explorable Explanations

| Finding | Sev | Loc |
|---|---|---|
| The Capex annual-bar + smoothed-reserve chart (`app.py:1139-1153`) is a *new* explorable surface — it directly answers "how much should I be reserving per year?" by overlaying the lumpy reality on the steady-state ideal. Strongest single explorable since v1. **Underused: the chart isn't introduced in the Methodology section on Petersche Formel** (`app.py:1486-1488`), so the user who reads about Petersche has no idea this visualisation exists. | 2 | `app.py:1130-1162, 1486-1488` |
| Buy-vs-Rent has a "💡 Try this" caption under the 50-year chart (`app.py:857-858`) — v1 win. But the rest of the app has zero counterfactual prompts. Cash flow, Debt, Tax, Capex tabs all show charts without a "try changing X — watch Y" nudge. | 2 | `app.py:922, 1025, 1040, 1119, 1215` |
| Sample-scenario framing is now explicit (`app.py:506-511`) — v1 win. But the *worked-example* aspect (why this scenario, what makes it interesting, what to learn from it) isn't called out. A user picking Köln Einfamilienhaus from the dropdown gets the framing banner but no "this scenario shows you what a freestanding house looks like vs. an apartment" guidance. | 2 | `app.py:118-148` |
| Glossary table (`app.py:1380-1447`) is a static reference, not interactive. Each entry could be a deep link into the actual surface where the term lights up — but Streamlit's link-to-anchor isn't wired across tabs. | 1 | `app.py:1380-1447` |
| The "Auto-schedule component capex" checkbox (`app.py:491-494`) is the highest-leverage *toggle* in the app for understanding capex — flip it and the entire capex tab redraws. There's no nudge anywhere ("turn this off to see only your manual entries"). | 2 | `app.py:491-494` |

### 2.6 Plain Language + Microcopy

| Finding | Sev | Loc |
|---|---|---|
| `Property transfer tax (Grunderwerbsteuer, 6.5% NRW)` (`app.py:737`) — exemplary: English first, German term, rate, jurisdiction. Reuse pattern. | — (positive) | `app.py:737` |
| Same row 3 lines down: `Notary + land registry (~2%)` (`app.py:739`) drops the German term. Inconsistent with the row above. Should be `Notary + land registry (Notar + Grundbuch, ~2%)`. | 2 | `app.py:739` |
| Capex item labels: `Capitalized` column header (`app.py:1113`) renders values "AfA" / "Deductible". The string "AfA" is unexplained at this surface (the term is dedicated in Methodology and Summary). A user reading the Capex table for the first time has no gloss. | 2 | `app.py:1113, 1165-1167` |
| Tax tab AfA-basis row label `(Grunderwerb + Makler + 80% of Notar, × building share)` (`app.py:1190`) — three abbreviations (Grunderwerb, Makler, Notar) on one line. The *full* terms are used elsewhere; abbreviations save bytes but break the term-lookup chain. | 2 | `app.py:1190` |
| Tax tab caption: *"Black line = your taxable result after all deductions"* (`app.py:1217`) — accurate, but the **chart shows the line going negative in early years**, and no caption explains what a negative line means. The Verlustverrechnung explanation is at `app.py:1222-1225`, *below* the totals. Move it adjacent to the chart caption. | 2 | `app.py:1217-1225` |
| Glossary entry for *AfA* (`app.py:1390`) — first sentence is fine; second sentence "Available only in rent mode" is technically true but doesn't gloss what *Absetzung für Abnutzung* means literally ("write-off for wear"). The literal translation is the cheapest single sentence to teach the term. | 1 | `app.py:1380-1447` |
| Glossary entry for *Anschaffungsnaher Aufwand* uses *>15%* but the Summary "What are these fees?" expander says nothing about a 15% threshold (`app.py:756-760`). Two surfaces, slightly different facts. | 1 | `app.py:756-760, 1380-1447` |

### 2.7 Dual Coding Theory

| Finding | Sev | Loc |
|---|---|---|
| Most charts now have an `st.caption()` insight sentence (v1 win, `app.py:923, 937, 1026, 1124, 1216, 844, 857`). | — (positive) | multiple |
| **Costs pie chart** (`app.py:993-995`) has a Plotly title (`title="Cost composition"`) but **no `st.caption`**. Every other chart in the app pairs visual + prose; this one stands alone. Scanner sees the largest slice but isn't told what to do about it. | 2 | `app.py:993-995` |
| **Debt annual-payment-breakdown bar chart** (`app.py:1033-1040`) has neither title nor caption. The companion balance-stack chart immediately above (`app.py:1014-1028`) is captioned; this one is a silent visual. | 2 | `app.py:1033-1040` |
| The Buy-vs-Rent year-1 monthly cash flow table (`app.py:860-879`) carries no caption. After the chart's "Try raising the Horizon slider" nudge, the user lands on a 6-row table without a sentence telling them what comparison to make. | 1 | `app.py:860-879` |
| Tax-tab AfA-basis block (`app.py:1184-1194`) is **6 lines of `st.write` with no chart**. A waterfall or sankey of "purchase price → land vs building → + capitalized fees → AfA basis" would unlock dual coding for the most arithmetic-heavy concept in the app. (Out of scope for v2-low-effort fix; flagging for future.) | 1 | `app.py:1184-1194` |

### 2.8 Jobs-to-be-Done

| Finding | Sev | Loc |
|---|---|---|
| Core JTBD ("can my finances absorb this?") is now answered in the verdict banner — v1 closed the v1 §2.8 blocker. | — (positive) | `app.py:514-515` |
| Related job *"is this a reasonable price?"* — still not served. Bodenrichtwert is in the engine; the BORIS NRW rate × plot share + a building-cost benchmark could surface a "your price looks fair / high / low for this Bundesland" callout. Same finding as v1 §2.8; not addressed. | 3 | engine has data; nowhere surfaced |
| Related job *"what if rates rise?"* — still no sensitivity strip. The single biggest near-term external risk for a German buyer (mortgage rates moved 1% → 4% in 2022-2023) has no first-class affordance. | 2 | engine supports per-loan rates; only via data-editor |
| Related job *"how much down payment do I need?"* — Summary shows current Down-payment-% (`app.py:618-620`); doesn't reverse-compute "to hit 20% you'd need €X more." | 2 | `app.py:618-620` |
| Next-step job is now scaffolded by `✅ What now?` (`app.py:694-716`), v1 win. But it branches only on `n_fail ≤ 1` vs. `≥ 2` — the **exact thresholds and rule names** that drove the verdict aren't echoed inside "What now?" The user reading "Some rules are stretched. Try raising Initial capital or lowering Purchase price" has to scroll *up* to see *which* rules failed. | 2 | `app.py:688-716` |
| The four built-in scenarios (Bonn, Munich Neubau, Berlin Altbau, Köln Einfamilienhaus) span apartment-vs-house and Altbau-vs-Neubau — they're a *natural curriculum* for the persona. The Scenarios expander shows them as a flat dropdown (`app.py:124-128`) with no "what each one teaches" hint. JTBD-related-job: *"show me a scenario like the place I'm considering"*. | 2 | `app.py:118-148` |

---

## 3. Per-surface findings

### 3.1 Sidebar (`app.py:109-495`)

- **Default state is correct** (v1 win). Scenarios open, all others closed.
- **Mode radio** (`app.py:152-156`) uses `format_func` to display "Live in it" / "Rent it out" — v1 fix for the jargon. But it still lacks a *caption* below it explaining "this changes which tabs/metrics make sense." Most consequential toggle in the app, no hint. **Severity 2.**
- **Operating costs expander** (`app.py:393-443`) — 8 inputs in a flat list, no sub-grouping. Same as v1; not addressed. Suggested grouping: Utilities (gas, electricity, municipal) → Property tax & insurance (Grundsteuer, building, liability) → WEG (Hausgeld, administration). **Severity 2.**
- **Globals expander** (`app.py:446-484`) — 5 inputs with the longest tooltip in the app on Cost inflation (`app.py:464-470`, ~80 words). v1 P0-6 was supposed to shorten this. **Severity 2.**
- **Scenarios dropdown** (`app.py:124-128`) — flat options, no descriptive hint. A persona who doesn't know what *Einfamilienhaus* means just sees "koeln_einfamilienhaus" as one of four options. **Severity 2.**
- **Loans data-editor** still has no novice-mode "Just one loan?" simple form (v1 §3.1 finding); same as v1. The editor is still intimidating to a first-timer. **Severity 2.**
- **Adaptive debt budget** (`app.py:233-239`) — gated correctly on `any_adaptive` (v1 fix landed), but its label still says "**Total monthly debt budget** (€/mo)" without saying *who* this number constrains. Should be: "Adaptive debt ceiling (€/mo, total across loans)". **Severity 1.**
- **Capex editor** has `min_value=0` on cost (v1 win) but **not on year**. Negative offsets accepted; the row is silently dropped. **Severity 2.**

### 3.2 Header (`app.py:500-537`)

- **Sample banner** uses raw YAML key `bonn_poppelsdorf` (`app.py:506-511`) instead of `s.property.name`. **Severity 2.**
- **Verdict banner** is the v1 win — keep, protect.
- **"50-yr cumulative wealth" KPI** (`app.py:522-527`) — has a `help=` explaining "Positive = pays back; negative = costs more than it earns." Good. But the tile label still says "50-yr" — a user with horizon set to 30 yr sees mismatched labelling (the engine respects `s.globals.horizon_years` but the label is hardcoded "50-yr"). **Severity 2.**
- **"Affordability" KPI** (`app.py:530-537`) carries the rule-pass count and a delta label ("Within rules" / "Mostly within rules" / "Stretching the rules"). The help= text is descriptive but doesn't list *which* rules. Click-through path to the per-rule strip in Summary is implicit. **Severity 1.**
- **Modified-scenario badge** (`app.py:502-503`) only fires if `_is_scenario_modified()` returns True — and that helper (`app.py:73-84`) doesn't check loans/capex. **Severity 2.**

### 3.3 Summary tab (`app.py:543-792`) — **the new bottleneck**

- **Highest-density tab in the app**: 12+ semantic blocks. Verdict in the header has *already* told the user the answer; Summary then re-litigates with 8 metric tiles + pass/fail strip. Consider: "this tab is the proof; the answer is in the banner above."
- **`✅ What now?` expanded by default** (`app.py:694`) breaks the visual rhythm of the page (every other expander on this tab defaults closed). Bigger issue: it sits *above* the property/purchase/financing/AfA detail block — the actual numerical receipts the user will need to take to a bank. **Severity 2.**
- **Live-mode warning** (`app.py:547-554`) duplicates the Buy-vs-Rent warning at `app.py:799-804`. Same trigger, same wording. **Severity 2.**
- **Walkthrough expander on Summary** (`app.py:557-567`) duplicates the "New here?" tab content (`app.py:1250-1261`). The two have **drifted**: Summary's version says "tweak inputs" / "read this tab"; tab's version says "tweak inputs" / "read the tabs above". Same content, two voices. **Severity 2.**
- **Limitations expander on Summary** (`app.py:570-581`) duplicates Methodology body (`app.py:1498-1504`). The two have **drifted** (5 items each, but wording differs — "Loss carryforward" vs "Loss carry-back limits"). **Severity 2.**
- **"What are these fees?"** (`app.py:746-760`) is good content but only covers Purchase costs. The Financing block right next to it (`app.py:762-780`) has loan principals + rates + cleared-year, no explainer for what *Cleared* means or why some loans never clear in the horizon. **Severity 1.**
- **Mode-conditional Returns tiles** (`app.py:629-685`) — gross/net yield in rent mode, ownership-vs-rent in live mode — change semantically based on mode, but the section heading "Return, leverage, timing" (`app.py:628`) is constant. User who toggles modes sees different metrics under the same heading. **Severity 2.**

### 3.4 Buy vs Rent tab (`app.py:794-879`)

- **Cross-mode verdict sentence** (`app.py:821-823`) — v1 win. Keep.
- **Live-mode warning** (`app.py:799-804`) duplicates Summary's identical warning. **Severity 2.** Pick one.
- **50-year chart caption + try-this nudge** (`app.py:844, 857-858`) — v1 win. Keep.
- **Year-1 monthly cash flow table** (`app.py:860-879`) carries no caption. After the chart's verdict, the table is the per-row decomposition; should be introduced with a sentence like *"Where the year-1 monthly burden of each mode comes from."* **Severity 2.**
- **`_mode_summary_block`** (`app.py:882-893`) renders 5 metric tiles per mode = 10 tiles below the verdict. This is *the* JTBD detail surface; don't shrink, but consider: the 5 metrics could be rendered as a single comparison table (Live | Rent | Δ) that respects the verdict's "ahead by €X" framing. **Severity 1.**

### 3.5 Cash flow tab (`app.py:896-956`)

- **Mode badge** (`app.py:898`) — v1 win.
- **Bar+line chart caption** (`app.py:923-925`) — concise, names the colours, names the zero-crossing meaning. Best caption in the app. Keep as exemplar for the missing ones.
- **Cumulative position chart caption** (`app.py:937-938`) — fine.
- **Year-by-year expander** (`app.py:940-956`) — fine.
- No counterfactual nudge ("try raising rent escalation by 1% — watch the green bars compound"). **Severity 2.**

### 3.6 Costs tab (`app.py:959-995`)

- **Pie chart has no st.caption** (`app.py:993-995`). Only chart in the app without one. **Severity 2.**
- 8-column table (`app.py:980-983`) — same as v1 §3.6 finding; not addressed. Could be split: filter rows by `Active=✓` by default and offer a "show all lines" toggle. **Severity 1.**
- **Total line** is plain markdown (`app.py:985-986`) — not a `st.metric` tile. Inconsistent with other tabs that use tiles for totals. **Severity 1.**

### 3.7 Debt tab (`app.py:998-1065`)

- **Annual payment breakdown bar chart** (`app.py:1033-1040`) — no title, no caption. Only chart in the app with neither. **Severity 2.**
- **Caption on balance chart** (`app.py:1026-1028`) — fine.
- Per-loan summary table is good. **Severity —.**
- No "rate sensitivity" affordance (JTBD related-job, see §2.8).

### 3.8 Capex tab (`app.py:1068-1173`)

- **Annual bar + smoothed reserve line** (`app.py:1139-1153`) — *the* new explorable since v1. Visualises the Petersche-Formel concept (lumpy spend vs steady-state reserve) better than any prose could. **Should be cross-referenced from the Methodology Petersche-Formel section** (`app.py:1486-1488`) — currently isn't.
- **Caption is too long** (`app.py:1154-1162`, 6 sentences). Halve. The Erhaltungsrücklage / Hausgeld connection in the last 2 sentences is the single most teaching-rich claim in the app — should be its own short paragraph, not buried at the end of a long caption.
- **Bubble timeline caption** (`app.py:1124-1128`) — 4 sentences explaining 4 things (size, colour, hover, capitalized flag). Fine but on the edge; could be 2 sentences.
- "Capitalized" column shows `AfA` / `Deductible` (`app.py:1113`). At a Capex-tab user's first visit, the term *AfA* shows up unexplained. **Severity 2.**

### 3.9 Tax tab (`app.py:1176-1228`)

- **Mode badge** present (`app.py:1178`). Good.
- **Live-mode info** correctly returns early (`app.py:1179-1182`).
- **AfA basis block** is 7 lines of `st.write` (`app.py:1184-1194`). Walks the user through the arithmetic but is text-only — see §2.7. **Severity 1.**
- **Tax bar+line chart caption** (`app.py:1216-1217`) — explains colours but **does not explain that the black line goes negative** in early years, which is precisely what the Verlustverrechnung paragraph below (`app.py:1222-1225`) addresses. The negative-line + refund explanation should be **adjacent to the chart caption**, not separated by the totals lines. **Severity 2.**
- **"Marginal rate applied"** line (`app.py:1221`) — single number, no link back to the Globals slider. User who didn't set their Grenzsteuersatz sees the default applied with no acknowledgement. **Severity 1.**

### 3.10 New here? tab (`app.py:1231-1459`)

- **Per-section walkthrough** is a good asset. Same structural concern as v1: it's a long page (~228 lines), mostly markdown. No interactive element (Case-style "click to advance" or "open the Property expander now" trigger). **Severity 2.**
- **Glossary table** (`app.py:1380-1447`) is the v1 win. Two issues:
  - It's at the *bottom* of an already-long tab, so a user who lands on this tab to find a definition has to scroll past the entire walkthrough.
  - Some entries duplicate facts that exist elsewhere with subtly different wording (Anschaffungsnaher Aufwand uses *>15%* threshold; "What are these fees?" expander on Summary doesn't mention the threshold). Drift risk. **Severity 2.**
- **Privacy notice** (`app.py:1244-1247`) is well-placed.

### 3.11 Methodology tab (`app.py:1462-1524`)

- **TOC anchors** at top (`app.py:1465-1469`) — v1 P2-23 landed.
- **Citations section** (`app.py:1506-1523`) is dense but well-organised.
- **"What this tool does NOT model"** (`app.py:1498-1504`) duplicates Summary expander (`app.py:570-581`). Drift already present — should pick one canonical location and have the other reference it. **Severity 2.**
- **No cross-link to the Capex annual-bar chart** in the Petersche-Formel section (`app.py:1486-1488`). Missed teaching opportunity. **Severity 2.**

### 3.12 Footer (`app.py:1601-1614` approx)

- v1 fix landed (disclaimer + sources link). Verify it includes a model-version / last-updated line — if not, add. **Severity 1.**

---

## 4. Educational coverage matrix (delta vs. v1)

Same rating scheme as v1: **Unexplained** / **Tooltip-only** / **In-context** / **Dedicated**.

### 4.1 Tax / legal — coverage gains since v1

| Term | v1 status | Current status | Now |
|---|---|---|---|
| Grunderwerbsteuer | ❌ Unexplained at use | In-context (Summary row label) + Dedicated (gloss expander + Glossary) | ✅ |
| Maklerprovision | ❌ Unexplained at use | In-context + Dedicated | ✅ |
| Notar + Grundbuch | ❌ Unexplained at use | English-only at use; Dedicated in Methodology + Glossary | ⚠ — German term dropped from row label (`app.py:739`) |
| Anschaffungsnaher Aufwand | ⚠ Tooltip + Methodology | In-context (gloss expander) + Glossary entry | ✅ — but Glossary's *>15%* threshold isn't echoed in Summary expander |
| Herstellungskosten / Erhaltungsaufwand | ⚠ Tooltip-only | In-context (gloss expander) + Glossary | ✅ |
| Verlustverrechnung | Not user-visible | Tax-tab paragraph (`app.py:1222-1225`) + Methodology | ✅ |
| Solidaritätszuschlag / Soli | ❌ Tooltip-only | Tooltip-only (`app.py:451`) | ❌ — gap remains |
| Einkommensteuer §32a EStG | ❌ Tooltip-only | Tooltip-only | ❌ — gap remains |
| Kirchensteuer | ❌ Mentioned only in tooltip | Mentioned in "NOT modelled" expander (`app.py:580`) | ⚠ — flagged as not modelled but never glossed |
| Sonderumlagen (WEG) | Not user-visible | "NOT modelled" expander + Glossary entry "Sonderumlage" | ✅ |
| Denkmal-AfA (§ 7i) | ⚠ Tooltip-only | Tooltip + "NOT modelled" mention | ⚠ — same as v1 |

### 4.2 Property-specific — coverage gains since v1

| Term | v1 status | Current status |
|---|---|---|
| WEG / Gemeinschaftseigentum / Sondereigentum | ⚠ Tooltip-only | Glossary entry exists (`app.py:1446-1447`) for WEG; *Gemeinschaftseigentum* and *Sondereigentum* still tooltip-only in Operating costs / Property |
| Erhaltungsrücklage (§ 19 WEG) | ⚠ Dedicated only | Dedicated + **mentioned in Capex tab caption** (`app.py:1161-1162`); **not in Glossary table** |
| Sanierungspflicht / GEG / EnEV | Not user-visible | Still not user-visible. ❌ gap — relevant for Altbau buyers |

### 4.3 Cost / operating — coverage gains since v1

| Term | v1 status | Current status |
|---|---|---|
| Hausgeld | ❌ Jargon label | **Improved** — label now `Building fee (Hausgeld)` (`app.py:416`); Glossary entry; tooltip explanation. ✅ |
| Mietspiegel / Mietpreisbremse | ⚠ Tooltip-only | Tooltip + Glossary entries (`app.py:1429-1432`) ✅ |
| Hausverwaltung / Verwalterhonorar | ⚠ Tooltip-only | Tooltip + Glossary mentions ✅ |
| Wohngebäudeversicherung | ⚠ Tooltip-only | **Improved** — label now `Building insurance €/m²/yr`; tooltip + Glossary ✅ |
| Haus- und Grundbesitzerhaftpflicht | ⚠ Tooltip-only | Tooltip + Glossary ⚠ — label is plain English, term only in tooltip |
| Grundsteuer | ⚠ Tooltip + label | **Improved** — label `Property tax rate (Grundsteuer, % of price)` ✅ |
| Betriebskostenabrechnung | ❌ Tooltip-only | Tooltip + Glossary ✅ |
| Schornsteinfeger, Rundfunkbeitrag | Not user-visible | Mentioned in `Municipal €/m²/mo` tooltip (`app.py:431-432`) ⚠ |
| Nebenkosten | Not surfaced | Glossary entry ✅ |
| Warmmiete | ⚠ Tooltip-only | Glossary entry ✅ |

### 4.4 Financing — coverage gains since v1

| Term | v1 status | Current status |
|---|---|---|
| Annuitätendarlehen | ✅ adequate | ✅ Maintained |
| Tilgung | ⚠ tooltip + Methodology | Glossary entry (`app.py:1443-1444`) ✅ |
| Bausparvertrag | ⚠ Tooltip-only | Glossary entry ✅ |
| Finanzierungszusage | ❌ gap | **In-context** in `What now?` expander (`app.py:698`) ✅ |
| Grundschuld | Not user-visible | Still not user-visible — flag for Glossary inclusion |

### 4.5 Summary of coverage gaps (post v1)

**Still ❌ at point of use (not addressed by v1):**
- Solidaritätszuschlag — only in marginal-tax tooltip
- Sanierungspflicht / GEG (energy-renovation obligation, relevant for Altbau buyers — material in 2026)
- Grundschuld (loan registration; user encounters at notary)
- Sondereigentum — used in Operating costs / Property tooltips, not in Glossary

**Still ⚠ marginal:**
- Notar + Grundbuch — German term dropped from Summary purchase-row label
- Erhaltungsrücklage — visible in Capex tab caption but not in the Glossary table
- Kirchensteuer — flagged as not modelled but never glossed
- AfA at Capex tab (`app.py:1113`) — abbreviation appears as a column value with no in-tab gloss

**New drift / consistency issues:**
- Anschaffungsnaher Aufwand 15% threshold mentioned in Glossary, missing from Summary expander
- "What this tool does NOT model" wording differs between Summary expander and Methodology body
- "3-step walkthrough" wording differs between Summary expander and "New here?" tab

---

## 5. Severity summary and top risks

Counting each finding once:

| Severity | Count |
|---|---|
| 4 — Blocker | 0 |
| 3 — Major | 5 |
| 2 — Minor | 41 |
| 1 — Cosmetic | 12 |

**No blockers** is itself the v1 audit's biggest result — the landing experience now answers the JTBD. v2's findings are the next layer down: the new bottlenecks created by stacking helpful surfaces on top of the existing ones.

### Top 5 Goal-A risks (post-verdict)

1. **Summary tab is the new bottleneck** — 12 semantic blocks per tab; the verdict at the top is now followed by a long page that competes with itself. (`app.py:545-791`) [CLT, Krug, Nielsen H8]
2. **Mode-state visibility on Summary and Buy-vs-Rent** — the violet badge pattern stops at the detail tabs; the two surfaces whose semantics flip with mode have *no* badge. (`app.py:545, 796`) [Nielsen H6]
3. **Three banner types stack on Summary load** — sample-scenario + verdict + (conditional) live-mode warning, all coloured. Same visual weight forces parsing order. (`app.py:506-554`) [Nielsen H4, CLT]
4. **Duplicate live-mode warning** on Summary and Buy-vs-Rent fires the same trigger. (`app.py:547-554, 799-804`) [Progressive Disclosure, CLT redundancy]
5. **Operating costs expander still has 8 flat fields** — same as v1, not addressed; opening it is still a wall of dense labels. (`app.py:393-443`) [Progressive Disclosure, Nielsen H8]

### Top 5 Goal-B risks (educational depth)

1. **Drift between duplicated content blocks** — "NOT modelled", 3-step walkthrough, Anschaffungsnaher 15% threshold all exist in two places with subtly different wording. Maintenance + trust risk. (`app.py:557-581 vs 1250-1261, 1498-1504, 756-760 vs 1380-1391`) [Plain Language, JTBD trust]
2. **Costs pie chart has no caption** — only chart in the app without one. (`app.py:993-995`) [Dual Coding]
3. **Capex annual-bar / smoothed-reserve chart is the new explorable star but its long caption + missing cross-link** from the Methodology Petersche section throttle the win. (`app.py:1130-1162, 1486-1488`) [Explorable Explanations, CLT]
4. **Tax tab's negative-line / Verlustverrechnung explanation is below the totals**, separated from the chart caption that triggers the question. (`app.py:1217-1225`) [Dual Coding, Nielsen H10]
5. **Glossary lives in tab 1 only** — a user reading the Summary purchase-cost row can't reach it without leaving the page; the cross-tab term-lookup chain is broken. (`app.py:1380-1447`) [Nielsen H10]

### Lower-tier patterns worth a sweep

- **Long captions** on Capex (`app.py:1154-1162`) and **long tooltips** on Cost inflation / Hausgeld / Grundsteuer rate (`app.py:412-470`) — v1 P0-6 partial, finish the rewrite.
- **Negative-input prevention** on capex year and loan rate (`app.py:466-480, 253-258`).
- **`_is_scenario_modified` doesn't watch loans/capex** (`app.py:73-84`) — the modified badge is silently wrong for the most common edits.
- **Sample banner uses YAML key** instead of property name (`app.py:506-511`).

Both top-5 lists, plus the lower-tier sweep, are addressed in [`actionable_items.md`](./actionable_items.md).
