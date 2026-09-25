import pandas as pd
import pytest

from brief import derive_starting_assumptions
from brief.seeds import MAX_SEED_GROWTH, moat_rating
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
    assert s["growth_y1"] == s["growth_y2"] == MAX_SEED_GROWTH
    assert "capped" in s["provenance"]["growth_y1"]


def test_target_margin_is_halfway_to_median_so_one_bad_year_does_not_set_normal():
    s = derive_starting_assumptions(_Rebound(), "AAPL")
    margins = pd.Series([0.20, -0.75, 1 / 6, 25 / 130, 0.20, 0.20])
    assert s["target_ebit_margin"] == pytest.approx((0.20 + margins.median()) / 2)


def test_no_positive_roic_history_seeds_cost_of_capital():
    s = derive_starting_assumptions(_Rebound(), "AAPL")
    assert s["roic"] == s["discount_rate"]


def test_moat_rating_from_roic_against_cost_of_capital():
    wide = moat_rating(pd.Series([0.30, 0.28, 0.32, 0.29, 0.31]), 0.08)
    narrow = moat_rating(pd.Series([0.12, 0.07, 0.11, 0.10, 0.06]), 0.08)
    none = moat_rating(pd.Series([0.05, 0.09, 0.04, 0.06, 0.03]), 0.08)
    assert (wide["fade_years"], narrow["fade_years"], none["fade_years"]) == (20, 10, 5)
    assert "5 of 5 years" in wide["reason"]
