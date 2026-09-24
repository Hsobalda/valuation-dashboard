"""Sliders in ui/assumptions.py must display real percentages (e.g. 60.0%)
while still handing the model the equivalent decimal (0.60), no matter what
percentage-point value the slider itself shows."""

from streamlit.testing.v1 import AppTest

from engine.valuation import Assumptions, run_valuation


def _seed(ebit_margin: float = 0.20) -> dict:
    return {
        "revenue_growth": 0.05,
        "ebit_margin": ebit_margin,
        "tax_rate": 0.21,
        "da_pct_revenue": 0.05,
        "capex_pct_revenue": 0.05,
        "nwc_pct_revenue": 0.0,
        "fade_years": 10,
        "terminal_growth": 0.025,
        "discount_rate": 0.08,
        "margin_of_safety": 0.25,
        "provenance": {"fade_years": "test fixture"},
    }


def _panel_script():
    import streamlit as st

    from ui.assumptions import render_assumption_panel

    seed = st.session_state["seed"]
    st.session_state["assumptions"] = render_assumption_panel(seed)


def test_margin_slider_shows_and_returns_real_percentage():
    at = AppTest.from_function(_panel_script)
    at.session_state["seed"] = _seed(ebit_margin=0.60)
    at.run()
    assert not at.exception

    margin_slider = next(s for s in at.slider if s.label == "EBIT margin")
    assert margin_slider.value == 60.0  # displayed in real percentage points

    assumptions = at.session_state["assumptions"]
    assert assumptions.ebit_margin == 0.60  # model still receives the decimal


def test_60pct_margin_same_model_value_however_entered():
    """A 60% EBIT margin must produce the same fair value whether it arrives
    as a pre-seeded value (already 0.60 in the seed dict) or is dragged to
    60.0 on the on-screen percentage slider."""
    # Path 1: seed already carries the 60% margin as a decimal.
    at = AppTest.from_function(_panel_script)
    at.session_state["seed"] = _seed(ebit_margin=0.60)
    at.run()
    assumptions_from_seed: Assumptions = at.session_state["assumptions"]

    # Path 2: seed starts elsewhere, user drags the slider to 60.0%.
    at2 = AppTest.from_function(_panel_script)
    at2.session_state["seed"] = _seed(ebit_margin=0.20)
    at2.run()
    margin_slider = next(s for s in at2.slider if s.label == "EBIT margin")
    margin_slider.set_value(60.0).run()
    assert not at2.exception
    assumptions_from_slider: Assumptions = at2.session_state["assumptions"]

    assert assumptions_from_seed.ebit_margin == assumptions_from_slider.ebit_margin == 0.60

    run_kwargs = dict(base_revenue=1000.0, net_debt=0.0, minority_interest=0.0,
                       shares_diluted=1.0)
    result_from_seed = run_valuation(assumptions=assumptions_from_seed, **run_kwargs)
    result_from_slider = run_valuation(assumptions=assumptions_from_slider, **run_kwargs)

    assert (result_from_seed.result.equity_value_per_share
            == result_from_slider.result.equity_value_per_share)
