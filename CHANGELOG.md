# Changelog

All notable changes to **immokalkul** are documented here. Format based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[Semantic Versioning](https://semver.org/).

Minor versions correspond to audit cycles — each audit report and its
actionable-items list live in [`docs/audits/`](docs/audits/).

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
