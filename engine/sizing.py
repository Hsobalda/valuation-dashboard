"""Position sizing for a concentrated stock pie of about N holdings.

Each stock starts from a standard slot (1/N of the pie: 10% for 10 holdings)
and is scaled by conviction (expected return above your hurdle, and the
uncertainty rating) and by volatility against a typical single stock. Expected
returns only tilt the size, since they are the least reliable input; stocks that
fail the hurdle get nothing, and those that clear it but still trade above the
buy zone get a half-size starter. Caps per stock (by uncertainty) and per sector
keep one idea or one theme from dominating.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

UNCERTAINTY_SCALE = {"Low": 1.0, "Medium": 0.75, "High": 0.5, "Very high": 0.25}
MAX_SLOTS = {"Low": 2.0, "Medium": 1.5, "High": 1.0, "Very high": 0.5}  # cap, in standard slots
FULL_EDGE = 0.05      # an expected return 5 points above the hurdle earns full conviction
TYPICAL_VOL = 0.25    # a typical single stock's annual volatility


@dataclass
class Candidate:
    ticker: str
    sector: str
    expected_return: float | None  # annual return offered at today's price (IRR)
    uncertainty: str
    volatility: float               # annualised
    passes_margin_of_safety: bool = True  # price at or below the buy zone


def conviction(c: Candidate, hurdle: float) -> float:
    """0 if the stock fails your required return; otherwise 0.5-1.0 by edge over
    the hurdle, scaled down for uncertainty."""
    if c.expected_return is None or c.expected_return < hurdle:
        return 0.0
    edge = min((c.expected_return - hurdle) / FULL_EDGE, 1.0)
    return (0.5 + 0.5 * edge) * UNCERTAINTY_SCALE.get(c.uncertainty, 0.5)


def size_positions(candidates: list[Candidate], hurdle: float, holdings: int = 10,
                   sector_cap: float = 0.30) -> pd.DataFrame:
    """Weights as a share of the full pie (what it will hold at `holdings` names).

    weight = slot x (0.5 + conviction) x (typical vol / stock vol, kept to 0.5-1.5x),
    halved if the price is above the buy zone (a starter: add the rest if it falls
    into the zone), capped at MAX_SLOTS slots for its uncertainty; then the sector
    cap; then scaled down if the total passes 100%. Below 100%, the rest is
    unfilled slots.
    """
    slot = 1.0 / holdings
    rows = []
    for c in candidates:
        conv = conviction(c, hurdle)
        vol_adj = min(max(TYPICAL_VOL / c.volatility, 0.5), 1.5) if c.volatility > 0 else 1.0
        raw = slot * (0.5 + conv) * vol_adj if conv > 0 else 0.0
        starter = conv > 0 and not c.passes_margin_of_safety
        if starter:
            raw *= 0.5
        cap = slot * MAX_SLOTS.get(c.uncertainty, 0.5)
        rows.append({"ticker": c.ticker, "sector": c.sector, "expected_return": c.expected_return,
                     "uncertainty": c.uncertainty, "volatility": c.volatility, "conviction": conv,
                     "weight": min(raw, cap),
                     "limit": ("fails required return" if conv == 0 else "stock cap" if raw > cap
                               else "starter: price above buy zone" if starter else "")})
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    for _, members in df.groupby("sector"):
        total = members["weight"].sum()
        if total > sector_cap:
            df.loc[members.index, "weight"] *= sector_cap / total
            df.loc[members.index, "limit"] = "sector cap"
    if df["weight"].sum() > 1.0:
        df["weight"] /= df["weight"].sum()
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


def in_base_currency(closes: pd.Series, fx: pd.Series) -> pd.Series:
    """Prices converted at each week's exchange rate (base-currency units per unit
    of the listing's currency). For a UK investor a US stock's risk includes the
    dollar: its sterling return is (1 + dollar return) x (1 + change in USD/GBP) - 1."""
    closes, fx = closes.align(fx, join="inner")
    return (closes * fx).dropna()
