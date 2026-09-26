"""Position sizing: equal risk budgets, tilted by conviction, inside hard caps.

Each satellite stock gets a slice of portfolio risk rather than of money: a
volatile stock gets fewer pounds for the same risk. The slice is scaled by
conviction (expected return above your hurdle, and the uncertainty rating), so
the DCF tilts the size but can't dominate it -- expected returns are the least
reliable input, volatility and correlation the most. The rest sits in the core
index fund.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

UNCERTAINTY_SCALE = {"Low": 1.0, "Medium": 0.75, "High": 0.5, "Very high": 0.25}
MAX_WEIGHT = {"Low": 0.05, "Medium": 0.04, "High": 0.02, "Very high": 0.01}
FULL_EDGE = 0.05  # an expected return 5 points above the hurdle earns full conviction


@dataclass
class Candidate:
    ticker: str
    sector: str
    expected_return: float | None  # annual return offered at today's price (IRR)
    uncertainty: str
    volatility: float               # annualised


def conviction(c: Candidate, hurdle: float) -> float:
    """0 if the stock fails your required return; otherwise 0.5-1.0 by edge over
    the hurdle, scaled down for uncertainty."""
    if c.expected_return is None or c.expected_return < hurdle:
        return 0.0
    edge = min((c.expected_return - hurdle) / FULL_EDGE, 1.0)
    return (0.5 + 0.5 * edge) * UNCERTAINTY_SCALE.get(c.uncertainty, 0.5)


def size_positions(candidates: list[Candidate], hurdle: float, risk_budget: float = 0.01,
                   satellite_cap: float = 0.25, sector_cap: float = 0.10) -> pd.DataFrame:
    """Weights as a share of the whole portfolio.

    Standalone risk budget per stock = `risk_budget` x conviction, so
    weight = budget / volatility (e.g. 1% risk on a 20%-volatility stock = 5%).
    Then: per-stock cap by uncertainty, sector cap, satellite cap.
    """
    rows = []
    for c in candidates:
        conv = conviction(c, hurdle)
        raw = risk_budget * conv / c.volatility if c.volatility > 0 else 0.0
        cap = MAX_WEIGHT.get(c.uncertainty, 0.01)
        rows.append({"ticker": c.ticker, "sector": c.sector, "expected_return": c.expected_return,
                     "uncertainty": c.uncertainty, "volatility": c.volatility, "conviction": conv,
                     "raw_weight": raw, "weight": min(raw, cap),
                     "limit": "stock cap" if raw > cap else ("fails hurdle" if conv == 0 else "")})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for sector, members in df.groupby("sector"):
        total = members["weight"].sum()
        if total > sector_cap:
            df.loc[members.index, "weight"] *= sector_cap / total
            df.loc[members.index, "limit"] = "sector cap"
    total = df["weight"].sum()
    if total > satellite_cap:
        df["weight"] *= satellite_cap / total
        df["limit"] = df["limit"].where(df["limit"] != "", "satellite cap")
    return df


def portfolio_risk(weights: pd.Series, returns: pd.DataFrame, periods_per_year: int = 52) -> tuple[float, pd.Series]:
    """Annualised portfolio volatility and each holding's share of it.

    Risk contribution_i = w_i x (covariance . w)_i / portfolio variance: this is
    where correlation shows up, so a stock that moves with the core adds more
    risk than its own volatility suggests, and one that moves against it less.
    """
    cols = list(weights.index)
    cov = returns[cols].cov().to_numpy() * periods_per_year
    w = weights.to_numpy()
    variance = float(w @ cov @ w)
    contributions = w * (cov @ w) / variance if variance > 0 else np.zeros_like(w)
    return float(np.sqrt(variance)), pd.Series(contributions, index=cols)
