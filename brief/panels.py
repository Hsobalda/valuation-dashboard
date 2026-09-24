"""Research brief panels.

Each panel transforms raw normalized data into *evidence* for one decision.
Panels show evidence and never draw the conclusion
(no "wide moat" / "undervalued" verdicts). Plain-language "what this means"
strings are descriptive, not judgmental.

All functions are pure with respect to the provider (no Streamlit, no I/O of
their own) and return plain dicts of numbers, pandas objects and strings so the
UI can render them however it likes.
"""

from __future__ import annotations

import pandas as pd

from engine.quality import (
    fcf_conversion_series,
    gross_margin,
    margin_stability,
    net_margin,
    operating_margin,
    roic_series,
)


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    """Return a column, or a zero-valued Series if the field is absent.

    Live data (yfinance) omits some statement rows entirely (e.g. `goodwill`,
    `short_term_investments`, or `cost_of_revenue` for banks), so panels must
    not assume every normalized column exists.
    """
    if name in df.columns:
        return df[name]
    return pd.Series(0.0, index=df.index, name=name)


def _ebitda(income: pd.DataFrame) -> pd.Series:
    return income["operating_income"] + _col(income, "depreciation_amortization")


def _fcf(cashflow: pd.DataFrame) -> pd.Series:
    return _col(cashflow, "operating_cash_flow") - _col(cashflow, "capital_expenditure")


def _effective_tax_rate(income: pd.DataFrame) -> pd.Series:
    """Per-year effective tax rate, clipped to [0, 0.5], default 0.21."""
    pretax = _col(income, "pretax_income")
    tax = _col(income, "income_tax")
    out = pd.Series(index=income.index, dtype=float)
    for y in income.index:
        if pretax[y] and pretax[y] > 0:
            out[y] = min(max(tax[y] / pretax[y], 0.0), 0.5)
        else:
            out[y] = 0.21
    return out


def _align_years(a: pd.Series, b: pd.Series) -> tuple[pd.Series, pd.Series, list[int]]:
    """Align two statement-derived series on their common fiscal years.

    Each statement (income, balance sheet, cash flow) is fetched from the
    provider independently, so the live provider can return a different set
    of fiscal years for one statement than another (e.g. yfinance's cash
    flow history for a ticker can include an extra year its income
    statement omits). Comparing or dividing unaligned series either raises
    (`Series.__lt__` etc. require identical labels) or silently produces NaN
    for the non-overlapping years, so callers combining series from two
    different statements must align first.

    Returns the two series restricted to their common index, plus the
    sorted list of fiscal years present in only one of them (empty if the
    two statements already agree on their fiscal years).
    """
    a_aligned, b_aligned = a.align(b, join="inner")
    dropped = sorted(set(a.index).symmetric_difference(set(b.index)))
    return a_aligned, b_aligned, dropped


def _invested_capital(balance: pd.DataFrame) -> pd.Series:
    # financing approach: total debt + equity - cash - short-term investments
    return (
        balance["total_debt"]
        + balance["stockholder_equity"]
        - balance["cash_and_equiv"]
        - _col(balance, "short_term_investments")
    )


def panel_business(provider, ticker: str) -> dict:
    info = provider.company_info(ticker)
    return {
        "title": "A. What is this business?",
        "decision": "go / no-go (circle of competence) + the revenue story",
        "name": info.get("name", ticker),
        "sector": info.get("sector", ""),
        "industry": info.get("industry", ""),
        "summary": info.get("summary", ""),
        "currency": info.get("currency", ""),
        "what_this_means": (
            "Read the one-paragraph model and check you can explain how this "
            "company makes money in a sentence. If not, don't value it yet."
        ),
    }


def panel_history(provider, ticker: str) -> dict:
    inc = provider.income_statement(ticker)
    cf = provider.cash_flow(ticker)

    revenue = inc["revenue"]
    ebitda = _ebitda(inc)
    ni = inc["net_income"]
    fcf = _fcf(cf)

    # indexed to first year = 100
    def index100(s: pd.Series) -> pd.Series:
        base = s.dropna().iloc[0] if s.dropna().size else float("nan")
        return (s / base * 100.0) if base else s

    return {
        "title": "B. What has it done?",
        "decision": "growth & margin inputs (history sits beside the input)",
        "revenue": revenue,
        "ebitda": ebitda,
        "net_income": ni,
        "fcf": fcf,
        "revenue_idx": index100(revenue),
        "ebitda_idx": index100(ebitda),
        "ni_idx": index100(ni),
        "gross_margin": gross_margin(inc["revenue"], _col(inc, "cost_of_revenue")),
        "operating_margin": operating_margin(inc["operating_income"], inc["revenue"]),
        "net_margin": net_margin(inc["net_income"], inc["revenue"]),
        "fcf_conversion": fcf_conversion_series(fcf, ni),
        "revenue_cagr": _cagr(revenue),
        "what_this_means": (
            "This is the empirical anchor: every forecast is a deviation from "
            "this history, and the deviation is what you must justify. Check "
            "FCF/income conversion -- earnings that aren't backed by cash are "
            "weaker than they look."
        ),
    }


def panel_quality(provider, ticker: str, reference_wacc: float = 0.08) -> dict:
    inc = provider.income_statement(ticker)
    bal = provider.balance_sheet(ticker)
    cf = provider.cash_flow(ticker)

    nopat = inc["operating_income"] * (1.0 - _effective_tax_rate(inc))
    ic = _invested_capital(bal)
    roic = roic_series(nopat, ic)
    gm = gross_margin(inc["revenue"], _col(inc, "cost_of_revenue"))
    fcf_conv = fcf_conversion_series(_fcf(cf), inc["net_income"])

    years_above_wacc = int((roic - reference_wacc > 0).sum())
    avg_roic = float(roic.dropna().mean()) if roic.dropna().size else float("nan")

    goodwill_pct = 0.0
    ta_last = float(bal["total_assets"].iloc[-1]) if bal["total_assets"].iloc[-1] else 0.0
    if ta_last:
        goodwill_pct = float(_col(bal, "goodwill").iloc[-1]) / ta_last

    return {
        "title": "C. How good is it?",
        "decision": "fade period (the moat input)",
        "roic": roic,
        "reference_wacc": reference_wacc,
        "avg_roic": avg_roic,
        "years_above_wacc": years_above_wacc,
        "years_total": int(roic.dropna().size),
        "gross_margin_std": margin_stability(gm),
        "fcf_conversion": fcf_conv,
        "goodwill_pct_assets": goodwill_pct,
        "what_this_means": (
            "A moat shows up as ROIC staying above the cost of capital for a "
            "long time. The longer the spread has held (and the more stable "
            "gross margins are), the longer a fade period you can defend. "
            "Duration matters more than magnitude."
        ),
    }


def panel_risk(provider, ticker: str) -> dict:
    inc = provider.income_statement(ticker)
    bal = provider.balance_sheet(ticker)
    cf = provider.cash_flow(ticker)
    info = provider.company_info(ticker)

    ebitda = _ebitda(inc)
    net_debt = bal["total_debt"] - bal["cash_and_equiv"] - _col(bal, "short_term_investments")
    net_debt_a, ebitda_a, nd_ebitda_dropped = _align_years(net_debt, ebitda)
    nd_ebitda = net_debt_a / ebitda_a.replace(0, pd.NA)
    debt_equity = bal["total_debt"] / bal["stockholder_equity"].replace(0, pd.NA)

    fcf = _fcf(cf)
    ni = inc["net_income"]
    fcf_a, ni_a, fcf_ni_dropped = _align_years(fcf, ni)
    years_fcf_below_ni = int((fcf_a < ni_a).sum())

    flags = []
    dropped_years = sorted(set(nd_ebitda_dropped) | set(fcf_ni_dropped))
    if dropped_years:
        flags.append(
            f"Data provider returned mismatched fiscal years across statements "
            f"({', '.join(str(y) for y in dropped_years)} present in only one "
            "statement) -- ratios below use only the overlapping years"
        )
    if years_fcf_below_ni >= 3:
        flags.append(
            f"FCF below net income in {years_fcf_below_ni} of the last "
            f"{len(ni_a)} years (earnings may be less cash-backed than they appear)"
        )
    ta_last = float(bal["total_assets"].iloc[-1]) if bal["total_assets"].iloc[-1] else 0.0
    goodwill_pct = float(_col(bal, "goodwill").iloc[-1]) / ta_last if ta_last else 0.0
    if goodwill_pct > 0.40:
        flags.append(f"Goodwill is {goodwill_pct:.0%} of total assets (impairment sensitivity)")

    return {
        "title": "E. What could go wrong?",
        "decision": "discount rate + margin of safety",
        "net_debt_to_ebitda": nd_ebitda,
        "latest_nd_ebitda": float(nd_ebitda.dropna().iloc[-1]) if nd_ebitda.dropna().size else float("nan"),
        "debt_to_equity": float(debt_equity.dropna().iloc[-1]) if debt_equity.dropna().size else float("nan"),
        "beta": info.get("beta", 0.0),
        "flags": flags,
        "what_this_means": (
            "Higher leverage, more volatile cash flows and weaker earnings "
            "quality all mean more uncertain value -> a higher discount rate "
            "and a larger required margin of safety."
        ),
    }


def panel_priced_in(provider, ticker: str) -> dict:
    m = provider.fundamental_metrics(ticker)
    info = provider.company_info(ticker)
    price = m["price"]
    eps = m["eps"]
    ev = m["market_cap"] + m["net_debt"] + m["minority_interest"]

    pe = price / eps if eps else float("nan")
    ev_ebitda = ev / m["ebitda"] if m["ebitda"] else float("nan")
    ev_rev = ev / m["revenue"] if m["revenue"] else float("nan")
    pb = price / m["bvps"] if m["bvps"] else float("nan")

    return {
        "title": "F. What's already priced in?",
        "decision": "variant view (where is the market wrong?)",
        "price": price,
        "currency": info.get("currency", ""),
        "pe": pe,
        "ev_ebitda": ev_ebitda,
        "ev_revenue": ev_rev,
        "pb": pb,
        "what_this_means": (
            "The market is always pricing in *some* forecast. Compare these "
            "multiples to the peers below and ask: is the premium/discount "
            "justified by Panels B-E? Your variant view is the specific place "
            "you believe the market is wrong."
        ),
    }


def _cagr(series: pd.Series) -> float:
    s = series.dropna()
    if s.size < 2 or s.iloc[0] <= 0 or s.iloc[-1] <= 0:
        return float("nan")
    years = s.size - 1
    return (s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1.0


def build_brief(provider, ticker: str, reference_wacc: float = 0.08) -> dict:
    """Aggregate all panels into a single brief dict."""
    return {
        "business": panel_business(provider, ticker),
        "history": panel_history(provider, ticker),
        "quality": panel_quality(provider, ticker, reference_wacc),
        "risk": panel_risk(provider, ticker),
        "priced_in": panel_priced_in(provider, ticker),
    }
