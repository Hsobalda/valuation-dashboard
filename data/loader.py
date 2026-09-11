"""Cached data loading + a provider that serves one or many tickers.

`load_company` is cached (via @cache_data) so slider drags never re-fetch.
It tries live data first and falls back to bundled sample data -- with the
source recorded so the UI can banner it honestly.
"""

from __future__ import annotations

from .cache import cache_data
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
            return {"source": "live", "info": info, "market": market,
                    "income": income, "balance": balance, "cashflow": cashflow}
        except Exception:
            pass  # fall through to sample
    p = SampleProvider()
    return {"source": "sample", "info": p.company_info(ticker),
            "market": p.market_data(ticker),
            "income": p.income_statement(ticker),
            "balance": p.balance_sheet(ticker),
            "cashflow": p.cash_flow(ticker)}


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

    def fundamental_metrics(self, ticker: str) -> dict:
        d = self._get(ticker)
        return derive_metrics(d["info"], d["market"], d["income"], d["balance"], d["cashflow"])
