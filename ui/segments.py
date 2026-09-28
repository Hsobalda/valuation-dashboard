"""Streamlit editor for the segment build."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from data.segments import load_segments, save_segments
from engine.segments import Segment, build

COLS = ["Segment", "Revenue (bn)", "Growth yr 1 (%)", "Growth yr 2 (%)", "Growth yr 5 (%)",
        "Operating margin (%)"]


def _default_rows(seed: dict) -> list[dict]:
    return [{
        "Segment": "Whole company (split me)",
        "Revenue (bn)": round(seed["base_revenue"] / 1e9, 2),
        "Growth yr 1 (%)": round(seed["growth_y1"] * 100, 1),
        "Growth yr 2 (%)": round(seed["growth_y2"] * 100, 1),
        "Growth yr 5 (%)": round(seed["growth_y5"] * 100, 1),
        "Operating margin (%)": round(seed["ebit_margin"] * 100, 1),
    }]


def _num(v) -> float | None:
    return None if v is None or v != v else float(v)


def _clean(rows: list[dict]) -> list[dict]:
    """JSON-safe rows: NaN (a blank cell) becomes None."""
    return [{c: (None if isinstance(v, float) and v != v else v) for c, v in r.items()} for r in rows]


def to_segments(records: list[dict]) -> tuple[list[Segment], list[str]]:
    """Editor rows -> Segments, plus the names of rows missing a growth rate."""
    segments, missing = [], []
    for r in records:
        g1, g2, g5 = (_num(r.get(c)) for c in ("Growth yr 1 (%)", "Growth yr 2 (%)", "Growth yr 5 (%)"))
        if g1 is None or g5 is None:
            missing.append(str(r["Segment"]))
            continue
        m = _num(r.get("Operating margin (%)"))
        segments.append(Segment(r["Segment"], _num(r["Revenue (bn)"]) * 1e9, g1 / 100, g5 / 100,
                                None if m is None else m / 100, None if g2 is None else g2 / 100))
    return segments, missing


def render_segment_editor(seed: dict, ticker: str) -> tuple[tuple[float, ...], float | None] | None:
    """Returns (blended growth path, target EBIT margin implied by the mix shift or None),
    or None if unusable."""
    st.markdown("#### Segment build")
    st.caption(
        "Enter each reported segment from the latest 10-K / annual report (the segment note). "
        "Each segment grows at its year-1 and year-2 rates, then moves in a straight line to "
        "its year-5 rate (leave year 2 blank for a straight line from year 1); the company "
        "path is their sum, so a fast-growing segment's rising share lifts growth over time."
    )
    # The editor's input must stay fixed for the session. Streamlit keeps edits as a
    # delta against that input; handing it freshly saved rows on each rerun resets
    # the widget and silently drops the edit made just after every save.
    base_key = f"{ticker}:segments_base"
    if base_key not in st.session_state:
        st.session_state[base_key] = load_segments(ticker) or _default_rows(seed)
    base = st.session_state[base_key]
    edited = st.data_editor(
        pd.DataFrame(base, columns=COLS), num_rows="dynamic", key=f"{ticker}:segments_editor",
        width="stretch", hide_index=True,
        column_config={
            "Revenue (bn)": st.column_config.NumberColumn(min_value=0.0, format="%.2f"),
            "Growth yr 1 (%)": st.column_config.NumberColumn(format="%.1f"),
            "Growth yr 2 (%)": st.column_config.NumberColumn(
                format="%.1f", help="Optional. Blank: straight line from year 1 to year 5"),
            "Growth yr 5 (%)": st.column_config.NumberColumn(format="%.1f"),
            "Operating margin (%)": st.column_config.NumberColumn(
                format="%.1f", help="Optional. Fill in every segment to get a blended margin"),
        },
    )
    records = _clean([r for r in edited.to_dict("records")
                      if r.get("Segment") and _num(r.get("Revenue (bn)"))])
    if records != _clean(load_segments(ticker) or []):
        save_segments(ticker, records)

    segments, missing = to_segments(records)
    if missing:
        st.warning(f"Left out until they have year-1 and year-5 growth: {', '.join(missing)}.")
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
    target = None
    if result.margin_start is not None:
        # Segment margins usually leave out unallocated corporate costs, so the blend
        # overstates the company margin. Carry only the mix-driven change across.
        target = seed["ebit_margin"] + (result.margin_end - result.margin_start)
        msg += (f". Segment margins blend to {result.margin_start:.1%} now → {result.margin_end:.1%} "
                f"in year 5; applied to the reported {seed['ebit_margin']:.1%}, that is {target:.1%}.")
    st.caption(msg)
    return tuple(result.growth), target
