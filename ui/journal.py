"""Streamlit widgets for the valuation journal."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from data.journal import journal_path, load_entries, save_entry
from engine.track_record import scorecard, track_record


def _pct(v) -> str:
    return "—" if v is None or v != v else f"{v:+.1%}"


def render_save_form(entry: dict) -> None:
    with st.form(f"journal:{entry['ticker']}", clear_on_submit=True):
        decision = st.segmented_control("Decision", ["Buy", "Watch", "Pass"], default="Watch")
        note = st.text_area(
            "Thesis",
            placeholder="Why this value, which assumption matters most, and what would change your mind",
        )
        if st.form_submit_button("Save valuation", icon=":material/bookmark_add:"):
            save_entry({**entry, "decision": decision or "Watch", "note": note.strip()})
            st.success(f"Saved {entry['ticker']} to {journal_path().name}.")


def render_history(provider, ticker: str) -> None:
    entries = load_entries()
    if not entries:
        st.caption("No saved valuations yet.")
        return

    show_all = st.toggle("All companies", value=False, key="journal:all")
    shown = entries if show_all else [e for e in entries if e["ticker"] == ticker]
    if not shown:
        st.caption(f"No saved valuations for {ticker} yet. Switch on 'All companies' to see the rest.")
        return

    tickers = sorted({e["ticker"] for e in shown})
    prices = {p["ticker"]: p["price"] for p in provider.peer_profiles(tickers) if p.get("price")}
    rec = track_record(shown, prices)
    ccys = [e.get("currency", "") for e in shown]
    st.dataframe(pd.DataFrame({
        "Date": rec["date"],
        "Ticker": rec["ticker"],
        "Decision": rec["decision"],
        "Price then": [f"{c} {v:,.2f}" for c, v in zip(ccys, rec["price_then"])],
        "Fair value then": [f"{c} {v:,.2f}" for c, v in zip(ccys, rec["fair_value"])],
        "Upside then": [_pct(v) for v in rec["upside_then"]],
        "Price now": ["—" if v is None or v != v else f"{c} {v:,.2f}" for c, v in zip(ccys, rec["price_now"])],
        "Return since": [_pct(v) for v in rec["return_since"]],
        "Thesis": rec["note"],
    }).iloc[::-1], hide_index=True, width="stretch")

    card = scorecard(rec)
    st.dataframe(pd.DataFrame({
        "Calls": card["calls"],
        "Average return since": [_pct(v) for v in card["average_return"]],
    }), width="stretch")
    st.caption(
        "Price returns only, excluding dividends. A handful of calls proves nothing either way: "
        "judge the model after dozens of calls held for 6-12 months or more, and compare with "
        "what an index fund returned over the same period."
    )
