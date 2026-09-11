"""Normalized data schema.

Every provider normalizes raw vendor data into these canonical field names.
Statements are pandas DataFrames indexed by fiscal year (int, ascending) with
these columns. All currency-denominated figures share one currency per company.

Cash-flow sign convention: capital_expenditure, dividends_paid and
stock_buybacks are stored as POSITIVE magnitudes (cash outflows), so
FCF = operating_cash_flow - capital_expenditure. This is a deliberate choice to
avoid the sign bug where a negative capex gets *added back*.
"""

INCOME_FIELDS = [
    "revenue",
    "cost_of_revenue",
    "gross_profit",
    "operating_income",
    "depreciation_amortization",
    "interest_expense",
    "pretax_income",
    "income_tax",
    "net_income",
    "eps_diluted",
]

BALANCE_FIELDS = [
    "cash_and_equiv",
    "short_term_investments",
    "total_debt",
    "total_assets",
    "total_liabilities",
    "stockholder_equity",
    "minority_interest",
    "goodwill",
]

CASHFLOW_FIELDS = [
    "operating_cash_flow",
    "capital_expenditure",
    "dividends_paid",
    "stock_buybacks",
]

# --- yfinance row-name -> normalized field mapping ---------------------------
# yfinance renames statement rows between versions, so each normalized field
# carries a list of candidate row labels matched case-insensitively.
YF_INCOME_MAP = {
    "revenue": ["Total Revenue", "Operating Revenue", "Revenue"],
    "cost_of_revenue": ["Cost Of Revenue", "Cost of Goods Sold", "Cost Of Sales"],
    "gross_profit": ["Gross Profit"],
    "operating_income": ["Operating Income", "Operating Income or Loss"],
    "depreciation_amortization": [
        "Reconciled Depreciation",
        "Depreciation And Amortization",
        "Depreciation & Amortization",
    ],
    "interest_expense": ["Interest Expense"],
    "pretax_income": ["Pretax Income", "Income Before Tax"],
    "income_tax": ["Tax Provision", "Income Tax Expense"],
    "net_income": ["Net Income"],
    "eps_diluted": ["Diluted EPS", "Diluted Earnings Per Share"],
}

YF_BALANCE_MAP = {
    "cash_and_equiv": ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"],
    "short_term_investments": ["Short Term Investments", "Other Short Term Investments"],
    "total_debt": ["Total Debt"],
    "total_assets": ["Total Assets"],
    "total_liabilities": ["Total Liabilities Net Minority Interest", "Total Liabilities"],
    "stockholder_equity": ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"],
    "minority_interest": ["Minority Interest"],
    "goodwill": ["Goodwill"],
}

YF_CASHFLOW_MAP = {
    "operating_cash_flow": ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
    "capital_expenditure": ["Capital Expenditure", "Capital Expenditures"],
    "dividends_paid": ["Cash Dividends Paid", "Common Stock Dividend Paid"],
    "stock_buybacks": ["Repurchase Of Capital Stock", "Common Stock Payments"],
}


def pick_row(df, candidates):
    """Return the first DataFrame row whose (case-insensitive) label matches a
    candidate. Returns None if none match."""
    if df is None or df.empty:
        return None
    lowered = {str(idx).strip().lower(): idx for idx in df.index}
    for cand in candidates:
        if cand.lower() in lowered:
            return df.loc[lowered[cand.lower()]]
    return None
