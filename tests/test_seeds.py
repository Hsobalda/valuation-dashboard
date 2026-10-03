import pandas as pd
import pytest

from brief import derive_starting_assumptions
from brief.seeds import DISCOUNT_RANGE, MAX_SEED_GROWTH, moat_rating
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


class _LowBetaHeavyDebt(SampleProvider):
    """A low-beta, heavily-indebted company (Verizon's shape): CAPM alone would
    put its cost of equity near 6.5%, but heavy, cheap debt pulls the blended
    WACC below that -- the floor exists for exactly this combination."""

    def company_info(self, ticker):
        return {**super().company_info(ticker), "beta": 0.24}

    def balance_sheet(self, ticker, period="annual"):
        bal = super().balance_sheet(ticker).copy()
        # wacc() weights by *market* cap, not book equity, so the debt has to
        # dwarf market cap (not book equity) to dominate the blend
        market_cap = super().market_data(ticker)["market_cap"]
        bal["total_debt"] = market_cap * 4
        return bal

    def income_statement(self, ticker, period="annual"):
        inc = super().income_statement(ticker).copy()
        inc["interest_expense"] = inc["interest_expense"] * 0  # ~0% cost of debt: falls back to risk-free
        return inc


def test_discount_rate_floored_when_low_beta_and_heavy_debt_blend_too_low():
    s = derive_starting_assumptions(_LowBetaHeavyDebt(), "AAPL")
    assert s["wacc_reference"]["wacc"] < DISCOUNT_RANGE[0]
    assert s["discount_rate"] == DISCOUNT_RANGE[0]
    assert "floor was used instead" in s["provenance"]["discount_rate"]


def test_moat_rating_from_roic_against_cost_of_capital():
    wide = moat_rating(pd.Series([0.30, 0.28, 0.32, 0.29, 0.31]), 0.08)
    narrow = moat_rating(pd.Series([0.12, 0.07, 0.11, 0.10, 0.06]), 0.08)
    none = moat_rating(pd.Series([0.05, 0.09, 0.04, 0.06, 0.03]), 0.08)
    assert (wide["fade_years"], narrow["fade_years"], none["fade_years"]) == (20, 10, 5)
    assert "5 of 5 years" in wide["reason"]


def test_history_warning_for_short_or_loss_making_records():
    import pandas as pd

    from brief.seeds import _history_warning

    four_years = pd.Series([-0.10, -0.03, 0.01, 0.04], index=[2022, 2023, 2024, 2025])
    w = _history_warning(four_years, float(four_years.median()))
    assert "only 4 years" in w and "a loss" in w
    decade = pd.Series([0.2] * 10, index=range(2016, 2026))
    assert _history_warning(decade, 0.2) == ""


def test_tax_rate_seed_not_below_global_minimum():
    import pandas as pd

    from brief import derive_starting_assumptions
    from data.provider import SampleProvider

    p = SampleProvider()
    inc = p.income_statement("AAPL").copy()
    inc["income_tax"] = 0.0  # one-off credits wiping out the tax charge
    p.income_statement = lambda t, period="annual": inc
    seed = derive_starting_assumptions(p, "AAPL")
    assert seed["tax_rate"] == 0.15
    assert "global minimum" in seed["provenance"]["tax_rate"]
