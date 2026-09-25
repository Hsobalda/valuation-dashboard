"""Annual financial statements for US filers from SEC EDGAR XBRL company facts.

EDGAR gives 15+ years straight from 10-K filings, against Yahoo's 4-5. The SEC's
fair-access policy requires every request to identify itself with a contact
email in the User-Agent; set SEC_CONTACT_EMAIL (or the Streamlit secret of the
same name). Without it EDGAR is skipped and Yahoo's statements are used.
"""

from __future__ import annotations

import datetime as dt
import os

import pandas as pd

CONTACT_ENV = "SEC_CONTACT_EMAIL"
_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"

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


def _facts(gaap: dict, tag: str, instant: bool) -> pd.Series:
    """One tag's annual 10-K values, keyed by period end date; restatements win."""
    if tag not in gaap:
        return pd.Series(dtype=float)
    best: dict[str, tuple[str, float]] = {}
    for unit_facts in gaap[tag]["units"].values():
        for f in unit_facts:
            if not f.get("form", "").startswith("10-K"):
                continue
            if instant != ("start" not in f):
                continue
            if not instant:
                days = (dt.date.fromisoformat(f["end"]) - dt.date.fromisoformat(f["start"])).days
                if not 350 <= days <= 380:  # full years only, not quarters
                    continue
            if f["end"] not in best or f["filed"] > best[f["end"]][0]:
                best[f["end"]] = (f["filed"], float(f["val"]))
    return pd.Series({end: val for end, (_, val) in best.items()}, dtype=float)


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

    @classmethod
    def from_env(cls) -> "EdgarClient | None":
        contact = os.environ.get(CONTACT_ENV, "").strip()
        return cls(contact) if contact else None

    def _get(self, url: str) -> dict:
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
