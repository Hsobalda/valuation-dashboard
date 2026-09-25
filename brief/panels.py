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
    return _col(income, "operating_income") + _col(income, "depreciation_amortization")


def _fcf(cashflow: pd.DataFrame) -> pd.Series:
    """Free cash flow after stock-based pay. Operating cash flow adds SBC back as
    "non-cash", but paying staff in shares is a real cost to shareholders."""
    return (_col(cashflow, "operating_cash_flow") - _col(cashflow, "capital_expenditure")
            - _col(cashflow, "stock_based_compensation"))


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


def _net_debt(balance: pd.DataFrame) -> pd.Series:
    """Debt less cash, short-term investments and long-term marketable securities."""
    return (_col(balance, "total_debt") - _col(balance, "cash_and_equiv")
            - _col(balance, "short_term_investments") - _col(balance, "long_term_investments"))


def _invested_capital(balance: pd.DataFrame) -> pd.Series:
    # financing approach: equity plus net debt (debt less cash and investments)
    return _col(balance, "stockholder_equity") + _net_debt(balance)


# Balance-sheet businesses: debt is funding for the product, not financing, so
# free cash flow to the firm is undefined. Payment networks and asset managers
# (also "Financial Services" on Yahoo) are fee businesses and are left in.
_NO_DCF_INDUSTRIES = ("Banks", "Insurance", "Mortgage Finance", "Capital Markets")


def dcf_applicable(info: dict) -> bool:
    """False for banks, insurers and lenders. Card lenders (Capital One, Synchrony)
    share Yahoo's "Credit Services" industry with Visa and Mastercard, but Yahoo
    reports no EBITDA for lenders, which tells them apart."""
    if (info.get("industry") or "").startswith(_NO_DCF_INDUSTRIES):
        return False
    return not (info.get("sector") == "Financial Services" and not info.get("reports_ebitda", True))


# Industries where manufacturers usually run a finance arm lending to customers
# (Ford Credit, GM Financial, Cat Financial, John Deere Financial)
_CAPTIVE_FINANCE_INDUSTRIES = ("Auto Manufacturers", "Farm & Heavy Construction Machinery")


def captive_finance_likely(info: dict) -> bool:
    return (info.get("industry") or "") in _CAPTIVE_FINANCE_INDUSTRIES


def screen_peers(target: dict, candidates: list[dict]) -> list[dict]:
    """Mark each candidate peer as suggested or not, with the reason.

    Operating margin within 1.5x either way, or within 3 percentage points for
    thin-margin businesses like grocers, is a rough test for "same business
    model": it separates Visa (66%) from PayPal (17%) under the same industry
    label. Lenders are only compared with lenders.
    """
    out = []
    t_margin, t_dcf = target.get("operating_margin"), dcf_applicable(target)
    for c in candidates:
        margin = c.get("operating_margin")
        if c.get("currency_mismatch"):
            ok, why = False, "reports in a different currency from its share price"
        elif dcf_applicable(c) != t_dcf:
            ok, why = False, "lender or insurer vs operating company" if t_dcf else "not a lender or insurer"
        elif t_margin and margin and t_margin > 0 and margin > 0:
            ratio = margin / t_margin
            ok = 2 / 3 <= ratio <= 1.5 or abs(margin - t_margin) <= 0.03
            why = (f"similar operating margin ({margin:.0%} vs {t_margin:.0%})" if ok else
                   f"operating margin {margin:.0%} vs {t_margin:.0%}: probably a different business model")
        else:
            ok, why = True, "same industry; margins not comparable (a loss or missing data)"
        out.append({**c, "suggested": ok, "reason": why})
    return out


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

    revenue = _col(inc, "revenue")
    ebitda = _ebitda(inc)
    ni = _col(inc, "net_income")
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
        "gross_margin": gross_margin(_col(inc, "revenue"), _col(inc, "cost_of_revenue")),
        "operating_margin": operating_margin(_col(inc, "operating_income"), _col(inc, "revenue")),
        "net_margin": net_margin(_col(inc, "net_income"), _col(inc, "revenue")),
        "fcf_conversion": fcf_conversion_series(fcf, ni),
        "revenue_cagr": _cagr(revenue),
        "what_this_means": (
            "This is the empirical anchor: every forecast is a deviation from "
            "this history, and the deviation is what you must justify. Check "
            "FCF/income conversion: earnings that aren't backed by cash are "
            "weaker than they look."
        ),
    }


def roic_history(provider, ticker: str) -> pd.Series:
    inc = provider.income_statement(ticker)
    nopat = _col(inc, "operating_income") * (1.0 - _effective_tax_rate(inc))
    return roic_series(nopat, _invested_capital(provider.balance_sheet(ticker)))


def reinvestment_history(provider, ticker: str) -> pd.DataFrame:
    """Historical capex, D&A and net capex against NOPAT, by fiscal year.

    Net capex (capex - D&A) is what the company spent beyond replacing worn-out
    assets; it excludes working capital and acquisitions, which the model's
    reinvestment line includes.
    """
    inc = provider.income_statement(ticker)
    nopat = _col(inc, "operating_income") * (1.0 - _effective_tax_rate(inc))
    capex = _col(provider.cash_flow(ticker), "capital_expenditure")
    capex, da = capex.align(_col(inc, "depreciation_amortization"), join="inner")
    df = pd.DataFrame({
        "revenue_growth": _col(inc, "revenue").pct_change(),
        "nopat": nopat,
        "capex": capex,
        "da": da,
    }).loc[capex.index].dropna(subset=["capex"])
    df["net_capex"] = df["capex"] - df["da"]
    df["net_capex_pct_nopat"] = df["net_capex"] / df["nopat"].where(df["nopat"] > 0)
    return df


def panel_quality(provider, ticker: str, reference_wacc: float) -> dict:
    inc = provider.income_statement(ticker)
    bal = provider.balance_sheet(ticker)
    cf = provider.cash_flow(ticker)

    roic = roic_history(provider, ticker)
    gm = gross_margin(_col(inc, "revenue"), _col(inc, "cost_of_revenue"))
    fcf_conv = fcf_conversion_series(_fcf(cf), _col(inc, "net_income"))

    years_above_wacc = int((roic - reference_wacc > 0).sum())
    avg_roic = float(roic.dropna().mean()) if roic.dropna().size else float("nan")

    goodwill_pct = 0.0
    ta_last = float(_col(bal, "total_assets").iloc[-1]) if _col(bal, "total_assets").iloc[-1] else 0.0
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


def panel_capital_allocation(provider, ticker: str) -> dict:
    inc = provider.income_statement(ticker)
    bal = provider.balance_sheet(ticker)
    cf = provider.cash_flow(ticker)

    # yfinance often returns an all-NaN earliest year; drop years without cash flow data
    fcf = _fcf(cf).dropna()
    dividends = _col(cf, "dividends_paid").reindex(fcf.index).fillna(0.0)
    buybacks = _col(cf, "stock_buybacks").reindex(fcf.index).fillna(0.0)
    sbc = _col(cf, "stock_based_compensation").reindex(fcf.index).fillna(0.0)
    total_fcf = float(fcf.sum())
    # buybacks up to the value of stock pay only stop dilution; what's returned
    # to existing shareholders is the rest
    total_returned = float((dividends + buybacks - sbc).sum())
    payout = total_returned / total_fcf if total_fcf > 0 else float("nan")
    sbc_share_of_buybacks = float(sbc.sum() / buybacks.sum()) if buybacks.sum() > 0 else float("nan")

    shares = _col(inc, "shares_diluted_avg").replace(0, pd.NA).dropna().astype(float)
    share_cagr = _cagr(shares)

    net_debt = _net_debt(bal).dropna()
    nd_start = float(net_debt.iloc[0]) if net_debt.size else float("nan")
    nd_end = float(net_debt.iloc[-1]) if net_debt.size else float("nan")

    flags = []
    if payout == payout and payout > 1.0:
        flags.append(
            f"Returned {payout:.0%} of free cash flow (after stock pay) over {fcf.size} years; the excess "
            "came from cash or borrowing"
        )
    if total_fcf <= 0 and total_returned > 0:
        flags.append("Paying dividends/buybacks while cumulative free cash flow is negative")
    if share_cagr == share_cagr and share_cagr > 0.01:
        flags.append(f"Diluted share count growing {share_cagr:.1%} a year (dilution)")

    return {
        "title": "D. How does it use its cash?",
        "decision": "trust in management (margin of safety)",
        "fcf": fcf,
        "dividends": dividends,
        "buybacks": buybacks,
        "sbc": sbc,
        "sbc_share_of_buybacks": sbc_share_of_buybacks,
        "payout_of_fcf": payout,
        "share_cagr": share_cagr,
        "net_debt_start": nd_start,
        "net_debt_end": nd_end,
        "flags": flags,
        "what_this_means": (
            "Value in the DCF only reaches shareholders if management spends the "
            "cash well. Steady buybacks shrinking the share count and payouts "
            "covered by free cash flow are good signs; payouts funded by new debt, "
            "or a rising share count, mean value is leaking."
        ),
    }


def panel_risk(provider, ticker: str) -> dict:
    inc = provider.income_statement(ticker)
    bal = provider.balance_sheet(ticker)
    cf = provider.cash_flow(ticker)
    info = provider.company_info(ticker)

    ebitda = _ebitda(inc)
    net_debt = _net_debt(bal)
    net_debt_a, ebitda_a, nd_ebitda_dropped = _align_years(net_debt, ebitda)
    nd_ebitda = net_debt_a / ebitda_a.replace(0, pd.NA)
    debt_equity = _col(bal, "total_debt") / _col(bal, "stockholder_equity").replace(0, pd.NA)

    fcf = _fcf(cf)
    ni = _col(inc, "net_income")
    fcf_a, ni_a, fcf_ni_dropped = _align_years(fcf, ni)
    years_fcf_below_ni = int((fcf_a < ni_a).sum())

    flags = []
    dropped_years = sorted(set(nd_ebitda_dropped) | set(fcf_ni_dropped))
    if dropped_years:
        flags.append(
            f"Data provider returned mismatched fiscal years across statements "
            f"({', '.join(str(y) for y in dropped_years)} present in only one "
            "statement), so ratios use only the overlapping years"
        )
    if years_fcf_below_ni >= 3:
        flags.append(
            f"FCF below net income in {years_fcf_below_ni} of the last "
            f"{len(ni_a)} years (earnings may be less cash-backed than they appear)"
        )
    ta_last = float(_col(bal, "total_assets").iloc[-1]) if _col(bal, "total_assets").iloc[-1] else 0.0
    goodwill_pct = float(_col(bal, "goodwill").iloc[-1]) / ta_last if ta_last else 0.0
    if goodwill_pct > 0.40:
        flags.append(f"Goodwill is {goodwill_pct:.0%} of total assets (impairment sensitivity)")

    return {
        "title": "E. What could go wrong?",
        "decision": "margin of safety",
        "net_debt_to_ebitda": nd_ebitda,
        "latest_nd_ebitda": float(nd_ebitda.dropna().iloc[-1]) if nd_ebitda.dropna().size else float("nan"),
        "debt_to_equity": float(debt_equity.dropna().iloc[-1]) if debt_equity.dropna().size else float("nan"),
        "beta": info.get("beta", 0.0),
        "flags": flags,
        "what_this_means": (
            "Higher leverage, more volatile cash flows and weaker earnings "
            "quality all mean more uncertain value, so a larger required "
            "margin of safety. The discount rate stays at your required return."
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
            "justified by Panels B-E? The reverse DCF in section 3 shows the "
            "growth today's price implies; your variant view is where you "
            "believe the market is wrong."
        ),
    }


def _cagr(series: pd.Series) -> float:
    s = series.dropna()
    if s.size < 2 or s.iloc[0] <= 0 or s.iloc[-1] <= 0:
        return float("nan")
    years = s.size - 1
    return (s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1.0


def build_brief(provider, ticker: str, reference_wacc: float) -> dict:
    """Aggregate all panels into a single brief dict."""
    return {
        "business": panel_business(provider, ticker),
        "history": panel_history(provider, ticker),
        "quality": panel_quality(provider, ticker, reference_wacc),
        "capital_allocation": panel_capital_allocation(provider, ticker),
        "risk": panel_risk(provider, ticker),
        "priced_in": panel_priced_in(provider, ticker),
    }
