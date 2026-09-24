"""Regression: the live provider fetches each statement independently, so a
ticker can have a cash flow history covering different fiscal years than its
income statement (observed for PYPL: yfinance's cashflow includes an extra
year the income_stmt omits). brief/panels.py must align statement-derived
series on their common fiscal years before comparing or dividing them,
instead of raising `ValueError: Can only compare identically-labeled Series
objects`."""

import pandas as pd
import pytest

from brief import build_brief
from brief.panels import _align_years, panel_risk
from data.provider import SampleProvider


class MisalignedYearProvider(SampleProvider):
    """Cash flow statement has one extra fiscal year the income statement
    lacks -- reproduces the PYPL index mismatch without hitting the network.
    """

    def cash_flow(self, ticker, period="annual"):
        df = super().cash_flow(ticker, period)
        extra_year = min(df.index) - 1
        extra_row = df.iloc[[0]].copy()
        extra_row.index = [extra_year]
        return pd.concat([extra_row, df]).sort_index()


def test_align_years_returns_common_index_and_dropped_years():
    a = pd.Series([1.0, 2.0, 3.0], index=[2020, 2021, 2022])
    b = pd.Series([10.0, 20.0], index=[2021, 2022])
    a_aligned, b_aligned, dropped = _align_years(a, b)
    assert list(a_aligned.index) == [2021, 2022]
    assert list(b_aligned.index) == [2021, 2022]
    assert dropped == [2020]


def test_align_years_no_mismatch_returns_no_dropped_years():
    a = pd.Series([1.0, 2.0], index=[2020, 2021])
    b = pd.Series([10.0, 20.0], index=[2020, 2021])
    _, _, dropped = _align_years(a, b)
    assert dropped == []


def test_comparing_raw_misaligned_series_raises():
    """Documents the bug being fixed: pandas comparison operators require
    identically-labeled Series, unlike arithmetic which silently aligns."""
    fcf = pd.Series([1.0, 2.0, 3.0], index=[2019, 2020, 2021])
    ni = pd.Series([1.0, 2.0], index=[2020, 2021])
    with pytest.raises(ValueError):
        fcf < ni  # noqa: B015 -- intentional, asserts the failure mode


def test_panel_risk_tolerates_misaligned_fiscal_years():
    p = MisalignedYearProvider()
    risk = panel_risk(p, "AAPL")
    assert isinstance(risk["net_debt_to_ebitda"], pd.Series)
    assert any("mismatched fiscal years" in f for f in risk["flags"])


def test_build_brief_tolerates_misaligned_fiscal_years():
    p = MisalignedYearProvider()
    brief = build_brief(p, "AAPL", reference_wacc=0.09)
    assert brief["risk"]["flags"] is not None
