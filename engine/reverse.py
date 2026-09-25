"""Reverse DCF: the revenue growth the current share price implies."""

from __future__ import annotations

from .valuation import Assumptions, value_per_share


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
    """Constant Stage-1 revenue growth at which DCF value equals `price`,
    holding every other assumption fixed. Returns None if no growth in [low, high] reaches the
    price. When ROIC is below the discount rate, extra growth lowers value, so
    the price may be unreachable through growth at all.
    """
    def gap(g: float) -> float:
        a = assumptions.with_flat_growth(g)
        return value_per_share(base_revenue, a, net_debt, minority_interest, shares_diluted) - price

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
