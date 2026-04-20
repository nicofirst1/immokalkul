# Audit — immokalkul UX + educational review

Applies the eight frameworks from [`research.md`](./research.md) to `app.py` at its current state (1341 lines). All findings cite `file:line` where possible. Severity scale: **1 cosmetic** / **2 minor** / **3 major** / **4 blocker**.

Persona lens throughout: **first-time buyer living in Germany, not assumed to be German-native**. That means we fail if a first-time visitor gets overwhelmed *and* we fail if a user can't learn what a German term means without leaving the app.

---

## 1. Goal audit

### 1.1 5-second test (Goal A — "don't overwhelm")

**Scenario.** User opens the app for the first time. The Bonn-Poppelsdorf scenario (`data/bonn_poppelsdorf.yaml`) auto-loads (`app.py:40-41, 62-68`), `mode = "rent"` (yaml line 7), so the sidebar has three expanders open at once: Property (`app.py:139`), Financing (`app.py:180`), Rent parameters (`app.py:266` — `expanded=(s.mode=="rent")`). The header renders with five KPI metrics (`app.py:468-497`). Default tab is "🚀 Start here" (`app.py:1305, 1315`).

**What a five-second scanner sees.**

| Surface | Visible content | Goal A verdict |
|---|---|---|
| Sidebar top | `🏠 Property Calculator` / `German property finance — live vs. rent` (`app.py:99-100`) | ✅ tells the user what the app is |
| Sidebar, 3 expanders open | ~15+ numeric inputs — price, m², year, loans table, rent, vacancy, manager | ❌ **blocker — wall of inputs** |
| Main title | `🏠 Bonn-Poppelsdorf 3-Zimmer` (`app.py:470`) | ⚠ cryptic — user may think the app is for one house only |
| Header metrics | 5 KPIs: Mode RENT / Total purchase cost / Year-1 monthly burden / Years to debt-free / 50yr cumulative (`app.py:483-497`) | ⚠ numbers without a verdict sentence; "Mode: RENT" is a *state*, not a metric |
| Tab bar | 9 tabs with icons (`app.py:1304-1314`) | ⚠ on the upper edge of scannability |
| Start-here tab content | Welcome + 3-step walkthrough + plain-language glossary (`app.py:1050-1204`) | ✅ but the user sees this *after* the KPIs and sidebar, which have already landed |

**Scorecard.** Out of the five-second-test's three questions:

- *What is this page?* — **yes** (sidebar title + Start-here tab)
- *What is the headline answer for this scenario?* — **no**. The user sees five numbers; none is a sentence-form verdict. The ✅/❌ pass-fail narrative at `app.py:665-668` exists — buried inside the Summary tab, below the KPI cluster + input tables.
- *What do I do next?* — **partially**. The Start-here tab's 3-step walkthrough is visible once the user looks down, but the 3-expanders-open sidebar implies "fill this all in first," which contradicts the walkthrough's "tweak to see what-if."

**Severity-4 finding:** the landing experience is not delivering a verdict. A first-time user is presented with three times more input surface than output surface before any conclusion is stated.

### 1.2 First-click test (Goal B — "teach transparently")

**Prompt.** Assume the user has read the top KPIs and wants to understand where the number `€66,560` for *Total purchase cost* comes from. Where do they click?

**Expected path.** Summary tab → Purchase costs table (`app.py:685-696`). This table lists: Purchase price, Grunderwerbsteuer, Maklerprovision, Notary + Grundbuch, Initial renovation, Total. That's five rows with **no definitions and no rates adjacent**. A non-German user sees `Grunderwerbsteuer` as a foreign word of unknown value. The only way to learn the 6.5 % NRW rate encoded in `immokalkul/rules_de.py:61` is to scroll to the Methodology tab (tab 8 of 9, `app.py:1213-1262`) — and even there, `6.5%` is not stated; the user is redirected to the Finanzamt NRW site.

**Severity-3 finding:** the educational layer is misaligned with where the user asks educational questions. The user asks *at the point of use* (Summary's purchase cost table); we answer *in a reference tab* with an external link. This is the opposite of in-context teaching.

---

## 2. Heuristic findings (by framework)

### 2.1 Nielsen's 10 Heuristics

| # | Heuristic | Finding | Sev | Loc |
|---|---|---|---|---|
| H1 | Visibility of system status | No indicator distinguishes "unmodified Bonn scenario" from "modified scenario". After the user edits the price, there's no "(modified)" badge next to the scenario name in `render_header`. If they refresh, they lose work without warning. | 2 | `app.py:470, 116-120` |
| H1 | Visibility of system status | Engine errors render via `st.error + st.exception` (`app.py:1294-1296`) — good — but normal recomputes have no "updating…" indicator; minor on fast hardware, noticeable on slower devices. | 1 | `app.py:1291-1297` |
| H2 | Match system and real world | **German legal terms are shown without plain-English glosses** at the point of use: Grunderwerbsteuer / Maklerprovision / Notary + Grundbuch (`app.py:687-694`), AfA / capitalized fees / AfA basis / useful life (`app.py:719-726`), Annuitätendarlehen (`app.py:884`), Anschaffungsnaher Aufwand (only in sidebar caption `app.py:433`). Glosses do exist inside the Start-here tab (`app.py:1084-1192`) and Methodology tab, but those are remote from where the number is displayed. | **3** | multiple |
| H2 | Match system and real world | Sidebar label `Hausgeld (€/mo, rent mode)` (`app.py:360`) assumes the user knows what a Hausgeld is. Tooltip explains it but the label alone is jargon. | 3 | `app.py:360` |
| H2 | Match system and real world | Sidebar label `Grundsteuer rate (% of price)` (`app.py:354`) uses a German term; user may not know this is "property tax." | 2 | `app.py:354` |
| H3 | User control and freedom | No undo for data-editor edits (loans table, capex table). User can accidentally delete a row and there's no obvious recovery path aside from re-loading the YAML. | 2 | `app.py:209-253, 442-457` |
| H3 | User control and freedom | No "reset this section to scenario defaults" button per section. | 1 | `app.py:94-462` |
| H4 | Consistency and standards | The `Mode` KPI (`app.py:484`) shows e.g. `RENT` but the tab content dynamically switches on the same variable — user must learn that changing the sidebar radio retunes every tab. Inconsistent with the 5-KPI strip which reads like a fixed report. | 2 | `app.py:483-497` |
| H4 | Consistency and standards | Footer uses raw HTML (`app.py:1330-1336`) while every other surface uses Streamlit markdown. Minor stylistic drift. | 1 | `app.py:1330-1336` |
| H4 | Consistency and standards | Tab icons are a mix of single- and double-character glyphs (`🚀 📋 ⚖ 💸 💡 🏦 🔨 🧾 📚`) — visually unstable; `⚖` and `🧾` render narrower. | 1 | `app.py:1304-1314` |
| H5 | Error prevention | `marginal_tax_rate` slider is clamped 20 – 50 % (`app.py:413`). A part-time earner could legitimately have ~14 %; a high earner with Kirchensteuer could exceed 50 %. User cannot enter outside this range. | 2 | `app.py:413` |
| H5 | Error prevention | `Suggested Bank principal` caption (`app.py:260-262`) is a valuable reality-check that could prevent silently miscomputed scenarios. But it's only a caption — doesn't block save/run. Keep as-is for now, just highlight it. | 1 | `app.py:256-263` |
| H5 | Error prevention | Capex editor accepts negative costs (no `min_value=0`), which would break downstream sums. | 2 | `app.py:442-457` |
| H6 | Recognition over recall | **The mode radio (`app.py:132`) sets a state the user must remember across every tab.** The only in-tab reminder is a subtitle like `Cash flow — RENT mode` (`app.py:795`) — easy to miss. | 3 | `app.py:132, 795, 843, 882` |
| H6 | Recognition over recall | The `current_monthly_rent_warm_eur` value (`app.py:327-336`) is entered in the sidebar, then its value drives the `Ownership vs current rent` KPI in Summary (`app.py:589-602`). User sees the delta without the reference; if they forgot what they entered, they can't interpret the number. | 2 | `app.py:327, 589-602` |
| H6 | Recognition over recall | All KPI `help=` tooltips explain the *formula*; none shows the *raw inputs*. E.g., the loan/income metric (`app.py:537-543`) explains "monthly debt service as share of monthly net income" but doesn't echo the actual income number pulled from the sidebar. | 2 | `app.py:537-543` |
| H7 | Flexibility and efficiency | No novice / expert toggle. Adaptive loans, Bodenrichtwert override, Denkmal flag, Anschaffungsnaher window, auto-schedule-capex (`app.py:175-177, 166-170, 185-198, 459-462`) are all exposed in line with basic fields. Novice sees the same sidebar as the power user. | 3 | `app.py:94-462` |
| H7 | Flexibility and efficiency | YAML upload (`app.py:114-120`) is a power-user shortcut; fine to keep, already disclosed behind an expander. | — | `app.py:103-129` |
| H8 | Aesthetic and minimalist | Header has 5 metrics; Summary tab's "Can you afford this?" has 4 more + "Return, leverage, timing" 4 more = 13 metric tiles within one viewport on a wide screen. Above Miller's 7±2; and three of the header metrics (Year-1 monthly burden, Years to debt-free, Mode) duplicate Summary content. | 3 | `app.py:468-497, 536-627` |
| H8 | Aesthetic and minimalist | Sidebar `Operating costs` expander contains **8 inputs** (gas, electricity, Grundsteuer, Hausgeld, Administration, Municipal, Building insurance, Liability insurance — `app.py:345-387`), each with a help icon. If the expander is opened, user sees a dense column of numbers most of which should stay at default. | 2 | `app.py:339-387` |
| H8 | Aesthetic and minimalist | `Property` expander shows 11 fields in 2 columns (`app.py:140-177`) — combines "physical facts" (price, m², year) and "tax-relevant flags" (Bodenrichtwert, Denkmal) without sub-grouping. | 2 | `app.py:140-177` |
| H9 | Error recovery | Calculation errors print `st.exception` (the full Python traceback — `app.py:1296`). Scares a non-developer. | 2 | `app.py:1294-1297` |
| H10 | Help and documentation | The Start-here tab + Methodology tab are the strongest help surfaces in the app — well-written, reference-linked. **But they are two separate tabs** (tab 0 and tab 8), requiring the user to remember that long-form explanation is split across the tab bar. | 2 | `app.py:1050-1262` |
| H10 | Help and documentation | No glossary of German terms. `Start here` has a *per-sidebar-section* walkthrough but not an alphabetical index — impossible to look up "what's Petersche?" without knowing it's tied to capex. | 3 | `app.py:1082-1192` |

### 2.2 Cognitive Load Theory (CLT)

| Finding | Type of load | Sev | Loc |
|---|---|---|---|
| Three sidebar expanders open at once on first load (Property + Financing + Rent-params) — user parses ~15 fields simultaneously before reaching an output. | Extraneous | **3** | `app.py:139, 180, 266` |
| Header 5-KPI strip sits *above* the "Start here" tab content. Goal-A persona lands on the welcome tab; but their eye has already absorbed five numeric tiles before reading the walkthrough. Split-attention between the header number and the sidebar input that produced it. | Extraneous | 3 | `app.py:468-497, 1050-1081` |
| The Summary tab's "Can you afford this?" strip (`app.py:535-627`) is a *worked example* in CLT terms: four metrics with explicit pass/fail thresholds + a narrative strip (`app.py:665-668`). This is the highest-quality surface in the app. | Germane (positive) | — | `app.py:535-668` |
| Default Bonn scenario pre-loads (`app.py:62-68`). Good — prevents blank-form paralysis. But it isn't *framed* as a worked example — no "this is a Bonn Altbau; here's why these numbers look the way they do." User may not realise the data is illustrative. | Germane underused | 2 | `app.py:62-68, 1053-1067` |
| Redundancy: `Year-1 monthly burden on salary` appears in the header (`app.py:488`) and again in Summary's `Net burden / income` (`app.py:545-550`). Same number, two labels, different framings. | Extraneous | 2 | `app.py:488, 545` |
| Tab `Live vs Rent` computes both modes regardless of sidebar mode (`app.py:1288-1293`). Useful, but forces the user to hold *two parallel realities* in mind. Without a "which one is cheaper" explicit callout, the user has to visually compare two 50-year charts. | Intrinsic unmanaged | 3 | `app.py:730-776` |
| All the chart tabs (Cash flow, Debt, Capex, Tax) present 3-5 concurrent traces per chart. No in-chart annotations, no "watch the crossover at year 18" arrows. High intrinsic load is served raw. | Intrinsic unmanaged | 3 | `app.py:798-815, 896-919, 973-984, 1020-1037` |

### 2.3 Progressive Disclosure

| Finding | Sev | Loc |
|---|---|---|
| **On load, three of eight sidebar expanders are open** — Property, Financing, and (because default mode is "rent") Rent parameters. The persona doesn't need all three at once. | **3** | `app.py:139, 180, 266` |
| Tab bar exposes 9 tabs at once with no hierarchy. Compare: Summary (answer) / Live vs Rent (comparison) are peer with Cash flow / Debt / Capex / Tax (detail) and Start here / Methodology (help). | 3 | `app.py:1304-1314` |
| "Total monthly debt budget" input (`app.py:189-198`) is visible even when no loan is flagged Adaptive. The tooltip admits "No adaptive loan set, so this value is inert." — exactly the case for the default Bonn scenario on load. Should be hidden until a loan toggles Adaptive. | 3 | `app.py:189-198` |
| `auto_schedule_capex` checkbox, user-capex editor, Anschaffungsnaher automatic behaviour — all exposed in the sidebar's "User-specified renovations" expander which is collapsed by default (`app.py:430`). Good. | — (positive) | `app.py:430-462` |
| Summary tab shows the full set of four *Can-you-afford* metrics + four *Return-leverage-timing* metrics + a success-strip + Property/Purchase/Financing/AfA tables all at once. No progressive disclosure inside the Summary tab — everything is visible the moment the tab opens. | 2 | `app.py:503-727` |
| "Year-by-year" tables across Cash flow (`app.py:828-838`), Debt (`app.py:942-944`), Tax (`app.py:1046-1047`) are behind expanders. Good use of progressive disclosure. | — (positive) | multiple |

### 2.4 Krug — "Don't Make Me Think"

| Finding | Sev | Loc |
|---|---|---|
| Tab label `⚖ Live vs Rent` — icon does not clearly signal "comparison." A user not familiar with the scales-of-justice metaphor may read it as "ethics." | 1 | `app.py:1307` |
| Sidebar title `🏠 Property Calculator` repeats the main-area title `🏠 {property name}` — two `🏠` emojis with different semantics compete for attention. | 1 | `app.py:99, 470` |
| Many tooltip strings are 3-4 sentences long. Example: `annual_rent_escalation` tooltip (`app.py:284-288`) packs four claims into 90 words. Fails "halve the words." | 2 | `app.py:284-288, 319-326, 331-336` |
| The Summary tab's verdict narrative (`app.py:665-668`) uses `st.error` for failures + `st.success` for passes. **This is the single most scannable surface in the app** — a user who lands on Summary will see two coloured boxes and read them. Keep; amplify. | — (positive) | `app.py:665-668` |
| No page-top one-sentence verdict. A Krug scanner spends their first 1-2 seconds on the area between the title and the tab bar; we currently use that area for 5 numeric tiles. | **3** | `app.py:470-497` |
| The 9-tab bar label "📚 Methodology" is unambiguous but also unavoidable; a scanner looking for "help" won't necessarily hit it — the first tab `🚀 Start here` is the onboarding, not a methodology reference. Two help surfaces split across the bar. | 2 | `app.py:1305, 1313` |

### 2.5 Explorable Explanations

| Finding | Sev | Loc |
|---|---|---|
| Every sidebar control is a live parameter — change any input, everything updates. The Streamlit auto-rerun is a textbook *reactive document* pattern; this is the strongest implicit explorable-explanations foundation in the app. | — (positive) | `app.py:1281-1323` |
| No *guided tour* exists. The Start-here tab (`app.py:1050-1204`) is static prose — does not drive the user to "try changing the initial capital to €150k and watch the 30 %-rule strip." | 3 | `app.py:1050-1204` |
| No chart carries a *caption* that names the insight. Titles are labels (`Capex timeline`, `Cost composition`, `Cumulative position`) not questions (`How long until I'm debt-free?`). | 3 | `app.py:761-763, 822, 875, 975` |
| No counterfactual prompt anywhere. "What if rates rise 1 %?" is answerable via the loans table but never suggested. | 2 | app-wide |
| The pre-loaded Bonn scenario is a de-facto worked example but is not labelled as one. A first-time user may think it's "the wrong number" for them and immediately try to overwrite. | 2 | `app.py:40-41, 62-68` |

### 2.6 Plain Language + Microcopy

| Finding | Sev | Loc |
|---|---|---|
| Label `Hausgeld (€/mo, rent mode)` — German noun, unfamiliar to expat persona. | 3 | `app.py:360` |
| Label `Grundsteuer rate (% of price)` — same. | 2 | `app.py:354` |
| Label `Monthly rent (Kaltmiete, €)` — German introduced in parentheses after the English; good pattern. Reuse elsewhere. | — (positive) | `app.py:271` |
| Tooltip for `annual_rent_escalation` (`app.py:284-288`) — four densely-packed claims. Could become two sentences. | 2 | `app.py:284-288` |
| `Grenzsteuersatz` used in the marginal-tax tooltip (`app.py:413`) without a plain-English gloss. | 2 | `app.py:413-420` |
| `burden` used as a label (`app.py:488, 546`) — financial microcopy convention would say `net cost to household`. | 2 | `app.py:488, 546` |
| `LTV` (Loan-to-value) is introduced only inline on the Summary tab (`app.py:617`) with a parenthetical. Consistent. | 1 | `app.py:617` |
| Start-here tab writes in "you" voice ("Pick a scenario…") — good plain-language convention. Preserve. | — (positive) | `app.py:1070-1081` |
| Methodology tab has the phrase *"this floors annual tax at €0 even in loss years"* (`app.py:1042`) — truthful, but uses jargon ("floors") where "this model doesn't let tax go negative" would be clearer. | 1 | `app.py:1042-1044` |

### 2.7 Dual Coding Theory

| Finding | Sev | Loc |
|---|---|---|
| Summary tab has prose sub-headings + metric tiles (verbal channel strong; visual = metric tiles with colour deltas). No chart. | — | `app.py:535-627` |
| Live-vs-Rent tab has the 50-year cumulative chart and a month-1 comparison table — **no captions**, no sentence stating which mode "wins" in this scenario. Visual channel served alone. | 3 | `app.py:747-776` |
| Cash flow tab: bar + line chart, then table behind expander. No prose tells the user what the black net-property line represents or what the zero crossing means. | 3 | `app.py:793-838` |
| Costs tab: table + pie chart in parallel. No prose tying the largest pie slice to a recommendation ("Hausgeld is your biggest cost — worth auditing"). | 2 | `app.py:841-877` |
| Debt tab: balance stack chart + payment-breakdown chart + summary table. Caption at the top (`app.py:883-886`) is introductory but describes *what the engine does*, not *what the user should look at*. | 2 | `app.py:880-944` |
| Capex tab: bubble-scatter timeline is unusual. The mapping (bubble size = inflated cost) appears in the chart title but not in an adjacent caption. | 2 | `app.py:972-977` |
| Tax tab: bar+line chart with 5 series on a single axis (`app.py:1020-1037`). No visual hierarchy or legend annotation. High dual-channel load on a novice. | 3 | `app.py:1020-1037` |

### 2.8 Jobs-to-be-Done

| Finding | Sev | Loc |
|---|---|---|
| Core JTBD ("can my finances absorb this property?") is answered indirectly through 13 metric tiles + a pass/fail strip. No one-sentence verdict. | **4** (Goal-A blocker) | `app.py:468-497, 535-668` |
| Related job "is this a reasonable *price*?" not served. The app takes price as an input; doesn't cross-check against Bodenrichtwert × plot + rough building estimate. The data is already in the engine — the check would be cheap. | 3 | `immokalkul/tax.py`, surfaced nowhere |
| Related job "how much down payment do I need?" partially served via Summary's `Down payment / price` metric (`app.py:552-558`), but no reverse-computation (e.g., "to hit 20 % down you'd need €X more"). | 2 | `app.py:552-558` |
| Related job "what if rates change?" not scaffolded. User can edit the rate column in the loans editor, but there's no sensitivity strip. | 2 | `app.py:201-253` |
| Next-step support missing. After the user reads their verdict, there's no "what now?" panel — no link to Finanzierungszusage / Steuerberater / BORIS NRW beyond the Methodology tab's reference list. | 3 | `app.py:1207-1262` |

---

## 3. Per-surface findings

### 3.1 Sidebar (`app.py:94-462`)

- **Too many fields visible on load** — default expanded = Property + Financing + (Rent-params because mode=rent). Seven to ten additional inputs visible the moment the user opens the sidebar. **Severity 3.**
- **Scenarios expander is collapsed by default** (`app.py:103`) but it's the highest-leverage feature for a first-time user — the whole point of worked examples (Bonn / Munich / Berlin / Köln). Should be open on first visit. **Severity 2.**
- **Mode radio placement** is correct (top, visible) but the labels *live* / *rent* are domain jargon to the persona. *Live in it* / *Rent it out* would fit plain-language. **Severity 2.**
- **Data-editor for loans** is powerful but intimidating. Novice with a single bank loan would be better served by a "Just one loan?" simple-form radio that renders three `st.number_input`s; the editor could be behind an "I have more than one loan" toggle. **Severity 2.**
- **`Total monthly debt budget`** is inert when no Adaptive flag is checked (self-admitted at `app.py:197-198`). Hide or grey-out. **Severity 3.**
- **Denkmal / Bodenrichtwert / Anschaffungsnaher / Adaptive / auto-schedule-capex** — expert controls interleaved with basic fields. No visual separation (e.g., an "advanced" sub-expander). **Severity 3.**
- **Grunderwerbsteuer's 6.5 % NRW rate** is not surfaced anywhere the user can see — it's hardcoded in `rules_de.py:61`. The Summary table shows the computed EUR but not the percentage or the Bundesland. **Severity 2.**
- **Tooltip length.** Several `help=` props exceed ~80 words; e.g., `annual_rent_escalation` (`app.py:284-288`), `expected_vacancy_months_per_year` (`app.py:292-296`), `current_monthly_rent_warm_eur` (`app.py:331-336`). Users scan; they won't read 80-word tooltips. **Severity 2.**

### 3.2 Header (`app.py:468-497`)

- **No verdict line.** Five tiles, each a number. Should carry a one-sentence answer: "*At your income, this property is within the 30% rule — lightly stretched.*" **Severity 4** (drives Goal-A blocker).
- **`Mode` as a metric tile** is a state, not a KPI. Repurpose as a toggle / tag instead. **Severity 2.**
- **`Total purchase cost`** (not purchase *price*) is a good micro-teaching signal but needs a plain-English gloss: "price plus Grunderwerbsteuer + Makler + Notar." **Severity 2.**
- **`50yr cumulative`** is a signed EUR number that requires the user to know (a) sign conventions, (b) what "cumulative wealth change" captures, (c) that 50 years is the horizon default. None of this is visible in the KPI. **Severity 3.**
- **No scenario modification indicator.** After editing the scenario, the title still reads "Bonn-Poppelsdorf 3-Zimmer" even if every number has been replaced. **Severity 2.**

### 3.3 Summary tab (`app.py:503-727`)

- **Strongest surface in the app.** "Can you afford this?" heading + 4 rule-based metrics + pass-fail strip is exactly the JTBD answer. Protect it.
- **Pass-fail strip** (`app.py:665-668`) should be elevated higher in the page — currently appears below *two* blocks of 4 metrics (`app.py:535-627`). The narrative is the verdict; the metrics support it, not the other way around.
- **Purchase costs table** (`app.py:685-696`) lists German line items without rates, definitions, or sources. A non-German user sees "Grunderwerbsteuer €29k" and has no framework to evaluate it. **Severity 3.**
- **AfA block** (`app.py:718-727`) shows rate + useful life + basis + annual AfA. Good. But the AfA concept itself isn't introduced here — user has to know it's a depreciation mechanism available only to rental landlords. **Severity 2.**
- **"Return, leverage, timing" heading** is expert vocabulary. "Cost & timing" would read plainly. **Severity 2.**
- **`Ownership vs current rent`** (live mode only, `app.py:589-602`) — great feature introduced in commit `4a4bf86`. Only renders if the user filled in `current_monthly_rent_warm_eur`; the sidebar caption tells them to but the absence state on the KPI is a generic "set your current warm rent" message. **Severity 1.**

### 3.4 Live vs Rent tab (`app.py:730-776`)

- **Central feature** — the comparison is what makes this app not a generic calculator. It is the second-most-load-bearing surface.
- **No verdict.** Two side-by-side "mode summary" blocks + a 50-year chart + a monthly cash-flow table. User is left to compare 13 numbers across two modes. Should carry a sentence: "*After year 14, rent mode pulls ahead; if you plan to hold >15 years, rent-mode pencils out.*" **Severity 3.**
- **50-year chart title missing.** The `fig.update_layout` sets x/y axis titles but no `title=`. The markdown heading (`app.py:748`) says "50-year cumulative wealth change" — fine — but there's no caption telling the user what the crossover point means. **Severity 2.**
- **Red/blue colour assignments** for Live/Rent (`app.py:756-758`) are picked from the Tableau palette and are fine, but there's no legend telling the user "red = live, blue = rent." The legend is auto-generated by Plotly. Colour-blind users (~8% of males) will struggle; consider adding a subtle pattern or label. **Severity 1.**

### 3.5 Cash flow, Debt, Capex, Tax tabs

- **Cash flow tab** (`app.py:793-838`) — dense bar+line chart (6 series in rent mode), then a table. Zero captions, zero insight callouts. **Severity 3** (on dual coding).
- **Debt tab** (`app.py:880-944`) — stacked balance chart, payment breakdown chart, summary table, expander. Caption at top describes the algorithm, not the insight. **Severity 2.**
- **Capex tab** (`app.py:947-995`) — bubble-scatter timeline is unusual and low-literacy for novices. Annual aggregate bar chart is clearer. Consider prioritising the bar chart. **Severity 2.**
- **Tax tab** (`app.py:998-1047`) — 5-series bar+line chart + the explicit caveat "this floors annual tax at €0 even in loss years" (good transparency). But the caveat is at the bottom; a user who doesn't read to the bottom applies the shown numbers uncritically. Caveat should be higher. **Severity 2.**

### 3.6 Costs tab (`app.py:841-877`)

- Table with 8 columns (Item, Annual €, Monthly €, Live ✓, Rent ✓, Active ✓, Deductible (rent) ✓, Note) is **too wide**; on 13" screens, the Note column wraps awkwardly.
- Pie chart at bottom duplicates the table's proportions. Without prose connecting them (e.g., "Hausgeld and Grundsteuer account for X%") it's redundant. **Severity 2.**
- Totals footer (`app.py:867-868`) is a single markdown line; should be a `st.metric` tile for consistency with other tabs. **Severity 1.**

### 3.7 Start here tab (`app.py:1050-1204`)

- Excellent content. Welcome + privacy note + 3-step walkthrough + per-section glossary + "what to read after this."
- **Placement problem.** It's tab 0 by default so the user lands on it — good — but the header KPIs appear *above* the tab content. A strict Krug scanner may read the KPIs first (numbers always attract the eye) and skip the onboarding below.
- **3-step walkthrough could be interactive.** Currently static prose at `app.py:1069-1080`. A Case-style "click to advance" could be done with session_state + `st.button` without architectural change. **Severity 2.**
- **No glossary of German terms.** Per-section plain-language is excellent but not searchable. **Severity 3** (see H10 Help).

### 3.8 Methodology tab (`app.py:1207-1262`)

- Dense but well-organised. Citations to gesetze-im-internet.de, Finanzamt NRW, BORIS NRW — primary sources. Tier-ranked references.
- **No table of contents inside the tab.** User scrolls to find AfA vs. Petersche. **Severity 1.**
- **"What this tool does NOT model"** section (`app.py:1236-1242`) is the single most important transparency surface — boosts Goal B's trust. Consider elevating.

### 3.9 Footer (`app.py:1328-1337`)

- Raw HTML with attribution only. No disclaimer, no "not financial advice", no version/date, no link to source or to REFERENCES.md. **Severity 2** (for Goal B — transparency expects this).

---

## 4. Educational coverage matrix

Rating each German term for *where* the user encounters an explanation:

- **Unexplained** — term appears without definition
- **Tooltip-only** — definition is inside a `help=` prop (scanner-invisible per Krug)
- **In-context** — definition is in visible copy adjacent to first use
- **Dedicated** — full explanation in Start-here or Methodology tab

### 4.1 Tax / legal

| Term | Where used | Current coverage | Goal-B rating |
|---|---|---|---|
| AfA (Absetzung für Abnutzung) | Summary (`app.py:719`), Tax tab (`1000-1016`), Start here, Methodology | Dedicated + in-context | ✅ adequate |
| Grunderwerbsteuer | Summary purchase table (`app.py:689`), Methodology | **Unexplained at point of use** | ❌ gap |
| Maklerprovision | Summary purchase table (`app.py:690`), Methodology | **Unexplained at point of use** | ❌ gap |
| Notar / Grundbuch | Summary purchase table (`app.py:691`) | **Unexplained at point of use** | ❌ gap |
| Anschaffungsnaher Aufwand | Sidebar capex caption (`app.py:433`), Methodology | Tooltip-only + Methodology | ⚠ marginal |
| Herstellungskosten | Sidebar capex caption (`app.py:433`) | Tooltip-only | ❌ gap |
| Erhaltungsaufwand | Sidebar capex caption (`app.py:433`) | Tooltip-only | ❌ gap |
| Denkmal (§7i EStG) | Sidebar checkbox (`app.py:175-177`) | Tooltip-only | ⚠ marginal |
| Werbungskosten / Geldbeschaffungskosten | `rules_de.py:70` (not user-visible) | Not shown | — |
| Grenzsteuersatz | Sidebar marginal tax rate tooltip (`app.py:413-420`) | Tooltip-only | ⚠ marginal |
| Einkommensteuer §32a EStG | Sidebar marginal tax rate tooltip | Tooltip-only | ❌ gap |
| Solidaritätszuschlag / Soli | Sidebar marginal tax rate tooltip (`app.py:420`) | Tooltip-only | ❌ gap |
| Anschaffungsnebenkosten | Methodology tab | Dedicated only | ⚠ marginal |
| Sonder-AfA §7b | Methodology tab (`app.py:1242`) | Dedicated only — flagged as not implemented | ✅ (transparency good) |

### 4.2 Property-specific

| Term | Where used | Current coverage | Goal-B rating |
|---|---|---|---|
| Bodenrichtwert | Sidebar input + tooltip (`app.py:166-170`), Start-here, Methodology | Tooltip + Dedicated, with BORIS NRW link | ✅ adequate |
| Wohnfläche | Sidebar tooltip (`app.py:160`), Start here | Tooltip + Dedicated | ✅ adequate |
| WEG / Gemeinschaftseigentum / Sondereigentum | Sidebar tooltips (`app.py:160, 362-367`) | Tooltip-only | ⚠ marginal |
| Erhaltungsrücklage (§19 WEG) | Methodology tab | Dedicated only | ⚠ marginal |
| Energieausweis | Sidebar tooltip (`app.py:165`) | Tooltip-only | ⚠ marginal |
| Energiebedarf (kWh/m²/yr) | Sidebar input (`app.py:161-165`) with thresholds (<100 good, 100-150 avg, 150+ poor) | In-context | ✅ adequate |
| Altbau / Neubau | AfA block in Summary (`app.py:726`) | In-context | ✅ adequate |
| Einfamilienhaus | Sample scenario name | Unexplained (but only in a file name) | — |
| GEG / EnEV / Sanierungspflicht | `rules_de.py:146-164` | Not user-visible | — |

### 4.3 Cost / operating

| Term | Where used | Current coverage | Goal-B rating |
|---|---|---|---|
| Kaltmiete | Sidebar label (`app.py:271`) | In-context (good pattern) | ✅ |
| Warmmiete / Nebenkosten | Sidebar tooltip live.current_monthly_rent_warm_eur (`app.py:331-336`) | Tooltip-only | ⚠ marginal |
| Hausgeld | Sidebar label (`app.py:360`), Methodology | Tooltip-only + Dedicated | ❌ label uses jargon without gloss |
| Mietspiegel / Mietpreisbremse | Sidebar tooltip (`app.py:284-288`) | Tooltip-only | ⚠ marginal |
| Hausverwaltung / Verwalterhonorar | Sidebar tooltip (`app.py:368-372`) | Tooltip-only | ⚠ marginal |
| Wohngebäudeversicherung | Sidebar tooltip (`app.py:378-382`) | Tooltip-only | ⚠ marginal |
| Haus- und Grundbesitzerhaftpflicht | Sidebar tooltip (`app.py:383-387`) | Tooltip-only | ⚠ marginal |
| Grundsteuer (Bundesmodell, Hebesatz) | Sidebar label (`app.py:354`) + tooltip | Tooltip + label partially | ⚠ marginal |
| Schornsteinfeger, Rundfunkbeitrag | `rules_de.py:180-181` | Not user-visible | — |
| Betriebskostenabrechnung | Sidebar tooltip (`app.py:366-367`) | Tooltip-only | ❌ gap |

### 4.4 Financing / loan

| Term | Where used | Current coverage | Goal-B rating |
|---|---|---|---|
| Annuitätendarlehen / Annuität | Data-editor tooltip (`app.py:229-233`), Debt tab caption (`app.py:884`), Methodology | Tooltip + Dedicated | ✅ adequate |
| Tilgung | Data-editor tooltip (`app.py:226`), Methodology | Tooltip + Dedicated | ⚠ marginal (label not used in visible copy) |
| Bausparvertrag / LBS | Data-editor tooltip (`app.py:232-233`), Bonn YAML sample | Tooltip-only | ⚠ marginal |
| Adaptive loan | Data-editor tooltip (`app.py:234-239`), Start here | Tooltip + Dedicated | ✅ adequate |
| Finanzierungszusage | Not mentioned | Unexplained | ❌ gap (JTBD next-step concept) |
| Grundschuld | `rules_de.py:70` | Not user-visible | — |

### 4.5 Methodology / sources

| Term | Where used | Current coverage | Goal-B rating |
|---|---|---|---|
| Petersche Formel | Methodology tab (`app.py:1224-1226`), Wikipedia link | Dedicated | ✅ adequate |
| II. Berechnungsverordnung / II. BV | Methodology tab (`app.py:1255`) | Dedicated | ✅ adequate |
| Paritätische Lebensdauertabelle (HEV/MV) | Methodology tab (`app.py:1232`) | Dedicated | ✅ adequate |
| BKI (Baukosteninformationszentrum) | Methodology tab (`app.py:1234`) | Dedicated | ✅ adequate |
| BORIS NRW | Sidebar tooltip + Methodology + REFERENCES | Tooltip + Dedicated | ✅ adequate |
| BFH (Bundesfinanzhof) | `rules_de.py:10` / REFERENCES.md only | Not user-visible | — |

### 4.6 Summary of coverage gaps

**Unexplained at point of use (visible in Summary tab, no gloss adjacent):**
- Grunderwerbsteuer
- Maklerprovision
- Notar / Grundbuch

**Tooltip-only for high-importance terms a first-time buyer will ask about:**
- Hausgeld (label uses raw term)
- Mietspiegel / Mietpreisbremse
- Hausverwaltung
- Grenzsteuersatz
- Betriebskostenabrechnung
- Herstellungskosten / Erhaltungsaufwand
- WEG-terms (Gemeinschaftseigentum, Sondereigentum, Erhaltungsrücklage)

**Missing entirely:**
- No alphabetical glossary tying the above together
- No visible rate: the 6.5 % Grunderwerbsteuer NRW, the 3.57 % Makler, the 2 % Notar + Grundbuch — all encoded in `rules_de.py` but none surfaced as a number the user sees alongside its EUR product

---

## 5. Severity summary and top risks

Counting by severity (each finding counted once):

| Severity | Count |
|---|---|
| 4 — Blocker | 2 |
| 3 — Major | 22 |
| 2 — Minor | 27 |
| 1 — Cosmetic | 9 |

### Top 5 Goal-A risks (first-open disengagement)

1. **No top-of-page verdict sentence** — the user sees 5 numbers, not an answer (`app.py:468-497`). [Nielsen H8, Krug 5s, JTBD, CLT extraneous]
2. **Three sidebar expanders open on load** — visual overload before the user asks a question (`app.py:139, 180, 266`). [Progressive Disclosure, CLT]
3. **Expert controls interleaved with basic inputs** — Adaptive, Denkmal, Bodenrichtwert, Anschaffungsnaher all visible in the novice's field of view (`app.py:94-462`). [Nielsen H7, Progressive Disclosure]
4. **13+ metric tiles in Header + Summary with redundancies** — exceeds Miller's 7±2 (`app.py:468-497, 535-627`). [Nielsen H8, CLT]
5. **Inert "Total monthly debt budget" input always visible** (`app.py:189-198`). [Progressive Disclosure]

### Top 5 Goal-B risks (educational transparency failure)

1. **Grunderwerbsteuer / Maklerprovision / Notar line items in the Summary Purchase-costs table have no definitions or rates adjacent** (`app.py:685-696`). [Plain Language, Nielsen H2]
2. **No alphabetical glossary of German terms** — the per-section walkthrough in Start-here doesn't index by term (`app.py:1050-1204`). [Nielsen H10, Plain Language]
3. **Charts have titles but no insight captions** — dual-channel learning broken across Cash-flow, Debt, Capex, Tax tabs. [Dual Coding]
4. **No guided tour / counterfactual prompts** — the reactive document is never explicitly invited. [Explorable Explanations]
5. **Methodology tab is the eighth of nine tabs** — user has to hunt for the transparency layer. [Nielsen H10]

Both top-5 lists are addressed in [`actionable_items.md`](./actionable_items.md), with each item linked back to one or more of the above findings.
