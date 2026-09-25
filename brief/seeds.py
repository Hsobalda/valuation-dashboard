"""Derive evidence-based starting assumptions from a company's own history.

These are *starting points*, not silent defaults: each carries a provenance
string so the UI can show exactly where the number came from (e.g. "FY2025
operating margin"). The analyst overrides them; the override is the point.
"""

from __future__ import annotations

import pandas as pd

from engine.wacc import cost_of_equity, wacc

from .panels import roic_history

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

    revenue = inc["revenue"].dropna()
    latest_rev = float(revenue.iloc[-1]) if revenue.size else 0.0

    # revenue CAGR (oldest -> newest)
    cagr = 0.0
    if revenue.size >= 2 and revenue.iloc[0] > 0:
        cagr = (revenue.iloc[-1] / revenue.iloc[0]) ** (1 / (revenue.size - 1)) - 1.0

    ebit_margin = _latest(inc, "operating_income") / latest_rev if latest_rev else 0.0
    # normalised margin: the average over the history, so one unusual year
    # isn't projected forever
    margins = ((inc["operating_income"] / inc["revenue"]).dropna()
               if "operating_income" in inc.columns else pd.Series(dtype=float))
    target_margin = float(margins.mean()) if margins.size else ebit_margin

    roic_hist = roic_history(provider, ticker).dropna()
    roic = min(max(float(roic_hist.mean()), 0.01), 1.0) if roic_hist.size else DISCOUNT_RATE

    # effective tax rate (latest year)
    pretax = _latest(inc, "pretax_income")
    tax = _latest(inc, "income_tax")
    tax_rate = min(max(tax / pretax, 0.0), 0.5) if pretax > 0 else 0.21

    ref = wacc_reference(provider, ticker, tax_rate)

    return {
        "revenue_growth": cagr,
        "ebit_margin": ebit_margin,
        "target_ebit_margin": target_margin,
        "tax_rate": tax_rate,
        "roic": roic,
        "fade_years": 10,
        "terminal_growth": 0.025,
        "discount_rate": DISCOUNT_RATE,
        "margin_of_safety": 0.25,
        "wacc_reference": ref,
        "provenance": {
            "revenue_growth": f"revenue CAGR {revenue.index[0]}-{revenue.index[-1]}",
            "ebit_margin": f"FY{revenue.index[-1]} operating margin",
            "target_ebit_margin": (
                f"average operating margin FY{margins.index[0]}-{margins.index[-1]}; "
                "the margin moves here in a straight line by year 5"
                if margins.size else "no margin history: set to the latest margin"
            ),
            "roic": (
                f"average ROIC FY{roic_hist.index[0]}-{roic_hist.index[-1]} (Panel C); "
                "sets what growth costs (reinvestment = growth / ROIC) and "
                "fades to the discount rate over the fade period"
                if roic_hist.size else "no ROIC history: set to the discount rate (no excess returns)"
            ),
            "tax_rate": f"FY{revenue.index[-1]} effective tax rate",
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
