"""immokalkul — German property finance modeling for live vs. rent decisions."""
from .models import (Property, Loan, Financing, CapexItem, RentParameters,
                      LiveParameters, CostInputs, GlobalParameters, Scenario)
from .cashflow import run, ScenarioResult
from .io import load_scenario, save_scenario
from .affordability import compute_affordability
from . import rules_de

__all__ = [
    "Property", "Loan", "Financing", "CapexItem", "RentParameters",
    "LiveParameters", "CostInputs", "GlobalParameters", "Scenario",
    "run", "ScenarioResult", "load_scenario", "save_scenario",
    "compute_affordability", "rules_de",
]
