import pytest

from engine.dcf import dcf_3stage


def test_perpetuity_sanity_g_zero():
    """g=0, wacc=10%, flat FCF=100 forever -> value = 100/0.10 = 1000."""
    # Single stage-1 year of 100, no fade, then perpetuity of 100 forever.
    # PV explicit = 100/1.1, TV = 100/0.10 discounted 1 year.
    # Total should be exactly 100/0.10 = 1000 (a flat perpetuity).
    r = dcf_3stage(
        fcff_stage1=[100.0],
        wacc=0.10,
        fade_years=0,
        terminal_growth=0.0,
        shares_diluted=1.0,
    )
    # 100/1.1 + (100/0.10)/1.1 = 90.909... + 909.09... = 1000
    assert r.equity_value_per_share == pytest.approx(1000.0, rel=1e-9)


def test_spreadsheet_cross_check():
    """Independent hand-computed 5-year flat DCF.

    fcff = [100]*5, wacc=10%, terminal growth=3%, no fade, no debt/cash,
    1 share. Hand-built in a spreadsheet; engine must match to <0.01%.
    """
    r = dcf_3stage(
        fcff_stage1=[100.0, 100.0, 100.0, 100.0, 100.0],
        wacc=0.10,
        fade_years=0,
        terminal_growth=0.03,
        shares_diluted=1.0,
    )
    assert r.pv_explicit == pytest.approx(379.07867694084473, rel=1e-9)
    assert r.pv_terminal == pytest.approx(913.6413753584708, rel=1e-9)
    assert r.enterprise_value == pytest.approx(1292.7200522993155, rel=1e-9)
    assert r.equity_value_per_share == pytest.approx(1292.7200522993155, rel=1e-9)
    assert r.terminal_share_of_ev == pytest.approx(0.7067588792588226, rel=1e-9)


def test_equity_bridge():
    """EV -> equity: subtract net debt (already net of cash) and minority interest."""
    r = dcf_3stage(
        fcff_stage1=[100.0, 100.0, 100.0, 100.0, 100.0],
        wacc=0.10,
        fade_years=0,
        terminal_growth=0.03,
        net_debt=200.0,
        minority_interest=10.0,
        shares_diluted=10.0,
    )
    expected_equity = r.enterprise_value - 200.0 - 10.0
    assert r.equity_value == pytest.approx(expected_equity)
    assert r.equity_value_per_share == pytest.approx(expected_equity / 10.0)


def test_fade_extends_value():
    """A longer moat (fade) with growing cash flows must raise enterprise value."""
    base = dcf_3stage(
        fcff_stage1=[100.0, 105.0, 110.0, 115.0, 120.0],
        wacc=0.10,
        fade_years=0,
        terminal_growth=0.02,
    )
    wide_moat = dcf_3stage(
        fcff_stage1=[100.0, 105.0, 110.0, 115.0, 120.0],
        wacc=0.10,
        fade_years=20,
        terminal_growth=0.02,
    )
    assert wide_moat.enterprise_value > base.enterprise_value


def test_terminal_share_flag_threshold():
    r = dcf_3stage(
        fcff_stage1=[100.0, 100.0, 100.0, 100.0, 100.0],
        wacc=0.10,
        fade_years=0,
        terminal_growth=0.03,
    )
    # Known ~0.707 -> below the 0.8 warning threshold.
    assert r.terminal_share_of_ev < 0.8


def test_wacc_at_or_below_growth_raises():
    with pytest.raises(ValueError):
        dcf_3stage([100.0], wacc=0.05, fade_years=0, terminal_growth=0.05)
    with pytest.raises(ValueError):
        dcf_3stage([100.0], wacc=0.03, fade_years=0, terminal_growth=0.05)


def test_nonpositive_shares_raises():
    with pytest.raises(ValueError):
        dcf_3stage([100.0], wacc=0.10, fade_years=0, terminal_growth=0.03,
                   shares_diluted=0.0)
