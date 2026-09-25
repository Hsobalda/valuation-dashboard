"""Comparable-company analysis.

Relative valuation for context: how the target's multiples compare with a peer
median. It isn't used to price the stock, because a peer median is only as good
as the peer set (Yahoo groups Mastercard with card lenders, for example). The
peer *selection* is the analyst's judgment call; this module does the arithmetic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import nan

import pandas as pd

# Multiple key -> column label -> raw metric it divides / is divided by.
# value = numerator(metric) / denominator(metric), all from provider.fundamental_metrics().
_MULTIPLES = {
    "ev_ebitda": ("EV/EBITDA", "ev", "ebitda"),
    "pe": ("P/E", "price", "eps"),
    "pe_fwd": ("Fwd P/E", "price", "eps_forward"),
    "ev_revenue": ("EV/Revenue", "ev", "revenue"),
    "ev_revenue_fwd": ("Fwd EV/Revenue", "ev", "revenue_forward"),
    "pb": ("P/B", "price", "bvps"),
}


@dataclass
class CompsResult:
    peer_table: pd.DataFrame          # rows = tickers, cols = multiples
    medians: dict[str, float] = field(default_factory=dict)
    premium: dict[str, float] = field(default_factory=dict)  # target vs peer median, e.g. +0.2 = 20% above


def _ev(m: dict) -> float:
    return m["market_cap"] + m["net_debt"] + m["minority_interest"]


def _multiple(num: float, den: float) -> float:
    """A valuation multiple, or NaN when negative/undefined (e.g. loss-making P/E)."""
    if not den:
        return nan
    value = num / den
    return value if value > 0 else nan


def comps_analysis(
    target_ticker: str,
    peers: list[str],
    metrics: list[str],
    provider,
) -> CompsResult:
    """Multiples for the target and peers, peer medians, and the target's premium
    or discount to each median."""
    tickers = []
    for t in [target_ticker, *peers]:
        if t and t not in tickers:
            tickers.append(t)

    rows = {}
    for t in tickers:
        try:
            m = provider.fundamental_metrics(t)
        except Exception:
            continue
        if m.get("currency_mismatch"):
            continue
        ev = _ev(m)
        row = {}
        for key in metrics:
            label, num_key, den_key = _MULTIPLES[key]
            num = ev if num_key == "ev" else m[num_key]
            row[label] = _multiple(num, m.get(den_key, 0.0))
        rows[t] = row

    table = pd.DataFrame.from_dict(rows, orient="index")

    # The target is shown in the table but excluded from the benchmark,
    # otherwise its own multiple pulls the median towards its current price.
    peer_rows = table.drop(index=target_ticker, errors="ignore")
    medians = {}
    for col in table.columns:
        med = peer_rows[col].dropna().median()
        medians[col] = float(med) if not pd.isna(med) else nan

    target_row = table.loc[target_ticker] if target_ticker in table.index else None
    premium = {
        col: (float(target_row[col] / medians[col] - 1)
              if target_row is not None and not pd.isna(target_row[col]) and medians[col] == medians[col]
              else nan)
        for col in table.columns
    }
    return CompsResult(peer_table=table, medians=medians, premium=premium)
