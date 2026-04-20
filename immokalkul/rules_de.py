"""
German property finance rules and constants.

Single source of truth for everything legally / empirically defined.
Each constant is cited so it can be verified later. When tax law changes,
this is the only file that needs touching.

Primary legal sources:
- AfA rules: § 7 Abs. 4 EStG (Einkommensteuergesetz)
- Anschaffungsnaher Aufwand: § 6 Abs. 1 Nr. 1a EStG, BFH 9.5.2017 IX R 6/16
- WEG-Reform 2020: § 19 Abs. 2 Nr. 4 WEG (Erhaltungsrücklage)
- II. Berechnungsverordnung: § 28 Abs. 2 II. BV (age-based reserve table)
- Petersche Formel: Heinz Peters, "Instandhaltung und Instandsetzung von
  Wohnungseigentum", Bauverlag 1984
- Component lifecycles: HEV / Mieterverband paritätische Lebensdauertabelle
- Bodenrichtwert Bonn-Poppelsdorf 2024: €1,000-1,600/m² range (verified Jan 2026)

Verification sources (where the above interpretations were confirmed), with a
reliability ranking and caveats, are listed in REFERENCES.md at the repo root.
"""
from __future__ import annotations
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# AfA (Absetzung für Abnutzung) — annual depreciation rate by build year
# ---------------------------------------------------------------------------
# Source: § 7 Abs. 4 EStG; confirmed by Finanzamt NRW publication.
# 2023+ band introduced by Jahressteuergesetz 2022 (JStG 2022) as a Wohnungs-
# bau-Förderung — statute wording is "33⅓ Jahre Nutzungsdauer" with "3 % AfA",
# so we treat 0.030/yr as the canonical rate and report useful life as 33⅓
# (display rounded to 33). The engine consumes `rate`, not `useful_life`,
# so the residual mismatch (0.030 × 33 = 0.99 ≠ 1.0) is display-only.
def afa_rate(year_built: int) -> float:
    """Linear AfA rate (per year) on the building+capitalizable-fees basis."""
    if year_built < 1925:
        return 0.025   # 40 yr useful life
    elif year_built < 2023:
        return 0.020   # 50 yr useful life
    else:
        return 0.030   # 33⅓ yr useful life (JStG 2022 Förderung)


def afa_useful_life_years(year_built: int) -> int:
    """Useful life in years. For 2023+ builds the statute says 33⅓; we
    return the floor (33) for integer typing — see `afa_rate` docstring."""
    if year_built < 1925:
        return 40
    elif year_built < 2023:
        return 50
    else:
        return 33  # statute: 33⅓ — display layer rounds


# ---------------------------------------------------------------------------
# Anschaffungsnaher Aufwand — § 6 Abs. 1 Nr. 1a EStG
# ---------------------------------------------------------------------------
# If renovation costs in the first 3 years after purchase exceed 15% of the
# building value (excl. VAT), they're reclassified as Herstellungskosten and
# must be depreciated via AfA (over 40-50 yr) instead of being immediately
# deductible (over 1-5 yr as Erhaltungsaufwand).
ANSCHAFFUNGSNAH_THRESHOLD_PCT = 0.15
ANSCHAFFUNGSNAH_WINDOW_YEARS = 3


# ---------------------------------------------------------------------------
# German purchase fees (NRW)
# ---------------------------------------------------------------------------
GRUNDERWERBSTEUER_NRW = 0.065        # 6.5% Grunderwerbsteuer in NRW (varies by Bundesland)
MAKLERPROVISION_TYPICAL = 0.0357     # ~3.57% incl. VAT, buyer share post-
                                     # § 656c BGB (Bestellerprinzip extended
                                     # to private buyers, in force since
                                     # 23.12.2020 — Gesetz zur Verteilung der
                                     # Maklerkosten bei der Vermittlung von
                                     # Kaufverträgen über Wohnungen und
                                     # Einfamilienhäuser).
NOTARY_FEE = 0.015                    # ~1.5% notary
GRUNDBUCH_FEE = 0.005                 # ~0.5% land registry
NOTARY_AND_GRUNDBUCH = NOTARY_FEE + GRUNDBUCH_FEE  # 2% combined

# Of these, only Grunderwerbsteuer + Maklerprovision + (most of) Notar count
# as Anschaffungsnebenkosten that can be capitalized into AfA basis.
# The Grundschuldbestellung portion of notary/Grundbuch is deductible
# as Werbungskosten (Geldbeschaffungskosten), not capitalized.
# Simplification: assume 80 % of notary+Grundbuch is capitalizable.
# Realistic range is 70–90 %: cash purchases skew higher (no Grundschuld
# entry, almost all is Auflassung/Erwerbskosten), leveraged purchases skew
# lower (Grundschuldbestellung adds ~0.5–1 % of loan amount as Geldbeschaf-
# fungskosten, fully Werbungskosten). 0.80 is a defensible mid-range
# assumption — replace with a per-scenario field if your closing statement
# shows the exact split. Source: BMF-Schreiben "Anschaffungsnebenkosten",
# discussions at Steuerberaterkammer Westfalen-Lippe, Haufe Steuer-Office.
NOTARY_GRUNDBUCH_AFA_SHARE = 0.80


# ---------------------------------------------------------------------------
# Petersche Formel — annual maintenance reserve for Gemeinschaftseigentum
# ---------------------------------------------------------------------------
# Original formula: (Herstellungskosten/m² × 1.5 / 80) gives total annual reserve
# per m². Of that, 65-70% is Gemeinschaftseigentum (the rest is Sondereigentum).
# Source: Wikipedia Peterssche Formel + WEG-Reform 2020 (§19 Abs. 2 Nr. 4 WEG)
PETERS_LIFETIME_FACTOR = 1.5         # 1.5× construction cost over 80 years
PETERS_PERIOD_YEARS = 80
PETERS_GEMEINSCHAFT_SHARE = 0.70     # WEG portion (apartment vs. house)


def petersche_formel_per_m2_year(construction_cost_per_m2: float,
                                  weg_only: bool = False) -> float:
    """Annual reserve per m² of living space. weg_only=True returns only the
    Gemeinschaftseigentum portion (relevant for apartment owners; house owners
    are responsible for everything)."""
    base = construction_cost_per_m2 * PETERS_LIFETIME_FACTOR / PETERS_PERIOD_YEARS
    if weg_only:
        return base * PETERS_GEMEINSCHAFT_SHARE
    return base


# ---------------------------------------------------------------------------
# II. Berechnungsverordnung age-based maintenance table (§28 Abs. 2 II. BV)
# ---------------------------------------------------------------------------
# Used for sozialer Wohnungsbau but a useful realism check. Older buildings
# need more maintenance reserve. Values in €/m²/yr. Add €1/m²/yr if there's
# an elevator.
# Source: §28 Abs. 2 II. BV; updated reference values 2024
def ii_bv_reserve_per_m2_year(building_age_years: int,
                                has_elevator: bool = False) -> float:
    """Returns the maintenance reserve per m² per year per II. BV table."""
    if building_age_years <= 22:
        base = 7.10
    elif building_age_years <= 32:
        base = 9.00
    else:
        base = 11.50
    if has_elevator:
        base += 1.00
    return base


# ---------------------------------------------------------------------------
# Realistic maintenance reserve for owner-occupied / single-family
# ---------------------------------------------------------------------------
# Rule of thumb: 1.0% to 1.5% of building value per year for an own house
# (no WEG to absorb common areas — everything is yours).
# Source: Sparkasse, Raiffeisen, Verband Privater Bauherren
HOUSE_RESERVE_PCT_OF_BUILDING_LOW = 0.010
HOUSE_RESERVE_PCT_OF_BUILDING_HIGH = 0.015


# ---------------------------------------------------------------------------
# Component lifecycles & typical costs
# ---------------------------------------------------------------------------
# Used by capex.py to schedule major one-off renovations.
# Source: Sparkasse Bauteil-Lebenserwartung, paritätische Lebensdauertabelle
# (HEV/MV), Baukosteninformationszentrum BKI Q4/2025

@dataclass(frozen=True)
class Component:
    name: str
    lifetime_years: int            # typical useful life
    cost_basis: str                # "per_m2_living", "flat", "per_m2_roof", etc.
    cost_low: float                # low-end EUR estimate
    cost_high: float               # high-end EUR estimate
    scope: str = "se_individual"   # "we_building" = Gemeinschaftseigentum
                                   # (apartment owner's share ≈ WEG_SHARE_APARTMENT
                                   # of the full figure); "se_individual" =
                                   # Sondereigentum (individual owner pays full)
    notes: str = ""


# Typical user's share of a Mehrfamilienhaus WEG (6-8 units → 12-17 %);
# applied to Gemeinschaftseigentum items for apartments.
WEG_SHARE_APARTMENT = 0.15


COMPONENTS = [
    Component("Heating system (boiler)", 20, "flat", 12000, 25000,
              scope="we_building",
              notes="GEG mandates replacement >30yr. Heat pump retrofit may push higher."),
    Component("Roof covering", 40, "per_m2_roof", 100, 250,
              scope="we_building",
              notes="Tile/copper roofs last longest; tar paper much less."),
    Component("Façade paint", 12, "per_m2_facade", 30, 60,
              scope="we_building"),
    Component("Façade insulation (WDVS)", 35, "per_m2_facade", 90, 250,
              scope="we_building",
              notes="WDVS most common; vorhängte Fassade more expensive."),
    Component("Windows (full replacement)", 30, "per_window", 800, 1500,
              scope="se_individual",
              notes="Wood ~25-30yr, PVC/aluminum up to 40yr. Pre-1995 single-glazing urgent."),
    Component("Bathroom (renovation)", 28, "per_bathroom", 15000, 25000,
              scope="se_individual",
              notes="Plumbing + tiles + fixtures together."),
    Component("Electrical system", 35, "per_m2_living", 80, 150,
              scope="se_individual",
              notes="Pre-1990 systems often need full rewire; safety + capacity issues."),
    Component("Plumbing (water/drain)", 45, "per_m2_living", 80, 200,
              scope="we_building",
              notes="Risers are Gemeinschaftseigentum; in-unit plumbing is Sondereigentum — WEG share applied as a rough average."),
    Component("Floors (parquet/laminate refresh)", 25, "per_m2_living", 40, 120,
              scope="se_individual"),
    Component("Kitchen (full replacement)", 20, "flat", 10000, 25000,
              scope="se_individual",
              notes="Owner-occupier expense in live mode; landlord may not provide."),
    Component("Interior renovation (paint, doors)", 15, "per_m2_living", 30, 80,
              scope="se_individual"),
]


# ---------------------------------------------------------------------------
# Tax — marginal rate brackets are too dynamic to hardcode here
# ---------------------------------------------------------------------------
# We let the user input their marginal rate. The 2026 Spitzensteuersatz
# is 42% up to ~€70k, 45% (Reichensteuer) above ~€280k, but most users
# of this tool are in the 35-45% effective marginal range.


# ---------------------------------------------------------------------------
# Other German specifics
# ---------------------------------------------------------------------------
GRUNDSTEUER_RATE_OF_PRICE_PROXY = 0.002  # rough; real depends on Hebesatz × Einheitswert
SCHORNSTEINFEGER_ANNUAL = 80              # Chimney sweep, mandatory (~€60-100/yr)
GEZ_HOUSEHOLD_ANNUAL = 220                # Rundfunkbeitrag (debatable: paid anyway)
HEATING_MAINTENANCE_ANNUAL = 150          # Boiler service (Wartung)


def is_pre_1925(year_built: int) -> bool:
    return year_built < 1925


def is_likely_denkmal_candidate(year_built: int) -> bool:
    """Buildings before 1900 are often Denkmal-eligible; user must verify."""
    return year_built < 1900
