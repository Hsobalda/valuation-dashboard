"""Derive evidence-based starting assumptions from a company's own history.

These are *starting points*, not silent defaults: each carries a provenance
string so the UI can show exactly where the number came from (e.g. "FY2025
operating margin"). The analyst overrides them; the override is the point.
"""

from __future__ import annotations


def _latest(df, field):
    s = df[field].dropna()
    return float(s.iloc[-1]) if s.size else 0.0


def derive_starting_assumptions(provider, ticker: str) -> dict:
    inc = provider.income_statement(ticker)
    bal = provider.balance_sheet(ticker)
    cf = provider.cash_flow(ticker)

    revenue = inc["revenue"].dropna()
    latest_rev = float(revenue.iloc[-1]) if revenue.size else 0.0

    # revenue CAGR (oldest -> newest)
    cagr = 0.0
    if revenue.size >= 2 and revenue.iloc[0] > 0:
        cagr = (revenue.iloc[-1] / revenue.iloc[0]) ** (1 / (revenue.size - 1)) - 1.0

    ebit_margin = _latest(inc, "operating_income") / latest_rev if latest_rev else 0.0
    da_pct = _latest(inc, "depreciation_amortization") / latest_rev if latest_rev else 0.0
    capex_pct = _latest(cf, "capital_expenditure") / latest_rev if latest_rev else 0.0

    # effective tax rate (latest year)
    pretax = _latest(inc, "pretax_income")
    tax = _latest(inc, "income_tax")
    tax_rate = min(max(tax / pretax, 0.0), 0.5) if pretax > 0 else 0.21

    return {
        "revenue_growth": cagr,
        "ebit_margin": ebit_margin,
        "tax_rate": tax_rate,
        "da_pct_revenue": da_pct,
        "capex_pct_revenue": capex_pct,
        "nwc_pct_revenue": 0.0,  # not derivable from this schema; analyst sets it
        "fade_years": 10,
        "terminal_growth": 0.025,
        "wacc": 0.08,
        "margin_of_safety": 0.25,
        "provenance": {
            "revenue_growth": f"revenue CAGR {revenue.index[0]}-{revenue.index[-1]}",
            "ebit_margin": f"FY{revenue.index[-1]} operating margin",
            "tax_rate": f"FY{revenue.index[-1]} effective tax rate",
            "da_pct_revenue": f"FY{revenue.index[-1]} D&A / revenue",
            "capex_pct_revenue": f"FY{revenue.index[-1]} capex / revenue",
            "nwc_pct_revenue": "not derived (no working-capital data) -- set if relevant",
            "fade_years": "placeholder -- set from the moat evidence in Panel C",
            "terminal_growth": "placeholder -- long-run GDP/inflation, 2-3%",
            "wacc": "placeholder -- set from the risk evidence in Panel E",
            "margin_of_safety": "placeholder -- scale by confidence (see Panel E)",
        },
    }
