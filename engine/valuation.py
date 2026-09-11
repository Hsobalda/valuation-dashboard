"""Orchestrates a full valuation run from a set of assumptions.

Pure: takes numbers in, returns numbers + DataFrames out. The UI populates
`Assumptions` and renders the results; nothing here touches I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .dcf import ValuationResult, dcf_3stage
from .projection import project_fcff
from .sensitivity import sensitivity_grid


@dataclass
class Assumptions:
    revenue_growth: float = 0.05
    ebit_margin: float = 0.20
    tax_rate: float = 0.21
    da_pct_revenue: float = 0.05
    capex_pct_revenue: float = 0.05
    nwc_pct_revenue: float = 0.0
    fade_years: int = 10
    terminal_growth: float = 0.025
    wacc: float = 0.08
    margin_of_safety: float = 0.25
    years: int = 5


@dataclass
class ValuationRun:
    fcff: list[float]
    result: ValuationResult
    sensitivity: pd.DataFrame


def run_valuation(
    base_revenue: float,
    assumptions: Assumptions,
    net_debt: float = 0.0,
    minority_interest: float = 0.0,
    cash: float = 0.0,
    shares_diluted: float = 1.0,
) -> ValuationRun:
    """Project FCFF, run the 3-stage DCF, and build the sensitivity grid."""
    fcff = project_fcff(
        base_revenue=base_revenue,
        revenue_growth=assumptions.revenue_growth,
        ebit_margin=assumptions.ebit_margin,
        tax_rate=assumptions.tax_rate,
        da_pct_revenue=assumptions.da_pct_revenue,
        capex_pct_revenue=assumptions.capex_pct_revenue,
        nwc_pct_revenue=assumptions.nwc_pct_revenue,
        years=assumptions.years,
    )

    bridge = dict(
        net_debt=net_debt,
        minority_interest=minority_interest,
        cash=cash,
        shares_diluted=shares_diluted,
    )
    result = dcf_3stage(
        fcff,
        wacc=assumptions.wacc,
        fade_years=assumptions.fade_years,
        terminal_growth=assumptions.terminal_growth,
        stage1_growth=assumptions.revenue_growth,
        **bridge,
    )

    grid = sensitivity_grid(
        fcff,
        wacc_range=(assumptions.wacc - 0.02, assumptions.wacc + 0.02, 0.01),
        growth_range=(assumptions.terminal_growth - 0.01, assumptions.terminal_growth + 0.01, 0.005),
        fade_years=assumptions.fade_years,
        **bridge,
    )
    return ValuationRun(fcff=fcff, result=result, sensitivity=grid)
