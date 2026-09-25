"""Comparable-company analysis.

Values a target by benchmarking its multiples against a peer set. The peer
*selection* is the analyst's judgment call; this module does the arithmetic.
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
    implied_values: dict[str, float] = field(default_factory=dict)  # median x target metric


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
    """Compute multiples for the target and peers, and implied target values."""
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

    # Implied value: apply each median multiple to the target's own metric and
    # bridge to a per-share equity value (EV multiples -> equity -> per share).
    implied = {}
    target = provider.fundamental_metrics(target_ticker)
    shares = target.get("shares_diluted") or 0.0
    for key in metrics:
        label, num_key, den_key = _MULTIPLES[key]
        if pd.isna(medians[label]):
            implied[label] = nan
            continue
        den = _ev(target) if den_key == "ev" else target.get(den_key, 0.0)
        if not den or den <= 0:  # no estimate, or losses: the multiple says nothing
            implied[label] = nan
            continue
        val = medians[label] * den
        if num_key == "ev":  # EV multiple -> enterprise value -> equity -> per share
            equity = val - target["net_debt"] - target["minority_interest"]
            val = equity / shares if shares else nan
        implied[label] = val

    return CompsResult(peer_table=table, medians=medians, implied_values=implied)
