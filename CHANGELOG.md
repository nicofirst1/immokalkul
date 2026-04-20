# Changelog

All notable changes to **immokalkul** are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[Semantic Versioning](https://semver.org/).

Minor versions correspond to audit cycles — each audit report and its
actionable-items list live in [`docs/audits/`](docs/audits/).

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
