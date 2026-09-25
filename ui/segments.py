"""Streamlit editor for the segment build."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from data.segments import load_segments, save_segments
from engine.segments import Segment, build

COLS = ["Segment", "Revenue (bn)", "Growth yr 1 (%)", "Growth yr 5 (%)", "Operating margin (%)"]


def _default_rows(seed: dict) -> list[dict]:
    return [{
        "Segment": "Whole company (split me)",
        "Revenue (bn)": round(seed["base_revenue"] / 1e9, 2),
        "Growth yr 1 (%)": round(seed["growth_y1"] * 100, 1),
        "Growth yr 5 (%)": round(seed["growth_y5"] * 100, 1),
        "Operating margin (%)": round(seed["ebit_margin"] * 100, 1),
    }]


def _num(v) -> float | None:
    return None if v is None or v != v else float(v)


def render_segment_editor(seed: dict, ticker: str) -> tuple[tuple[float, ...], float | None] | None:
    """Returns (blended growth path, blended year-5 margin or None), or None if unusable."""
    st.markdown("#### Segment build")
    st.caption(
        "Enter each reported segment from the latest 10-K / annual report (the segment note). "
        "Each segment's growth moves in a straight line from year 1 to year 5; the company "
        "path is their sum, so a fast-growing segment's rising share lifts growth over time."
    )
    saved = load_segments(ticker)
    rows = saved or _default_rows(seed)
    edited = st.data_editor(
        pd.DataFrame(rows, columns=COLS), num_rows="dynamic", key=f"{ticker}:segments_editor",
        width="stretch", hide_index=True,
        column_config={
            "Revenue (bn)": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
            "Growth yr 1 (%)": st.column_config.NumberColumn(format="%.1f"),
            "Growth yr 5 (%)": st.column_config.NumberColumn(format="%.1f"),
            "Operating margin (%)": st.column_config.NumberColumn(
                format="%.1f", help="Optional. Fill in every segment to get a blended margin"),
        },
    )
    records = [r for r in edited.to_dict("records") if r.get("Segment") and _num(r.get("Revenue (bn)"))]
    if records != rows:
        save_segments(ticker, records)

    segments = [
        Segment(r["Segment"], _num(r["Revenue (bn)"]) * 1e9,
                (_num(r["Growth yr 1 (%)"]) or 0.0) / 100, (_num(r["Growth yr 5 (%)"]) or 0.0) / 100,
                None if _num(r.get("Operating margin (%)")) is None else _num(r["Operating margin (%)"]) / 100)
        for r in records
    ]
    try:
        result = build(segments)
    except ValueError as e:
        st.warning(f"Segment build not used: {e}.")
        return None

    total = sum(s.revenue for s in segments)
    gap = total / seed["base_revenue"] - 1 if seed["base_revenue"] else 0.0
    if abs(gap) > 0.02:
        st.warning(
            f"Segments add up to {total / 1e9:,.1f}bn, {abs(gap):.0%} {'above' if gap > 0 else 'below'} "
            f"reported revenue of {seed['base_revenue'] / 1e9:,.1f}bn. Add an 'Other / eliminations' "
            "row, or check the units. The model applies the blended growth to reported revenue."
        )

    st.dataframe(pd.DataFrame({
        "Mix now": [f"{m:.0%}" for m in result.mix_start],
        "Mix in year 5": [f"{m:.0%}" for m in result.mix_end],
    }, index=[s.name for s in segments]).T, width="stretch")
    msg = "Blended growth: " + " → ".join(f"{g:.1%}" for g in result.growth)
    if result.margin_start is not None:
        msg += (f". Blended operating margin {result.margin_start:.1%} now → "
                f"{result.margin_end:.1%} in year 5 (reported: {seed['ebit_margin']:.1%}).")
    st.caption(msg)
    return tuple(result.growth), result.margin_end
