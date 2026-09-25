import pytest

from engine.dcf import dcf_3stage


def test_perpetuity_sanity_g_zero():
    """g=0, discount_rate=10%, flat FCF=100 forever -> value = 100/0.10 = 1000."""
    # Single stage-1 year of 100, no fade, then perpetuity of 100 forever.
    # PV explicit = 100/1.1, TV = 100/0.10 discounted 1 year.
    # Total should be exactly 100/0.10 = 1000 (a flat perpetuity).
    r = dcf_3stage(
        fcff_stage1=[100.0],
        discount_rate=0.10,
        fade_years=0,
        terminal_growth=0.0,
        shares_diluted=1.0,
    )
    # 100/1.1 + (100/0.10)/1.1 = 90.909... + 909.09... = 1000
    assert r.equity_value_per_share == pytest.approx(1000.0, rel=1e-9)


def test_spreadsheet_cross_check():
    """Independent hand-computed 5-year flat DCF.

    fcff = [100]*5, discount_rate=10%, terminal growth=3%, no fade, no debt/cash,
    1 share. Hand-built in a spreadsheet; engine must match to <0.01%.
    """
    r = dcf_3stage(
        fcff_stage1=[100.0, 100.0, 100.0, 100.0, 100.0],
        discount_rate=0.10,
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
        discount_rate=0.10,
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
        discount_rate=0.10,
        fade_years=0,
        terminal_growth=0.02,
    )
    wide_moat = dcf_3stage(
        fcff_stage1=[100.0, 105.0, 110.0, 115.0, 120.0],
        discount_rate=0.10,
        fade_years=20,
        terminal_growth=0.02,
    )
    assert wide_moat.enterprise_value > base.enterprise_value


def test_terminal_share_flag_threshold():
    r = dcf_3stage(
        fcff_stage1=[100.0, 100.0, 100.0, 100.0, 100.0],
        discount_rate=0.10,
        fade_years=0,
        terminal_growth=0.03,
    )
    # Known ~0.707 -> below the 0.8 warning threshold.
    assert r.terminal_share_of_ev < 0.8


def test_discount_rate_at_or_below_growth_raises():
    with pytest.raises(ValueError):
        dcf_3stage([100.0], discount_rate=0.05, fade_years=0, terminal_growth=0.05)
    with pytest.raises(ValueError):
        dcf_3stage([100.0], discount_rate=0.03, fade_years=0, terminal_growth=0.05)


def test_nonpositive_shares_raises():
    with pytest.raises(ValueError):
        dcf_3stage([100.0], discount_rate=0.10, fade_years=0, terminal_growth=0.03,
                   shares_diluted=0.0)


def test_roic_fade_hand_computed():
    """One fade year, worked by hand.

    Stage 1: FCFF 100 in year 1              -> PV 100 / 1.1
    Fade year: g = 2%, ROIC fades 20% -> 10%
        NOPAT 100 * 1.02 = 102, reinvest g/ROIC = 20% -> FCF 81.6 -> PV 81.6 / 1.1^2
    Terminal: NOPAT 102 * 1.02 = 104.04, reinvest 2%/10% = 20% -> 83.232
        TV = 83.232 / (10% - 2%) = 1040.4       -> PV 1040.4 / 1.1^2
    """
    r = dcf_3stage([100.0], discount_rate=0.10, fade_years=1, terminal_growth=0.02,
                   stage1_growth=0.04, nopat_last=100.0, roic_start=0.20)
    expected = 100 / 1.1 + 81.6 / 1.1 ** 2 + 1040.4 / 1.1 ** 2
    assert r.enterprise_value == pytest.approx(expected)


def test_terminal_growth_adds_no_value_when_ronic_equals_discount_rate():
    """With RONIC = r, TV = NOPAT_(T+1) / r: g only matters through one year of NOPAT growth."""
    kwargs = dict(discount_rate=0.10, fade_years=0, nopat_last=100.0, roic_start=0.10)
    low = dcf_3stage([100.0], terminal_growth=0.00, **kwargs).pv_terminal
    high = dcf_3stage([100.0], terminal_growth=0.04, **kwargs).pv_terminal
    assert high / low == pytest.approx(1.04)


def test_growth_destroys_value_when_roic_below_discount_rate():
    kwargs = dict(discount_rate=0.10, fade_years=10, terminal_growth=0.02,
                  nopat_last=100.0, roic_start=0.06, terminal_excess_return=-0.04)
    slow = dcf_3stage([100.0], stage1_growth=0.02, **kwargs).enterprise_value
    fast = dcf_3stage([100.0], stage1_growth=0.10, **kwargs).enterprise_value
    assert fast < slow


def test_terminal_excess_return_adds_value_through_growth():
    kwargs = dict(discount_rate=0.10, fade_years=0, terminal_growth=0.03, nopat_last=100.0, roic_start=0.10)
    no_moat = dcf_3stage([100.0], **kwargs).pv_terminal
    lasting_moat = dcf_3stage([100.0], terminal_excess_return=0.10, **kwargs).pv_terminal
    # RONIC 20%: TV = 103 * (1 - 0.03/0.20) / 0.07 vs 103 * (1 - 0.03/0.10) / 0.07
    assert lasting_moat / no_moat == pytest.approx((1 - 0.03 / 0.20) / (1 - 0.03 / 0.10))
