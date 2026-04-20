"""Tests for the auto capex scheduler — in particular the new scope-aware
apartment WEG share that prevents the big lump-sum over-count for
Gemeinschaftseigentum items."""
from __future__ import annotations

import pytest

from immokalkul import CapexItem, rules_de
from immokalkul.capex import auto_schedule, estimate_component_cost

from .conftest import make_scenario


def test_capexitem_validates_inputs() -> None:
    """Data-level validator — blocks bad YAMLs / test fixtures loudly
    instead of letting NaN / negative years slip into the engine."""
    # Happy path.
    item = CapexItem(name="Roof", cost_eur=20_000, year_due=2030)
    assert item.name == "Roof"

    # Zero cost is fine (placeholder capex pinned to a year).
    CapexItem(name="Placeholder", cost_eur=0, year_due=2030)

    # Negative cost → ValueError.
    with pytest.raises(ValueError, match="cost_eur"):
        CapexItem(name="Bad", cost_eur=-100, year_due=2030)

    # Year < 1900 (e.g. 0 from NaN coercion) → ValueError.
    with pytest.raises(ValueError, match="year_due"):
        CapexItem(name="Bad", cost_eur=5_000, year_due=0)


def _heating_component():
    for c in rules_de.COMPONENTS:
        if c.name.startswith("Heating"):
            return c
    raise AssertionError("heating component missing")


def _kitchen_component():
    for c in rules_de.COMPONENTS:
        if c.name.startswith("Kitchen"):
            return c
    raise AssertionError("kitchen component missing")


def test_heating_is_we_building() -> None:
    """Heating is Gemeinschaftseigentum in a Mehrfamilienhaus — flagged so."""
    assert _heating_component().scope == "we_building"


def test_kitchen_is_se_individual() -> None:
    """Kitchen is always individual — Sondereigentum."""
    assert _kitchen_component().scope == "se_individual"


def test_apartment_heating_cost_is_weg_share() -> None:
    """Apartment heating cost = WEG_SHARE_APARTMENT × full-boiler midpoint."""
    s = make_scenario(price=400_000)  # defaults to apartment
    heating = _heating_component()
    full_midpoint = (heating.cost_low + heating.cost_high) / 2
    est = estimate_component_cost(heating, s.property)
    assert est == pytest.approx(full_midpoint * rules_de.WEG_SHARE_APARTMENT)


def test_house_heating_cost_is_full() -> None:
    """Freestanding house pays the full boiler cost."""
    s = make_scenario(price=400_000)
    s.property.property_type = "house"
    heating = _heating_component()
    full_midpoint = (heating.cost_low + heating.cost_high) / 2
    est = estimate_component_cost(heating, s.property)
    assert est == pytest.approx(full_midpoint)


def test_kitchen_cost_same_apartment_or_house() -> None:
    """Kitchen is individual — no apartment discount."""
    s_ap = make_scenario(price=400_000)
    s_ho = make_scenario(price=400_000)
    s_ho.property.property_type = "house"
    kitchen = _kitchen_component()
    assert estimate_component_cost(kitchen, s_ap.property) \
        == pytest.approx(estimate_component_cost(kitchen, s_ho.property))


def test_auto_schedule_preserves_lifetime_for_reserve_line(bonn_scenario) -> None:
    """Capex tab's smoothed-reserve line reads lifetime_years off each
    ComponentSchedule; the auto_schedule must populate it from the source
    Component."""
    schedule = auto_schedule(bonn_scenario.property, 2026, 50)
    assert schedule, "expected auto-scheduled items for a 1904 Altbau"
    for s in schedule:
        assert s.lifetime_years > 0, f"{s.component_name} is missing lifetime"
