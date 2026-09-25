"""Stage-1 projection. Pure, deterministic, no I/O."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Projection:
    revenue: list[float]
    nopat: list[float]
    fcff: list[float]


def project(
    base_revenue: float,
    revenue_growth: float,
    ebit_margin: float,
    tax_rate: float,
    da_pct_revenue: float,
    capex_pct_revenue: float,
    nwc_pct_revenue: float,
    years: int = 5,
    target_margin: float | None = None,
) -> Projection:
    """Project revenue, NOPAT and unlevered free cash flow (FCFF) for `years` years.

    FCFF = EBIT * (1 - tax) + D&A - CapEx - change in net working capital, with
    each driver a % of revenue. The EBIT margin moves in a straight line from
    `ebit_margin` (year 0) to `target_margin` by the final year, so a margin
    that is temporarily high or low can revert to a normal level; with no target
    it stays flat. The change in NWC is driven by the change in revenue.
    """
    if target_margin is None:
        target_margin = ebit_margin
    out = Projection([], [], [])
    prev_revenue = revenue = base_revenue
    for t in range(1, years + 1):
        revenue = revenue * (1.0 + revenue_growth)
        margin = ebit_margin + (target_margin - ebit_margin) * t / years
        nopat = revenue * margin * (1.0 - tax_rate)
        da = revenue * da_pct_revenue
        capex = revenue * capex_pct_revenue
        delta_nwc = (revenue - prev_revenue) * nwc_pct_revenue
        out.revenue.append(revenue)
        out.nopat.append(nopat)
        out.fcff.append(nopat + da - capex - delta_nwc)
        prev_revenue = revenue
    return out
