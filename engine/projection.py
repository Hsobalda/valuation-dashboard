"""Stage-1 projection. Pure, deterministic, no I/O."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Projection:
    revenue: list[float]
    ebit_margin: list[float]
    nopat: list[float]
    reinvestment: list[float]  # net capex + change in working capital
    fcff: list[float]


def project(
    base_revenue: float,
    revenue_growth: float,
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

    The EBIT margin moves in a straight line from `ebit_margin` (year 0) to
    `target_margin` by the final year; with no target it stays flat.
    """
    if roic <= 0:
        raise ValueError("ROIC must be positive")
    if target_margin is None:
        target_margin = ebit_margin
    out = Projection([], [], [], [], [])
    revenue = base_revenue
    for t in range(1, years + 1):
        revenue = revenue * (1.0 + revenue_growth)
        margin = ebit_margin + (target_margin - ebit_margin) * t / years
        nopat = revenue * margin * (1.0 - tax_rate)
        reinvestment = nopat * revenue_growth / roic
        out.revenue.append(revenue)
        out.ebit_margin.append(margin)
        out.nopat.append(nopat)
        out.reinvestment.append(reinvestment)
        out.fcff.append(nopat - reinvestment)
    return out
