# Research — frameworks for auditing immokalkul's financial correctness

## Purpose

This is the financial-correctness companion to [`../UI/research.md`](../UI/research.md). Where the UI audit asks *does the app explain itself and not overwhelm*, this audit asks *does the app produce the right numbers, for the right reasons, traceable to German law and financial practice*.

Two parallel goals, analogous to Goal A / Goal B of the UI audit:

- **Goal C — computational correctness.** Every EUR displayed is computed without bug, crash, unit mismatch, or silently mis-applied rule across the plausible input space.
- **Goal D — factual traceability.** Every rate, threshold, and useful-life value traces to a primary German legal source (EStG, BGB, WEG, II. BV, GNotKG, GrEStG) or a reputable empirical source (BKI, paritätische Lebensdauertabelle, BORIS NRW, Bundesbank) — and the link is visible from the code, not just from `REFERENCES.md`.

A useful financial-audit framework for this app must therefore (1) verify *each statute-derived constant* against its source, (2) verify *each formula* against textbook finance, (3) surface *silent assumptions* the model makes that would mislead a diligent user, (4) identify *edge cases* that crash or produce junk numbers, (5) expose *bias direction* (a buyer-facing tool should lean pessimistic), and (6) audit *test coverage* so regressions are pinned. Frameworks that require deployment analytics, full Steuerberater review, or external statistical calibration are out of scope.

The engine is ~1,500 lines across 8 `.py` files plus ~1,900 lines in `app.py`; the audit works at the level of single constants, single formulas, and single tests — **not** architectural refactoring.

Below is the shortlist. Each entry states the framework, why it fits, the concrete audit questions it unlocks, and canonical references. Every framework is tied to automated tests where possible — this is the most important structural difference from the UI audit.

---

## 1. Primary-source verification

**Summary.** For every numerical constant and every decision threshold in the engine, verify: (a) does the code include a source citation, (b) does the value match the statute or reference, (c) would a future auditor be able to trace the number if the statute changed.

**Why it fits.** `rules_de.py` is the single file intended to hold every legally-derived constant. Its self-description — *"When tax law changes, this is the only file that needs touching"* — is a correctness invariant we can audit directly. A finding here is any rule where code diverges from source, any source that changed without the code catching up, or any constant whose provenance lives only in a comment (and not in `REFERENCES.md`).

**Audit questions.**
- Does each rate in `rules_de.py` carry an adjacent statute reference?
- For rules without explicit comments (operating-cost defaults, affordability thresholds), what is the implied source and where should it be documented?
- Where `REFERENCES.md` makes a claim about a rule, does the code actually implement that claim?
- Are there rules the code implements that are **not** covered in `REFERENCES.md`?

**Primary sources.**
- [§ 7 Abs. 4 EStG — AfA rates](https://www.gesetze-im-internet.de/estg/__7.html)
- [§ 6 Abs. 1 Nr. 1a EStG — Anschaffungsnaher Aufwand](https://www.gesetze-im-internet.de/estg/__6.html)
- [§ 19 WEG — Erhaltungsrücklage](https://www.gesetze-im-internet.de/woeigg/__19.html)
- [§ 28 II. BV — maintenance reserve table](https://www.gesetze-im-internet.de/bv_2/__28.html)
- [§§ 656a-d BGB — Maklerprovision split](https://www.gesetze-im-internet.de/bgb/__656a.html)
- [GrEStG + state-specific rate acts](https://www.gesetze-im-internet.de/grestg_1983/)
- [Jahressteuergesetz 2022 (§ 7 Abs. 4 EStG increase to 3%)](https://www.bgbl.de/xaver/bgbl/start.xav?startbk=Bundesanzeiger_BGBl&jumpTo=bgbl122s2294.pdf)

---

## 2. Formula correctness

**Summary.** Each closed-form formula (Annuitätendarlehen, AfA straight-line, Anschaffungsnaher threshold, building/land split, Petersche, Verlustverrechnung) has a textbook definition. The audit asks whether the Python matches the textbook.

**Why it fits.** Formula bugs are the kind of finding that survives many eyes of code review because the code *looks right* — the test is "does this output the same EUR a manual calculation would." CLT-style cognitive bugs don't apply at this layer; we're after unit mismatches, off-by-one in year indexing, sign errors, and mis-ordered operations.

**Audit questions.**
- For the annuity schedule, is interest computed on the opening balance, the closing balance, or some average?
- For the 15% Anschaffungsnaher Aufwand threshold, is the denominator the purchase price or the building value (the correct answer per BFH IX R 6/16)?
- For AfA, does the basis include capitalizable purchase fees at the right proportion?
- For Verlustverrechnung, does a rental loss produce tax savings linearly in the marginal rate?
- For the building/land split from Bodenrichtwert, what happens when Bodenrichtwert × plot > price?
- Is horizon indexing consistent across modules (all `range(1, N+1)` vs some `range(0, N)`)?

**References.**
- [Annuitätendarlehen formula — Wikipedia (DE)](https://de.wikipedia.org/wiki/Annuit%C3%A4tendarlehen)
- [BFH IX R 6/16 — Anschaffungsnaher on building value not price](https://www.bundesfinanzhof.de/en/entscheidungen/)
- [Peterssche Formel — Wikipedia (DE)](https://de.wikipedia.org/wiki/Petersche_Formel)

---

## 3. Model risk / silent assumptions

**Summary.** Even when every formula and constant is correct, a model can be wrong because of what it *does not say*. Silent assumptions are the simplifications the engine makes without surfacing them — and they are where a diligent user's Steuerberater check will diverge from the app's output.

**Why it fits.** The engine is deliberately simplified. Some simplifications are appropriate (e.g., treating Mietspiegel escalation as a single rate); some are material and should be documented (e.g., treating Hausgeld as 100% deductible); some are standard German practice but not obvious to a non-native user (e.g., annual interest compounding on monthly-paid annuities per § 488 BGB). This framework catalogues each one and asks: is the user informed?

**Audit questions.**
- What is the cash-flow timing convention (end-of-year, start-of-year, mid-year)?
- Does interest compound annually or monthly, and does it matter for the output?
- Is the marginal tax rate decomposed into income tax + Soli + Kirchensteuer, or taken as a blended user input?
- Does the Hausgeld input get split into deductible operating vs. non-deductible reserve portions, or treated as fully deductible?
- Is the maintenance reserve cash-flowed but not deducted (correct per § 19 WEG), and is that distinction visible?
- Are Mietpreisbremse (§ 556d BGB) and Kappungsgrenze (§ 558 BGB) enforced on rent escalation, or left to user discipline?

**A silent assumption is a finding even if the code is internally consistent.** The severity depends on magnitude of the EUR impact under plausible inputs and whether the simplification favours the user (see Framework 5).

---

## 4. Edge cases & numerical stability

**Summary.** Which plausible user inputs cause the engine to crash, return NaN, or silently produce junk numbers?

**Why it fits.** A Streamlit app is a live calculator; every sidebar change re-runs the engine. A crash is a worse Goal-A failure than any UI finding because it replaces the answer with a traceback. A silent junk number is worse than a crash because the user acts on it.

**Audit questions.** Sweep the input space for each of:
- `horizon_years` = 0, 1, 100
- interest rate = 0, negative
- `purchase_price` = 0
- `living_space_m2` = 0
- `income_net_monthly` = 0
- Bodenrichtwert × plot_size > purchase_price (land alone worth more than the whole property)
- `initial_capital` > total financing need
- all loans paid off before horizon
- `year_built` in the future
- `year_last_major_renovation` in the future
- capex item > purchase_price
- user enters rate as 4 (meaning 4%) not 0.04

For each, classify: **crash / NaN / silently clamped to valid / silently returns 0 / warns**. Crashes and silent junk are always findings; clamps need a disclosed disclaimer.

---

## 5. Conservative-bias check

**Summary.** A buyer-facing calculator should lean pessimistic — err toward higher costs, lower returns, longer payback, so the tool is unlikely to tell the user a marginal purchase is attractive when it isn't. Where does the code round *in the buyer's favour* instead?

**Why it fits.** A calculator that over-promises is a calculator that hurts its users. A calculator that under-promises is a calculator users might distrust; that's recoverable. So every silent assumption should be classified by bias direction, and user-optimistic assumptions get harsher severity than user-pessimistic ones of the same magnitude.

**Audit questions.**
- For each simplification catalogued under Framework 3, does it over- or under-state net wealth at the horizon?
- Which defaults (vacancy months/year, rent escalation, cost inflation, marginal tax rate) are generous?
- Does the model ever *help* the user rationalize a marginal purchase?
- Is there a net bias on apartments in appreciated markets (the population most likely to use this tool)?

---

## 6. Test coverage

**Summary.** Which rules are pinned by unit tests, and which would break silently if the code or a constant changed? A financial calculator without regression tests is a calculator that decays.

**Why it fits.** Every finding from Frameworks 1-5 that *should have been caught by a test but wasn't* is doubly a finding — the bug itself, plus the untested code path that let it survive. This framework produces the most directly actionable output: a list of tests to write.

**Audit questions.**
- For each primary-source rule (AfA, 15% Anschaffungsnaher, Petersche, II. BV, annuity, Verlustverrechnung), is there a test pinning the numerical output?
- For each edge case from Framework 4, is there a test?
- Are the tests *snapshot-style* (freezes today's output and would pin even buggy current behaviour) or *property-style* (asserts an invariant that would catch a refactor bug)?
- Are the tests at the right level of the engine (one per module, one per rule, one per user-visible EUR)?

**Method.** Every finding in the audit that can be expressed as a test should be. The actionable-items file (`actionable_items.md`) treats each testable finding as a prescription to write one test.

---

## 7. Regional applicability

**Summary.** The engine is pitched as "German property finance" but much of it is implicitly NRW-centric. This framework asks: which rules vary by Bundesland, are they parameterized or hardcoded, and how wrong is the output for a user outside NRW?

**Why it fits.** The Goal-B persona is a first-time buyer *in Germany*, not *in NRW specifically*. A Bayern user running the app with a Munich property gets Grunderwerbsteuer at NRW's 6.5% rate when Bayern charges 3.5% — a €18k error on a €600k purchase. This is a factuality failure (Goal D) masquerading as a data-entry responsibility.

**Audit questions.**
- Which constants in `rules_de.py` are genuinely federal (EStG, BGB, WEG) vs. state-specific?
- What are the 16 Bundesland values for each state-specific rate?
- How is the user told that NRW defaults apply?
- What would a minimum-viable "works for any Bundesland" version look like?

This framework's findings are concentrated enough to deserve a dedicated plan: see [`v1/germany_expansion.md`](./v1/germany_expansion.md).

**References.**
- [Grunderwerbsteuer rates by Bundesland (aktuell) — Haufe](https://www.haufe.de/immobilien/)
- [Grundsteuer Reform 2025 Länderöffnung](https://www.bundesfinanzministerium.de/)
- [BORIS Portal — all states](https://www.bodenrichtwerte-boris.de/)

---

## 8. Audit trail / traceability

**Summary.** Can the user (or a future maintainer) trace any displayed EUR back through the formula, the rule, and the primary source that produced it — without leaving the repository?

**Why it fits.** This is the operational translation of Goal D into a correctness test. If the user sees a number in the Summary tab and cannot, within two clicks, find the statute that produced it, the educational guarantee of the app fails — regardless of whether the number is correct. The UI audit already treats the Summary-tab layer; this framework treats the **code layer**.

**Audit questions.**
- Does the UI show the rate alongside the EUR (e.g., "Grunderwerbsteuer 6.5% → €29,250")?
- Does `REFERENCES.md` cover every rule in the code, with a reliability rank?
- Is each `rules_de.py` constant annotated with its statute in an adjacent comment?
- If a statute changes, is the change point singular and obvious?

---

## How the audit will apply these

The eight frameworks compose into a layered financial audit:

- **Statute-fidelity layer:** Frameworks 1, 7, 8 — does every rule map to a source, and is the mapping visible?
- **Formula layer:** Framework 2 — does the implementation match the textbook?
- **Model-disclosure layer:** Frameworks 3, 5 — what does the model hide, and in whose favour?
- **Robustness layer:** Framework 4 — what crashes or returns junk?
- **Regression layer:** Framework 6 — which findings become tests; which tests already pin the rule?

### Severity scale

Same as the UI audit, for direct comparability:

- **1 — Cosmetic:** doc nit, comment typo, unused line.
- **2 — Minor:** conservative/optimistic rounding within tolerance, silent simplification that is disclosed in README or without material EUR impact.
- **3 — Major:** wrong number in a plausible real-world scenario, or an undisclosed simplification with material EUR impact.
- **4 — Blocker:** crash, NaN propagation, or wrong number in the **default** scenario the first-open user will see.

Findings in `v1/audit.md` carry both a severity and a *testability* tag: most findings can be expressed as a unit test (see Framework 6 and `v1/actionable_items.md`); a minority are documentation issues where the right fix is a comment, a REFERENCES.md entry, or a UI caption.

---

## Frameworks deliberately excluded

- **Full Steuerberater review.** Confirming a tax number matches what a Steuerberater would produce for a specific household requires case-by-case work; out of scope.
- **External statistical calibration of empirical constants.** The 0.2% Grundsteuer proxy, the 2% escalation default, the 0.25-month vacancy default — these are empirical choices that would need a research project to re-calibrate. We audit whether they are *disclosed*, not whether they are *optimal*.
- **Stochastic / Monte-Carlo modelling.** The engine is deterministic by design; simulation-based risk metrics are a different product.
- **WCAG / internationalization.** Treated (in part) under the UI audit; not repeated here.

---

## Sources

- [§ 7 Abs. 4 EStG — AfA rates](https://www.gesetze-im-internet.de/estg/__7.html)
- [§ 6 Abs. 1 Nr. 1a EStG — Anschaffungsnaher Aufwand](https://www.gesetze-im-internet.de/estg/__6.html)
- [§ 19 WEG — Erhaltungsrücklage](https://www.gesetze-im-internet.de/woeigg/__19.html)
- [§ 28 II. BV — Instandhaltungskostenpauschale](https://www.gesetze-im-internet.de/bv_2/__28.html)
- [§§ 656a-d BGB — Maklerprovision split (post-2020)](https://www.gesetze-im-internet.de/bgb/__656a.html)
- [§ 488 BGB — Darlehensvertrag (interest crediting)](https://www.gesetze-im-internet.de/bgb/__488.html)
- [§§ 556d, 558 BGB — Mietpreisbremse, Kappungsgrenze](https://www.gesetze-im-internet.de/bgb/__556d.html)
- [§ 196 BauGB — Bodenrichtwerte](https://www.gesetze-im-internet.de/bbaug/__196.html)
- [GrEStG + 16 state-specific rate acts](https://www.gesetze-im-internet.de/grestg_1983/)
- [GNotKG — notary fee schedule](https://www.gesetze-im-internet.de/gnotkg/)
- [Jahressteuergesetz 2022 — § 7 Abs. 4 EStG increase](https://www.bgbl.de/)
- [BFH IX R 6/16 — Anschaffungsnaher on building value](https://www.bundesfinanzhof.de/)
- [Peterssche Formel — Wikipedia (DE)](https://de.wikipedia.org/wiki/Petersche_Formel)
- [Paritätische Lebensdauertabelle — Haus & Grund / Mieterverband](https://www.haus-und-grund.de/)
- [BKI Baukosteninformationszentrum](https://www.bki.de/)
- [BORIS Portal (all states)](https://www.bodenrichtwerte-boris.de/)
