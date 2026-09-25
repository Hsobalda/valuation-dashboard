import pandas as pd
import pytest

from engine.quality import (
    fcf_conversion_series,
    gross_margin,
    margin_stability,
    net_margin,
    operating_margin,
    roic_series,
)


def test_roic_series():
    nopat = pd.Series([100.0, 120.0, 90.0], index=[2020, 2021, 2022])
    ic = pd.Series([1000.0, 1000.0, 1500.0], index=[2020, 2021, 2022])
    roic = roic_series(nopat, ic)
    assert roic[2020] == pytest.approx(0.10)
    assert roic[2021] == pytest.approx(0.12)
    assert roic[2022] == pytest.approx(0.06)


def test_roic_ignores_nonpositive_invested_capital():
    nopat = pd.Series([100.0], index=[2020])
    ic = pd.Series([-50.0], index=[2020])
    assert roic_series(nopat, ic)[2020] != roic_series(nopat, ic)[2020]  # NaN


def test_margin_stability():
    stable = pd.Series([0.30, 0.31, 0.29, 0.30, 0.30])
    volatile = pd.Series([0.30, 0.45, 0.15, 0.40, 0.20])
    assert margin_stability(stable) < margin_stability(volatile)


def test_margin_stability_short_series_is_nan():
    assert margin_stability(pd.Series([0.30])) != margin_stability(pd.Series([0.30]))


def test_fcf_conversion():
    fcf = pd.Series([80.0, 90.0], index=[2020, 2021])
    ni = pd.Series([100.0, 100.0], index=[2020, 2021])
    conv = fcf_conversion_series(fcf, ni)
    assert conv[2020] == pytest.approx(0.8)
    assert conv[2021] == pytest.approx(0.9)


def test_margins():
    rev = pd.Series([1000.0, 1100.0], index=[2020, 2021])
    cogs = pd.Series([600.0, 640.0], index=[2020, 2021])
    oi = pd.Series([200.0, 250.0], index=[2020, 2021])
    ni = pd.Series([120.0, 160.0], index=[2020, 2021])
    assert gross_margin(rev, cogs)[2020] == pytest.approx(0.40)
    assert operating_margin(oi, rev)[2020] == pytest.approx(0.20)
    assert net_margin(ni, rev)[2020] == pytest.approx(0.12)


def test_dcf_not_applied_to_banks_and_insurers():
    from brief import dcf_applicable

    assert not dcf_applicable("Banks - Diversified")
    assert not dcf_applicable("Insurance - Property & Casualty")
    assert dcf_applicable("Credit Services")  # Visa/Mastercard: fee businesses
    assert dcf_applicable("Consumer Electronics")
    assert dcf_applicable("")


class _CapStub:
    def __init__(self, fcf, dividends, buybacks, shares=None):
        import pandas as pd

        idx = list(range(2021, 2021 + len(fcf)))
        self.cf = pd.DataFrame({"operating_cash_flow": fcf, "capital_expenditure": [0.0] * len(fcf),
                                "dividends_paid": dividends, "stock_buybacks": buybacks}, index=idx)
        self.inc = pd.DataFrame({"shares_diluted_avg": shares} if shares else {}, index=idx)
        self.bal = pd.DataFrame({"total_debt": [10.0] * len(fcf), "cash_and_equiv": [5.0] * len(fcf)}, index=idx)

    def income_statement(self, t):
        return self.inc

    def balance_sheet(self, t):
        return self.bal

    def cash_flow(self, t):
        return self.cf


def test_capital_allocation_payout_and_buyback_shrinkage():
    from brief import panel_capital_allocation

    d = panel_capital_allocation(_CapStub([100.0, 100.0], [30.0, 30.0], [50.0, 50.0], [100.0, 95.0]), "X")
    assert d["payout_of_fcf"] == pytest.approx(0.8)
    assert d["share_cagr"] == pytest.approx(-0.05)
    assert d["flags"] == []


def test_capital_allocation_flags_overpayment_and_dilution():
    from brief import panel_capital_allocation

    d = panel_capital_allocation(_CapStub([100.0, 100.0], [80.0, 80.0], [40.0, 40.0], [100.0, 104.0]), "X")
    assert d["payout_of_fcf"] == pytest.approx(1.2)
    assert len(d["flags"]) == 2


def test_stock_pay_reduces_fcf_and_offsetting_buybacks_are_not_returns():
    from brief import panel_capital_allocation

    stub = _CapStub([100.0, 100.0], [0.0, 0.0], [50.0, 50.0])
    stub.cf["stock_based_compensation"] = [20.0, 20.0]
    d = panel_capital_allocation(stub, "X")
    # FCF after stock pay = 80/yr; buybacks 50 of which 20 just offset dilution
    assert list(d["fcf"]) == [80.0, 80.0]
    assert d["payout_of_fcf"] == pytest.approx(60 / 160)
    assert d["sbc_share_of_buybacks"] == pytest.approx(0.4)
