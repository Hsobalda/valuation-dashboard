"""Stage-1 projection. Pure, deterministic, no I/O."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Projection:
    revenue: list[float]
    growth: list[float]
    ebit_margin: list[float]
    nopat: list[float]
    reinvestment: list[float]  # net capex + change in working capital
    fcff: list[float]


def project(
    base_revenue: float,
    revenue_growth: float | list[float],
    ebit_margin: float,
    tax_rate: float,
    roic: float,
    years: int = 5,
    target_margin: float | None = None,
) -> Projection:
    """Project revenue, NOPAT, reinvestment and unlevered free cash flow (FCFF).

    Growth has to be paid for: growing at g with a return of `roic` on new
    capital means reinvesting g / roic of NOPAT (net capex plus working
    capital), so FCFF = NOPAT * (1 - g / roic). This is the same rule Stages 2
    and 3 of the DCF use, so the whole model agrees on what growth costs.

    `revenue_growth` is one rate for every year or a list with one rate per
    year. The EBIT margin moves in a straight line from `ebit_margin` (year 0)
    to `target_margin` by the final year; with no target it stays flat.
    """
    if roic <= 0:
        raise ValueError("ROIC must be positive")
    if target_margin is None:
        target_margin = ebit_margin
    growth = [revenue_growth] * years if isinstance(revenue_growth, (int, float)) else list(revenue_growth)
    years = len(growth)
    out = Projection([], [], [], [], [], [])
    revenue = base_revenue
    for t, g in enumerate(growth, start=1):
        revenue = revenue * (1.0 + g)
        margin = ebit_margin + (target_margin - ebit_margin) * t / years
        nopat = revenue * margin * (1.0 - tax_rate)
        reinvestment = nopat * g / roic
        out.revenue.append(revenue)
        out.growth.append(g)
        out.ebit_margin.append(margin)
        out.nopat.append(nopat)
        out.reinvestment.append(reinvestment)
        out.fcff.append(nopat - reinvestment)
    return out
