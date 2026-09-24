"""Two-dimensional sensitivity grid (discount rate x terminal growth)."""

from __future__ import annotations

import pandas as pd

from .dcf import dcf_3stage


def _frange(start: float, stop: float, step: float) -> list[float]:
    """Inclusive float range with rounding to avoid fp drift."""
    if step <= 0:
        raise ValueError("step must be positive")
    vals = []
    x = start
    while round(x, 8) <= round(stop, 8) + 1e-12:
        vals.append(round(x, 8))
        x += step
    return vals


def sensitivity_grid(
    fcff_stage1: list[float],
    rate_range: tuple[float, float, float],
    growth_range: tuple[float, float, float],
    fade_years: int,
    **bridge_kwargs,
) -> pd.DataFrame:
    """Equity value per share for each (discount rate, terminal growth) combination.

    rate_range / growth_range are (min, max, step). Returns a DataFrame indexed
    by discount rate (rows) and terminal growth (columns); invalid cells (rate <= g) are
    NaN.
    """
    rate_min, rate_max, rate_step = rate_range
    g_min, g_max, g_step = growth_range

    rows: dict[float, dict[float, float | None]] = {}
    for w in _frange(rate_min, rate_max, rate_step):
        row: dict[float, float | None] = {}
        for g in _frange(g_min, g_max, g_step):
            try:
                result = dcf_3stage(
                    fcff_stage1, w, fade_years, g, **bridge_kwargs
                )
                row[g] = round(result.equity_value_per_share, 2)
            except ValueError:
                row[g] = None
        rows[w] = row

    df = pd.DataFrame(rows).T
    df.index.name = "discount rate"
    df.columns.name = "terminal growth"
    return df
