"""End-to-end engine checks on the bundled sample scenarios."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from immokalkul import load_scenario, run


def test_all_sample_scenarios_load_and_run(sample_yaml_paths: list[Path]) -> None:
    """Each YAML in data/ parses into a Scenario and the engine returns a
    result object with the expected shape."""
    assert len(sample_yaml_paths) >= 4, "expected the 4 bundled samples"
    for path in sample_yaml_paths:
        s = load_scenario(path)
        r = run(s)
        assert isinstance(r.cashflow, pd.DataFrame)
        assert isinstance(r.amort, pd.DataFrame)
        assert len(r.cashflow) == s.globals.horizon_years
        assert len(r.amort) == s.globals.horizon_years
        # Cumulative must be monotone in the sense that it's always defined
        assert not r.cashflow["cumulative"].isna().any()


def test_bonn_reference_cumulative(bonn_result) -> None:
    """Guard against accidental engine drift: the Bonn sample must keep
    reproducing the long-established 50-year cumulative, within ±€1.

    Pinned value reflects:
    - Verlustverrechnung on rental losses offsetting salary at the marginal
      rate (§ 10d EStG). Pre-fix pin €405,936 floored tax at €0.
    - Apartment WEG share on Gemeinschaftseigentum capex items (heating,
      roof, façade, plumbing risers) — the WEG's Erhaltungsrücklage funds
      ~85 % of those costs via Hausgeld, so counting them 100 % against the
      owner was double-counting. Pre-fix pin €500,507 over-charged.
    - Bonn sample's `year_last_major_renovation` was set from null → 1995
      (Kernsanierung anchor); pushed component-replacement years out and
      lifted the cumulative from €525,196.
    - Removed the 0.75/0.50 building-share floor in
      `estimate_building_share`. Bonn's Bodenrichtwert × plot implies
      building share ≈ 0.63; pre-fix code floored to 0.75. Honest split
      lowers AfA (tax up) but also lowers the Petersche-derived
      maintenance reserve (op costs down); the latter dominates. Pin
      lifted from €526,894.
    - Hausgeld split into deductible operating portion + non-deductible
      Erhaltungsrücklage portion (§ 19 WEG, default 40/60). Reserve
      portion is no longer offset against rental income, so taxable
      income rises in rent mode. Pin dropped from €558,906.
    - Grundsteuer base switched from `price × rate` to
      `Grundstückswert × land_rate` (post-2025 Bundesmodell). Bonn's
      land value (BRW × plot ≈ €167k) × 0.34 % is lower than the old
      446k × 0.20 % proxy, but the deduction shrinks too — small net.
    """
    final = float(bonn_result.cashflow["cumulative"].iloc[-1])
    # Bonn sample's `expected_vacancy_months_per_year` changed 0.25 → 2
    # (audit v1 Phase-2b: realistic conservative default for German urban
    # rentals). 50 years of higher vacancy reduces rent income materially;
    # pin dropped from €518,104 → €316,213.
    # AfA now stops at year 40 for pre-1925 Altbau (§ 7 Abs. 4 EStG, audit
    # v1 [C5]). Bonn is year_built=1904, so years 41-50 lose ~€7.8k/yr of
    # AfA deduction; at marginal rate 38 % that's ~€3k/yr of extra tax for
    # 10 years (~€30k cumulative). Pin dropped €316,213 → €286,585.
    assert final == pytest.approx(286_585, abs=1)


def test_horizon_respected(bonn_scenario) -> None:
    bonn_scenario.globals.horizon_years = 20
    r = run(bonn_scenario)
    assert len(r.cashflow) == 20
    assert len(r.amort) == 20


def test_live_mode_has_no_rent_income(bonn_scenario) -> None:
    bonn_scenario.mode = "live"
    r = run(bonn_scenario)
    assert (r.cashflow["rent_net"] == 0).all()


def test_rent_mode_has_nonzero_afa(bonn_scenario) -> None:
    bonn_scenario.mode = "rent"
    r = run(bonn_scenario)
    assert r.afa_basis is not None
    assert r.afa_basis.annual_afa > 0


def test_bonn_is_pre_1925_afa_rate(bonn_scenario) -> None:
    """Bonn sample is 1904 → 2.5% AfA, 40-year useful life."""
    bonn_scenario.mode = "rent"
    r = run(bonn_scenario)
    assert r.afa_basis.afa_rate == pytest.approx(0.025)
    assert r.afa_basis.useful_life_years == 40


def test_afa_capped_at_useful_life(bonn_scenario) -> None:
    """Audit v1 [C5]: AfA must stop at the statutory useful life
    (§ 7 Abs. 4 EStG). Bonn is pre-1925 → 40-year life; horizon 50 →
    years 41-50 must carry deduct_afa=0, while years 1-40 carry the
    full annual_afa."""
    bonn_scenario.mode = "rent"
    bonn_scenario.globals.horizon_years = 50
    r = run(bonn_scenario)
    tax = r.tax
    afa_annual = r.afa_basis.annual_afa
    assert r.afa_basis.useful_life_years == 40

    # Years 1-40: full AfA deduction each year.
    assert tax["deduct_afa"].iloc[:40].gt(0).all(), (
        "AfA should be non-zero during useful-life window")
    assert tax["deduct_afa"].iloc[0] == pytest.approx(afa_annual, rel=1e-6)

    # Years 41-50: AfA exhausted.
    assert (tax["deduct_afa"].iloc[40:] == 0).all(), (
        "AfA must be zero past the 40-year useful life")


def test_afa_not_capped_when_horizon_fits(bonn_scenario) -> None:
    """Horizon ≤ useful_life: AfA runs through every year, nothing capped."""
    bonn_scenario.mode = "rent"
    bonn_scenario.globals.horizon_years = 30  # well under Bonn's 40-yr life
    r = run(bonn_scenario)
    assert (r.tax["deduct_afa"] > 0).all()


def test_rent_mode_avoided_rent_is_zero(bonn_scenario) -> None:
    """Rent mode never credits avoided rent, regardless of live-mode field."""
    bonn_scenario.mode = "rent"
    bonn_scenario.live.current_monthly_rent_warm_eur = 1_800
    r = run(bonn_scenario)
    assert "avoided_rent" in r.cashflow.columns
    assert (r.cashflow["avoided_rent"] == 0).all()


def test_live_mode_avoided_rent_zero_when_unset(bonn_scenario) -> None:
    """Live mode keeps the legacy behaviour if the field is left at 0."""
    bonn_scenario.mode = "live"
    bonn_scenario.live.current_monthly_rent_warm_eur = 0.0
    r = run(bonn_scenario)
    assert (r.cashflow["avoided_rent"] == 0).all()


def test_live_mode_credits_avoided_rent_year_one(bonn_scenario) -> None:
    """Year 1 avoided_rent = 12 × monthly (no escalation yet)."""
    bonn_scenario.mode = "live"
    bonn_scenario.live.current_monthly_rent_warm_eur = 1_800
    r = run(bonn_scenario)
    yr1 = r.cashflow.iloc[0]
    assert yr1["avoided_rent"] == pytest.approx(1_800 * 12)


def test_live_mode_avoided_rent_escalates_with_inflation(bonn_scenario) -> None:
    """Avoided rent escalates by cost_inflation_annual, same as op costs."""
    bonn_scenario.mode = "live"
    bonn_scenario.live.current_monthly_rent_warm_eur = 1_000
    bonn_scenario.globals.cost_inflation_annual = 0.02
    r = run(bonn_scenario)
    yr1 = r.cashflow["avoided_rent"].iloc[0]
    yr10 = r.cashflow["avoided_rent"].iloc[9]
    assert yr10 == pytest.approx(yr1 * 1.02 ** 9)


def test_rent_mode_tax_can_go_negative(bonn_scenario) -> None:
    """Early years with high interest + AfA should produce a negative
    tax_owed — that's Verlustverrechnung crediting the salary."""
    bonn_scenario.mode = "rent"
    r = run(bonn_scenario)
    tax = r.tax["tax_owed"]
    # Bonn has year-1 AfA plus Bank interest north of €10k; taxable income
    # lands negative, so tax_owed should be < 0 in the early years.
    assert tax.iloc[0] < 0


def test_loss_offset_scales_with_marginal_rate(bonn_scenario) -> None:
    """Doubling the marginal rate should double the magnitude of the
    year-1 tax credit (losses offset at the marginal rate, linearly)."""
    from copy import deepcopy
    low = deepcopy(bonn_scenario); low.mode = "rent"
    low.globals.marginal_tax_rate = 0.20
    high = deepcopy(bonn_scenario); high.mode = "rent"
    high.globals.marginal_tax_rate = 0.40

    t_low = run(low).tax["tax_owed"].iloc[0]
    t_high = run(high).tax["tax_owed"].iloc[0]
    # Both negative; high magnitude should be 2× low magnitude.
    assert t_high < 0 and t_low < 0
    assert abs(t_high) == pytest.approx(abs(t_low) * 2, rel=1e-6)


# F-P1-12 — extend Verlustverrechnung pin across multiple rates.
@pytest.mark.parametrize("rate", [0.20, 0.30, 0.42, 0.45])
def test_loss_offset_scales_linearly_across_rates(bonn_scenario, rate) -> None:
    """The year-1 tax credit must be exactly `taxable_income × rate`. Pin
    the linear relationship at every realistic marginal rate."""
    from copy import deepcopy
    s = deepcopy(bonn_scenario); s.mode = "rent"
    s.globals.marginal_tax_rate = rate
    r = run(s)
    yr1 = r.tax.iloc[0]
    expected = yr1["taxable_income"] * rate
    assert yr1["tax_owed"] == pytest.approx(expected, rel=1e-9)


# F-P0-1 / F-P1-9 — input validation rejects nonsense scenarios.
@pytest.mark.parametrize("horizon", [0, -1, -50])
def test_horizon_zero_or_negative_raises(bonn_scenario, horizon: int) -> None:
    bonn_scenario.globals.horizon_years = horizon
    with pytest.raises(ValueError, match="horizon_years"):
        run(bonn_scenario)


def test_zero_purchase_price_raises(bonn_scenario) -> None:
    bonn_scenario.property.purchase_price = 0
    with pytest.raises(ValueError, match="purchase_price"):
        run(bonn_scenario)


def test_zero_living_space_raises(bonn_scenario) -> None:
    bonn_scenario.property.living_space_m2 = 0
    with pytest.raises(ValueError, match="living_space_m2"):
        run(bonn_scenario)


def test_zero_household_income_raises(bonn_scenario) -> None:
    bonn_scenario.globals.monthly_household_income = 0
    with pytest.raises(ValueError, match="monthly_household_income"):
        run(bonn_scenario)


# F-P0-5 — pin the 15 % Anschaffungsnaher Aufwand threshold (§ 6 Abs. 1 Nr. 1a).
def _make_anschaffungsnaher_scenario(bonn_scenario, *, capex_cost: float):
    """Bonn variant with one user_capex item in the year of purchase."""
    from copy import deepcopy
    from immokalkul import CapexItem
    s = deepcopy(bonn_scenario)
    s.mode = "rent"
    s.user_capex = [CapexItem(
        name="Bathroom + heating",
        cost_eur=capex_cost,
        year_due=s.globals.today_year + 1,  # within the 3-yr window
        is_capitalized=False,                # claim Erhaltungsaufwand
    )]
    s.auto_schedule_capex = False  # isolate the user item
    return s


def test_anschaffungsnaher_below_threshold_stays_deductible(bonn_scenario) -> None:
    """Capex below 15 % of building value stays Erhaltungsaufwand —
    immediately deductible, no AfA uplift."""
    from copy import deepcopy
    s = _make_anschaffungsnaher_scenario(bonn_scenario, capex_cost=1.0)
    baseline_afa = run(deepcopy(s)._replace_user_capex_with_empty() if hasattr(s, "_replace_user_capex_with_empty") else s).afa_basis.annual_afa
    # Use the explicit baseline: same scenario with empty user_capex.
    s_empty = deepcopy(s); s_empty.user_capex = []
    baseline_afa = run(s_empty).afa_basis.annual_afa

    # Now bump capex to a sub-threshold amount: 5 % of building value.
    bv = run(s_empty).afa_basis.building_value
    s.user_capex[0].cost_eur = bv * 0.05
    r = run(s)
    # AfA basis should NOT include the capex (Erhaltungsaufwand path).
    assert r.afa_basis.annual_afa == pytest.approx(baseline_afa, rel=1e-9)
    # The capex appears as a one-year deductible cost in the tax frame.
    yr_offset = s.user_capex[0].year_due - s.globals.today_year + 1
    deduct_capex = r.tax["deduct_capex"].iloc[yr_offset - 1]
    assert deduct_capex > 0


def test_anschaffungsnaher_above_threshold_reclassifies_to_afa(bonn_scenario) -> None:
    """Capex above 15 % of building value reclassifies as Herstellungs-
    kosten — added to AfA basis, depreciated over useful life, NOT
    immediately deductible."""
    from copy import deepcopy
    s = _make_anschaffungsnaher_scenario(bonn_scenario, capex_cost=1.0)
    s_empty = deepcopy(s); s_empty.user_capex = []
    baseline_afa = run(s_empty).afa_basis.annual_afa
    bv = run(s_empty).afa_basis.building_value

    # Above threshold: 20 % of building value
    s.user_capex[0].cost_eur = bv * 0.20
    r = run(s)
    # AfA increases — capex was uplifted to basis.
    assert r.tax["deduct_afa"].iloc[0] > baseline_afa
    # The capex no longer appears as a one-year immediate deduction.
    yr_offset = s.user_capex[0].year_due - s.globals.today_year + 1
    deduct_capex = r.tax["deduct_capex"].iloc[yr_offset - 1]
    assert deduct_capex == 0


# F-P0-2 / F-P1-11 — building/land split honours real Bodenrichtwert.
def test_building_share_falls_back_to_default_without_brw(bonn_scenario) -> None:
    """No BRW given → property-type prior (0.80 apartment, 0.65 house)."""
    from copy import deepcopy
    from immokalkul.financing import estimate_building_share
    s = deepcopy(bonn_scenario)
    s.property.bodenrichtwert_eur_per_m2 = None
    assert estimate_building_share(s.property) == 0.80  # apartment

    s.property.property_type = "house"
    assert estimate_building_share(s.property) == 0.65


def test_building_share_honours_low_land_share(bonn_scenario) -> None:
    """A modest BRW × plot share gives a high building share — not floored."""
    from copy import deepcopy
    from immokalkul.financing import estimate_building_share
    s = deepcopy(bonn_scenario)
    # Tiny land value: BRW 100 €/m² × 80 m² = 8000 € on a 446k property → 1.8%
    s.property.bodenrichtwert_eur_per_m2 = 100
    s.property.plot_size_m2 = 80
    share = estimate_building_share(s.property)
    assert share == pytest.approx(1 - 8_000 / s.property.purchase_price, abs=1e-4)


def test_building_share_unfloored_when_land_dominates(bonn_scenario) -> None:
    """Bodenrichtwert × plot just under the price → tiny building share —
    pre-fix code floored to 0.75; new code honours the real ~0.06."""
    import warnings
    from copy import deepcopy
    from immokalkul.financing import estimate_building_share
    s = deepcopy(bonn_scenario)
    # Make land 94 % of the price.
    s.property.bodenrichtwert_eur_per_m2 = (s.property.purchase_price * 0.94
                                             / s.property.plot_size_m2)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # we know the warning fires
        share = estimate_building_share(s.property)
    assert share == pytest.approx(0.06, abs=0.01)


def test_building_share_overshoot_floors_at_zero(bonn_scenario) -> None:
    """Land alone > price → land_share clamps to 1, building_share = 0."""
    import warnings
    from copy import deepcopy
    from immokalkul.financing import estimate_building_share
    s = deepcopy(bonn_scenario)
    s.property.bodenrichtwert_eur_per_m2 = (s.property.purchase_price * 2
                                             / s.property.plot_size_m2)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        share = estimate_building_share(s.property)
    assert share == 0.0


# F-P1-10 — clamp negative loan rates with a warning, keep zero rates valid.
def test_zero_rate_amortization_is_linear(bonn_scenario) -> None:
    """At rate=0 each annual payment goes 100 % to principal; the loan
    clears in `principal / (12 × monthly_payment)` years."""
    from copy import deepcopy
    s = deepcopy(bonn_scenario)
    for l in s.financing.loans:
        l.interest_rate = 0.0
    r = run(s)
    interest_cols = [c for c in r.amort.columns if c.endswith("_interest")]
    assert (r.amort[interest_cols].values == 0).all()


def test_negative_rate_clamps_to_zero_with_warning(bonn_scenario) -> None:
    import warnings
    from copy import deepcopy
    s = deepcopy(bonn_scenario)
    bank = next(l for l in s.financing.loans if l.name == "Bank")
    bank.interest_rate = -0.01
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        r = run(s)
    msgs = [str(w.message) for w in caught]
    assert any("negative interest_rate" in m for m in msgs)
    # Behaviour matches a 0 % loan: no interest accrues on the Bank loan.
    assert (r.amort["Bank_interest"] == 0).all()


# F-P2-27 — vacancy reduces rent income but doesn't double-count as a cost.
def test_vacancy_does_not_double_count_in_op_costs(bonn_scenario) -> None:
    """Setting a 2-month vacancy reduces year-1 rent_net by 2/12 of gross
    annual rent, but op_costs must NOT also drop — vacancy already nets
    out of the rent line, so the cashflow loop strips it from costs."""
    from copy import deepcopy
    s_lo = deepcopy(bonn_scenario); s_lo.mode = "rent"
    s_lo.rent.expected_vacancy_months_per_year = 0.0
    s_hi = deepcopy(bonn_scenario); s_hi.mode = "rent"
    s_hi.rent.expected_vacancy_months_per_year = 2.0

    yr1_lo = run(s_lo).cashflow.iloc[0]
    yr1_hi = run(s_hi).cashflow.iloc[0]

    expected_rent_drop = (s_hi.rent.monthly_rent + s_hi.rent.monthly_parking) * 2
    actual_rent_drop = yr1_lo["rent_net"] - yr1_hi["rent_net"]
    assert actual_rent_drop == pytest.approx(expected_rent_drop, rel=1e-6)

    # op_costs must NOT have shifted by the same magnitude — vacancy is
    # excluded from the cost roll-up.
    assert abs(yr1_hi["op_costs"] - yr1_lo["op_costs"]) < 1.0


def test_live_mode_cumulative_lifts_when_rent_is_credited(bonn_scenario) -> None:
    """With avoided rent set, the live-mode cumulative must be materially
    higher than with it at 0 — exactly by the escalated sum of the credit
    (since nothing else in the cashflow changes)."""
    from copy import deepcopy
    s_unset = deepcopy(bonn_scenario)
    s_unset.mode = "live"
    s_unset.live.current_monthly_rent_warm_eur = 0.0

    s_set = deepcopy(bonn_scenario)
    s_set.mode = "live"
    s_set.live.current_monthly_rent_warm_eur = 1_800.0

    r_unset = run(s_unset)
    r_set = run(s_set)

    final_unset = float(r_unset.cashflow["cumulative"].iloc[-1])
    final_set = float(r_set.cashflow["cumulative"].iloc[-1])
    credited = float(r_set.cashflow["avoided_rent"].sum())

    assert credited > 0
    assert final_set == pytest.approx(final_unset + credited, abs=1.0)
