"""Data access layer -- the ONLY layer that talks to external data sources.

Two providers implement the same interface:
  * YFinanceProvider -- live Yahoo Finance (works on a normal machine).
  * SampleProvider   -- bundled offline data (works offline / in sandboxes).

Swap/implement new providers (FMP, Alpha Vantage, ...) without touching the
engine, brief, or UI: they all depend only on `DataProvider`.
"""

from __future__ import annotations

from typing import Protocol

import pandas as pd

from . import schema as S
from .sample_data import COMPANIES, to_dataframes


class DataProvider(Protocol):
    def income_statement(self, ticker: str, period: str = "annual") -> pd.DataFrame: ...
    def balance_sheet(self, ticker: str, period: str = "annual") -> pd.DataFrame: ...
    def cash_flow(self, ticker: str, period: str = "annual") -> pd.DataFrame: ...
    def market_data(self, ticker: str) -> dict: ...
    def company_info(self, ticker: str) -> dict: ...
    def fundamental_metrics(self, ticker: str) -> dict: ...


# --- shared derivation ------------------------------------------------------

def _latest(series: pd.Series) -> float:
    """Most recent non-NaN value of a (year-indexed) series, else 0.0."""
    clean = series.dropna()
    if clean.empty:
        return 0.0
    return float(clean.iloc[-1])


def derive_metrics(info: dict, market: dict, income: pd.DataFrame,
                   balance: pd.DataFrame, cashflow: pd.DataFrame) -> dict:
    """Compute the fundamental_metrics dict from normalized statements."""
    def f(df, field):
        return _latest(df[field]) if field in df.columns else 0.0

    revenue = f(income, "revenue")
    oi = f(income, "operating_income")
    da = f(income, "depreciation_amortization")
    ebitda = oi + da
    eps = f(income, "eps_diluted")
    net_income = f(income, "net_income")
    cash = f(balance, "cash_and_equiv")
    st_inv = f(balance, "short_term_investments")
    debt = f(balance, "total_debt")
    equity = f(balance, "stockholder_equity")
    minority = f(balance, "minority_interest")
    shares = market.get("shares_outstanding", 0.0)
    net_debt = debt - cash - st_inv
    bvps = equity / shares if shares else 0.0
    fcf = f(cashflow, "operating_cash_flow") - f(cashflow, "capital_expenditure")

    return {
        "revenue": revenue,
        "ebitda": ebitda,
        "eps": eps,
        "bvps": bvps,
        "net_income": net_income,
        "fcf": fcf,
        "market_cap": market.get("market_cap", 0.0),
        "net_debt": net_debt,
        "cash": cash,
        "minority_interest": minority,
        "beta": info.get("beta", 0.0),
        "price": market.get("price", 0.0),
        "shares_outstanding": market.get("shares_outstanding", 0.0),
        "shares_diluted": market.get("shares_diluted", market.get("shares_outstanding", 0.0)),
    }


# --- sample (offline) provider ----------------------------------------------

class SampleProvider:
    """Loads bundled offline data. Clearly non-live."""

    is_live = False

    def __init__(self):
        self._frames = {t: to_dataframes(c) for t, c in COMPANIES.items()}

    def _tickers(self) -> list[str]:
        return list(COMPANIES.keys())

    def company_info(self, ticker: str) -> dict:
        self._check(ticker)
        return dict(COMPANIES[ticker]["info"])

    def market_data(self, ticker: str) -> dict:
        self._check(ticker)
        return dict(COMPANIES[ticker]["market"])

    def income_statement(self, ticker: str, period: str = "annual") -> pd.DataFrame:
        self._check(ticker)
        return self._frames[ticker]["income"]

    def balance_sheet(self, ticker: str, period: str = "annual") -> pd.DataFrame:
        self._check(ticker)
        return self._frames[ticker]["balance"]

    def cash_flow(self, ticker: str, period: str = "annual") -> pd.DataFrame:
        self._check(ticker)
        return self._frames[ticker]["cashflow"]

    def fundamental_metrics(self, ticker: str) -> dict:
        self._check(ticker)
        return derive_metrics(
            self.company_info(ticker),
            self.market_data(ticker),
            self.income_statement(ticker),
            self.balance_sheet(ticker),
            self.cash_flow(ticker),
        )

    def _check(self, ticker: str):
        if ticker not in COMPANIES:
            raise KeyError(
                f"{ticker!r} not in offline sample data. Available: "
                f"{', '.join(self._tickers())}"
            )


# --- live (yfinance) provider -----------------------------------------------

class YFinanceProvider:
    """Live data via yfinance. Not exercised in the offline sandbox."""

    is_live = True

    def __init__(self):
        import yfinance as yf  # deferred import: only this layer may import it

        self._yf = yf

    def _ticker(self, ticker: str):
        return self._yf.Ticker(ticker)

    @staticmethod
    def _normalize(raw: pd.DataFrame, mapping: dict) -> pd.DataFrame:
        out = {}
        for field, candidates in mapping.items():
            row = S.pick_row(raw, candidates)
            if row is not None:
                # yfinance columns are Period objects -> use .year; index ascending
                s = row.copy()
                s.index = [getattr(i, "year", i) for i in s.index]
                s = s.sort_index()
                out[field] = s
        if not out:
            return pd.DataFrame()
        df = pd.DataFrame(out)
        return df

    def income_statement(self, ticker: str, period: str = "annual") -> pd.DataFrame:
        raw = self._ticker(ticker).income_stmt
        df = self._normalize(raw, S.YF_INCOME_MAP)
        # sign normalisation: capex/dividends handled in cash_flow; income is fine
        return self._sign_fix_income(df)

    def _sign_fix_income(self, df: pd.DataFrame) -> pd.DataFrame:
        # cost_of_revenue sometimes reported as negative -> make positive
        if "cost_of_revenue" in df.columns:
            df["cost_of_revenue"] = df["cost_of_revenue"].abs()
        if "interest_expense" in df.columns:
            df["interest_expense"] = df["interest_expense"].abs()
        return df

    def balance_sheet(self, ticker: str, period: str = "annual") -> pd.DataFrame:
        raw = self._ticker(ticker).balance_sheet
        return self._normalize(raw, S.YF_BALANCE_MAP)

    def cash_flow(self, ticker: str, period: str = "annual") -> pd.DataFrame:
        raw = self._ticker(ticker).cashflow
        df = self._normalize(raw, S.YF_CASHFLOW_MAP)
        # store cash outflows as positive magnitudes (schema convention)
        for field in ("capital_expenditure", "dividends_paid", "stock_buybacks"):
            if field in df.columns:
                df[field] = df[field].abs()
        return df

    def company_info(self, ticker: str) -> dict:
        info = self._ticker(ticker).info or {}
        return {
            "name": info.get("shortName") or info.get("longName") or ticker,
            "sector": info.get("sector", ""),
            "industry": info.get("industry", ""),
            "summary": info.get("longBusinessSummary", ""),
            "currency": info.get("currency", "USD"),
            "beta": float(info.get("beta") or 0.0),
        }

    def market_data(self, ticker: str) -> dict:
        info = self._ticker(ticker).info or {}
        return {
            "price": float(info.get("currentPrice") or info.get("regularMarketPrice") or 0.0),
            "market_cap": float(info.get("marketCap") or 0.0),
            "shares_outstanding": float(info.get("sharesOutstanding") or 0.0),
            "shares_diluted": float(info.get("sharesOutstanding") or 0.0),
        }

    def fundamental_metrics(self, ticker: str) -> dict:
        return derive_metrics(
            self.company_info(ticker),
            self.market_data(ticker),
            self.income_statement(ticker),
            self.balance_sheet(ticker),
            self.cash_flow(ticker),
        )
