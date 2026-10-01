"""Annual financial statements for US filers from SEC EDGAR XBRL company facts.

EDGAR gives 15+ years straight from 10-K filings, against Yahoo's 4-5. The SEC's
fair-access policy requires every request to identify itself with a contact
email in the User-Agent; set SEC_CONTACT_EMAIL (or the Streamlit secret of the
same name). Without it EDGAR is skipped and Yahoo's statements are used.
"""

from __future__ import annotations

import datetime as dt
import math
import os
import statistics
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

CONTACT_ENV = "SEC_CONTACT_EMAIL"
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
_ARCHIVE_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{accession}/{document}"
_MAX_REQUESTS_PER_SECOND = 8  # the SEC's fair-access limit is 10

# normalized field -> us-gaap tags, preferred first. Companies switch tags over
# time (Apple moved from SalesRevenueNet to RevenueFromContractWith... in 2017),
# so every tag is read and merged year by year.
INCOME_TAGS = {
    "revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet",
                "RevenueFromContractWithCustomerIncludingAssessedTax"],
    "cost_of_revenue": ["CostOfRevenue", "CostOfGoodsAndServicesSold", "CostOfGoodsSold"],
    "gross_profit": ["GrossProfit"],
    "operating_income": ["OperatingIncomeLoss"],
    "depreciation_amortization": ["DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet",
                                  "DepreciationAndAmortization", "Depreciation"],
    "interest_expense": ["InterestExpense", "InterestExpenseNonoperating", "InterestExpenseDebt"],
    "pretax_income": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
                      "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],
    "income_tax": ["IncomeTaxExpenseBenefit"],
    "net_income": ["NetIncomeLoss", "ProfitLoss"],
    "eps_diluted": ["EarningsPerShareDiluted"],
    "shares_basic_avg": ["WeightedAverageNumberOfSharesOutstandingBasic"],
    "shares_diluted_avg": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
}
BALANCE_TAGS = {
    "cash_and_equiv": ["CashAndCashEquivalentsAtCarryingValue",
                       "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
    "short_term_investments": ["ShortTermInvestments", "MarketableSecuritiesCurrent",
                               "AvailableForSaleSecuritiesDebtSecuritiesCurrent"],
    "total_assets": ["Assets"],
    "total_liabilities": ["Liabilities"],
    "stockholder_equity": ["StockholdersEquity",
                           "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "minority_interest": ["MinorityInterest"],
    "goodwill": ["Goodwill"],
    # explicitly non-current marketable securities: cash-like, but outside cash
    # and short-term investments (Apple holds ~$78bn)
    "long_term_investments": ["MarketableSecuritiesNoncurrent", "AvailableForSaleSecuritiesDebtSecuritiesNoncurrent"],
}
# Total debt: a reported total where one exists, else assembled from parts.
# Tagging varies a lot between companies, so the loader cross-checks the result
# against Yahoo and drops it when they disagree. Operating lease liabilities are
# excluded, consistent with US GAAP rent sitting inside EBIT.
_DEBT_GRAND_TOTAL = ["DebtLongtermAndShorttermCombinedAmount"]
_DEBT_TOTAL = ["LongTermDebt", "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities"]
_DEBT_NONCURRENT = ["LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"]
_DEBT_CURRENT = ["LongTermDebtCurrent", "LongTermDebtAndCapitalLeaseObligationsCurrent"]
_DEBT_SHORT = ["CommercialPaper", "ShortTermBorrowings"]
CASHFLOW_TAGS = {
    "operating_cash_flow": ["NetCashProvidedByUsedInOperatingActivities",
                            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "capital_expenditure": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "dividends_paid": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
    "stock_buybacks": ["PaymentsForRepurchaseOfCommonStock"],
    "stock_based_compensation": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
}


def _reports(gaap: dict, tag: str, instant: bool) -> dict[str, list[tuple[str, float]]]:
    """Every annual 10-K value of one tag, as (filing date, value) by period end."""
    out: dict[str, list[tuple[str, float]]] = {}
    for unit_facts in gaap.get(tag, {}).get("units", {}).values():
        for f in unit_facts:
            if not f.get("form", "").startswith("10-K"):
                continue
            if instant != ("start" not in f):
                continue
            if not instant:
                days = (dt.date.fromisoformat(f["end"]) - dt.date.fromisoformat(f["start"])).days
                if not 350 <= days <= 380:  # full years only, not quarters
                    continue
            out.setdefault(f["end"], []).append((f["filed"], float(f["val"])))
    return out


def _facts(gaap: dict, tag: str, instant: bool) -> pd.Series:
    """One tag's annual 10-K values, keyed by period end date; restatements win."""
    return pd.Series({end: max(vals, key=lambda v: v[0])[1]
                      for end, vals in _reports(gaap, tag, instant).items()}, dtype=float)


def _restatements(reports: dict[str, list[tuple[str, float]]]) -> dict[str, float]:
    """Filing date -> ratio by which that filing changed earlier years' figures,
    ignoring routine restatements of a few percent."""
    seen: dict[str, list[float]] = {}
    for vals in reports.values():
        vals = sorted(vals)
        for (_, old), (filed, new) in zip(vals, vals[1:]):
            if old and not 0.8 < new / old < 1.25:
                seen.setdefault(filed, []).append(new / old)
    return {filed: statistics.median(ratios) for filed, ratios in seen.items()}


def _share_basis(gaap: dict) -> tuple[pd.Series, pd.Series]:
    """Multipliers, by period end, that put share counts and EPS on today's share basis.

    A 10-K restates share counts and EPS for a stock split, but only for the
    three years it presents, so older years stay as first filed (Nvidia's FY2019
    count predates its 4-for-1 and 10-for-1 splits). Where a later filing gives
    a different count for the same year, the ratio is the split, and it applies
    to every year last reported before that filing. EPS moves the other way,
    unless the filing left EPS alone: then it was correcting a count reported in
    thousands, not a split.
    """
    tags = INCOME_TAGS["shares_diluted_avg"] + INCOME_TAGS["shares_basic_avg"]
    shares = next((r for r in (_reports(gaap, t, instant=False) for t in tags) if r), {})
    eps = _reports(gaap, INCOME_TAGS["eps_diluted"][0], instant=False)
    share_x, eps_x = _restatements(shares), _restatements(eps)
    # EPS alone gets restated for other reasons (GE's discontinued operations),
    # so a split needs the share count to confirm it
    eps_x = {filed: 1 / share_x[filed] for filed in eps_x if filed in share_x}

    def factors(reports: dict, ratios: dict[str, float]) -> pd.Series:
        return pd.Series({end: math.prod(r for filed, r in ratios.items() if filed > max(vals)[0])
                          for end, vals in reports.items()}, dtype=float)

    return factors(shares, share_x), factors(eps, eps_x)


def _merged(gaap: dict, tags: list[str], instant: bool) -> pd.Series:
    out = pd.Series(dtype=float)
    for tag in tags:
        out = out.combine_first(_facts(gaap, tag, instant)) if not out.empty else _facts(gaap, tag, instant)
    return out


def _by_year(s: pd.Series, fy_ends: dict[int, str]) -> pd.Series:
    """Keep values dated at a fiscal year end and index them by fiscal year."""
    return pd.Series({y: s[end] for y, end in fy_ends.items() if end in s.index}, dtype=float)


def statements_from_facts(facts: dict) -> dict | None:
    """Normalized income / balance / cash-flow DataFrames from a companyfacts payload."""
    gaap = facts.get("facts", {}).get("us-gaap")
    if not gaap:
        return None
    revenue = _merged(gaap, INCOME_TAGS["revenue"], instant=False)
    if revenue.empty:
        return None
    # fiscal years are labelled by the calendar year they end in, as Yahoo does
    fy_ends = {int(end[:4]): end for end in sorted(revenue.index)}

    def frame(tags: dict[str, list[str]], instant: bool) -> pd.DataFrame:
        cols = {field: _by_year(_merged(gaap, t, instant), fy_ends) for field, t in tags.items()}
        return pd.DataFrame({k: v for k, v in cols.items() if not v.empty}).sort_index()

    income = frame(INCOME_TAGS, instant=False)
    shares_x, eps_x = (_by_year(x, fy_ends).reindex(income.index).fillna(1.0) for x in _share_basis(gaap))
    for field, factor in (("shares_basic_avg", shares_x), ("shares_diluted_avg", shares_x), ("eps_diluted", eps_x)):
        if field in income:
            income[field] = income[field] * factor
    balance = frame(BALANCE_TAGS, instant=True)
    cashflow = frame(CASHFLOW_TAGS, instant=False)

    def part(tags):
        return _by_year(_merged(gaap, tags, instant=True), fy_ends)

    long_term = part(_DEBT_TOTAL).combine_first(
        pd.concat([part(_DEBT_NONCURRENT), part(_DEBT_CURRENT)], axis=1).sum(axis=1, min_count=1))
    assembled = pd.concat([long_term, part(_DEBT_SHORT[:1]), part(_DEBT_SHORT[1:])], axis=1).sum(axis=1, min_count=1)
    debt = part(_DEBT_GRAND_TOTAL).combine_first(assembled)
    if not debt.dropna().empty:
        balance["total_debt"] = debt
    return {"income": income, "balance": balance.sort_index(), "cashflow": cashflow}


class EdgarClient:
    def __init__(self, contact: str):
        import requests  # deferred: only the data layer touches the network

        self._session = requests.Session()
        self._session.headers["User-Agent"] = f"valuation-dashboard {contact}"
        self._ciks: dict[str, int] | None = None
        self._lock = threading.Lock()
        self._next_request = 0.0

    def _throttle(self) -> None:
        with self._lock:
            now = time.monotonic()
            wait = self._next_request - now
            self._next_request = max(now, self._next_request) + 1 / _MAX_REQUESTS_PER_SECOND
        if wait > 0:
            time.sleep(wait)

    @classmethod
    def from_env(cls) -> "EdgarClient | None":
        contact = os.environ.get(CONTACT_ENV, "").strip()
        return cls(contact) if contact else None

    def _get(self, url: str) -> dict:
        self._throttle()
        r = self._session.get(url, timeout=30)
        r.raise_for_status()
        return r.json()

    def cik(self, ticker: str) -> int | None:
        if self._ciks is None:
            self._ciks = {v["ticker"].upper(): int(v["cik_str"]) for v in self._get(_TICKERS_URL).values()}
        return self._ciks.get(ticker.upper())

    def statements(self, ticker: str) -> dict | None:
        cik = self.cik(ticker)
        if cik is None:
            return None
        return statements_from_facts(self._get(_FACTS_URL.format(cik=cik)))

    def insider_trades(self, ticker: str, days: int = 183, max_filings: int = 120) -> list[dict] | None:
        """Form 4 transactions filed in the last `days`, newest filings first."""
        from .insiders import parse_form4

        cik = self.cik(ticker)
        if cik is None:
            return None
        recent = self._get(_SUBMISSIONS_URL.format(cik=cik))["filings"]["recent"]
        since = (dt.date.today() - dt.timedelta(days=days)).isoformat()
        filings = [
            (recent["accessionNumber"][i], recent["primaryDocument"][i], recent["filingDate"][i])
            for i in range(len(recent["form"]))
            if recent["form"][i] == "4" and recent["filingDate"][i] >= since
        ][:max_filings]

        def fetch(filing):
            accession, document, filed = filing
            self._throttle()
            url = _ARCHIVE_URL.format(cik=cik, accession=accession.replace("-", ""),
                                      document=document.split("/")[-1])  # raw XML, not the XSL view
            try:
                r = self._session.get(url, timeout=30)
                r.raise_for_status()
                return [{**t, "filed": filed} for t in parse_form4(r.text)]
            except Exception:
                return []

        with ThreadPoolExecutor(max_workers=4) as pool:
            return [t for batch in pool.map(fetch, filings) for t in batch]
