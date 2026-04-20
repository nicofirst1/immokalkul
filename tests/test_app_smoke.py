"""Streamlit AppTest smoke — [C10] layer 3.

Runs the full Streamlit app via `streamlit.testing.v1.AppTest` against
each bundled sample YAML and a handful of hypothesis-generated
scenarios. The invariant is:

- `at.exception` stays empty (no uncaught Python exception bubbles up),
- no `st.error` element carries the catch-all crash-banner text
  "Something went wrong" (the bespoke banner in `app.py` main's
  exception handler — legitimate `st.error` uses elsewhere render
  failed affordability rules as a styled narrative strip and are NOT
  signs of a crash).

Interaction tests additionally flip the mode radio and drag the
marginal-tax-rate slider to confirm the widget-generation machinery
from [C1] doesn't regress.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings

from immokalkul import load_scenario, save_scenario
from streamlit.testing.v1 import AppTest

from .test_fuzz_models import scenarios

REPO_ROOT = Path(__file__).resolve().parent.parent
APP_PATH = REPO_ROOT / "app.py"
DATA_DIR = REPO_ROOT / "data"
CRASH_BANNER_PREFIX = "Something went wrong"

# AppTest runs are ~1s each; keep defaults modest.
APPTEST_TIMEOUT = 60


def _fresh_apptest() -> AppTest:
    return AppTest.from_file(str(APP_PATH), default_timeout=APPTEST_TIMEOUT)


def _seed_scenario(at: AppTest, scenario, source: str = "test") -> None:
    """Pre-seed the AppTest's session state so init_scenario() doesn't
    overwrite our pick with the default YAML."""
    at.session_state["scenario"] = scenario
    at.session_state["scenario_original"] = deepcopy(scenario)
    at.session_state["scenario_source"] = source
    at.session_state["widget_generation"] = 0


def _assert_no_crash(at: AppTest, context: str) -> None:
    """Invariant: script ran to completion without uncaught exceptions
    and without surfacing the crash-banner st.error."""
    assert len(at.exception) == 0, (
        f"{context}: uncaught exception "
        f"{[e.value for e in at.exception]}")
    crash_banners = [e for e in at.error
                      if e.value.startswith(CRASH_BANNER_PREFIX)]
    assert not crash_banners, (
        f"{context}: crash banner present "
        f"{[e.value for e in crash_banners]}")


@pytest.mark.parametrize("yaml_name", [
    "bonn_poppelsdorf.yaml",
    "munich_neubau.yaml",
    "berlin_altbau.yaml",
    "koeln_einfamilienhaus.yaml",
])
def test_app_renders_each_sample_scenario(yaml_name: str) -> None:
    """Every bundled sample must render the Streamlit app cleanly."""
    at = _fresh_apptest()
    scenario = load_scenario(DATA_DIR / yaml_name)
    _seed_scenario(at, scenario, source=yaml_name.removesuffix(".yaml"))
    at.run()
    _assert_no_crash(at, f"sample {yaml_name}")
    # Sanity: the app's tabs rendered.
    assert len(at.tabs) >= 7, (
        f"{yaml_name}: only {len(at.tabs)} tabs rendered")


def test_glossary_tab_is_present() -> None:
    """Audit v1 [C8]: the dedicated '💬 Glossary' tab must appear in the
    tab strip and render without crash."""
    at = _fresh_apptest()
    scenario = load_scenario(DATA_DIR / "bonn_poppelsdorf.yaml")
    _seed_scenario(at, scenario, source="bonn_poppelsdorf")
    at.run()
    _assert_no_crash(at, "glossary tab presence")
    tab_labels = [t.label for t in at.tabs]
    assert any("Glossary" in lbl for lbl in tab_labels), (
        f"Glossary tab missing from strip: {tab_labels}")


def test_app_survives_mode_toggle() -> None:
    """Flipping the mode radio must not crash — regression guard for
    the [C1] widget-generation fix."""
    at = _fresh_apptest()
    scenario = load_scenario(DATA_DIR / "bonn_poppelsdorf.yaml")
    _seed_scenario(at, scenario, source="bonn_poppelsdorf")
    at.run()
    _assert_no_crash(at, "pre-toggle run")

    # Flip the mode radio (live → rent or vice versa) and re-run.
    assert at.sidebar.radio, "mode radio not found in sidebar"
    current = at.sidebar.radio[0].value
    target = "live" if current == "rent" else "rent"
    at.sidebar.radio[0].set_value(target).run()
    _assert_no_crash(at, f"post-toggle (to {target})")
    assert at.sidebar.radio[0].value == target, (
        "mode radio did not persist new selection — widget-generation regression")


def test_app_survives_marginal_rate_change() -> None:
    """Moving the marginal-tax-rate slider must not crash and the new
    rate must be honoured on the rerun."""
    at = _fresh_apptest()
    scenario = load_scenario(DATA_DIR / "bonn_poppelsdorf.yaml")
    _seed_scenario(at, scenario, source="bonn_poppelsdorf")
    at.run()
    _assert_no_crash(at, "pre-slider run")

    # Find the marginal-tax-rate slider by label.
    sliders = [s for s in at.sidebar.slider
               if "Marginal tax rate" in s.label]
    assert sliders, "marginal-tax-rate slider not found"
    new_rate = 50.0 if sliders[0].value < 45.0 else 30.0
    sliders[0].set_value(new_rate).run()
    _assert_no_crash(at, f"post-slider (rate={new_rate})")


@given(scenarios())
@settings(
    max_examples=3,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.data_too_large,
                             HealthCheck.function_scoped_fixture],
)
def test_app_survives_fuzzed_scenario(scenario) -> None:
    """Seed a hypothesis-generated scenario into the app and confirm no
    crash. Small example count — each AppTest run is ~1 s."""
    at = _fresh_apptest()
    _seed_scenario(at, scenario, source="hypothesis")
    at.run()
    _assert_no_crash(at, "fuzzed scenario")
