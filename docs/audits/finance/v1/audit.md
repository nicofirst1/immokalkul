# Audit v1 — immokalkul financial correctness + factual review

Applies the eight frameworks from [`../research.md`](../research.md) to the engine in `immokalkul/*.py` (1,517 LOC across 8 files) plus `REFERENCES.md` and the sample scenario in `data/bonn_poppelsdorf.yaml`. All findings cite `file:line`. Severity scale 1-4 per `research.md`.

Persona lens: first-time buyer running the default Bonn scenario, then tweaking to their own numbers. We fail if the app produces a wrong EUR for a plausible scenario even when the formula is "correct" per its docstring. We also fail if a primary-source rule (AfA, § 6 Abs. 1 Nr. 1a EStG, § 19 WEG) is mis-encoded or mis-applied.

Every finding carries a **testability tag** — whether it can be pinned by a unit test — because Framework 6 promises that actionable items will become tests wherever possible.

- `T` — can become a unit test (most Framework 2 and Framework 4 findings)
- `S` — can become a snapshot/regression test pinning a constant (most Framework 1 findings)
- `D` — documentation-only (comment, REFERENCES.md entry, UI caption)
- `F` — requires a feature change before it can be tested

---

## 0. What the code gets right (the baseline)

Establishing the positive baseline up-front so the findings below read as deltas against a generally well-built engine:

- **AfA rates and useful lives** match § 7 Abs. 4 EStG verbatim: pre-1925 → 2.5%/40yr; 1925-2022 → 2.0%/50yr; 2023+ → 3.0%/33yr (`rules_de.py:28-44`).
- **Anschaffungsnaher Aufwand threshold** is correctly applied to **building value**, not purchase price — the most common mistake in German property calculators. `tax.py:82` multiplies `building_value * ANSCHAFFUNGSNAH_THRESHOLD_PCT`.
- **Anschaffungsnaher window** is 3 calendar years, inclusive of purchase year: `[today_year, today_year + 3)` (`tax.py:84`, `rules_de.py:55`).
- **`NOTARY_GRUNDBUCH_AFA_SHARE = 0.80`** (`rules_de.py:72`) correctly splits notary/Grundbuch into the capitalizable Anschaffungsnebenkosten (AfA basis) and the deductible Geldbeschaffungskosten (Werbungskosten) portions.
- **Maintenance reserve is marked non-deductible** until actually spent (`operating_costs.py:117-122` — `deductible_in_rent=False` on the Petersche/II.BV reserve line). This follows § 19 WEG case law that many Excel models miss.
- **Vacancy is netted once** — rent is reduced by vacancy in `cashflow.py:77-80`, and the explicit "Vacancy risk" cost line is subtracted from operating costs at aggregation (`cashflow.py:83-86`) to prevent double-counting.
- **Verlustverrechnung** correctly implemented: rental losses offset at marginal rate, and `tests/test_engine.py::test_loss_offset_scales_with_marginal_rate` pins linear scaling with `marginal_tax_rate`.
- **`WEG_SHARE_APARTMENT = 0.15`** (`rules_de.py:151`, applied in `capex.py`): common-area capex items (`scope="we_building"`) are charged at the owner's share of the Gemeinschaftseigentum, not full cost. Prevents a material overstatement for apartments.
- **Horizon indexing is consistent** across all modules: `financing.py`, `capex.py`, `tax.py`, and `cashflow.py` all use `range(1, horizon_years + 1)` over the same N. Cross-module audit confirms no off-by-one.
- **Adaptive-loan reallocation** guards against empty active-adaptive sets before division (`financing.py:132`).
- **Every constant in `rules_de.py` carries a statute citation** in an adjacent comment, and `REFERENCES.md` ranks each source by reliability.
- **YAML round-trip** is tested (`tests/test_io.py`) so scenario files can't silently drift.

These are real strengths and the audit below should be read as improvements *on top* of them, not as a rebuttal.

---

## 1. Goal audit

### 1.1 Correctness on the default scenario (Goal C)

The default scenario is `data/bonn_poppelsdorf.yaml`: 3-Zimmer apartment, rent mode, horizon 50 yr, NRW. Running through each lens:

- **Formula level** — every EUR in the Summary tab is traceable and reproducible from the inputs + `rules_de.py` constants; no crash.
- **Edge-case level** — the default never exercises `horizon_years=0`, negative rate, or garbage Bodenrichtwert. But each is one sidebar keystroke away:

**Severity-4 finding (Goal-C blocker).** `cashflow.py:132` — `pd.DataFrame(rows).set_index("year")` raises `KeyError: "None of ['year'] are in the columns"` when `horizon_years = 0` because `rows` is empty and the DataFrame has no columns. Any user who drags the horizon slider to 0 (or enters 0 in YAML) sees a raw traceback in the Streamlit UI. [Framework 4. Tag: **T**.]

### 1.2 Factuality on the default scenario (Goal D)

On the Bonn default every displayed rate ties to a statute:

- **6.5% Grunderwerbsteuer** → GrEStG + NRW state rate (`rules_de.py:61`) — ✅ correct for NRW.
- **3.57% Maklerprovision** → § 656c BGB post-2020 split (`rules_de.py:62`) — ✅.
- **2% Notar + Grundbuch** → GNotKG schedules (`rules_de.py:63-65`) — ✅ within typical range.
- **2.0% AfA** on a 1960s building → § 7 Abs. 4 EStG (`rules_de.py:32-33`) — ✅.

Change the sample scenario's Bundesland to Bayern and the same UI still displays 6.5% Grunderwerbsteuer — a **Severity-3 Goal-D failure** per Framework 7. Treated fully in [`germany_expansion.md`](./germany_expansion.md).

---

## 2. Per-framework findings

### 2.1 Framework 1 — Primary-source verification

| Rule | Code | Source | Match? | Sev | Tag | Loc |
|---|---|---|---|---|---|---|
| AfA rate pre-1925 | 2.5% | § 7 Abs. 4 EStG | ✅ exact | — | S | `rules_de.py:30-31` |
| AfA rate 1925-2022 | 2.0% | § 7 Abs. 4 EStG | ✅ exact | — | S | `rules_de.py:32-33` |
| AfA rate 2023+ | 3.0% | JStG 2022 | ✅ rate; useful-life mismatch | 2 | S | `rules_de.py:34-35,41-44` (rate 3.0% implies 33⅓yr; useful_life returns 33 — internally inconsistent by ~1% of residual) |
| Anschaffungsnaher threshold | 15% | § 6 Abs. 1 Nr. 1a EStG | ✅ exact | — | S | `rules_de.py:54` |
| Anschaffungsnaher window | 3 yr | § 6 Abs. 1 Nr. 1a EStG | ✅ exact | — | S | `rules_de.py:55` |
| Anschaffungsnaher basis = building value | BFH IX R 6/16 | ✅ | — | S | `tax.py:82` |
| Grunderwerbsteuer NRW | 6.5% | state law | ✅ for NRW only | **3** | F | `rules_de.py:61` — see `germany_expansion.md` |
| Maklerprovision buyer share | 3.57% | § 656c BGB | ✅ | 2 | D | `rules_de.py:62` — comment doesn't cite § 656c explicitly |
| Notar + Grundbuch | 2% | GNotKG | ✅ within tolerance | — | S | `rules_de.py:63-65` |
| `NOTARY_GRUNDBUCH_AFA_SHARE` | 0.80 | custom heuristic | ⚠ no source | 2 | D | `rules_de.py:68-72` — real split depends on whether there's a loan; 70-90% range |
| Petersche Formel | 1.5/80 × 0.70 | Peters 1984 | ✅ historical | 2 | D | `rules_de.py:78-83` — under-provisions by modern standards; mitigated via `max(Peters, II.BV)` in operating_costs |
| II. BV reserve table | 7.10 / 9.00 / 11.50 + €1 elevator | § 28 II. BV | ✅ within published range | — | S | `rules_de.py:104-115` |
| `GRUNDSTEUER_RATE_OF_PRICE_PROXY` | 0.002 | comment says "rough" | ❌ wrong base (applied to price not Grundstückswert) | **3** | F | `rules_de.py:199`, applied in `operating_costs.py:90-94` |
| § 7b Sonder-AfA (5% bonus, post-2023 new builds) | not modelled | README-disclosed | ⚠ gap | 2 | F | `rules_de.py` / `models.py` |
| § 7h / § 7i Denkmal AfA | flag exists, engine ignores | README-disclosed | ⚠ gap | 2 | F | `models.py:is_denkmal`, no consumer in `tax.py` |
| Marginal tax — Soli + Kirchensteuer | single blended rate | not disclosed in model | ⚠ silent | 2 | D | `models.py:globals.marginal_tax_rate`, `tax.py:215` |
| Hausgeld deductibility | 100% in rent mode | implicit | ❌ should split operating/reserve | **3** | F | `operating_costs.py:80-86` |
| Erhaltungsrücklage non-deductible until spent | ✅ correct | § 19 WEG | — | — | T | `operating_costs.py:117-122` |
| Mietpreisbremse / Kappungsgrenze | not enforced | README-disclosed | ⚠ gap | 2 | F | `models.py:rent_params` |

### 2.2 Framework 2 — Formula correctness

| Finding | Sev | Tag | Loc |
|---|---|---|---|
| Annuitätendarlehen: interest on opening balance, constant annuity, correct balance reduction | — (positive) | — | `financing.py:82-158` |
| Annuity capped at `balance + interest` in the final year — forces final-year over-payment; user-pessimistic rounding, within tolerance | 1 | T | `financing.py:123-124` |
| **Building/land split inversion.** When Bodenrichtwert × plot_size > price, `building_share` is computed as ≤ 0, then floored to 0, then **capped up** to 0.75 for apartments. Net effect: user gets AfA basis of 0.75 × price even when the plot alone is worth more than the whole property. With a €100k property and a €500k plot (pathological but possible on bad BRW data) the engine generates €1,875/yr AfA on a worthless building. | **3** | T | `financing.py:62-77` |
| Interest compounds annually on an annual schedule (German Annuitätendarlehen convention per § 488 BGB — correct) | — (positive, silent assumption) | — | `financing.py:82-158` |
| Anschaffungsnaher all-or-nothing reclassification on threshold crossing — matches BFH IX R 6/16 | — (positive) | T | `tax.py:66-91` |
| Vacancy double-count avoided — rent reduced by vacancy in cashflow, Vacancy-risk cost line subtracted at aggregation | — (positive) | T | `cashflow.py:77-86` |
| Capex inflation compounds by calendar year (correct) | — (positive) | — | `capex.py:132` |
| AfA rate 0.030 vs. useful life 33 — residual depreciates ~1% faster than mathematically justified | 2 | T | `rules_de.py:35,44` |
| AfA basis includes capitalizable purchase fees proportionally (GrESt + Makler + 0.8×Notar/Grundbuch) | — (positive) | T | `financing.py:37-49`, `rules_de.py:67-72` |

### 2.3 Framework 3 — Model risk / silent assumptions

Each entry is a simplification the engine makes that is *not surfaced to the user in the app*.

| Silent assumption | Bias (F5) | Sev | Tag | Loc |
|---|---|---|---|---|
| **Hausgeld 100% deductible in rent mode.** Real split: ~60% operating (deductible) / ~40% Instandhaltungsrücklage (not deductible until spent). On a €400/mo Hausgeld with 40% reserve this overstates annual deductions by €1,920; at 38% marginal rate ~€730/yr → ~€36k over 50 years. | user-optimistic | **3** | F | `operating_costs.py:80-86` |
| Annual interest compounding on monthly-paid annuities (German convention per § 488 BGB — correct, but not disclosed) | neutral | 2 | D | `financing.py:82-158` |
| End-of-year cash-flow convention (all payments aggregated to year-end) | neutral | 1 | D | `cashflow.py:68-130` |
| Marginal tax = single user input, no Soli / Kirchensteuer decomposition | neutral (user can enter blended) | 2 | D | `models.py`, `tax.py:215` |
| Petersche over-estimates reserve for old-but-appreciated buildings (reserve scales with current-price-implied construction cost, not historical Herstellungskosten) | user-pessimistic | 2 | D | `operating_costs.py:29-42` |
| No Mietpreisbremse / Kappungsgrenze enforcement | user-optimistic | 2 | F | `models.py`, `cashflow.py:75-80` |
| Adaptive-loan freed-capacity split is equal across active adaptive loans, not proportional to principal | neutral | 2 | D | `financing.py:132-145` |
| Vacancy modelled as fixed months/year, not stochastic | neutral (point estimate) | 1 | D | `operating_costs.py:94` |
| Avoided rent in live mode escalates with `cost_inflation_annual`, not Mietspiegel / wage growth | mildly user-pessimistic in appreciating cities | 1 | D | `cashflow.py:96-98` |
| Maintenance-reserve line is in the costs DataFrame but marked non-deductible — correct, but UI surfaces that list verbatim which can confuse users | neutral | 2 | D | `operating_costs.py:117-122`, `app.py` Costs tab |
| Vacancy-risk line is in the costs DataFrame but silently removed at rent-mode aggregation | neutral | 2 | D | `operating_costs.py:143-149`, `cashflow.py:83-86` |

### 2.4 Framework 4 — Edge cases & numerical stability

| Input | Current | Expected | Sev | Tag | Loc |
|---|---|---|---|---|---|
| `horizon_years = 0` | **KeyError at `.set_index("year")`** | graceful error or empty result | **4** | T | `cashflow.py:132` |
| `purchase_price = 0` | silent: `down_pct=0`, `gross_yield=None` | error or flag | 2 | T | `affordability.py:70-78` |
| `living_space_m2 = 0` | silent: `cost_per_m2=0` | error | 2 | T | `affordability.py:79` |
| `income_net_monthly = 0` | silent: `premium_pct=0`, rules trivially pass | error | 2 | T | `affordability.py:125` |
| Bodenrichtwert × plot > price | `building_share=0.75` (apartment cap) — gives AfA on land-only property | clamp land_share at 100% with zero AfA basis; warn | **3** | T | `financing.py:62-77` |
| Negative interest rate | accepted silently — balance grows down faster than principal | reject or clamp | 2 | T | `financing.py:82-158` |
| Zero interest rate | annuity reduces to linear — works | — | — | T | `financing.py:82-158` |
| `year_last_major_renovation > today_year` | `max(0, today-ref)=0` (correct branch) | warn | 1 | T | `models.py:36` |
| Loan paid off before horizon | amort schedule zero-fills remaining years correctly | — (positive) | — | — | `financing.py` |
| `initial_capital > total financing need` | loans go to zero principal, user has excess cash | — (intentional all-cash path) | — | — | `financing.py` |
| Capex item cost > purchase_price | processed silently | warn | 1 | T | `capex.py` |
| 100-year horizon | runs fine; AfA fully depreciates mid-horizon with no residual-value logic | 2 | T | `tax.py` |

### 2.5 Framework 5 — Conservative-bias check

| Simplification | Direction | Impact on displayed net wealth at horizon |
|---|---|---|
| Hausgeld 100% deductible | **user-optimistic** | overstates tax refund → overstates net wealth |
| Building share floored at 0.75 on bad Bodenrichtwert | **user-optimistic** | gives unearned AfA basis |
| No Mietpreisbremse | **user-optimistic** | user can set 5% escalation in a regulated city |
| § 7b Sonder-AfA not modelled | user-pessimistic on new builds | understates benefit |
| § 7i/§ 7h Denkmal not modelled | user-pessimistic on historic builds | understates benefit |
| Petersche over-estimates reserve on old appreciated buildings | user-pessimistic | overstates costs → understates wealth |
| Annuity capped by `balance + interest` | user-pessimistic | forces final-year over-payment |
| Grundsteuer 0.2% of price proxy | depends on state | usually within ±30% of real |
| Soli / Kirchensteuer in blended rate | neutral | user controls |

**Net bias.** Two material user-optimistic simplifications (Hausgeld deductibility, building-share floor on bad BRW) are partially but not fully offset by user-pessimistic simplifications elsewhere. The net direction of bias is mildly optimistic on **apartments in appreciating markets** — exactly the population most likely to use this tool. Severity of net bias: 3.

### 2.6 Framework 6 — Test coverage

Existing tests (`tests/test_*.py`):

| Rule / invariant | Tested? | Loc |
|---|---|---|
| Annuity payment is constant year-over-year | ✅ | `tests/test_financing.py` |
| Adaptive-loan reallocation | ✅ | `tests/test_financing.py` |
| Building/land split with WEG adjustment | ✅ (normal path) | `tests/test_engine.py` |
| Horizon consistency across modules | ✅ | `tests/test_engine.py` |
| Verlustverrechnung scales linearly with marginal rate | ✅ | `tests/test_engine.py::test_loss_offset_scales_with_marginal_rate` |
| Affordability verdict levels (pass/warn/fail) | ✅ | `tests/test_affordability.py` |
| Affordability ratios have expected signs | ✅ | `tests/test_affordability.py` |
| Capex auto-schedule cycles | ✅ | `tests/test_capex.py` |
| YAML round-trip | ✅ | `tests/test_io.py` |

Missing tests — each is a finding in its own right:

| Gap | Sev | Tag |
|---|---|---|
| **15% Anschaffungsnaher threshold** — the pivotal German tax switch for rental scenarios, no test | **3** | T |
| **`horizon_years = 0` crash** — the blocker in §1.1 | **4** | T |
| AfA rate per year-built band (parametrized: 1900 / 1950 / 2022 / 2023 / 2026) | 2 | S |
| `NOTARY_GRUNDBUCH_AFA_SHARE` correctly applied in AfA basis computation | 2 | T |
| Hausgeld deductibility — pin current (simplified) behaviour so a future fix is visible | 2 | T |
| Bodenrichtwert × plot > price edge case — pin current behaviour | 3 | T |
| Zero interest rate | 2 | T |
| Negative interest rate | 2 | T |
| Grundsteuer applied to `purchase_price` (wrong base) — pin current behaviour | 3 | T |
| Denkmal flag currently ignored — pin zero effect, so a future § 7i fix is visible | 2 | T |
| `max(Peters, II.BV)` logic per building age | 2 | S |
| Vacancy double-count avoidance | 2 | T |
| Grunderwerbsteuer per-Bundesland parametrization (once implemented — see `germany_expansion.md`) | 3 | F → T |

### 2.7 Framework 7 — Regional applicability

| Rule | NRW-hardcoded? | Sev |
|---|---|---|
| Grunderwerbsteuer 6.5% | ✅ hardcoded | 3 |
| Grundsteuer 0.2% proxy | applies everywhere but wrong base & no state variation | 3 |
| Bodenrichtwert data source | BORIS NRW only; other states have own portals | 2 |
| Sample scenarios (Bonn / Munich / Berlin / Köln) | 3 of 4 are outside NRW but use NRW Grunderwerbsteuer silently | 3 |
| AfA rules | federal (§ 7 EStG) — OK | — |
| Anschaffungsnaher rules | federal (§ 6 EStG + BFH) — OK | — |
| WEG Erhaltungsrücklage | federal (§ 19 WEG) — OK | — |
| Notar / Grundbuch | federal (GNotKG) — OK | — |
| Maklerprovision | federal (§ 656c BGB) — OK | — |
| GEG / Energieausweis | federal — OK | — |

Addressed in depth in [`germany_expansion.md`](./germany_expansion.md).

### 2.8 Framework 8 — Audit trail / traceability

| Finding | Sev | Tag | Loc |
|---|---|---|---|
| Every constant in `rules_de.py` has a comment citing its statute | — (positive) | — | `rules_de.py` |
| `REFERENCES.md` ranks each source by reliability | — (positive) | — | `REFERENCES.md` |
| Summary tab's purchase-costs table shows rate + EUR (added in v1 UI audit fixes) | — (positive) | — | `app.py:737-760` |
| **Hausgeld deductibility simplification is not documented** anywhere in the app or REFERENCES.md | **3** | D | `operating_costs.py:80-86` |
| **Grundsteuer proxy limitation is not documented** in REFERENCES.md (only in a one-line code comment) | **3** | D | `rules_de.py:199` |
| AfA year-band cutoffs (1925, 2023) not cited in adjacent code comments; source is in REFERENCES.md only | 2 | D | `rules_de.py:28-44` |
| `NOTARY_GRUNDBUCH_AFA_SHARE = 0.80` is a custom heuristic with no cited source | 2 | D | `rules_de.py:72` |
| Bodenrichtwert integration limited to NRW not documented as such | 2 | D | `rules_de.py:16`, `models.py` |
| End-of-year cash-flow convention not documented in Methodology tab | 2 | D | `cashflow.py`, `app.py` Methodology tab |

---

## 3. Per-module findings

### 3.1 `rules_de.py` (211 LOC)

- ✅ **Best-documented module in the engine.** Nearly every constant carries an adjacent statute citation.
- **Sev 3 — Grundsteuer proxy applied to wrong base.** `GRUNDSTEUER_RATE_OF_PRICE_PROXY = 0.002` (line 199) is multiplied against `purchase_price` in `operating_costs.py:90-94`, but the real post-2025-Reform formula is `Steuermessbetrag × Hebesatz`, where Steuermessbetrag is derived from the Grundsteuerwert of the **plot** not the whole property. Net effect: understates Grundsteuer for expensive apartments in cheap plots; overstates for expensive plots with cheap buildings. Magnitude ±30%.
- **Sev 2 — AfA rate / useful life internal inconsistency.** Line 35 returns `0.030`; line 44 returns `33` (integer years). Either use 33⅓ years and a rate of 1/33.333 = 0.03000, or use 33 years and a rate of 1/33 = 0.03030. The current pair produces a residual-value drift of ~1% over the lifetime.
- **Sev 2 — `NOTARY_GRUNDBUCH_AFA_SHARE = 0.80` has no cited source** (line 72). The 80/20 split between Anschaffungsnebenkosten (capitalizable) and Geldbeschaffungskosten (Werbungskosten) depends on whether there's a loan and is not statutorily fixed. Document the range (70-90%) or make it configurable.
- **Sev 2 — Maklerprovision comment doesn't cite § 656c BGB** (line 62).

### 3.2 `financing.py` (170 LOC)

- ✅ Annuity amortization clean and correct across the schedule.
- ✅ Adaptive-loan reallocation guards against empty active set (line 132).
- **Sev 3 — `estimate_building_share()` inversion** (lines 62-77). When `bodenrichtwert × plot_size > purchase_price`, the computed building_share is ≤ 0, then floored to 0, then **capped up** to 0.75 for apartments / 0.50 for houses. The cap is a "bad-data guard" but the effect gives AfA basis on a land-dominant property. Replace with `land_share = min(1, bodenrichtwert × plot / price)` and `building_share = max(0, 1 - land_share)`, emitting a warning if `building_share < 0.1`.
- **Sev 2 — End-of-year convention undocumented.** Annuity is paid, interest is credited, balance updated — implicitly at year-end. Standard German practice per § 488 BGB, but worth a docstring line.
- **Sev 1 — Annuity capped at `balance + interest` in final year** (lines 123-124). Forces small final-year over-payment; user-pessimistic rounding within tolerance.

### 3.3 `tax.py` (228 LOC)

- ✅ Verlustverrechnung correctly implemented and tested.
- ✅ Anschaffungsnaher threshold applied to **building value** not price (line 82). The single most common mistake in German property calculators; this one avoids it.
- **Sev 2 — Window boundary comment at line 79** (`years 1-3, today_year + 0,1,2`) is correct but could be clearer: the window is `[today_year, today_year + 3)` — 3 calendar years inclusive of purchase.
- **Sev 1 — Defensive index guard** on `annual_interest_total.iloc[yr - 1]` (line 201). If horizon mismatch sneaks in later, this silently returns 0 instead of erroring. Prefer an assertion at function boundary.

### 3.4 `capex.py` (156 LOC)

- ✅ `WEG_SHARE_APARTMENT = 0.15` applied correctly to `scope="we_building"` items.
- ✅ `auto_schedule()` cycle math correct for any combination of `today_year`, `last_replacement`, and `lifetime_years`.
- **Sev 1 — No validation** that capex items' `year_due` is within horizon — out-of-horizon items silently drop (not a bug; could be a feature; should be documented).

### 3.5 `cashflow.py` (139 LOC)

- ✅ Vacancy double-count correctly avoided (lines 83-86).
- **Sev 4 — `horizon_years = 0` crash** at line 132 (`.set_index("year")` on empty DataFrame).
- **Sev 1 — Initial-renovation dead line** at `rows.append`-area initial-renovation computation; documented redundancy.

### 3.6 `operating_costs.py` (222 LOC)

- ✅ Erhaltungsrücklage line correctly marked non-deductible (lines 117-122).
- ✅ `max(Peters, II.BV)` realism check for old buildings.
- **Sev 3 — Hausgeld marked `deductible_in_rent=True` in full** (lines 80-86). Real split: operating portion deductible as Werbungskosten, Instandhaltungsrücklage portion not deductible until spent. A €400/mo Hausgeld with 40% reserve overstates deductions by ~€1,920/yr; at 38% marginal rate ~€730/yr tax benefit → ~€36k over a 50-yr horizon. The single largest user-optimistic silent assumption.
- **Sev 2 — `estimate_construction_cost_per_m2()`** backs out current purchase price / living space (lines 29-42), over-estimating Petersche for old-but-appreciated buildings. Documented in the docstring but not surfaced in the UI.
- **Sev 2 — Vacancy-risk cost line** is in the DataFrame but silently removed at cashflow aggregation. A future UI surface that renders the cost-list verbatim would confuse users.

### 3.7 `affordability.py` (161 LOC)

- ✅ All 5 primary rules match German banking convention.
- ✅ Well-tested (`tests/test_affordability.py`).
- **Sev 2 — Zero-denominator edges** silently return 0: `price=0`, `living_space=0`, `income=0`. Each should raise or flag "unset".
- **Sev 1 — 30% rule applied to all loan servicing across both modes** where real banks often apply it only to live-mode; current unified rule is conservative.

### 3.8 `models.py` (152 LOC)

- ✅ Clean dataclasses with sensible defaults.
- **Sev 2 — `marginal_tax_rate: float = 0.38`** is a single blended value; no decomposition into income tax + Soli + Kirchensteuer. Document in dataclass docstring.
- **Sev 1 — No validation** that `year_built <= today_year` or `year_last_major_renovation <= today_year`. Silent age calculation via `max(0, today-ref)`.

---

## 4. Coverage matrix (rule → code → source → test)

| Rule | Source | Code | Tested | Break severity |
|---|---|---|---|---|
| AfA pre-1925 2.5% | § 7 Abs. 4 EStG | `rules_de.py:30-31` | ❌ | 3 |
| AfA 1925-2022 2.0% | § 7 Abs. 4 EStG | `rules_de.py:32-33` | ❌ | 3 |
| AfA 2023+ 3.0% | JStG 2022 | `rules_de.py:34-35` | ❌ | 3 |
| Anschaffungsnaher 15% / 3yr | § 6 EStG + BFH IX R 6/16 | `rules_de.py:54-55`, `tax.py:66-91` | ❌ | 3 |
| Anschaffungsnaher basis = building value | BFH IX R 6/16 | `tax.py:82` | ❌ | 3 |
| § 7b Sonder-AfA | JStG 2022 | **not implemented** | — | 2 (disclosed gap) |
| § 7h / § 7i Denkmal AfA | EStG | **flag ignored** | ❌ | 2 (disclosed gap) |
| Verlustverrechnung linear in rate | §§ 2, 32a EStG | `tax.py` | ✅ | — |
| Grunderwerbsteuer NRW 6.5% | state GrEStG | `rules_de.py:61` | ❌ | 3 |
| Maklerprovision post-2020 3.57% | § 656c BGB | `rules_de.py:62` | ❌ | 2 |
| Notar + Grundbuch ~2% | GNotKG | `rules_de.py:63-65` | ❌ | 1 |
| `NOTARY_GRUNDBUCH_AFA_SHARE` 80% | heuristic | `rules_de.py:72` | ❌ | 2 |
| WEG Erhaltungsrücklage non-deductible | § 19 WEG | `operating_costs.py:117-122` | ❌ | 3 |
| Hausgeld operating/reserve split | § 19 WEG | **not implemented** | — | 3 |
| II. BV reserve table | § 28 II. BV | `rules_de.py:104-115` | ❌ | 2 |
| Petersche Formel | Peters 1984 | `rules_de.py:81-94` | ❌ | 2 |
| Annuitätendarlehen | textbook | `financing.py:82-158` | ✅ | — |
| Adaptive loan reallocation | custom | `financing.py:82-158` | ✅ | — |
| Building/land split via Bodenrichtwert | § 196 BauGB | `financing.py:52-77` | ✅ (normal path) | 3 (edge case untested) |
| Mietpreisbremse / Kappungsgrenze | §§ 556d, 558 BGB | **not implemented** | — | 2 (disclosed gap) |
| Horizon consistency across modules | engine invariant | 4 modules | ✅ | — |
| YAML round-trip | engine invariant | `io.py` | ✅ | — |
| `horizon_years = 0` graceful | engine invariant | `cashflow.py:132` | ❌ | **4** |

---

## 5. Severity summary and top risks

| Severity | Count |
|---|---|
| 4 — Blocker | 1 |
| 3 — Major | 10 |
| 2 — Minor | 20 |
| 1 — Cosmetic | 7 |

### Top 5 Goal-C risks (computational correctness)

1. **`horizon_years = 0` crash** — `cashflow.py:132`. Any user who drags horizon to 0 sees a traceback. *Fix and test.*
2. **Building/land split inversion** when Bodenrichtwert × plot > price — `financing.py:62-77`. Gives unearned AfA basis on land-dominant properties.
3. **Hausgeld 100% deductible** — `operating_costs.py:80-86`. Overstates tax refund by ~€36k over 50 years on a typical apartment.
4. **Grundsteuer proxy applied to `purchase_price`** instead of Grundstückswert — `operating_costs.py:90-94`. Wrong base, ±30%.
5. **15% Anschaffungsnaher Aufwand rule untested** — the pivotal German tax switch. No regression pin means a refactor could break it silently.

### Top 5 Goal-D risks (factual traceability)

1. **Grunderwerbsteuer hardcoded NRW 6.5%** — wrong for every other Bundesland. See [`germany_expansion.md`](./germany_expansion.md).
2. **Hausgeld deductibility simplification not documented** — the user cannot trace back why their refund is ~€700/yr higher than their Steuerberater's estimate.
3. **§ 7b Sonder-AfA and § 7i/§ 7h Denkmal AfA not modelled** — documented only in the README; a Denkmal buyer can toggle the flag and see no effect, with no in-app disclosure.
4. **Grundsteuer proxy limitations not documented** in REFERENCES.md.
5. **AfA year-band cutoffs not cited in adjacent code comments** — provenance split between code and REFERENCES.md.

All are addressed in [`actionable_items.md`](./actionable_items.md). Regional applicability is planned in [`germany_expansion.md`](./germany_expansion.md).
