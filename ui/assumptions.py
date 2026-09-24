"""Streamlit widgets for the assumption panel.

Every input carries a provenance label so the number is visibly a *choice*
anchored to evidence, never a silent default.

Convention: every slider here is displayed and dragged in real percentage
points (e.g. 60.0 for 60%), matching its "%" label, while the value handed to
the model is always the equivalent decimal (0.60). Seeds coming in and the
`Assumptions` object going out are always decimals; only the on-screen slider
itself is percentage-point scaled.
"""

from __future__ import annotations

import streamlit as st

from engine.valuation import Assumptions


def _pct_slider(label: str, min_pct: float, max_pct: float, seed_decimal: float,
                 step_pct: float, key: str, help: str | None = None) -> float:
    """A slider shown in percentage points, returning the equivalent decimal."""
    value_pct = st.slider(
        label, min_pct, max_pct, float(seed_decimal) * 100.0, step_pct,
        format="%.2f%%", help=help, key=key,
    )
    return value_pct / 100.0


def render_assumption_panel(seed: dict, ticker: str) -> Assumptions:
    """Render sliders pre-filled from evidence and return an Assumptions object.

    Widget keys include the ticker: Streamlit keeps a keyed slider's value and
    ignores new defaults, so shared keys would carry one company's assumptions
    over to the next.
    """
    prov = seed.get("provenance", {})

    st.markdown("### 3. Assumptions (each anchored to the evidence above)")

    col1, col2, col3 = st.columns(3)
    with col1:
        revenue_growth = _pct_slider(
            "Revenue growth / yr", 0.0, 25.0, seed["revenue_growth"], 0.25,
            key=f"{ticker}:revenue_growth", help=prov.get("revenue_growth"),
        )
        ebit_margin = _pct_slider(
            "EBIT margin", 0.0, 75.0, seed["ebit_margin"], 0.25,
            key=f"{ticker}:ebit_margin", help=prov.get("ebit_margin"),
        )
        tax_rate = _pct_slider(
            "Tax rate", 0.0, 40.0, seed["tax_rate"], 0.25,
            key=f"{ticker}:tax_rate", help=prov.get("tax_rate"),
        )
    with col2:
        da_pct = _pct_slider(
            "D&A % of revenue", 0.0, 20.0, seed["da_pct_revenue"], 0.25,
            key=f"{ticker}:da_pct_revenue", help=prov.get("da_pct_revenue"),
        )
        capex_pct = _pct_slider(
            "Capex % of revenue", 0.0, 30.0, seed["capex_pct_revenue"], 0.25,
            key=f"{ticker}:capex_pct_revenue", help=prov.get("capex_pct_revenue"),
        )
        nwc_pct = _pct_slider(
            "Δ net working capital % of revenue", 0.0, 15.0, seed["nwc_pct_revenue"], 0.25,
            key=f"{ticker}:nwc_pct_revenue", help=prov.get("nwc_pct_revenue"),
        )
    with col3:
        fade_years = st.select_slider(
            "Moat → fade period (years)", options=[5, 10, 15, 20],
            value=int(seed["fade_years"]), key=f"{ticker}:fade_years",
            help=prov.get("fade_years") + " · 5 = none, 10 = narrow, 20 = wide",
        )
        terminal_growth = _pct_slider(
            "Terminal growth / yr", 0.0, 5.0, seed["terminal_growth"], 0.1,
            key=f"{ticker}:terminal_growth", help=prov.get("terminal_growth"),
        )
        discount_rate = _pct_slider(
            "Discount rate (required return)", 4.0, 16.0, seed["discount_rate"], 0.1,
            key=f"{ticker}:discount_rate", help=prov.get("discount_rate"),
        )
        ref = seed.get("wacc_reference")
        if ref:
            st.caption(
                f"Reference WACC {ref['wacc']:.1%} · cost of equity {ref['cost_of_equity']:.1%} "
                f"(r_f {ref['risk_free']:.1%} + β {ref['beta']:.2f} × ERP "
                f"{ref['equity_risk_premium']:.1%}) · cost of debt {ref['cost_of_debt']:.1%}"
            )

    margin_of_safety = _pct_slider(
        "Required margin of safety", 0.0, 60.0, seed["margin_of_safety"], 1.0,
        key=f"{ticker}:margin_of_safety", help=prov.get("margin_of_safety"),
    )

    return Assumptions(
        revenue_growth=revenue_growth,
        ebit_margin=ebit_margin,
        tax_rate=tax_rate,
        da_pct_revenue=da_pct,
        capex_pct_revenue=capex_pct,
        nwc_pct_revenue=nwc_pct,
        fade_years=fade_years,
        terminal_growth=terminal_growth,
        discount_rate=discount_rate,
        margin_of_safety=margin_of_safety,
    )
