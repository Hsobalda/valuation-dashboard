import pytest

from engine.sensitivity import sensitivity_grid
from engine.valuation import Assumptions, run_valuation


def test_grid_shape_and_labels():
    df = sensitivity_grid(
        fcff_stage1=[100.0, 105.0, 110.0, 115.0, 120.0],
        wacc_range=(0.08, 0.12, 0.02),
        growth_range=(0.01, 0.03, 0.01),
        fade_years=10,
    )
    assert list(df.index) == [0.08, 0.10, 0.12]
    assert list(df.columns) == [0.01, 0.02, 0.03]


def test_grid_nan_where_wacc_le_growth():
    df = sensitivity_grid(
        fcff_stage1=[100.0],
        wacc_range=(0.02, 0.04, 0.02),
        growth_range=(0.03, 0.05, 0.02),
        fade_years=0,
    )
    # wacc 0.02 <= growth 0.03/0.05 -> NaN
    assert df.loc[0.02, 0.03] is None or df.loc[0.02, 0.03] != df.loc[0.02, 0.03]


def test_grid_higher_wacc_lower_value():
    df = sensitivity_grid(
        fcff_stage1=[100.0, 105.0, 110.0, 115.0, 120.0],
        wacc_range=(0.08, 0.12, 0.02),
        growth_range=(0.02, 0.02, 0.01),
        fade_years=10,
    )
    assert df.loc[0.12, 0.02] < df.loc[0.08, 0.02]


def test_grid_centre_cell_matches_headline_fair_value():
    """The sensitivity grid is built around the base WACC / terminal growth,
    so its centre cell must equal the headline fair value from run_valuation."""
    assumptions = Assumptions(
        revenue_growth=0.05, ebit_margin=0.20, tax_rate=0.21,
        da_pct_revenue=0.05, capex_pct_revenue=0.05, nwc_pct_revenue=0.0,
        fade_years=10, terminal_growth=0.025, wacc=0.08, margin_of_safety=0.25,
    )
    run = run_valuation(base_revenue=1000.0, assumptions=assumptions)

    centre = run.sensitivity.loc[round(assumptions.wacc, 8), round(assumptions.terminal_growth, 8)]
    assert centre == pytest.approx(run.result.equity_value_per_share, abs=0.01)
