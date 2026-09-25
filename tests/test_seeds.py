import pandas as pd

from brief import derive_starting_assumptions
from brief.seeds import DISCOUNT_RATE, MAX_SEED_GROWTH
from data.provider import SampleProvider


class _Rebound(SampleProvider):
    """AAPL sample data reshaped into a shutdown year followed by a rebound."""

    def income_statement(self, ticker, period="annual"):
        inc = super().income_statement(ticker).copy()
        inc["revenue"] = [100.0, 40.0, 90.0, 130.0, 150.0, 160.0]
        inc["operating_income"] = [20.0, -30.0, 15.0, 25.0, 30.0, 32.0]
        return inc

    def balance_sheet(self, ticker, period="annual"):
        bal = super().balance_sheet(ticker).copy()
        bal["stockholder_equity"] = -bal["total_debt"]  # no usable invested capital
        return bal


class _ReboundFromTrough(_Rebound):
    def income_statement(self, ticker, period="annual"):
        inc = super().income_statement(ticker)
        inc["revenue"] = [40.0, 60.0, 90.0, 130.0, 150.0, 160.0]  # 32% CAGR off a trough
        return inc


def test_seed_growth_capped_and_flagged():
    s = derive_starting_assumptions(_ReboundFromTrough(), "AAPL")
    assert s["revenue_growth"] == MAX_SEED_GROWTH
    assert "capped" in s["provenance"]["revenue_growth"]


def test_target_margin_is_median_so_one_bad_year_does_not_set_normal():
    s = derive_starting_assumptions(_Rebound(), "AAPL")
    margins = pd.Series([0.20, -0.75, 1 / 6, 25 / 130, 0.20, 0.20])
    assert s["target_ebit_margin"] == margins.median()


def test_no_positive_roic_history_seeds_discount_rate():
    s = derive_starting_assumptions(_Rebound(), "AAPL")
    assert s["roic"] == DISCOUNT_RATE
