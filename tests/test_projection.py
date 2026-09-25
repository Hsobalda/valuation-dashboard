import pytest

from engine.projection import project


def test_flat_no_growth_no_working_capital_change():
    # revenue flat -> delta NWC = 0
    fcf = project(
        base_revenue=1000,
        revenue_growth=0.0,
        ebit_margin=0.20,
        tax_rate=0.25,
        da_pct_revenue=0.05,
        capex_pct_revenue=0.06,
        nwc_pct_revenue=0.10,
        years=1,
    ).fcff
    # EBIT=200, NOPAT=150, +D&A=50, -CapEx=60, -dNWC=0 => 140
    assert fcf == [pytest.approx(140.0)]


def test_growth_drives_working_capital_drag():
    fcf = project(
        base_revenue=1000,
        revenue_growth=0.10,
        ebit_margin=0.20,
        tax_rate=0.25,
        da_pct_revenue=0.05,
        capex_pct_revenue=0.06,
        nwc_pct_revenue=0.10,
        years=1,
    ).fcff
    # revenue y1 = 1100; EBIT=220, NOPAT=165, +D&A=55, -CapEx=66,
    # dNWC = (1100-1000)*0.10 = 10 => 165+55-66-10 = 144
    assert fcf[0] == pytest.approx(144.0)


def test_years_length():
    fcf = project(1000, 0.05, 0.15, 0.20, 0.04, 0.05, 0.08, years=5).fcff
    assert len(fcf) == 5
    assert all(f > 0 for f in fcf)


def test_zero_revenue_returns_zeros():
    fcf = project(0.0, 0.05, 0.15, 0.20, 0.04, 0.05, 0.08, years=3).fcff
    assert fcf == [0.0, 0.0, 0.0]


def test_margin_moves_linearly_to_target():
    p = project(1000, 0.0, 0.10, 0.0, 0.0, 0.0, 0.0, years=4, target_margin=0.30)
    # margins 15%, 20%, 25%, 30% on flat revenue of 1000, no tax
    assert p.nopat == [pytest.approx(v) for v in (150.0, 200.0, 250.0, 300.0)]


def test_no_target_keeps_margin_flat():
    p = project(1000, 0.0, 0.20, 0.0, 0.0, 0.0, 0.0, years=3)
    assert p.nopat == [pytest.approx(200.0)] * 3
