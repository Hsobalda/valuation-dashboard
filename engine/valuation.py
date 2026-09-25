"""Orchestrates a full valuation run from a set of assumptions.

Pure: takes numbers in, returns numbers + DataFrames out. The UI populates
`Assumptions` and renders the results; nothing here touches I/O.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .dcf import ValuationResult, dcf_3stage
from .projection import Projection, project
from .sensitivity import sensitivity_grid


@dataclass
class Assumptions:
    revenue_growth: float = 0.05
    ebit_margin: float = 0.20
    target_ebit_margin: float | None = None  # None: margin stays at ebit_margin
    tax_rate: float = 0.21
    da_pct_revenue: float = 0.05
    capex_pct_revenue: float = 0.05
    nwc_pct_revenue: float = 0.0
    roic: float = 0.15  # today's return on invested capital, faded over fade_years
    fade_years: int = 10
    terminal_growth: float = 0.025
    discount_rate: float = 0.10
    margin_of_safety: float = 0.25
    years: int = 5


@dataclass
class ValuationRun:
    projection: Projection
    result: ValuationResult
    sensitivity: pd.DataFrame


def _projection(base_revenue: float, a: Assumptions) -> Projection:
    return project(
        base_revenue=base_revenue,
        revenue_growth=a.revenue_growth,
        ebit_margin=a.ebit_margin,
        tax_rate=a.tax_rate,
        da_pct_revenue=a.da_pct_revenue,
        capex_pct_revenue=a.capex_pct_revenue,
        nwc_pct_revenue=a.nwc_pct_revenue,
        years=a.years,
        target_margin=a.target_ebit_margin,
    )


def _dcf_kwargs(proj: Projection, a: Assumptions, net_debt: float,
                minority_interest: float, shares_diluted: float) -> dict:
    return dict(
        fade_years=a.fade_years,
        stage1_growth=a.revenue_growth,
        nopat_last=proj.nopat[-1],
        roic_start=a.roic,
        net_debt=net_debt,
        minority_interest=minority_interest,
        shares_diluted=shares_diluted,
    )


def value_per_share(base_revenue: float, a: Assumptions, net_debt: float = 0.0,
                    minority_interest: float = 0.0, shares_diluted: float = 1.0) -> float:
    proj = _projection(base_revenue, a)
    return dcf_3stage(
        proj.fcff, discount_rate=a.discount_rate, terminal_growth=a.terminal_growth,
        **_dcf_kwargs(proj, a, net_debt, minority_interest, shares_diluted),
    ).equity_value_per_share


def run_valuation(
    base_revenue: float,
    assumptions: Assumptions,
    net_debt: float = 0.0,
    minority_interest: float = 0.0,
    shares_diluted: float = 1.0,
) -> ValuationRun:
    """Project Stage 1, run the 3-stage DCF, and build the sensitivity grid."""
    a = assumptions
    proj = _projection(base_revenue, a)
    kwargs = _dcf_kwargs(proj, a, net_debt, minority_interest, shares_diluted)
    result = dcf_3stage(proj.fcff, discount_rate=a.discount_rate,
                        terminal_growth=a.terminal_growth, **kwargs)
    grid = sensitivity_grid(
        proj.fcff,
        rate_range=(a.discount_rate - 0.02, a.discount_rate + 0.02, 0.01),
        growth_range=(a.terminal_growth - 0.01, a.terminal_growth + 0.01, 0.005),
        **kwargs,
    )
    return ValuationRun(projection=proj, result=result, sensitivity=grid)
