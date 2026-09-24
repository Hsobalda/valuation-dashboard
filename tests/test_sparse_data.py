"""Regression: live (yfinance) data can omit statement rows entirely, so the
brief panels and assumption seeds must tolerate missing columns (goodwill,
short-term investments, cost_of_revenue, pretax, D&A, etc.) instead of raising
KeyError."""

from brief import build_brief, derive_starting_assumptions
from data.provider import SampleProvider

_DROP_INCOME = ["cost_of_revenue", "depreciation_amortization", "pretax_income", "income_tax"]
_DROP_BALANCE = ["goodwill", "short_term_investments", "minority_interest"]


class SparseProvider(SampleProvider):
    def income_statement(self, ticker, period="annual"):
        df = super().income_statement(ticker, period)
        return df.drop(columns=[c for c in _DROP_INCOME if c in df.columns])

    def balance_sheet(self, ticker, period="annual"):
        df = super().balance_sheet(ticker, period)
        return df.drop(columns=[c for c in _DROP_BALANCE if c in df.columns])


def test_build_brief_tolerates_missing_columns():
    p = SparseProvider()
    brief = build_brief(p, "AAPL")
    assert brief["quality"]["goodwill_pct_assets"] == 0.0
    assert brief["risk"]["flags"] == []
    assert brief["history"]["revenue_cagr"] > 0


def test_seeds_tolerate_missing_columns():
    p = SparseProvider()
    s = derive_starting_assumptions(p, "AAPL")
    assert s["tax_rate"] == 0.21  # falls back to default when pretax absent
    assert s["da_pct_revenue"] == 0.0
