import pytest

from engine.sensitivity import sensitivity_grid


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
