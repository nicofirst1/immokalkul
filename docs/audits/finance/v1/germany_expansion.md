# Germany expansion — extending immokalkul beyond NRW

Companion to [`audit.md`](./audit.md) Framework 7. This document scopes what changes are needed for the app to produce correct numbers for any of the 16 Bundesländer, not just NRW.

The audit finding driving this plan:

> **Grunderwerbsteuer hardcoded NRW 6.5%** — wrong for every other Bundesland. A user buying in Bayern (3.5%) sees a Grunderwerbsteuer overstatement of €18k on a €600k purchase.

The Bonn scenario works today; Munich / Berlin / Köln sample scenarios exist in `data/` but silently use NRW's Grunderwerbsteuer rate. Fixing this is not just a one-line constant change — it requires a data model, a UI, and tests that don't regress as rates change.

---

## 1. What is NRW-hardcoded today

Enumerated from the v1 audit (`audit.md §2.7`):

| Rule | Today | Real variation by state | Impact of getting it wrong |
|---|---|---|---|
| **Grunderwerbsteuer rate** | `rules_de.py:61` hardcoded 6.5% | 3.5% (Bayern, Sachsen) to 6.5% (NRW, Brandenburg, Saarland, SH, Thüringen, Berlin, Hessen, Mecklenburg-Vorpommern) | Up to ±3 pp → up to ±€18k on €600k |
| **Grundsteuer rate** | `rules_de.py:199` flat 0.2% proxy | States chose different post-2025 models (Bundesmodell vs. Länderöffnung — Bayern uses Flächenmodell, Hamburg uses Wohnlagenmodell, Baden-Württemberg uses Bodenwertmodell, NRW/Berlin/etc. use Bundesmodell); Hebesatz varies 150-1,150% across municipalities | Up to ±50% on annual Grundsteuer |
| **Bodenrichtwert data** | Sample scenarios use BORIS NRW values; engine accepts any number | Each state has its own BORIS portal with different coverage, licensing, and update cadence | Bad data → bad building/land split → wrong AfA basis |
| **Sample scenarios** | 3 of 4 samples are outside NRW but silently inherit NRW Grunderwerbsteuer | — | Users run a "Munich" scenario and get NRW tax |
| **UI copy** | Tooltips say "NRW 6.5%", REFERENCES.md cites Finanzamt NRW | — | Users outside NRW aren't told the app defaults to NRW |

Federal rules that do **not** change by Bundesland (safe to keep as-is):

- AfA (§ 7 EStG), Anschaffungsnaher Aufwand (§ 6 EStG), all income-tax logic
- WEG Erhaltungsrücklage (§ 19 WEG)
- Notar + Grundbuch (GNotKG — fee table is federal, though the Gerichtskosten side has minor state surcharges <1%)
- Maklerprovision split (§§ 656a-d BGB)
- GEG / Energieausweis
- II. BV reserve table (federal for sozialer Wohnungsbau; used as realism check)

---

## 2. The 16-state data to be added

### 2.1 Grunderwerbsteuer — current rates

Verify each against the state's GrEStG-Durchführungsgesetz before shipping. Rates as of 2026, consolidated public sources:

| Bundesland | Rate | Last change |
|---|---|---|
| Bayern | 3.5% | 1997 (baseline) |
| Sachsen | 5.5% | 2023 (from 3.5%) |
| Hamburg | 5.5% | 2023 (from 4.5%) |
| Bremen | 5.0% | 2014 |
| Niedersachsen | 5.0% | 2014 |
| Sachsen-Anhalt | 5.0% | 2012 |
| Rheinland-Pfalz | 5.0% | 2012 |
| Baden-Württemberg | 5.0% | 2011 |
| Berlin | 6.0% | 2014 |
| Hessen | 6.0% | 2013 |
| Mecklenburg-Vorpommern | 6.0% | 2019 |
| Brandenburg | 6.5% | 2015 |
| Nordrhein-Westfalen | 6.5% | 2015 |
| Saarland | 6.5% | 2015 |
| Schleswig-Holstein | 6.5% | 2014 |
| Thüringen | 6.5% | 2017 |

**Source quality.** GrEStG-state-DG acts are the primary source (gesetze-im-internet.de plus state-specific portals). Secondary: [Haufe](https://www.haufe.de/), [Steuertipps](https://www.steuertipps.de/), IHK tables. Tertiary: news coverage of rate changes.

### 2.2 Grundsteuer — post-2025 Reform

The reform replaces the old Einheitswert model with state-specific models:

| State | Model | Notes |
|---|---|---|
| Baden-Württemberg | Bodenwertmodell | Only land value counts; ignore building |
| Bayern | Flächenmodell | Area × factor; ignores value entirely — flat per m² |
| Hamburg | Wohnlagenmodell | Area × location factor |
| Hessen | Flächen-Faktor-Modell | Variant of Flächenmodell with value adjustment |
| Niedersachsen | Flächen-Lage-Modell | Like Hamburg |
| NRW, Berlin, Brandenburg, Bremen, Mecklenburg-Vorpommern, Rheinland-Pfalz, Saarland, Sachsen, Sachsen-Anhalt, Schleswig-Holstein, Thüringen | Bundesmodell | Standard formula: Grundsteuerwert × Steuermesszahl × Hebesatz |

**For v1 of the expansion**, the minimum-viable implementation is:

- Bundesmodell states: `grundsteuer = Grundstückswert × 0.00034 × hebesatz_decimal` (Steuermesszahl for residential is ~0.034% for plots up to ~€1M).
- Flächenmodell / other-land-models: expose a per-state lookup or a user override.
- Hebesatz: require user input with a helpful default (e.g., Bonn ~595%, Munich ~535%, Berlin ~810%). State-capital defaults are enough for v1; full municipal table is v2.

### 2.3 Bodenrichtwert portals

| State | Portal |
|---|---|
| NRW | [BORIS NRW](https://www.boris.nrw.de/) |
| Niedersachsen | [BORIS.NI](https://www.boris.niedersachsen.de/) |
| Bayern | [BORIS Bayern](https://geoportal.bayern.de/) |
| Baden-Württemberg | [BORIS-BW](https://www.gutachterausschuesse-bw.de/) |
| Berlin | [Geoportal Berlin](https://fbinter.stadt-berlin.de/) |
| Brandenburg | [BORIS Brandenburg](https://geobasis-bb.de/) |
| Hamburg | [Geoportal Hamburg](https://geoportal.hamburg.de/) |
| Hessen | [BORIS Hessen](https://www.gds.hessen.de/) |
| Mecklenburg-Vorpommern | [BORIS.MV](https://www.geoportal-mv.de/) |
| Rheinland-Pfalz | [BORIS.RLP](https://www.geoportal.rlp.de/) |
| Saarland | [BORIS Saarland](https://geoportal.saarland.de/) |
| Sachsen | [BORIS Sachsen](https://www.boris.sachsen.de/) |
| Sachsen-Anhalt | [BORIS Sachsen-Anhalt](https://www.lvermgeo.sachsen-anhalt.de/) |
| Schleswig-Holstein | [BORIS-SH](https://www.boris-sh.de/) |
| Thüringen | [BORIS.TH](https://www.geoportal-th.de/) |
| Bremen | [Bremen.de Portal](https://www.geo.bremen.de/) |

Most are public but with different UX and licensing. Don't scrape; link users to the right portal and ask for user input.

---

## 3. Data model changes

### 3.1 `rules_de.py` → `rules_de_by_state.py`

Current (`rules_de.py:61`):

```python
GRUNDERWERBSTEUER_NRW = 0.065
```

Proposed addition:

```python
# rules_de.py — keep existing constants; add lookups.

from enum import Enum


class Bundesland(str, Enum):
    BW = "Baden-Württemberg"
    BY = "Bayern"
    BE = "Berlin"
    BB = "Brandenburg"
    HB = "Bremen"
    HH = "Hamburg"
    HE = "Hessen"
    MV = "Mecklenburg-Vorpommern"
    NI = "Niedersachsen"
    NW = "Nordrhein-Westfalen"
    RP = "Rheinland-Pfalz"
    SL = "Saarland"
    SN = "Sachsen"
    ST = "Sachsen-Anhalt"
    SH = "Schleswig-Holstein"
    TH = "Thüringen"


GRUNDERWERBSTEUER_RATES: dict[Bundesland, float] = {
    Bundesland.BY: 0.035,
    Bundesland.SN: 0.055,
    Bundesland.HH: 0.055,
    Bundesland.HB: 0.050,
    Bundesland.NI: 0.050,
    Bundesland.ST: 0.050,
    Bundesland.RP: 0.050,
    Bundesland.BW: 0.050,
    Bundesland.BE: 0.060,
    Bundesland.HE: 0.060,
    Bundesland.MV: 0.060,
    Bundesland.BB: 0.065,
    Bundesland.NW: 0.065,
    Bundesland.SL: 0.065,
    Bundesland.SH: 0.065,
    Bundesland.TH: 0.065,
}


class GrundsteuerModel(str, Enum):
    BUNDES = "Bundesmodell"
    BW_BODENWERT = "Bodenwertmodell (BW)"
    BY_FLAECHE = "Flächenmodell (BY)"
    HH_WOHNLAGE = "Wohnlagenmodell (HH)"
    HE_FLAECHE_FAKTOR = "Flächen-Faktor (HE)"
    NI_FLAECHE_LAGE = "Flächen-Lage (NI)"


GRUNDSTEUER_MODELS: dict[Bundesland, GrundsteuerModel] = {
    Bundesland.BW: GrundsteuerModel.BW_BODENWERT,
    Bundesland.BY: GrundsteuerModel.BY_FLAECHE,
    Bundesland.HH: GrundsteuerModel.HH_WOHNLAGE,
    Bundesland.HE: GrundsteuerModel.HE_FLAECHE_FAKTOR,
    Bundesland.NI: GrundsteuerModel.NI_FLAECHE_LAGE,
    # all others → Bundesmodell
}


# Rough defaults for a few state capitals (%) — v1 placeholders
GRUNDSTEUER_HEBESATZ_DEFAULTS: dict[Bundesland, float] = {
    Bundesland.NW: 5.95,   # Bonn-ish
    Bundesland.BY: 5.35,   # München
    Bundesland.BE: 8.10,
    Bundesland.HH: 5.40,
    # ... extend
}
```

Keep `GRUNDERWERBSTEUER_NRW = GRUNDERWERBSTEUER_RATES[Bundesland.NW]` as a back-compat alias until all consumers are migrated.

### 3.2 `models.py`

Add to `PropertyParameters`:

```python
bundesland: Bundesland = Bundesland.NW   # keep NRW as default for back-compat
# optional user overrides — fall back to table if None
grunderwerbsteuer_rate: Optional[float] = None
grundsteuer_hebesatz: Optional[float] = None
```

### 3.3 `financing.py`

Change `compute_purchase_costs()` to read `s.property.grunderwerbsteuer_rate or GRUNDERWERBSTEUER_RATES[s.property.bundesland]`.

### 3.4 `operating_costs.py`

Replace `purchase_price × 0.002` Grundsteuer proxy with a per-state computation:

```python
def compute_grundsteuer(property: PropertyParameters, land_value: float) -> float:
    model = GRUNDSTEUER_MODELS.get(property.bundesland, GrundsteuerModel.BUNDES)
    hebesatz = property.grundsteuer_hebesatz \
        or GRUNDSTEUER_HEBESATZ_DEFAULTS.get(property.bundesland, 5.0)
    if model == GrundsteuerModel.BUNDES:
        steuermesszahl = 0.00034   # residential
        return land_value * steuermesszahl * hebesatz
    elif model == GrundsteuerModel.BY_FLAECHE:
        # €0.50/m² land + €0.50/m² building → multiplied by Hebesatz
        # (user may override)
        ...
    elif model == GrundsteuerModel.BW_BODENWERT:
        return land_value * 0.00091 * hebesatz
    # ... per state
```

---

## 4. UI changes

### 4.1 Sidebar — Bundesland selector

Add a Bundesland selector at the top of the Property expander (above price), using `st.selectbox` with the 16 states. Default to NRW. On change, auto-fill Grunderwerbsteuer and Grundsteuer Hebesatz fields from the lookup; the user can override.

### 4.2 Summary tab — purchase-costs table

Change the existing rate annotation (`app.py:737-740` per v1 UI fixes) from the fixed "6.5% NRW" string to the selected state's rate: `"Grunderwerbsteuer ({rate}% {state})"`.

### 4.3 Methodology tab

Add a Bundesland summary section listing the rate used, the Grundsteuer model active for that state, and links to primary sources (state GrEStG-DG + BORIS portal).

### 4.4 Sample scenarios

Update `data/munich.yaml`, `data/berlin.yaml`, `data/koeln.yaml` to set `bundesland:` correctly. Verify that running each produces a Grunderwerbsteuer that matches the real rate, not NRW's.

---

## 5. Tests

Each step above adds regression coverage:

| Test | File |
|---|---|
| Parametrized Grunderwerbsteuer rate per state (16 cases) | `tests/test_rules_de.py` |
| Grundsteuer computation per model type (at least one scenario per model) | `tests/test_operating_costs.py` |
| Scenario-level: running Munich sample produces Bayern's 3.5% Grunderwerbsteuer | `tests/test_io.py` or `tests/test_engine.py` |
| Back-compat: scenarios without a `bundesland:` field default to NRW and match pre-expansion output | `tests/test_io.py` |
| UI: selecting a new Bundesland updates the purchase-costs table | out of scope for unit tests; manual QA checklist |

---

## 6. Migration phases

### Phase 1 — NRW-parity expansion (v1.1, ~half-day)

- Add `Bundesland` enum, `GRUNDERWERBSTEUER_RATES` table, optional field on `PropertyParameters`.
- Update `financing.compute_purchase_costs()` to consume the table.
- Keep Grundsteuer as the flat proxy (log a disclosure that it will become state-specific in v1.2).
- Update the three non-NRW sample scenarios to declare their Bundesland.
- Sidebar: Bundesland selector, default NRW.
- Tests: parametrized Grunderwerbsteuer for all 16 states.

**Scope guardrail.** Don't touch Grundsteuer logic yet — Phase 1 is about getting Grunderwerbsteuer right everywhere. Shipping that alone closes the largest single EUR error for non-NRW users.

### Phase 2 — Grundsteuer per model (v1.2, ~day)

- Add `GrundsteuerModel` enum and per-state model mapping.
- Implement the Bundesmodell computation (covers 11 of 16 states).
- Implement Bayern Flächenmodell (covers Bayern users — largest non-Bundesmodell audience).
- Expose Hebesatz as a user input with state-capital defaults.
- Remaining states (BW / HH / HE / NI) fall back to Bundesmodell with a disclosure ("your state uses a different model; result is approximate").
- Tests: per-state parametrized Grundsteuer; Bundesmodell vs. Bayern diverge by > 20% for the same property.

### Phase 3 — Full per-municipality Hebesatz table (v1.3, optional, ~day)

- Add `hebesatz_table.csv` covering major German cities (Bonn, Köln, Düsseldorf, München, Berlin, Hamburg, Frankfurt, Stuttgart, Leipzig, Dresden, Hannover, Nürnberg, Bremen, Münster, Essen, Dortmund — the ~30 largest).
- Expose a "City" selector that pre-fills Hebesatz; user can still override.
- Tests: all cities produce a non-default Hebesatz; the default is used only for unknown cities.

### Phase 4 — Non-Bundesmodell states (v2, defer unless demand)

- Proper BW Bodenwertmodell, HH Wohnlagenmodell, HE Flächen-Faktor, NI Flächen-Lage formulas.
- Deferred because the Bundesmodell fallback is within ±30% for these states, which is comparable to the current proxy error — net parity with v1 even without the special formulas.

---

## 7. Open questions

These are decisions to settle before starting Phase 1:

1. **Default Bundesland.** Keep NRW (matches current behaviour, consistent with Bonn sample) or switch to a neutral "— select —" forcing user choice? Recommend: keep NRW, but show a visible selector so the choice is explicit.
2. **Grunderwerbsteuer rate changes.** Rates have changed ~every 3-5 years per state since 2006. Pin the date of the rate table in a comment; add a test that re-fails annually as a calendar-driven maintenance prompt? Or accept the staleness risk and document in REFERENCES.md?
3. **Sachsen-Anhalt's rate history.** The 2012 change is documented; if any state recently moved (e.g., Thüringen 2024 discussions), update before ship.
4. **BRW integration.** Should the app link directly to the state's BORIS portal ("Open BORIS for your Bundesland")? Or keep the sidebar tooltip-only approach? Recommend: single link in the sidebar caption, switches by Bundesland.
5. **Sample scenarios outside NRW.** Should we reset/rerun the Munich / Berlin / Köln samples to verify pre-expansion numbers, or rebuild them with correct Bundesland values? Recommend: rebuild with correct rates, and note in the sample YAML that the pre-expansion numbers differed.
6. **Austria / Schweiz scope creep.** Explicitly out of scope — only the 16 German Bundesländer.

---

## 8. Non-goals for the expansion

To keep the expansion bounded:

- **No Länder-level income tax.** German income tax is federal (§ 2 EStG) — no state variation.
- **No Erbschafts- / Schenkungsteuer.** Separate regime; out of scope.
- **No Gewerbesteuer.** The tool is for private buyers, not commercial investors.
- **No Kirchensteuer rate variation by state** (covered under P1-15 of `actionable_items.md` as a decomposition, not as a state issue).
- **No municipal Hebesatz database at launch.** Phase 3 only, and only the top-30 cities.
- **No historical rate time-series.** Current rates only; rate changes over time are accumulated directly into the table as they happen.

---

## 9. Dependencies with `actionable_items.md`

| Expansion item | Related item | Relationship |
|---|---|---|
| Phase 1 Grunderwerbsteuer table | P0-4 (pin AfA rates per year-built band) | Pattern — same parametrized-test structure |
| Phase 2 Grundsteuer per model | P0-7 (fix Grundsteuer base) | **Phase 2 supersedes P0-7** — if Phase 2 ships, skip P0-7 |
| Bundesland selector in sidebar | UI audit v2 findings | Minor sidebar surface addition |
| Per-state sample scenarios | UI audit §3.1 (Scenarios as onboarding) | Improves onboarding by showing per-state comparisons |
| Documentation of Bundesland defaults | P1-8 (Hausgeld disclosure pattern) | Same "document the simplification" pattern |

---

## 10. Success criteria

The expansion is complete (for v1.1 → v1.2) when:

- [ ] A user can select any of the 16 Bundesländer in the sidebar.
- [ ] Selecting a Bundesland updates the Grunderwerbsteuer rate shown in Summary.
- [ ] Selecting a Bundesland updates the Grundsteuer computation (Phase 2).
- [ ] The three non-NRW sample scenarios declare their Bundesland and produce the correct rate.
- [ ] `tests/test_rules_de.py` has a parametrized test for all 16 Grunderwerbsteuer rates with a cited source.
- [ ] `REFERENCES.md` has a section listing the 16 state GrEStG-DG acts with URLs.
- [ ] The Methodology tab lists the active state and model.
- [ ] No NRW-hardcoded string remains in `rules_de.py` or in UI copy (except as documented defaults).

Once these criteria are met, `audit/finance/v1/audit.md §2.7` is closed and the v2 audit can look for whatever new failure modes the expansion introduces (the UI-audit-v2 pattern).
