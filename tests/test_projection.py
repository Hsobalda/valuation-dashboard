import pytest

from engine.projection import project


def test_no_growth_needs_no_reinvestment():
    p = project(1000, 0.0, 0.20, 0.25, roic=0.15, years=1)
    # EBIT 200, NOPAT 150, growth 0 -> reinvest nothing, FCFF = NOPAT
    assert p.fcff == [pytest.approx(150.0)]
    assert p.reinvestment == [pytest.approx(0.0)]


def test_growth_costs_g_over_roic_of_nopat():
    p = project(1000, 0.10, 0.20, 0.25, roic=0.20, years=1)
    # revenue 1100, NOPAT 165, reinvest 10%/20% = 50% -> 82.5, FCFF 82.5
    assert p.reinvestment[0] == pytest.approx(82.5)
    assert p.fcff[0] == pytest.approx(82.5)


def test_higher_roic_means_cheaper_growth():
    low = project(1000, 0.08, 0.20, 0.25, roic=0.10, years=3).fcff
    high = project(1000, 0.08, 0.20, 0.25, roic=0.40, years=3).fcff
    assert all(h > lo for h, lo in zip(high, low))


def test_margin_moves_linearly_to_target():
    p = project(1000, 0.0, 0.10, 0.0, roic=0.2, years=4, target_margin=0.30)
    assert p.ebit_margin == [pytest.approx(v) for v in (0.15, 0.20, 0.25, 0.30)]
    assert p.nopat == [pytest.approx(v) for v in (150.0, 200.0, 250.0, 300.0)]


def test_zero_revenue_returns_zeros():
    assert project(0.0, 0.05, 0.15, 0.20, roic=0.2, years=3).fcff == [0.0, 0.0, 0.0]


def test_nonpositive_roic_raises():
    with pytest.raises(ValueError):
        project(1000, 0.05, 0.15, 0.20, roic=0.0)
