"""Pin German tax/finance rule constants so refactors can't silently shift them."""
from __future__ import annotations

import pytest

from immokalkul import rules_de


# F-P0-4 — pin AfA rates and useful lives across all year-built bands.
@pytest.mark.parametrize("year,rate,life", [
    (1900, 0.025, 40),  # pre-1925
    (1924, 0.025, 40),  # last pre-1925 year
    (1925, 0.020, 50),  # first 1925-2022 year
    (2022, 0.020, 50),  # last 1925-2022 year
    (2023, 0.030, 33),  # first JStG-2022 band (statute: 33⅓ yr)
    (2050, 0.030, 33),  # well into the 2023+ band
])
def test_afa_rate_and_useful_life(year: int, rate: float, life: int) -> None:
    assert rules_de.afa_rate(year) == rate
    assert rules_de.afa_useful_life_years(year) == life


# F-P0-6 — for 2023+ builds, rate × useful_life should land near 1.0
# (statute is 33⅓ yr × 3 %/yr; integer rounding gives 33 × 3 % = 99 %).
def test_afa_2023_band_rate_times_life_is_near_unity() -> None:
    assert rules_de.afa_rate(2023) * rules_de.afa_useful_life_years(2023) == \
        pytest.approx(1.0, rel=0.02)


# F-P2-26 — pin which formula wins (Petersche vs II.BV) per age band.
# Peters scales with construction cost/m²; II.BV is a flat age-tier table
# (7.10 / 9.00 / 11.50 €/m²/yr at ages ≤22 / 22-32 / >32). The max() winner
# flips with both the building value and the age — pin the boundaries.
@pytest.mark.parametrize("constr_per_m2,age,expected_winner", [
    # Low-value Altbau (€500/m² → Peters €6.56): II.BV always wins.
    (500.0, 10, "ii_bv"),
    (500.0, 25, "ii_bv"),
    (500.0, 40, "ii_bv"),
    # Mid-cost (€800/m² → Peters €10.50): Peters wins for ≤32 yr, loses at 40.
    (800.0, 10, "peters"),
    (800.0, 25, "peters"),
    (800.0, 40, "ii_bv"),
    # Typical apartment (€2,500/m² → Peters €32.81): Peters dominates always.
    (2_500.0, 10, "peters"),
    (2_500.0, 25, "peters"),
    (2_500.0, 40, "peters"),
])
def test_max_peters_vs_iibv(constr_per_m2: float, age: int,
                              expected_winner: str) -> None:
    peters = rules_de.petersche_formel_per_m2_year(constr_per_m2, weg_only=True)
    ii_bv = rules_de.ii_bv_reserve_per_m2_year(age)
    winner = "peters" if peters > ii_bv else "ii_bv"
    assert winner == expected_winner


def test_anschaffungsnaher_constants_pinned() -> None:
    """Statute: § 6 Abs. 1 Nr. 1a EStG — 15 % threshold over a 3-year window."""
    assert rules_de.ANSCHAFFUNGSNAH_THRESHOLD_PCT == 0.15
    assert rules_de.ANSCHAFFUNGSNAH_WINDOW_YEARS == 3
