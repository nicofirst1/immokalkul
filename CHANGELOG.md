# Changelog

All notable changes to **immokalkul** are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[Semantic Versioning](https://semver.org/).

Minor versions correspond to audit cycles — each audit report and its
actionable-items list live in [`docs/audits/`](docs/audits/).

## [1.7.2] — 2026-04-20

**Human UX audit v1 — complex item [C10], layer 3.** Streamlit UI smoke tests via `streamlit.testing.v1.AppTest`.

### Added
- `tests/test_app_smoke.py` — runs the full Streamlit app for each of the 4 sample YAMLs + 3 hypothesis-generated scenarios, asserting no uncaught Python exceptions and no catch-all "Something went wrong" crash banner
- Interaction tests: toggle mode radio + drag marginal-tax-rate slider — regression guards for the [C1] widget-generation fix
- 99 total tests (was 92), 2.95 s runtime

### Changed
- `APP_VERSION` bumped to 1.7.2

## [1.7.1] — 2026-04-20

**Human UX audit v1 — complex item [C10], layers 1 + 2.** Property-based fuzz tests and a hand-curated YAML noise corpus. The fuzz surfaced two real robustness bugs; both are fixed here.

### Added
- `hypothesis>=6.100,<7.0` as a dev dependency; `[tool.hypothesis]` with `derandomize=true` for CI determinism
- `tests/test_fuzz_models.py` — 6 invariant tests × 40 examples each: YAML round-trip, typed-error-or-success contract on `run(s)`, purchase-cost reconciliation, no NaN/inf in cashflow, affordability survival, annuity-balance monotonicity
- `tests/test_yaml_noise.py` — 8 hand-curated degenerate YAMLs (missing key, unknown key, bad mode, 0-budget adaptive, empty loans, negative capex cost, 1e12 price, 24-month vacancy)

### Fixed
- Unknown YAML keys no longer raise `TypeError` on load — every dataclass construction goes through `_only_known_fields()` for forward-compat with older / newer schemas
- `mode` values other than `"live"` / `"rent"` are now rejected with a clear `ValueError` on load; previously silently accepted and the engine ran with garbage

### Changed
- `APP_VERSION` bumped to 1.7.1

## [1.7.0] — 2026-04-20

**Human UX audit v1 — complex item [C1].** Fixes a systemic stale-widget bug that affected every sidebar input.

### Fixed
- Sidebar widgets (all 46 of them) were silently overriding programmatic scenario writes. Every scenario load / reset quietly reverted most fields to whatever the widget cache last held. The mode radio and the marginal-tax-rate slider were the most visible, but all 46 inputs had the bug.

### Changed
- Every sidebar widget now uses a `wk("base_name")` key derived from a module-level `widget_generation` counter
- Scenario-load paths ("Load selected", file uploader, "↺ Reset loans", "↺ Reset capex") bump the generation counter, invalidating every keyed widget so Streamlit re-seeds them from the fresh scenario's `value=`/`index=` kwargs
- `APP_VERSION` bumped to 1.7.0 (minor bump — scope touches every user-facing sidebar input)

## [1.6.4] — 2026-04-20

**Human UX audit v1 — complex item [C7].** Splits the bundled Notar + Grundbuch fee into two per-scenario-overridable rates.

### Added
- `Financing.notary_pct` / `Financing.grundbuch_pct` optional overrides (default `None` → fall back to `rules_de.NOTARY_FEE` / `GRUNDBUCH_FEE`)
- `PurchaseCostBreakdown.notary_fee` + `grundbuch_fee` as separate floats; convenience `notary_grundbuch` property preserves the bundled figure
- `compute_purchase_costs` accepts separate `notary_rate` + `grundbuch_rate` kwargs
- Sidebar **"🔧 Advanced: closing-fee rates"** collapsed expander under Financing — two `st.number_input` widgets, saved as overrides only when the user moves away from defaults
- Tests: default split matches `rules_de` and sums to the legacy 2 %; explicit overrides flow through to AfA basis

### Changed
- Summary purchase-costs table splits the single "Notary + land registry (~2 %)" row into "Notary (Notar, ~1.5 %)" and "Land registry (Grundbuch, ~0.5 %)"
- "What are these fees?" explainer now covers Notar and Grundbuch separately and points at the Advanced override
- `APP_VERSION` bumped to 1.6.4

## [1.6.3] — 2026-04-20

**Human UX audit v1 — complex item [C6].** Capex editor no longer hard-crashes on partially-filled rows.

### Added
- `CapexItem.__post_init__` validator — rejects `cost_eur < 0` or `year_due < 1900` with a clear `ValueError`
- Sidebar capex editor surfaces skipped incomplete rows via `st.warning` (previously `int(NaN)` crashed the app)
- `test_capexitem_validates_inputs` covering valid / negative-cost / zero-year cases

### Changed
- `APP_VERSION` bumped to 1.6.3 (main-footer version line)

### Removed
- Sidebar "🔓 Open source" footer caption (the main-page footer already carries the GitHub link)
- Orphaned `REPO_URL` constant

## [1.6.2] — 2026-04-20

**Human UX audit v1 — complex item [C9].** Adds an optional total monthly housing ceiling as a second, distinct affordability cap — not an engine knob.

### Added
- `Financing.monthly_total_housing_budget_eur` (default `0.0` = unset) — ceiling on loan + operating costs combined
- Always-visible sidebar input under Financing; tooltip explicitly contrasts it with the existing `[adaptive]` loan budget
- Summary-tab warning when total housing exceeds the ceiling; grey caption with headroom when within budget
- `total_housing_mo`, `housing_budget`, `housing_budget_set`, `housing_budget_exceeded` in the affordability dict
- YAML load/save round-trip support — existing YAMLs stay backward-compatible via `.get(..., 0.0)`
- Unit test covering unset / within-budget / exceeded boundaries

## [1.6.1] — 2026-04-20

**Human UX audit v1 — complex item [C2].** Phase-4 lowest-risk start: soft affordability warnings above the strained-zone thresholds.

### Added
- Soft `st.warning` blocks on the Summary tab when `loan_pct > 40 %` or `burden_pct > 45 %` — a second band above the existing 30 % rule-of-thumb badges
- `LOAN_INCOME_WARN_THRESHOLD` / `BURDEN_INCOME_WARN_THRESHOLD` constants in `immokalkul/affordability.py` so future tuning lives in one place
- `loan_pct_warn` / `burden_pct_warn` booleans + thresholds in the affordability dict
- Unit test `test_warn_flags_track_thresholds` covering both sides of each threshold

## [1.6.0] — 2026-04-20

**Human UX audit v1 — quick fixes applied.** Addresses 47 labelled items plus 3 iteration follow-ups from a first-person user walkthrough.

### Added
- App version + open-source GitHub link in the sidebar footer and page footer
- Question-opening tooltips on Loan/income, Net burden/income, Price/annual income, Net out of pocket, cumulative-wealth and capex tiles
- Cost-line notes for Building insurance, Liability insurance and Vermieter-Rechtsschutz; long notes collapse to a preview with a disclosure arrow
- Dotted "Tax owed @ N%" line on the annual-tax chart so the marginal-rate slider visibly moves the plot
- `Scenario detail` header + bordered-card layout on the Summary tail
- Hausgeld operating-vs-reserve explainer on the Operating costs tab; WEG defined inline everywhere it appears
- Clickable links for ImmoScout24 / Mietspiegel / ECB price-stability page

### Changed
- `RentParameters.expected_vacancy_months_per_year` default 0.25 → 2.0 (realistic conservative German baseline); all four sample scenarios updated accordingly
- Vacancy slider is integer months 0–6 (was 0.0–3.0 float)
- "Adaptive debt ceiling" renamed to "Monthly loan budget [adaptive] (€/mo, all loans)"; bracket convention for technical flags
- Loan examples diversified — Bonn sample renames LBS/Mamma → "Bausparer (LBS)" / "Family loan"; Munich Neubau adds a KfW 124 subsidised tranche
- Operating-costs tab reordered: pie chart + total now appear above the full line-by-line table
- Cashflow / Summary tables render as Styler-bolded totals with red/green sign-based colouring (Tax, Net property, Cumulative react to value sign)
- Capex tab: chart titles moved out of Plotly into section headers, bumped font size, rounded hover prices, capex-is-mode-independent caption
- AfA basis and Operating costs rendered as markdown tables so long explanations wrap freely instead of being truncated

### Fixed
- `year-1 monthly cash flow` Styler was colouring the wrong column positionally; now keyed by column name
- `-€0` rent-income row in live mode no longer renders as a green inflow
- Bonn reference cumulative pin updated (€518,104 → €316,213 at 50 yr) to reflect the new vacancy baseline

## [1.5.0] — 2026-04-20

**Finance audit v1 applied.** Audit artifacts: [`docs/audits/finance/v1/`](docs/audits/finance/v1/).

### Added
- Building/land value split drives a reverse-calculable depreciation basis
- Hausgeld split into deductible operating-cost and capex-reserve components
- Grundsteuer base calculation from Bodenrichtwert + building value
- 36 pinned regression tests locking Germany-specific math to reference scenarios
- Elevator, energy-class, and renovation-year tooltips on property inputs
- This `CHANGELOG.md`

### Changed
- Docs reorganised: `REFERENCES.md` → [`docs/REFERENCES.md`](docs/REFERENCES.md);
  addressed audit artifacts consolidated under [`docs/audits/`](docs/audits/)
- Sample scenario fix where building/land proportions were inverted

## [1.4.0] — 2026-04-20

**UI audit v2 applied.** Audit artifacts: [`docs/audits/UI/v2/`](docs/audits/UI/v2/).

### Added
- Year-1 monthly-cost section at the top of the Summary tab

### Changed
- Affordability: current rent now credited in live-mode burden; binary rent
  check replaced with a 15%-of-income premium rule
- Summary-tab density sweep, drift cleanup, and residual coverage-gap closure

## [1.3.0] — 2026-04-19

Interim release between audits: WEG share, capex scheduling, Verlustverrechnung,
references polish, and a prompt-builder for translating listings into YAML.

### Added
- Sidebar LLM prompt-builder (listing → YAML scenario)
- Clickable URLs on every source in `REFERENCES.md`
- Capex tab surfaces that items are auto-scheduled from the lifecycle table
- Apartment WEG-share on Gemeinschaftseigentum capex with a smoothed reserve
- Sidebar clarification of initial-capital vs. loan semantics

### Changed
- Rental losses now offset salary (Verlustverrechnung) instead of being floored
- Avoided-rent credited in live mode so cumulative wealth reflects reality
- Loans table: per-column help moved to a collapsible key below the editor
- Sample YAMLs populate current warm rent; app warns when left at 0

### Fixed
- Percent-formatted sliders for Grundsteuer and loan `Rate` now store and
  display as percent instead of silently mixing percent and ratio

## [1.2.0] — 2026-04-19

**UI audit v1 applied.** Audit artifacts: [`docs/audits/UI/v1/`](docs/audits/UI/v1/).
First test suite lands.

### Added
- `immokalkul/affordability.py` extracted from app code
- Affordability dashboard at the top of Summary with current-rent comparison
- Initial pytest suite (`affordability`, `financing`, `io`, `engine`)

### Changed
- UI-audit actionable items applied across the Streamlit UI and data layer

## [1.1.0] — 2026-04-19

### Added
- In-app guidance explaining how to interpret every number
- Expanded source references

### Changed
- Adaptive-loan logic generalised so it works across the full scenario-builder
  flow, not just the initial path

## [1.0.0] — 2026-04-19

Initial public release — German property-investment calculator focused on
tax-correct math (AfA, Peterssche Formel, Bodenrichtwert) and plain-language UI
explaining every number.

[1.5.0]: https://github.com/nicofirst1/immokalkul/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/nicofirst1/immokalkul/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/nicofirst1/immokalkul/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/nicofirst1/immokalkul/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/nicofirst1/immokalkul/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/nicofirst1/immokalkul/releases/tag/v1.0.0
