"""Reverse DCF: the revenue growth the current share price implies."""

from __future__ import annotations

from dataclasses import replace

from .dcf import dcf_3stage
from .projection import project_fcff
from .valuation import Assumptions


def _value_per_share(growth: float, base_revenue: float, a: Assumptions,
                     net_debt: float, minority_interest: float,
                     shares_diluted: float) -> float:
    a = replace(a, revenue_growth=growth)
    fcff = project_fcff(
        base_revenue=base_revenue, revenue_growth=a.revenue_growth,
        ebit_margin=a.ebit_margin, tax_rate=a.tax_rate,
        da_pct_revenue=a.da_pct_revenue, capex_pct_revenue=a.capex_pct_revenue,
        nwc_pct_revenue=a.nwc_pct_revenue, years=a.years,
    )
    return dcf_3stage(
        fcff, discount_rate=a.discount_rate, fade_years=a.fade_years,
        terminal_growth=a.terminal_growth, net_debt=net_debt,
        minority_interest=minority_interest, shares_diluted=shares_diluted,
        stage1_growth=growth,
    ).equity_value_per_share


def implied_revenue_growth(
    price: float,
    base_revenue: float,
    assumptions: Assumptions,
    net_debt: float = 0.0,
    minority_interest: float = 0.0,
    shares_diluted: float = 1.0,
    low: float = -0.10,
    high: float = 0.40,
) -> float | None:
    """Stage-1 revenue growth at which DCF value equals `price`, holding every
    other assumption fixed. Returns None if the price can't be reached within
    [low, high] growth, i.e. the market is pricing in something outside that range.
    """
    def gap(g: float) -> float:
        return _value_per_share(g, base_revenue, assumptions, net_debt,
                                minority_interest, shares_diluted) - price

    gap_low, gap_high = gap(low), gap(high)
    if gap_low * gap_high > 0:
        return None
    for _ in range(60):  # bisection: brackets shrink 2^60-fold, far below display precision
        mid = (low + high) / 2
        gap_mid = gap(mid)
        if gap_low * gap_mid <= 0:
            high = mid
        else:
            low, gap_low = mid, gap_mid
    return (low + high) / 2
