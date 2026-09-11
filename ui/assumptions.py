"""Streamlit widgets for the assumption panel.

Every input carries a provenance label so the number is visibly a *choice*
anchored to evidence, never a silent default.
"""

from __future__ import annotations

import streamlit as st

from engine.valuation import Assumptions


def render_assumption_panel(seed: dict) -> Assumptions:
    """Render sliders pre-filled from evidence and return an Assumptions object."""
    prov = seed.get("provenance", {})

    st.markdown("### 3. Assumptions (each anchored to the evidence above)")

    col1, col2, col3 = st.columns(3)
    with col1:
        revenue_growth = st.slider(
            "Revenue growth / yr", 0.0, 0.25, float(seed["revenue_growth"]), 0.005,
            format="%.1f%%", help=prov.get("revenue_growth"),
        ) / 100.0
        ebit_margin = st.slider(
            "EBIT margin", 0.0, 0.50, float(seed["ebit_margin"]), 0.005,
            format="%.1f%%", help=prov.get("ebit_margin"),
        ) / 100.0
        tax_rate = st.slider(
            "Tax rate", 0.0, 0.40, float(seed["tax_rate"]), 0.005,
            format="%.1f%%", help=prov.get("tax_rate"),
        ) / 100.0
    with col2:
        da_pct = st.slider(
            "D&A % of revenue", 0.0, 0.20, float(seed["da_pct_revenue"]), 0.005,
            format="%.1f%%", help=prov.get("da_pct_revenue"),
        ) / 100.0
        capex_pct = st.slider(
            "Capex % of revenue", 0.0, 0.30, float(seed["capex_pct_revenue"]), 0.005,
            format="%.1f%%", help=prov.get("capex_pct_revenue"),
        ) / 100.0
        nwc_pct = st.slider(
            "Δ net working capital % of revenue", 0.0, 0.15, float(seed["nwc_pct_revenue"]), 0.005,
            format="%.1f%%", help=prov.get("nwc_pct_revenue"),
        ) / 100.0
    with col3:
        fade_years = st.select_slider(
            "Moat → fade period (years)", options=[5, 10, 15, 20],
            value=int(seed["fade_years"]),
            help=prov.get("fade_years") + " · 5 = none, 10 = narrow, 20 = wide",
        )
        terminal_growth = st.slider(
            "Terminal growth / yr", 0.0, 0.05, float(seed["terminal_growth"]), 0.005,
            format="%.1f%%", help=prov.get("terminal_growth"),
        ) / 100.0
        wacc = st.slider(
            "WACC (discount rate)", 0.04, 0.16, float(seed["wacc"]), 0.005,
            format="%.1f%%", help=prov.get("wacc"),
        ) / 100.0

    margin_of_safety = st.slider(
        "Required margin of safety", 0.0, 0.60, float(seed["margin_of_safety"]), 0.05,
        format="%.0f%%", help=prov.get("margin_of_safety"),
    ) / 100.0

    return Assumptions(
        revenue_growth=revenue_growth,
        ebit_margin=ebit_margin,
        tax_rate=tax_rate,
        da_pct_revenue=da_pct,
        capex_pct_revenue=capex_pct,
        nwc_pct_revenue=nwc_pct,
        fade_years=fade_years,
        terminal_growth=terminal_growth,
        wacc=wacc,
        margin_of_safety=margin_of_safety,
    )
