"""Orchestrates a full valuation run from a set of assumptions.

Pure: takes numbers in, returns numbers + DataFrames out. The UI populates
`Assumptions` and renders the results; nothing here touches I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import pandas as pd

from .dcf import ValuationResult, dcf_3stage
from .projection import Projection, project
from .sensitivity import sensitivity_grid


@dataclass
class Assumptions:
    # revenue growth path: years 1 and 2 (usually analyst consensus), then a
    # straight line to the year-5 rate (your view), then the fade in Stage 2
    growth_y1: float = 0.05
    growth_y2: float = 0.05
    growth_y5: float = 0.05
    growth_override: tuple[float, ...] | None = None  # explicit path, e.g. from a segment build
    ebit_margin: float = 0.20
    target_ebit_margin: float | None = None  # None: margin stays at ebit_margin
    tax_rate: float = 0.21
    roic: float = 0.15  # return on capital: sets reinvestment, fades over fade_years
    fade_years: int = 10
    terminal_excess_return: float = 0.0  # RONIC above r kept forever; 0 = moat fully erodes
    terminal_growth: float = 0.025
    discount_rate: float = 0.08  # cost of capital: sets the fair value
    hurdle_rate: float = 0.10    # your required return: a buy test only
    margin_of_safety: float = 0.25
    years: int = 5
    growth_swing: float = 0.03  # bear/bull scenarios: +/- revenue growth
    margin_swing: float = 0.02  # bear/bull scenarios: +/- target EBIT margin
    tail_probability: float = 0.25  # probability of each of bear and bull


    def growth_path(self) -> list[float]:
        if self.growth_override is not None:
            return list(self.growth_override)[: self.years]
        path = [self.growth_y1, self.growth_y2]
        for t in range(3, self.years + 1):
            path.append(self.growth_y2 + (self.growth_y5 - self.growth_y2) * (t - 2) / (self.years - 2))
        return path[: self.years]

    def with_flat_growth(self, g: float) -> "Assumptions":
        return replace(self, growth_y1=g, growth_y2=g, growth_y5=g, growth_override=None)


@dataclass
class ValuationRun:
    projection: Projection
    result: ValuationResult
    sensitivity: pd.DataFrame


def _projection(base_revenue: float, a: Assumptions) -> Projection:
    return project(
        base_revenue=base_revenue,
        revenue_growth=a.growth_path(),
        ebit_margin=a.ebit_margin,
        tax_rate=a.tax_rate,
        roic=a.roic,
        years=a.years,
        target_margin=a.target_ebit_margin,
    )


def _dcf_kwargs(proj: Projection, a: Assumptions, net_debt: float,
                minority_interest: float, shares_diluted: float,
                years_since_fy_end: float) -> dict:
    return dict(
        discount_shift=0.5 + years_since_fy_end,  # mid-year convention + time since FY end
        fade_years=a.fade_years,
        stage1_growth=a.growth_path()[-1],
        terminal_excess_return=a.terminal_excess_return,
        nopat_last=proj.nopat[-1],
        roic_start=a.roic,
        net_debt=net_debt,
        minority_interest=minority_interest,
        shares_diluted=shares_diluted,
    )


def value_per_share(base_revenue: float, a: Assumptions, net_debt: float = 0.0,
                    minority_interest: float = 0.0, shares_diluted: float = 1.0,
                    years_since_fy_end: float = 0.0) -> float:
    proj = _projection(base_revenue, a)
    return dcf_3stage(
        proj.fcff, discount_rate=a.discount_rate, terminal_growth=a.terminal_growth,
        **_dcf_kwargs(proj, a, net_debt, minority_interest, shares_diluted, years_since_fy_end),
    ).equity_value_per_share


def run_valuation(
    base_revenue: float,
    assumptions: Assumptions,
    net_debt: float = 0.0,
    minority_interest: float = 0.0,
    shares_diluted: float = 1.0,
    years_since_fy_end: float = 0.0,
) -> ValuationRun:
    """Project Stage 1, run the 3-stage DCF, and build the sensitivity grid."""
    a = assumptions
    proj = _projection(base_revenue, a)
    kwargs = _dcf_kwargs(proj, a, net_debt, minority_interest, shares_diluted, years_since_fy_end)
    result = dcf_3stage(proj.fcff, discount_rate=a.discount_rate,
                        terminal_growth=a.terminal_growth, **kwargs)
    grid = sensitivity_grid(
        proj.fcff,
        rate_range=(a.discount_rate - 0.02, a.discount_rate + 0.02, 0.01),
        growth_range=(a.terminal_growth - 0.01, a.terminal_growth + 0.01, 0.005),
        **kwargs,
    )
    return ValuationRun(projection=proj, result=result, sensitivity=grid)
