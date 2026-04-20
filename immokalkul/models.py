"""
Domain models. Pure data + light validation. No business logic here.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Literal, Optional
from datetime import date

from .rules_de import Bundesland

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
    bundesland: Bundesland = Bundesland.NW  # drives Grunderwerbsteuer rate when
                                           # `grunderwerbsteuer_rate` override
                                           # is unset. Default NRW preserves
                                           # back-compat with existing YAMLs.
    grunderwerbsteuer_rate: Optional[float] = None  # per-scenario override —
                                           # beats the state lookup. None →
                                           # use rules_de.GRUNDERWERBSTEUER_RATES
                                           # for the selected Bundesland.
    notes: str = ""
    listing_url: str = ""

    def __post_init__(self) -> None:
        if self.grunderwerbsteuer_rate is not None and not (
                0 <= self.grunderwerbsteuer_rate <= 0.15):
            raise ValueError(
                f"Property {self.name!r}: grunderwerbsteuer_rate must be in "
                f"[0, 0.15], got {self.grunderwerbsteuer_rate}")

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
    monthly_payment: float                 # EUR/month — for Annuität this is the
                                           # constant annuity; for fixed-payment
                                           # loans it's the fixed payment; for
                                           # adaptive loans it's the MINIMUM.
    is_annuity: bool = True                # German Annuitätendarlehen?
                                           # If False, it's a fixed-payment loan
                                           # (LBS Bausparvertrag, family loan, …)
    is_adaptive: bool = False              # if True, this loan absorbs freed-up
                                           # debt-service capacity once other
                                           # loans clear (uses debt_budget_monthly
                                           # as the ceiling). Only meaningful on
                                           # non-annuity loans.
    annual_extra_repayment_eur: float = 0.0  # lump-sum Sondertilgung applied at
                                           # year-end after regular payment.
                                           # Contract-typical: €5k-€25k/yr.
                                           # Clamped to remaining balance.
    sondertilgung_pct_of_original_principal: float = 0.0  # German contract clause
                                           # "N % Sondertilgungsrecht p.a." — fraction
                                           # of ORIGINAL principal (not current
                                           # balance) the borrower may repay extra
                                           # each year. Typical: 5 % (0.05).
                                           # Stored as a decimal.
    fixed_term_years: int = 0              # Zinsbindung length. Purely informational
                                           # — the engine holds the rate constant
                                           # through the full horizon (the post-
                                           # Prolongation rate is a future market
                                           # rate nobody knows today). Surfaced in
                                           # the Debt tab so the user sees when the
                                           # Prolongationsangebot is due.

    def __post_init__(self) -> None:
        if self.annual_extra_repayment_eur < 0:
            raise ValueError(
                f"Loan {self.name!r}: annual_extra_repayment_eur must be "
                f"≥ 0, got {self.annual_extra_repayment_eur}")
        if not 0 <= self.sondertilgung_pct_of_original_principal <= 1:
            raise ValueError(
                f"Loan {self.name!r}: sondertilgung_pct_of_original_principal "
                f"must be in [0, 1], got "
                f"{self.sondertilgung_pct_of_original_principal}")
        if self.fixed_term_years < 0:
            raise ValueError(
                f"Loan {self.name!r}: fixed_term_years must be ≥ 0, got "
                f"{self.fixed_term_years}")


@dataclass
class Financing:
    """Total financing structure for a property."""
    initial_capital: float                 # cash deployed at closing (incl. any
                                           # Bauspar savings and family loan
                                           # proceeds used at closing)
    loans: list[Loan] = field(default_factory=list)
    debt_budget_monthly: float = 1745.0    # ceiling for total monthly debt
                                           # service; only used when at least one
                                           # loan has is_adaptive=True
    monthly_total_housing_budget_eur: float = 0.0   # optional ceiling on total
                                           # monthly housing spend (loan + op
                                           # costs — Hausgeld, insurance,
                                           # Grundsteuer, maintenance). Pure
                                           # affordability check — does NOT
                                           # drive the engine. 0 = unset / no
                                           # check.
    notary_pct: Optional[float] = None     # override for the Notar (GNotKG)
                                           # rate as a fraction of price. None
                                           # → fall back to rules_de.NOTARY_FEE
                                           # (~1.5 %).
    grundbuch_pct: Optional[float] = None  # override for the Grundbuch (land-
                                           # registry) rate. None → fall back
                                           # to rules_de.GRUNDBUCH_FEE (~0.5 %).


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

    def __post_init__(self) -> None:
        if self.cost_eur < 0:
            raise ValueError(
                f"CapexItem {self.name!r}: cost_eur must be ≥ 0, got "
                f"{self.cost_eur}")
        if self.year_due < 1900:
            raise ValueError(
                f"CapexItem {self.name!r}: year_due must be ≥ 1900, got "
                f"{self.year_due}")


@dataclass
class RentParameters:
    """Rent-mode-specific inputs."""
    monthly_rent: float                    # Kaltmiete
    monthly_parking: float = 0.0
    annual_rent_escalation: float = 0.02   # German Mietspiegel typical
    expected_vacancy_months_per_year: float = 2.0
    landlord_legal_insurance_annual: float = 300.0
    has_property_manager: bool = False     # adds 5-8% mgmt fee
    property_manager_pct_of_rent: float = 0.06


@dataclass
class LiveParameters:
    """Live-mode-specific inputs."""
    people_in_household: int = 2
    large_appliances: int = 4
    needs_kitchen_replacement: bool = False  # flag for capex
    current_monthly_rent_warm_eur: float = 0.0  # what the household currently
                                           # pays to rent, all-inclusive (warm
                                           # rent + electricity + internet +
                                           # everything). 0 = not set. Used in
                                           # Summary as the opportunity-cost
                                           # comparison for buying-to-live.


@dataclass
class CostInputs:
    """Operating cost rates that apply in both modes (with mode flags)."""
    gas_price_eur_per_kwh: float = 0.11
    electricity_price_eur_per_kwh: float = 0.35
    grundsteuer_rate_of_price: float = 0.002          # legacy proxy; kept for
                                                       # back-compat. Real engine
                                                       # now uses Grundstückswert
                                                       # × land_rate (post-2025
                                                       # Grundsteuerreform).
    grundsteuer_land_rate: float = 0.0034             # ~0.34 % of Grundstücks-
                                                       # wert ≈ Bodenrichtwert ×
                                                       # plot. Bundesmodell
                                                       # post-2025 reform; range
                                                       # 0.20–0.50 % across
                                                       # Bundesländer / Hebesätze.
    building_insurance_eur_per_m2_year: float = 4.0
    liability_insurance_annual: float = 150.0
    administration_monthly: float = 30.0
    municipal_charges_eur_per_m2_month: float = 0.60
    hausgeld_monthly_for_rent: float = 375.0          # actual WEG fee (rent
                                                       # mode only)
    hausgeld_reserve_share: float = 0.40              # share of Hausgeld that
                                                       # funds Erhaltungsrück-
                                                       # lage (NOT deductible
                                                       # until spent per § 19
                                                       # WEG). 0.30–0.50
                                                       # typical; remainder is
                                                       # the deductible operating
                                                       # portion.


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
