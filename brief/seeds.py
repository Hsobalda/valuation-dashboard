"""Derive evidence-based starting assumptions from a company's own history.

These are *starting points*, not silent defaults: each carries a provenance
string so the UI can show exactly where the number came from (e.g. "FY2025
operating margin"). The analyst overrides them; the override is the point.
"""

from __future__ import annotations

from engine.wacc import cost_of_equity, wacc

DISCOUNT_RATE = 0.10  # required return: the hurdle every investment must clear
RISK_FREE = 0.04
EQUITY_RISK_PREMIUM = 0.05


def _latest(df, field):
    if field not in df.columns:
        return 0.0
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

    ref = wacc_reference(provider, ticker, tax_rate)

    return {
        "revenue_growth": cagr,
        "ebit_margin": ebit_margin,
        "tax_rate": tax_rate,
        "da_pct_revenue": da_pct,
        "capex_pct_revenue": capex_pct,
        "nwc_pct_revenue": 0.0,  # not derivable from this schema; analyst sets it
        "fade_years": 10,
        "terminal_growth": 0.025,
        "discount_rate": DISCOUNT_RATE,
        "margin_of_safety": 0.25,
        "wacc_reference": ref,
        "provenance": {
            "revenue_growth": f"revenue CAGR {revenue.index[0]}-{revenue.index[-1]}",
            "ebit_margin": f"FY{revenue.index[-1]} operating margin",
            "tax_rate": f"FY{revenue.index[-1]} effective tax rate",
            "da_pct_revenue": f"FY{revenue.index[-1]} D&A / revenue",
            "capex_pct_revenue": f"FY{revenue.index[-1]} capex / revenue",
            "nwc_pct_revenue": "not derived (no working-capital data) -- set if relevant",
            "fade_years": "default -- set from the moat evidence in Panel C",
            "terminal_growth": "default -- long-run GDP/inflation, 2-3%",
            "discount_rate": (
                f"required return of {DISCOUNT_RATE:.0%}; company WACC for "
                f"reference is {ref['wacc']:.1%}"
            ),
            "margin_of_safety": "default -- scale by confidence (see Panel E)",
        },
    }


def wacc_reference(provider, ticker: str, tax_rate: float) -> dict:
    """Company WACC from CAPM and market-value weights, shown beside the discount rate.

    Cost of debt is interest expense / total debt, bounded to 2-15% so a stale
    or tiny debt balance can't produce an absurd rate; with no usable data it
    falls back to the risk-free rate.
    """
    m = provider.fundamental_metrics(ticker)
    inc = provider.income_statement(ticker)
    bal = provider.balance_sheet(ticker)

    beta = m.get("beta") or 1.0
    debt = _latest(bal, "total_debt")
    interest = _latest(inc, "interest_expense")
    cost_debt = min(max(interest / debt, 0.02), 0.15) if debt > 0 and interest > 0 else RISK_FREE

    ke = cost_of_equity(RISK_FREE, beta, EQUITY_RISK_PREMIUM)
    return {
        "wacc": wacc(m["market_cap"], debt, ke, cost_debt, tax_rate),
        "cost_of_equity": ke,
        "cost_of_debt": cost_debt,
        "beta": beta,
        "risk_free": RISK_FREE,
        "equity_risk_premium": EQUITY_RISK_PREMIUM,
    }
