"""Data access layer -- the ONLY layer that talks to external data sources.

Two providers implement the same interface:
  * YFinanceProvider -- live Yahoo Finance (works on a normal machine).
  * SampleProvider   -- bundled offline data (works offline / in sandboxes).

Swap/implement new providers (FMP, Alpha Vantage, ...) without touching the
engine, brief, or UI: they all depend only on `DataProvider`.
"""

from __future__ import annotations

import datetime as dt
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
    def consensus(self, ticker: str) -> dict: ...
    def peer_profile(self, ticker: str) -> dict: ...


# --- shared derivation ------------------------------------------------------

def _latest(series: pd.Series) -> float:
    """Most recent non-NaN value of a (year-indexed) series, else 0.0."""
    clean = series.dropna()
    if clean.empty:
        return 0.0
    return float(clean.iloc[-1])


def _years_since(iso_date: str | None) -> float:
    """Years from the base fiscal year end to today; 0 when unknown (sample data)."""
    if not iso_date:
        return 0.0
    days = (dt.date.today() - dt.date.fromisoformat(iso_date)).days
    return min(max(days / 365.25, 0.0), 1.5)


def derive_metrics(info: dict, market: dict, income: pd.DataFrame,
                   balance: pd.DataFrame, cashflow: pd.DataFrame,
                   consensus: dict | None = None) -> dict:
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
    st_inv = f(balance, "short_term_investments") + f(balance, "long_term_investments")
    debt = f(balance, "total_debt")
    equity = f(balance, "stockholder_equity")
    minority = f(balance, "minority_interest")
    shares = market.get("shares_outstanding", 0.0)
    # Current share count grossed up by last year's dilution ratio. Using the
    # average diluted count directly would overstate shares for companies that
    # have been buying stock back since.
    basic_avg, diluted_avg = f(income, "shares_basic_avg"), f(income, "shares_diluted_avg")
    dilution = diluted_avg / basic_avg if basic_avg > 0 and diluted_avg > 0 else 1.0
    shares_diluted = shares * max(dilution, 1.0)
    net_debt = debt - cash - st_inv
    bvps = equity / shares if shares else 0.0
    fcf = (f(cashflow, "operating_cash_flow") - f(cashflow, "capital_expenditure")
           - f(cashflow, "stock_based_compensation"))

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
        "shares_diluted": shares_diluted,
        "eps_forward": market.get("eps_forward", 0.0),
        # e.g. a US-listed foreign share: price in USD, statements in KRW, so
        # per-share ratios are meaningless without FX and ADR-ratio adjustments
        "currency_mismatch": bool(info.get("financial_currency"))
                             and info.get("financial_currency") != info.get("currency"),
        "revenue_forward": (consensus or {}).get("revenue_y1", 0.0),
        "years_since_fy_end": _years_since(market.get("fiscal_year_end")),
    }


def exclude_operating_leases(balance: pd.DataFrame) -> pd.DataFrame:
    """Take lease liabilities out of debt for a US GAAP company.

    Yahoo's total debt includes lease liabilities. Under IFRS 16 that is
    consistent: lease cost sits below EBIT (depreciation plus interest), so
    leases are financing. Under US GAAP (ASC 842) operating-lease rent is
    already deducted in EBIT, so also counting the liability as debt charges for
    the leases twice. Yahoo doesn't split operating from finance leases, so the
    whole line is treated as operating, which slightly flatters companies with
    large finance leases.
    """
    if "lease_liabilities" not in balance.columns or "total_debt" not in balance.columns:
        return balance
    out = balance.copy()
    out["total_debt"] = (out["total_debt"] - out["lease_liabilities"].fillna(0.0)).clip(lower=0.0)
    return out


# --- sample (offline) provider ----------------------------------------------

class SampleProvider:
    """Loads bundled offline data. Clearly non-live."""

    is_live = False

    def __init__(self):
        self._frames = {t: to_dataframes(c) for t, c in COMPANIES.items()}

    def _tickers(self) -> list[str]:
        return list(COMPANIES.keys())

    def peer_profile(self, ticker: str) -> dict:
        self._check(ticker)
        info, inc = COMPANIES[ticker]["info"], self._frames[ticker]["income"]
        return {
            "ticker": ticker,
            "price": COMPANIES[ticker]["market"]["price"],
            "name": info["name"],
            "industry": info["industry"],
            "sector": info["sector"],
            "market_cap": COMPANIES[ticker]["market"]["market_cap"],
            "operating_margin": float(inc["operating_income"].iloc[-1] / inc["revenue"].iloc[-1]),
            "reports_ebitda": True,
            "currency_mismatch": False,
        }

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

    def consensus(self, ticker: str) -> dict:
        return {}

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

def is_foreign_us_listing(country: str, quote_currency: str) -> bool:
    """A non-US company's US-dollar listing (usually an ADR): converting currency
    isn't enough, since one ADR can represent several home shares."""
    return quote_currency == "USD" and country not in ("United States", "")


def convert_currency(df: pd.DataFrame, rate: float) -> pd.DataFrame:
    """Scale every money column by `rate`; share counts are left alone."""
    if rate == 1.0 or df.empty:
        return df
    out = df.copy()
    money = [c for c in out.columns if c not in ("shares_basic_avg", "shares_diluted_avg")]
    out[money] = out[money] * rate
    return out


class YFinanceProvider:
    """Live data via yfinance. Not exercised in the offline sandbox."""

    is_live = True

    def __init__(self):
        import yfinance as yf  # deferred import: only this layer may import it

        self._yf = yf
        self._fx_cache: dict[str, float] = {}

    def _ticker(self, ticker: str):
        return self._yf.Ticker(ticker)

    # Some exchanges quote prices in minor units (London in pence) while market
    # cap and financial statements are in the major unit.
    _MINOR_UNITS = {"GBp": "GBP", "GBX": "GBP", "ZAc": "ZAR", "ILA": "ILS"}

    def _currencies(self, info: dict) -> tuple[str, str]:
        """(quote currency, reporting currency), minor units mapped to major."""
        cur = self._MINOR_UNITS.get(info.get("currency"), info.get("currency", ""))
        fin = self._MINOR_UNITS.get(info.get("financialCurrency"), info.get("financialCurrency", "")) or cur
        return cur, fin

    def _fx(self, ticker: str) -> float:
        """Rate taking reported figures into the quote currency, for a home listing
        that reports in another currency (Shell: dollar accounts, sterling shares).
        Every year uses today's rate, so growth rates and margins are unchanged.
        1.0 when no conversion is needed, or for a foreign US listing, which stays
        flagged as mismatched."""
        if ticker not in self._fx_cache:
            info = self._ticker(ticker).info or {}
            cur, fin = self._currencies(info)
            rate = 1.0
            if fin != cur and not is_foreign_us_listing(info.get("country", ""), cur):
                rate = float(self._yf.Ticker(f"{fin}{cur}=X").fast_info["last_price"])
            self._fx_cache[ticker] = rate
        return self._fx_cache[ticker]

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
        return convert_currency(self._sign_fix_income(df), self._fx(ticker))

    def _sign_fix_income(self, df: pd.DataFrame) -> pd.DataFrame:
        # cost_of_revenue sometimes reported as negative -> make positive
        if "cost_of_revenue" in df.columns:
            df["cost_of_revenue"] = df["cost_of_revenue"].abs()
        if "interest_expense" in df.columns:
            df["interest_expense"] = df["interest_expense"].abs()
        return df

    def balance_sheet(self, ticker: str, period: str = "annual") -> pd.DataFrame:
        raw = self._ticker(ticker).balance_sheet
        df = self._normalize(raw, S.YF_BALANCE_MAP)
        country = (self._ticker(ticker).info or {}).get("country", "")
        df = exclude_operating_leases(df) if country == "United States" else df
        return convert_currency(df, self._fx(ticker))

    def cash_flow(self, ticker: str, period: str = "annual") -> pd.DataFrame:
        raw = self._ticker(ticker).cashflow
        df = self._normalize(raw, S.YF_CASHFLOW_MAP)
        # store cash outflows as positive magnitudes (schema convention)
        for field in ("capital_expenditure", "dividends_paid", "stock_buybacks", "stock_based_compensation"):
            if field in df.columns:
                df[field] = df[field].abs()
        return convert_currency(df, self._fx(ticker))

    def company_info(self, ticker: str) -> dict:
        info = self._ticker(ticker).info or {}
        cur, fin = self._currencies(info)
        rate = self._fx(ticker)
        return {
            "name": info.get("shortName") or info.get("longName") or ticker,
            "sector": info.get("sector", ""),
            "reports_ebitda": info.get("ebitda") is not None,
            "industry": info.get("industry", ""),
            "summary": info.get("longBusinessSummary", ""),
            "currency": cur or "USD",
            # after conversion the statements are in the quote currency
            "financial_currency": cur if rate != 1.0 else fin,
            "reported_currency": fin,
            "fx_rate": rate,
            "industry_key": info.get("industryKey", ""),
            "sector_key": info.get("sectorKey", ""),
            "beta": float(info.get("beta") or 0.0),
        }

    def market_data(self, ticker: str) -> dict:
        info = self._ticker(ticker).info or {}
        # prices and price targets share the quote currency (pence in London)
        unit = 100.0 if info.get("currency") in self._MINOR_UNITS else 1.0
        price = float(info.get("currentPrice") or info.get("regularMarketPrice") or 0.0) / unit
        fy_end = info.get("lastFiscalYearEnd")
        return {
            "fiscal_year_end": dt.date.fromtimestamp(fy_end).isoformat() if fy_end else None,
            "price": price,
            "eps_forward": float(info.get("forwardEps") or 0.0) * self._fx(ticker),  # reported currency
            "target_mean": float(info.get("targetMeanPrice") or 0.0) / unit,
            "target_low": float(info.get("targetLowPrice") or 0.0) / unit,
            "target_high": float(info.get("targetHighPrice") or 0.0) / unit,
            "analyst_count": int(info.get("numberOfAnalystOpinions") or 0),
            "market_cap": float(info.get("marketCap") or 0.0),
            "shares_outstanding": float(info.get("sharesOutstanding") or 0.0),
        }

    def peer_profile(self, ticker: str) -> dict:
        """What's needed to judge a candidate peer, from one cheap info call."""
        info = self._ticker(ticker).info or {}
        cur, fin = self._currencies(info)
        unit = 100.0 if info.get("currency") in self._MINOR_UNITS else 1.0
        return {
            "ticker": ticker,
            "price": float(info.get("currentPrice") or info.get("regularMarketPrice") or 0.0) / unit,
            "name": info.get("shortName") or ticker,
            "industry": info.get("industry", ""),
            "sector": info.get("sector", ""),
            "market_cap": float(info.get("marketCap") or 0.0),
            "operating_margin": info.get("operatingMargins"),
            "reports_ebitda": info.get("ebitda") is not None,
            "currency_mismatch": fin != cur and is_foreign_us_listing(info.get("country", ""), cur),
        }

    def consensus(self, ticker: str) -> dict:
        """Analyst consensus revenue for the current and next fiscal year."""
        est = self._ticker(ticker).revenue_estimate
        if est is None or est.empty or not {"0y", "+1y"} <= set(est.index):
            return {}
        rate = self._fx(ticker)  # estimates are in the reporting currency
        return {
            "revenue_y1": float(est.loc["0y", "avg"]) * rate,
            "revenue_y2": float(est.loc["+1y", "avg"]) * rate,
            "analysts": int(est.loc["0y", "numberOfAnalysts"]),
        }

    def peer_suggestions(self, ticker: str, industry_key: str, sector_key: str,
                         limit: int = 8) -> list[str]:
        """Same-industry companies at least 1/20th of the target's size, topped up
        with the sector's largest companies when the industry is too thin (e.g.
        Apple is ~100% of Yahoo's "consumer electronics")."""
        peers: list[str] = []
        if industry_key:
            top = self._yf.Industry(industry_key).top_companies
            if top is not None and not top.empty:
                weights = top["market weight"].fillna(0.0)
                floor = weights[ticker] / 20 if ticker in weights.index else 0.01
                peers = [s for s, w in weights.items() if s != ticker and w >= floor]
        if len(peers) < 3 and sector_key:
            top = self._yf.Sector(sector_key).top_companies
            if top is not None:
                peers += [s for s in top.index if s != ticker and s not in peers]
        return peers[:limit]

    def fundamental_metrics(self, ticker: str) -> dict:
        return derive_metrics(
            self.company_info(ticker),
            self.market_data(ticker),
            self.income_statement(ticker),
            self.balance_sheet(ticker),
            self.cash_flow(ticker),
            self.consensus(ticker),
        )
