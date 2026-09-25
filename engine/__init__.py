"""Valuation engine -- pure math, zero I/O.

Nothing in this package may import from data/, brief/, ui/, streamlit, or
yfinance, so every calculation can be tested in isolation.
"""

from .dcf import ValuationResult, dcf_3stage
from .projection import Projection, project
from .reverse import implied_return, implied_revenue_growth
from .scenarios import Scenario, ScenarioRun, run_scenarios
from .quality import (
    fcf_conversion_series,
    gross_margin,
    margin_stability,
    net_margin,
    operating_margin,
    roic_series,
)
from .sensitivity import sensitivity_grid
from .valuation import Assumptions, ValuationRun, run_valuation, value_per_share
from .wacc import cost_of_equity, wacc
from .comps import CompsResult, comps_analysis

__all__ = [
    "Assumptions",
    "CompsResult",
    "ValuationResult",
    "ValuationRun",
    "cost_of_equity",
    "wacc",
    "Projection",
    "project",
    "value_per_share",
    "implied_revenue_growth",
    "implied_return",
    "Scenario",
    "ScenarioRun",
    "run_scenarios",
    "dcf_3stage",
    "sensitivity_grid",
    "run_valuation",
    "comps_analysis",
    "roic_series",
    "margin_stability",
    "fcf_conversion_series",
    "gross_margin",
    "operating_margin",
    "net_margin",
]
