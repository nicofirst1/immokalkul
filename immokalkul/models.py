"""
Domain models. Pure data + light validation. No business logic here.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional
from datetime import date

Mode = Literal["live", "rent"]
PropertyType = Literal["apartment", "house"]
HeatingType = Literal["gas", "oil", "heat_pump", "district", "electric", "wood"]


@dataclass
class Property:
    """Physical & legal facts about the property. Independent of how you finance
    or use it."""
    name: str
    purchase_price: float                  # EUR, the Kaufpreis on the contract
    living_space_m2: float                 # Wohnfläche
    plot_size_m2: float                    # Grundstücksgröße (full plot for a house;
                                           # equal to living for a pure apartment)
    year_built: int
    year_last_major_renovation: Optional[int] = None  # if Kernsanierung happened
    property_type: PropertyType = "apartment"
    heating_type: HeatingType = "gas"
    energy_demand_kwh_per_m2_year: float = 138.0  # from Energieausweis
    has_elevator: bool = False
    bodenrichtwert_eur_per_m2: Optional[float] = None  # if known; else estimated
    is_denkmal: bool = False               # listed building (special AfA rules)
    notes: str = ""
    listing_url: str = ""

    def effective_renovation_age_years(self, today_year: int) -> int:
        """Years since last major renovation (or original build, if none)."""
        ref = self.year_last_major_renovation or self.year_built
        return max(0, today_year - ref)

    def building_age_years(self, today_year: int) -> int:
        return max(0, today_year - self.year_built)


@dataclass
class Loan:
    """One financing tranche."""
    name: str
    principal: float                       # EUR borrowed
    interest_rate: float                   # decimal annual rate (e.g. 0.034)
    monthly_payment: float                 # EUR/month — for Annuität, this is
                                           # principal*(r+t)/12 at year 1
    is_annuity: bool = True                # German Annuitätendarlehen?
                                           # If False, it's a fixed-payment loan
                                           # like LBS Bausparvertrag or Mamma.


@dataclass
class Financing:
    """Total financing structure for a property."""
    initial_capital: float                 # cash deployed at closing (incl. LBS
                                           # savings & Mamma proceeds)
    loans: list[Loan] = field(default_factory=list)
    adaptive_mamma: bool = True            # if True, Mamma payment scales up
                                           # once Bank/LBS clear (uses budget below)
    debt_budget_monthly: float = 1745.0    # ceiling for total monthly debt service
                                           # when adaptive Mamma is on


@dataclass
class CapexItem:
    """A scheduled major renovation. Either based on age (component lifecycle)
    or user-specified."""
    name: str
    cost_eur: float
    year_due: int                          # absolute year (e.g. 2030)
    is_capitalized: bool = False           # True = Anschaffungsnaher Aufwand or
                                           # Herstellungskosten → adds to AfA basis
                                           # False = Erhaltungsaufwand → immediately
                                           # deductible as Werbungskosten


@dataclass
class RentParameters:
    """Rent-mode-specific inputs."""
    monthly_rent: float                    # Kaltmiete
    monthly_parking: float = 0.0
    annual_rent_escalation: float = 0.02   # German Mietspiegel typical
    expected_vacancy_months_per_year: float = 0.25
    landlord_legal_insurance_annual: float = 300.0
    has_property_manager: bool = False     # adds 5-8% mgmt fee
    property_manager_pct_of_rent: float = 0.06


@dataclass
class LiveParameters:
    """Live-mode-specific inputs."""
    people_in_household: int = 2
    large_appliances: int = 4
    needs_kitchen_replacement: bool = False  # flag for capex


@dataclass
class CostInputs:
    """Operating cost rates that apply in both modes (with mode flags)."""
    gas_price_eur_per_kwh: float = 0.11
    electricity_price_eur_per_kwh: float = 0.35
    grundsteuer_rate_of_price: float = 0.002
    building_insurance_eur_per_m2_year: float = 4.0
    liability_insurance_annual: float = 150.0
    administration_monthly: float = 30.0
    municipal_charges_eur_per_m2_month: float = 0.60
    hausgeld_monthly_for_rent: float = 375.0  # actual WEG fee (rent mode only)


@dataclass
class GlobalParameters:
    """Top-level economic assumptions."""
    monthly_household_income: float = 6000.0
    additional_monthly_savings: float = 500.0
    cost_inflation_annual: float = 0.02       # operating costs escalate
    marginal_tax_rate: float = 0.38           # Grenzsteuersatz on rental income
    horizon_years: int = 50
    today_year: int = 2026                    # used for capex scheduling


@dataclass
class Scenario:
    """Everything together for one analysis run."""
    mode: Mode
    property: Property
    financing: Financing
    costs: CostInputs
    rent: RentParameters
    live: LiveParameters
    globals: GlobalParameters
    user_capex: list[CapexItem] = field(default_factory=list)  # user-specified
                                           # one-off renovations on top of
                                           # auto-scheduled component capex
    auto_schedule_capex: bool = True       # if True, capex.py generates a
                                           # schedule from component lifecycles
