"""How past valuations have played out: return since each call, by decision."""

from __future__ import annotations

import pandas as pd


def track_record(entries: list[dict], prices_now: dict[str, float]) -> pd.DataFrame:
    """One row per journal entry with the price return since it was saved.

    Price return only (dividends excluded), so it slightly understates the
    return on dividend payers.
    """
    rows = []
    for e in entries:
        now = prices_now.get(e["ticker"])
        rows.append({
            "date": e["date"],
            "ticker": e["ticker"],
            "decision": e.get("decision", ""),
            "price_then": e["price"],
            "fair_value": e["fair_value"],
            "upside_then": e["fair_value"] / e["price"] - 1 if e["price"] else float("nan"),
            "price_now": now,
            "return_since": now / e["price"] - 1 if now and e["price"] else float("nan"),
            "note": e.get("note", ""),
        })
    return pd.DataFrame(rows)


def scorecard(record: pd.DataFrame) -> pd.DataFrame:
    """Average return since the call, per decision (Buy / Watch / Pass)."""
    if record.empty:
        return pd.DataFrame(columns=["calls", "average_return"])
    return record.groupby("decision").agg(
        calls=("ticker", "size"), average_return=("return_since", "mean"))
