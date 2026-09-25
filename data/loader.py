"""Cached data loading + a provider that serves one or many tickers.

`load_company` is cached (via @cache_data) so slider drags never re-fetch.
It tries live data first and falls back to bundled sample data -- with the
source recorded so the UI can banner it honestly.
"""

from __future__ import annotations

import pandas as pd

from .cache import cache_data
from .edgar import EdgarClient
from .provider import SampleProvider, YFinanceProvider, derive_metrics

# Live-availability probe. Cached in a module global (persists across Streamlit
# reruns because loader.py is imported once): after the first failed live
# attempt we stop retrying and go straight to sample data.
_LIVE_OK: bool | None = None


def _live_available() -> bool:
    global _LIVE_OK
    if _LIVE_OK is None:
        try:
            p = YFinanceProvider()
            p.company_info("AAPL")
            _LIVE_OK = True
        except Exception:
            _LIVE_OK = False
    return _LIVE_OK


_EDGAR: EdgarClient | None = None


def cross_check(sec: pd.DataFrame, yahoo: pd.DataFrame, tolerance: float = 0.10) -> tuple[pd.DataFrame, list[str]]:
    """Drop SEC columns that disagree with Yahoo where both report the same years.

    SEC figures are assembled from XBRL tags that companies use inconsistently
    (Coca-Cola's debt came out at $1.5bn against $45bn), so a line is kept only
    if its median gap to Yahoo on overlapping years is within `tolerance`.
    Columns Yahoo doesn't have can't be checked and are kept.
    """
    bad = []
    for col in sec.columns.intersection(yahoo.columns):
        s, y = sec[col].align(yahoo[col], join="inner")
        both = s.notna() & y.notna() & (y.abs() > 0)
        if not both.any():
            continue
        gap = ((s[both] - y[both]).abs() / y[both].abs()).median()
        if gap > tolerance:
            bad.append(col)
    return sec.drop(columns=bad), bad


def _sec_statements(ticker: str, info: dict) -> dict | None:
    """SEC filings for US-dollar reporters; None when unavailable or not configured."""
    global _EDGAR
    if info.get("financial_currency") not in ("USD", ""):
        return None
    if _EDGAR is None:
        _EDGAR = EdgarClient.from_env()
    if _EDGAR is None:
        return None
    try:
        return _EDGAR.statements(ticker)
    except Exception:
        return None


@cache_data(ttl=86400)
def load_company(ticker: str) -> dict:
    """Return normalized data for one ticker: {source, info, market, income,
    balance, cashflow}. Falls back to sample data when live is unavailable."""
    if _live_available():
        try:
            p = YFinanceProvider()
            info = p.company_info(ticker)
            market = p.market_data(ticker)
            if not market.get("price"):
                raise RuntimeError("no market data")
            income = p.income_statement(ticker)
            balance = p.balance_sheet(ticker)
            cashflow = p.cash_flow(ticker)
            if income.empty and balance.empty and cashflow.empty:
                raise RuntimeError("no statements")
            # SEC filings give 15+ years; Yahoo fills any gaps (and is used alone
            # outside the US). A SEC line that disagrees with Yahoo is dropped.
            sec = _sec_statements(ticker, info)
            rejected: list[str] = []
            if sec:
                merged = {}
                for name, yahoo in (("income", income), ("balance", balance), ("cashflow", cashflow)):
                    checked, bad = cross_check(sec[name], yahoo)
                    merged[name] = checked.combine_first(yahoo)
                    rejected += bad
                income, balance, cashflow = merged["income"], merged["balance"], merged["cashflow"]
            try:
                consensus = p.consensus(ticker)
            except Exception:
                consensus = {}
            return {"source": "live", "info": info, "market": market,
                    "income": income, "balance": balance, "cashflow": cashflow,
                    "consensus": consensus, "sec_filings": bool(sec), "sec_rejected": rejected}
        except Exception:
            pass  # fall through to sample
    p = SampleProvider()
    return {"source": "sample", "info": p.company_info(ticker),
            "market": p.market_data(ticker),
            "income": p.income_statement(ticker),
            "balance": p.balance_sheet(ticker),
            "cashflow": p.cash_flow(ticker),
            "consensus": {}, "sec_filings": False, "sec_rejected": []}


@cache_data(ttl=86400)
def load_peer_suggestions(ticker: str, industry_key: str, sector_key: str) -> list[str]:
    if (industry_key or sector_key) and _live_available():
        try:
            return YFinanceProvider().peer_suggestions(ticker, industry_key, sector_key)
        except Exception:
            pass
    return [t for t in sample_tickers() if t != ticker]


@cache_data(ttl=86400)
def load_peer_profile(ticker: str) -> dict | None:
    if _live_available():
        try:
            return YFinanceProvider().peer_profile(ticker)
        except Exception:
            pass
    try:
        return SampleProvider().peer_profile(ticker)
    except KeyError:
        return None


def sample_tickers() -> list[str]:
    return SampleProvider()._tickers()


class MultiProvider:
    """Satisfies the DataProvider interface for one or many tickers, pulling
    from the cached `load_company`. Cheap to construct each rerun."""

    def __init__(self):
        self._cache: dict[str, dict] = {}

    def _get(self, ticker: str) -> dict:
        if ticker not in self._cache:
            self._cache[ticker] = load_company(ticker)
        return self._cache[ticker]

    def income_statement(self, ticker: str, period: str = "annual"):
        return self._get(ticker)["income"]

    def balance_sheet(self, ticker: str, period: str = "annual"):
        return self._get(ticker)["balance"]

    def cash_flow(self, ticker: str, period: str = "annual"):
        return self._get(ticker)["cashflow"]

    def company_info(self, ticker: str) -> dict:
        return self._get(ticker)["info"]

    def market_data(self, ticker: str) -> dict:
        return self._get(ticker)["market"]

    def source(self, ticker: str) -> str:
        return self._get(ticker)["source"]

    def consensus(self, ticker: str) -> dict:
        return self._get(ticker)["consensus"]

    def uses_sec_filings(self, ticker: str) -> bool:
        return self._get(ticker)["sec_filings"]

    def sec_rejected(self, ticker: str) -> list[str]:
        return self._get(ticker)["sec_rejected"]

    def peer_profiles(self, tickers: list[str]) -> list[dict]:
        return [p for p in (load_peer_profile(t) for t in tickers) if p]

    def peer_suggestions(self, ticker: str) -> list[str]:
        info = self.company_info(ticker)
        return load_peer_suggestions(ticker, info.get("industry_key", ""), info.get("sector_key", ""))

    def fundamental_metrics(self, ticker: str) -> dict:
        d = self._get(ticker)
        return derive_metrics(d["info"], d["market"], d["income"], d["balance"], d["cashflow"],
                              d["consensus"])
