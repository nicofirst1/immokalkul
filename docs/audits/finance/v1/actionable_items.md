# Actionable items — immokalkul financial correctness

Concrete fixes and tests derived from [`audit.md`](./audit.md), using the frameworks in [`../research.md`](../research.md). Most items are prescriptions to **write a failing test, then fix the code** — Framework 6 promises that every testable finding becomes a pinned test.

Companion plan for multi-Bundesland support: [`germany_expansion.md`](./germany_expansion.md).

## How this file is organised

- **P0** — Goal-C blockers. Crashes, wrong numbers in plausible scenarios. Do first.
- **P1** — Goal-D wins. Factual traceability, material silent assumptions, missing regressions.
- **P2** — Polish. Doc nits, dead code, hygiene tests.

Each item carries:

- **Problem** — one-line summary with link to the audit finding.
- **Fix** — concrete change, often with a small code or test sketch.
- **Target** — `file:line` or function to modify.
- **Test** — whether the item should produce a pinned test (T), a snapshot-style regression (S), a doc change (D), or a feature (F).
- **Effort** — S (< 30 min), M (30-120 min), L (half-day+).
- **Frameworks** — which lenses from `../research.md` motivate it.

## Priority matrix (at-a-glance)

| # | Item | Priority | Effort | Tag |
|---|---|---|---|---|
| 1 | Guard `horizon_years = 0` crash | P0 | S | T |
| 2 | Fix building/land split inversion (Bodenrichtwert × plot > price) | P0 | M | T |
| 3 | Split Hausgeld into deductible + reserve portions | P0 | M | T |
| 4 | Pin AfA rates per year-built band | P0 | S | S |
| 5 | Pin 15% Anschaffungsnaher threshold | P0 | M | T |
| 6 | Align AfA rate + useful life (3% vs 33yr) | P0 | S | T |
| 7 | Fix Grundsteuer base (Grundstückswert, not price) | P0 | M | T |
| 8 | Document Hausgeld simplification in UI + REFERENCES.md (fallback if #3 blocked) | P1 | S | D |
| 9 | Validate zero-denominator inputs (price / income / living space) | P1 | S | T |
| 10 | Pin zero / negative interest rate behaviour | P1 | S | T |
| 11 | Pin Bodenrichtwert × plot > price current behaviour | P1 | S | T |
| 12 | Pin Verlustverrechnung scales linearly (exists, extend parametrization) | P1 | S | T |
| 13 | Cite § 656c BGB on Maklerprovision comment | P1 | S | D |
| 14 | Document `NOTARY_GRUNDBUCH_AFA_SHARE` source + range | P1 | S | D |
| 15 | Decompose marginal tax into Einkommensteuer + Soli + Kirchensteuer | P1 | L | F |
| 16 | Model § 7b Sonder-AfA (or disclose in UI) | P1 | L | F |
| 17 | Model § 7i/§ 7h Denkmal AfA (or remove ignored flag) | P1 | M | F |
| 18 | Add Mietpreisbremse / Kappungsgrenze enforcement (or disclose) | P1 | M | F |
| 19 | Document end-of-year cash-flow convention | P1 | S | D |
| 20 | Document annual vs monthly interest compounding convention | P1 | S | D |
| 21 | Validate `year_built` / `year_last_major_renovation` not in future | P2 | S | T |
| 22 | Remove dead initial-renovation line in cashflow | P2 | S | — |
| 23 | Replace defensive `iloc` index guard with assertion in tax.py | P2 | S | — |
| 24 | AfA year-band cutoffs: add statute citation adjacent to code | P2 | S | D |
| 25 | Document Bodenrichtwert NRW-only limitation | P2 | S | D |
| 26 | Pin `max(Peters, II.BV)` logic per age band | P2 | S | S |
| 27 | Pin vacancy double-count avoidance | P2 | S | T |
| 28 | Warn when capex item cost > purchase price | P2 | S | T |
| 29 | AfA residual-value behaviour at long horizons | P2 | M | T |

---

## P0 — Goal-C blockers (crashes, wrong numbers)

### P0-1. Guard `horizon_years = 0` crash

- **Problem.** `cashflow.py:132` calls `pd.DataFrame(rows).set_index("year")` on an empty `rows` list when `horizon_years = 0`, raising `KeyError: "None of ['year'] are in the columns"`. Any user who drags the horizon slider to 0 sees a raw Python traceback. Audit §1.1, §2.4, §3.5.
- **Fix.**
  ```python
  if s.globals.horizon_years <= 0:
      raise ValueError("horizon_years must be >= 1")
  ```
  at the top of `cashflow.run()` — or, if graceful handling is preferred, return an empty `ScenarioResult` with explicit zero-row DataFrames. Either is acceptable; an explicit error is simpler and matches how affordability handles `price=0`.
- **Test.** `tests/test_engine.py::test_horizon_zero_raises_or_returns_empty` — parametrized across {0, -1} inputs.
- **Target.** `cashflow.py:68-132`, plus YAML loader validation in `io.py` if we want to catch it at scenario load.
- **Effort.** S.
- **Frameworks.** Framework 4 (edge cases) • Framework 6 (test coverage).

### P0-2. Fix building/land split inversion

- **Problem.** `financing.py:62-77`, `estimate_building_share()`: when `bodenrichtwert × plot_size > purchase_price`, the computed `building_share` is ≤ 0, floored to 0, then **capped up** to 0.75 (apartments) / 0.50 (houses). Effect: AfA basis of 0.75 × price on a land-dominant property. Audit §2.2, §2.4 (Sev 3, T).
- **Fix.**
  ```python
  land_value = bodenrichtwert * plot_size_m2
  land_share = min(1.0, land_value / price)
  building_share = 1.0 - land_share  # no up-floor
  if building_share < 0.10:
      warnings.warn(
          f"Bodenrichtwert implies land alone is {land_share:.0%} of price — "
          f"AfA basis will be near zero. Verify Bodenrichtwert via BORIS."
      )
  ```
  Delete the 0.75/0.50 cap. Keep the existing defaults (0.80 / 0.65) when Bodenrichtwert is not provided — those are property-type priors, not bad-data guards.
- **Test.** Parametrize `tests/test_financing.py`:
  - Bodenrichtwert=0 → building_share = default for property type.
  - Normal BRW giving land_share=0.2 → building_share=0.8.
  - BRW giving land_share=0.99 → building_share=0.01 (not floored to 0.75).
  - BRW giving land_share>1.0 → building_share=0 with warning.
- **Target.** `financing.py:62-77`.
- **Effort.** M.
- **Frameworks.** Framework 2 (formula correctness) • Framework 5 (bias: user-optimistic).

### P0-3. Split Hausgeld into deductible + reserve portions

- **Problem.** `operating_costs.py:80-86` marks Hausgeld `deductible_in_rent=True` in full. Real split (§ 19 WEG): ~60% operating (deductible as Werbungskosten) / ~40% Instandhaltungsrücklage (not deductible until actually spent). Overstates annual deductions by ~€1,920 on a typical apartment; ~€36k over 50 years at 38% marginal rate. Audit §2.1, §2.3, §3.6 (Sev 3, F).
- **Fix.** Add a sidebar field in `app.py`: "Hausgeld reserve share (%)" default 40%. In the engine:
  ```python
  # operating_costs.py
  reserve_frac = costs.hausgeld_reserve_share  # default 0.40
  operating_frac = 1.0 - reserve_frac
  lines.append(CostLine(
      "Hausgeld — operating portion",
      costs.hausgeld_monthly_for_rent * 12 * operating_frac,
      in_live=False, in_rent=True, deductible_in_rent=True,
      note="Betriebskostenanteil; deductible per § 9(1) EStG",
  ))
  lines.append(CostLine(
      "Hausgeld — reserve portion",
      costs.hausgeld_monthly_for_rent * 12 * reserve_frac,
      in_live=False, in_rent=True, deductible_in_rent=False,
      note="Instandhaltungsrücklage; not deductible until spent (§ 19 WEG)",
  ))
  ```
- **Test.** `tests/test_engine.py::test_hausgeld_reserve_not_deductible` — assert that tax in rent mode drops when the reserve share is 0 (everything deductible) and rises when it is 1 (nothing deductible), proportionally.
- **Target.** `operating_costs.py:80-86`, `models.py` (new field with default 0.40), `app.py` sidebar.
- **Effort.** M.
- **Frameworks.** Framework 1 (primary source) • Framework 3 (silent assumption) • Framework 5 (bias: user-optimistic).

### P0-4. Pin AfA rates per year-built band

- **Problem.** `rules_de.py:28-44` encodes three AfA rates (2.5% / 2.0% / 3.0%) from § 7 Abs. 4 EStG, but no test pins them. A maintainer could silently change the rate or the cutoff. Audit §2.6 (Sev 2 → gap, but pinning is Sev 2 effort and catches a Sev 3 class of breakage).
- **Fix.** Parametrized test:
  ```python
  @pytest.mark.parametrize("year,rate,life", [
      (1900, 0.025, 40),
      (1924, 0.025, 40),
      (1925, 0.020, 50),
      (2022, 0.020, 50),
      (2023, 0.030, 33),
      (2050, 0.030, 33),
  ])
  def test_afa_rate_and_life(year, rate, life):
      assert afa_rate(year) == rate
      assert afa_useful_life_years(year) == life
  ```
- **Test.** Same as fix.
- **Target.** `tests/test_engine.py` (new test file `tests/test_rules_de.py` is also fine).
- **Effort.** S.
- **Frameworks.** Framework 1 • Framework 6.

### P0-5. Pin 15% Anschaffungsnaher Aufwand threshold

- **Problem.** The pivotal tax switch for rental scenarios — cross the threshold and renovation gets depreciated over 50 years instead of deducted immediately. No test. A refactor could invert the comparison operator and the default scenario would still pass. Audit §2.6, §4 coverage matrix.
- **Fix.** Scenario-based test:
  ```python
  def test_anschaffungsnaher_below_threshold_stays_deductible():
      s = _make_scenario(building_value=400_000,
                         user_capex=[(year=2027, cost=55_000)])  # 13.75% < 15%
      r = run(s)
      assert r.afa_basis is close to baseline  # no uplift
      assert r.cost_lines includes "Erhaltungsaufwand" with 55_000

  def test_anschaffungsnaher_above_threshold_reclassifies():
      s = _make_scenario(building_value=400_000,
                         user_capex=[(year=2027, cost=65_000)])  # 16.25% > 15%
      r = run(s)
      assert r.afa_basis uplifted by 65_000
      assert 65_000 not in Erhaltungsaufwand cost lines
  ```
- **Test.** Two scenarios bracketing the threshold.
- **Target.** `tests/test_engine.py`.
- **Effort.** M.
- **Frameworks.** Framework 1 • Framework 2 • Framework 6.

### P0-6. Align AfA rate with useful life for 2023+ buildings

- **Problem.** `rules_de.py:35` returns rate 0.030; `rules_de.py:44` returns useful life 33. Either 33⅓ years and rate 1/33.333 = 0.03000, or 33 years and 1/33 = 0.03030. Current pair drifts the residual ~1% over the lifetime. Audit §2.1, §3.1.
- **Fix.** Pick one. The statute wording is "33⅓ Jahre Nutzungsdauer" with "3% Absetzungen" — the spirit is 3%/yr over 33⅓ yr. Recommend keeping rate at 0.030 and reporting useful life as 33⅓ (float) or 34 (ceiling). The engine doesn't actually consume `useful_life` for depreciation (it uses `rate`), so a display-layer fix is sufficient.
- **Test.** `assert afa_rate(2023) * afa_useful_life_years(2023) == pytest.approx(1.0, rel=0.02)`.
- **Target.** `rules_de.py:34-44`; possibly `app.py` Summary AfA block if it displays useful-life.
- **Effort.** S.
- **Frameworks.** Framework 1 (primary source).

### P0-7. Fix Grundsteuer base

- **Problem.** `operating_costs.py:90-94` computes Grundsteuer as `purchase_price × 0.002`. Post-2025 Reform formula is `Steuermessbetrag × Hebesatz`, where Steuermessbetrag is derived from the **Grundstückswert** (plot value), not the whole property. ±30% error depending on land/building ratio. Audit §2.1, §3.1, §3.6.
- **Fix.** Minimum viable:
  ```python
  # operating_costs.py
  land_value = bodenrichtwert * plot_size_m2 if bodenrichtwert else price * (1 - building_share)
  grundsteuer = land_value * costs.grundsteuer_land_rate  # default 0.0034
  ```
  with `grundsteuer_land_rate` exposed as a sidebar input. Full per-state Hebesatz table is out of scope for v1 (see `germany_expansion.md`).
- **Test.** `tests/test_engine.py::test_grundsteuer_scales_with_land_value` — fix price, double plot size, assert Grundsteuer doubles.
- **Target.** `operating_costs.py:90-94`, `models.py`, `rules_de.py:199`.
- **Effort.** M.
- **Frameworks.** Framework 1 • Framework 2.

---

## P1 — Goal-D wins (traceability, material disclosures, regressions)

### P1-8. Document Hausgeld simplification (fallback if P0-3 blocked)

- **Problem.** If P0-3 is deferred, the Hausgeld 100%-deductible simplification has no disclosure — UI or REFERENCES.md. Audit §2.1, §2.8.
- **Fix.** Add to the Costs tab caption: *"We treat Hausgeld as fully deductible. Real tax practice splits it — only the operating portion is deductible as Werbungskosten; the Instandhaltungsrücklage portion is not deductible until actually spent on repairs. Verify with your Steuerberater."* Add a REFERENCES.md entry citing § 19 WEG.
- **Target.** `app.py` Costs tab, `REFERENCES.md`.
- **Effort.** S.
- **Frameworks.** Framework 3 • Framework 8.

### P1-9. Validate zero-denominator inputs

- **Problem.** `affordability.py:70-79` silently returns 0 when `price=0`, `living_space_m2=0`, or `income_net_monthly=0`. The affordability rules then trivially pass, masking a user input error. Audit §2.4, §3.7.
- **Fix.**
  ```python
  if s.property.purchase_price <= 0:
      raise ValueError("purchase_price must be > 0")
  if s.property.living_space_m2 <= 0:
      raise ValueError("living_space_m2 must be > 0")
  if s.globals.household_income_net_monthly <= 0:
      raise ValueError("household_income_net_monthly must be > 0")
  ```
  at the top of `affordability.verdict()`.
- **Test.** `tests/test_affordability.py::test_zero_inputs_raise` — parametrized.
- **Target.** `affordability.py:60-80`.
- **Effort.** S.
- **Frameworks.** Framework 4.

### P1-10. Pin zero / negative interest rate behaviour

- **Problem.** `financing.py` accepts any rate silently. Zero rate is valid (linear amortization); negative rate is ambiguous — subsidy? data error? Audit §2.4.
- **Fix.** Decide policy: clamp negative to 0 with warning, or reject. Recommend clamp for subsidized-loan realism.
- **Test.** `tests/test_financing.py::test_zero_rate_linear` + `test_negative_rate_clamped_or_rejected`.
- **Target.** `financing.py` loan-validation entry point.
- **Effort.** S.
- **Frameworks.** Framework 4.

### P1-11. Pin Bodenrichtwert × plot > price edge case

- **Problem.** After P0-2 the behaviour changes. Pin the post-fix behaviour so it can't regress.
- **Fix.** Test lives alongside P0-2's tests.
- **Test.** See P0-2.
- **Target.** `tests/test_financing.py`.
- **Effort.** S (bundled with P0-2).
- **Frameworks.** Framework 6.

### P1-12. Extend Verlustverrechnung test parametrization

- **Problem.** `test_loss_offset_scales_with_marginal_rate` exists but tests one direction. Extend to parametrize across {20%, 30%, 42%, 45%} and assert linear scaling of the tax credit. Audit §2.6.
- **Target.** `tests/test_engine.py`.
- **Effort.** S.
- **Frameworks.** Framework 6.

### P1-13. Cite § 656c BGB on Maklerprovision

- **Problem.** `rules_de.py:62` comment says "buyer share since 2020" but doesn't cite the statute. A future reader can't find the source. Audit §2.8.
- **Fix.** Update the comment: `# ~3.57% incl. VAT, buyer share post-§ 656c BGB (in force since 23.12.2020)`.
- **Target.** `rules_de.py:62`.
- **Effort.** S.
- **Frameworks.** Framework 8.

### P1-14. Document `NOTARY_GRUNDBUCH_AFA_SHARE` source + range

- **Problem.** `rules_de.py:72` hardcodes 0.80 with no cited source. Real range is ~70-90% depending on whether there's a loan. Audit §2.1, §2.8.
- **Fix.** Extend the adjacent comment. Optionally expose as a parameter in `FinancingParameters`.
- **Target.** `rules_de.py:67-72`.
- **Effort.** S.
- **Frameworks.** Framework 1 • Framework 8.

### P1-15. Decompose marginal tax

- **Problem.** `models.py:globals.marginal_tax_rate` is a single blended value. No Soli (5.5% of income tax, threshold ~€18k ESt), no Kirchensteuer (8-9% of income tax). Users who enter only their Spitzensteuersatz understate their effective rate by 1-3pp. Audit §2.3, §3.1.
- **Fix.** Split into three fields: `income_tax_rate`, `soli_rate` (default 5.5%, conditional on ESt threshold), `kirchensteuer_rate` (default 0, user toggles). Compute effective rate as `income_tax × (1 + soli + kirche)`. Keep blended input as a compatibility option.
- **Test.** `tests/test_engine.py::test_marginal_tax_decomposition` — parametrize across the three components, assert linear effect on tax_owed.
- **Target.** `models.py`, `tax.py:215`, `app.py` sidebar.
- **Effort.** L.
- **Frameworks.** Framework 1 • Framework 3.

### P1-16. Model § 7b Sonder-AfA (or disclose)

- **Problem.** § 7b EStG grants an additional 5% AfA in years 1-5 for qualifying post-2023 residential new builds. Not modelled; disclosed only in README. A new-build buyer sees understated tax benefit. Audit §2.1.
- **Fix (minimum viable).** Add a sidebar checkbox "Qualifies for § 7b Sonder-AfA"; when checked, add 5% × building_value for the first 5 years on top of the standard 3% AfA. Reference the [BMF FAQ](https://www.bundesfinanzministerium.de/). If deferred, add an in-app disclosure under the AfA block in the Summary tab.
- **Test.** `tests/test_engine.py::test_7b_sonder_afa_adds_5pct_years_1_to_5`.
- **Target.** `models.py`, `tax.py`, `rules_de.py`, `app.py` sidebar.
- **Effort.** L.
- **Frameworks.** Framework 1 • Framework 5 (pessimistic gap).

### P1-17. Model § 7i/§ 7h Denkmal AfA (or remove flag)

- **Problem.** `models.py` has a `is_denkmal` flag that the engine never consumes. Audit §2.1.
- **Fix.** Two options:
  1. Implement: 9% in years 1-8, 7% in years 9-12 on the Denkmal-qualifying portion (§ 7i) for pre-1900 buildings the user has documented.
  2. Remove the flag and add a "Denkmal buildings not modelled — see Steuerberater" note in the sidebar.
- **Target.** `models.py`, `tax.py`.
- **Effort.** M.
- **Frameworks.** Framework 1.

### P1-18. Mietpreisbremse / Kappungsgrenze enforcement

- **Problem.** `models.py:rent_params.annual_rent_escalation` is unconstrained. A user in a Mietpreisbremse city can set 5%/yr. §§ 556d, 558 BGB cap increases. Audit §2.3.
- **Fix.** Add `is_mietpreisbremse_area: bool` in rent_params; when true, cap annual escalation at 10%/3yr (Kappungsgrenze § 558 BGB) and initial rent at 110% of Mietspiegel (§ 556d BGB — Mietspiegel not modelled). Minimum viable: warn when escalation × 3 > 0.10 and flag is set.
- **Target.** `models.py`, `cashflow.py`, `app.py` sidebar.
- **Effort.** M.
- **Frameworks.** Framework 1 • Framework 5.

### P1-19. Document end-of-year cash-flow convention

- **Problem.** All payments are aggregated at year-end (`cashflow.py:68-130`), but the convention is undocumented. A user comparing to their bank statement will see different sub-year timing. Audit §2.3, §3.2.
- **Fix.** Docstring at `cashflow.run()` and a one-line caption on the Cash flow tab.
- **Target.** `cashflow.py`, `app.py` Cash flow tab.
- **Effort.** S.
- **Frameworks.** Framework 3 • Framework 8.

### P1-20. Document annual vs monthly interest compounding

- **Problem.** German Annuitätendarlehen per § 488 BGB compounds annually (monthly payments, annual interest credit). Engine matches this convention, but it's undocumented. Audit §2.3, §3.2.
- **Fix.** Docstring at `financing.py:amortization_schedule()`; one-line note in Methodology tab.
- **Target.** `financing.py`, `app.py` Methodology tab.
- **Effort.** S.
- **Frameworks.** Framework 3 • Framework 8.

---

## P2 — Hygiene

### P2-21. Validate future-dated `year_built` / `year_last_major_renovation`

- **Problem.** `models.py:36` handles future dates with `max(0, today-ref)` → age 0, silently. Audit §3.8.
- **Fix.** Warn in validation.
- **Target.** `models.py`.
- **Effort.** S.
- **Test.** Yes — `tests/test_models.py::test_future_year_rejected`.

### P2-22. Remove dead initial-renovation line

- **Problem.** Parallel agent flagged a dead computed line; harmless. Audit §3.5.
- **Target.** `cashflow.py:36` area.
- **Effort.** S.

### P2-23. Replace defensive `iloc` guard with assertion

- **Problem.** `tax.py:201` `iloc[yr - 1] if yr - 1 < len(...) else 0` hides a potential horizon mismatch. Audit §3.3.
- **Fix.** `assert len(annual_interest_total) >= horizon`.
- **Effort.** S.

### P2-24. AfA statute citation adjacent to code

- **Problem.** Year-band cutoffs (1925, 2023) cite the statute only in `REFERENCES.md`. Audit §3.1, §2.8.
- **Fix.** Extend existing comment to mention JStG 2022 for the 2023 cutoff.
- **Effort.** S.

### P2-25. Document Bodenrichtwert NRW-only integration

- **Problem.** Sample BRW is from BORIS NRW; other-state users need to look elsewhere. Audit §2.7.
- **Fix.** Add in the sidebar tooltip: *"Use BORIS NRW for NRW, BORIS.NI for Lower Saxony, etc. — see germany_expansion.md"*.
- **Effort.** S.

### P2-26. Pin `max(Peters, II.BV)` per age band

- **Problem.** Untested — a future refactor could break the realism check. Audit §2.6.
- **Fix.** Parametrized test at ages 10, 25, 40 → Peters, II.BV, II.BV.
- **Effort.** S.

### P2-27. Pin vacancy double-count avoidance

- **Problem.** Untested. A refactor that computes costs outside `cashflow.run()` could re-introduce the double-count. Audit §2.6.
- **Fix.** Test: set vacancy to 2 months; assert rent drops by 2/12 × rent and op_costs do **not** also drop by that amount.
- **Effort.** S.

### P2-28. Warn when capex item cost > purchase price

- **Problem.** No sanity check on user-capex inputs. Audit §3.4.
- **Fix.** Warn at scenario load.
- **Effort.** S.

### P2-29. AfA residual at long horizons

- **Problem.** At horizon 50 yr + year_built 2023, AfA fully depreciates at year 33 → no more deduction for years 34-50. No warning, no display. Audit §2.4.
- **Fix.** Engine behaviour is correct; add a caption on the Tax tab noting the residual-year effect.
- **Effort.** M.

---

## Implementation notes

- **Test-first on all P0 items.** Write the failing test, commit, then the fix.
- **P0-2, P0-3, P0-7 are feature changes** that require UI additions. Coordinate with the UI actionable_items backlog.
- **P1-15 through P1-18** are larger features; consider deferring to v2 and landing only the disclosures (P1-8 pattern) in v1.
- **The germany_expansion.md plan supersedes P0-7** for full-fidelity Grundsteuer — v1's fix is the minimum-viable "right base" correction.
- **Dependencies:** P1-11 depends on P0-2; P1-8 becomes moot if P0-3 lands.

After these items, the pinned-test count roughly doubles (from 9 to ~25 rules), every P0 finding is a test, and the silent-assumption surface is either fixed or disclosed.
