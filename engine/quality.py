"""Quality / moat indicators computed from normalized series.

Pure functions -- take pandas Series, return numbers or Series.
"""

from __future__ import annotations

import pandas as pd


def roic_series(nopat: pd.Series, invested_capital: pd.Series) -> pd.Series:
    """Return on invested capital = NOPAT / invested capital, per year.

    Aligns on the intersection of the two series' indices. Years with
    non-positive invested capital produce NaN (undefined ROIC).
    """
    aligned = pd.concat([nopat, invested_capital], axis=1, join="inner")
    nopat_a, ic_a = aligned.iloc[:, 0], aligned.iloc[:, 1]
    out = pd.Series(index=aligned.index, dtype=float)
    for y in aligned.index:
        if ic_a[y] and ic_a[y] > 0:
            out[y] = nopat_a[y] / ic_a[y]
        else:
            out[y] = float("nan")
    return out


def margin_stability(margins: pd.Series) -> float:
    """Standard deviation of a margin series (lower = more stable pricing power)."""
    clean = margins.dropna()
    if len(clean) < 2:
        return float("nan")
    return float(clean.std(ddof=1))


def fcf_conversion_series(fcf: pd.Series, net_income: pd.Series) -> pd.Series:
    """FCF / net income per year (>= 1 means earnings are backed by cash)."""
    aligned = pd.concat([fcf, net_income], axis=1, join="inner")
    fcf_a, ni_a = aligned.iloc[:, 0], aligned.iloc[:, 1]
    out = pd.Series(index=aligned.index, dtype=float)
    for y in aligned.index:
        out[y] = fcf_a[y] / ni_a[y] if ni_a[y] else float("nan")
    return out


def gross_margin(revenue: pd.Series, cost_of_revenue: pd.Series) -> pd.Series:
    """Gross margin = (revenue - COGS) / revenue."""
    aligned = pd.concat([revenue, cost_of_revenue], axis=1, join="inner")
    rev, cogs = aligned.iloc[:, 0], aligned.iloc[:, 1]
    out = pd.Series(index=aligned.index, dtype=float)
    for y in aligned.index:
        out[y] = (rev[y] - cogs[y]) / rev[y] if rev[y] else float("nan")
    return out


def operating_margin(operating_income: pd.Series, revenue: pd.Series) -> pd.Series:
    """Operating margin = operating income / revenue."""
    aligned = pd.concat([operating_income, revenue], axis=1, join="inner")
    oi, rev = aligned.iloc[:, 0], aligned.iloc[:, 1]
    out = pd.Series(index=aligned.index, dtype=float)
    for y in aligned.index:
        out[y] = oi[y] / rev[y] if rev[y] else float("nan")
    return out


def net_margin(net_income: pd.Series, revenue: pd.Series) -> pd.Series:
    """Net margin = net income / revenue."""
    aligned = pd.concat([net_income, revenue], axis=1, join="inner")
    ni, rev = aligned.iloc[:, 0], aligned.iloc[:, 1]
    out = pd.Series(index=aligned.index, dtype=float)
    for y in aligned.index:
        out[y] = ni[y] / rev[y] if rev[y] else float("nan")
    return out
