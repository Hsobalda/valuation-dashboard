"""Derive evidence-based starting assumptions from a company's own history.

These are *starting points*, not silent defaults: each carries a provenance
string so the UI can show exactly where the number came from (e.g. "FY2025
operating margin"). The analyst overrides them; the override is the point.
"""

from __future__ import annotations

import pandas as pd

from engine.wacc import cost_of_equity, wacc

from .panels import _col, _fcf, reinvestment_history, roic_history

DISCOUNT_RATE = 0.10  # required return: the hurdle every investment must clear
RISK_FREE = 0.04
EQUITY_RISK_PREMIUM = 0.05

# Margin of safety by uncertainty, on Morningstar's scale for a 5-star rating
MAX_SEED_GROWTH = 0.15
GROWTH_FLOOR, GROWTH_CEILING = -0.20, 1.00  # growth slider range
UNCERTAINTY_MOS = {"Low": 0.20, "Medium": 0.30, "High": 0.40, "Very high": 0.50}


def _latest(df, field):
    if field not in df.columns:
        return 0.0
    s = df[field].dropna()
    return float(s.iloc[-1]) if s.size else 0.0


def derive_starting_assumptions(provider, ticker: str) -> dict:
    inc = provider.income_statement(ticker)

    revenue = inc["revenue"].dropna()
    latest_rev = float(revenue.iloc[-1]) if revenue.size else 0.0

    # revenue CAGR (oldest -> newest), capped: growth above 15% for five years
    # should be an explicit judgement, not an extrapolation (e.g. a post-COVID rebound)
    cagr = 0.0
    if revenue.size >= 2 and revenue.iloc[0] > 0:
        cagr = (revenue.iloc[-1] / revenue.iloc[0]) ** (1 / (revenue.size - 1)) - 1.0
    growth = min(max(cagr, -0.05), MAX_SEED_GROWTH)
    hist_note = (
        f"revenue CAGR {revenue.index[0]}-{revenue.index[-1]} ({cagr:.1%})"
        + (f", capped at {growth:.0%}" if growth != cagr else "")
    ) if revenue.size >= 2 else "no revenue history"

    # years 1-2: analyst consensus where it exists (a forecast, so not capped);
    # year 5: halfway from year 2 to terminal growth, capped like historical
    # growth, since >15% five years out should be your explicit call
    cons = provider.consensus(ticker)
    g1 = cons["revenue_y1"] / latest_rev - 1 if cons and latest_rev else float("nan")
    g2 = cons["revenue_y2"] / cons["revenue_y1"] - 1 if cons and cons["revenue_y1"] else float("nan")
    has_consensus = -0.5 < g1 < 2.0 and -0.5 < g2 < 2.0  # else a period/currency mismatch
    if not has_consensus:
        g1 = g2 = growth
    terminal_growth = 0.025
    g5 = min((g2 + terminal_growth) / 2, MAX_SEED_GROWTH)
    g1, g2, g5 = (min(max(g, GROWTH_FLOOR), GROWTH_CEILING) for g in (g1, g2, g5))
    source = f"consensus of {cons['analysts']} analysts (Yahoo)" if has_consensus else hist_note

    ebit_margin = _latest(inc, "operating_income") / latest_rev if latest_rev else 0.0
    # normalised margin: the median over the history, so one abnormal year
    # (a shutdown, a one-off gain) neither sets nor distorts "normal"
    margins = ((inc["operating_income"] / inc["revenue"]).dropna()
               if "operating_income" in inc.columns else pd.Series(dtype=float))
    target_margin = float(margins.median()) if margins.size else ebit_margin
    ebit_margin, target_margin = (min(max(m, -0.30), 0.75) for m in (ebit_margin, target_margin))
    # bear/bull margin swing: how much the margin has actually moved, at least 2pp
    margin_swing = min(max(float(margins.std()) if margins.size >= 3 else 0.0, 0.02), 0.10)

    # no positive ROIC history -> assume new capital earns the discount rate,
    # so growth neither creates nor destroys value
    roic_hist = roic_history(provider, ticker).dropna()
    roic_avg = float(roic_hist.mean()) if roic_hist.size else float("nan")
    roic = min(max(roic_avg, 0.01), 1.0) if roic_avg > 0 else DISCOUNT_RATE

    # effective tax rate (latest year)
    pretax = _latest(inc, "pretax_income")
    tax = _latest(inc, "income_tax")
    tax_rate = min(max(tax / pretax, 0.0), 0.5) if pretax > 0 else 0.21

    # fundamental growth = reinvestment rate x ROIC: the growth the company's own
    # reinvestment can fund (net capex only; excludes working capital and M&A)
    reinvest_rate = reinvestment_history(provider, ticker)["net_capex_pct_nopat"].dropna()
    reinvest_rate = float(reinvest_rate.mean()) if reinvest_rate.size else float("nan")

    ref = wacc_reference(provider, ticker, tax_rate)
    unc = uncertainty_rating(provider, ticker)

    return {
        "growth_y1": g1,
        "growth_y2": g2,
        "growth_y5": g5,
        "ebit_margin": ebit_margin,
        "target_ebit_margin": target_margin,
        "tax_rate": tax_rate,
        "roic": roic,
        "fade_years": 10,
        "terminal_growth": terminal_growth,
        "terminal_excess_return": 0.0,
        "discount_rate": DISCOUNT_RATE,
        "growth_swing": 0.03,
        "margin_swing": margin_swing,
        "tail_probability": 0.25,
        "uncertainty": unc["rating"],
        "uncertainty_mos": UNCERTAINTY_MOS,
        "margin_of_safety": UNCERTAINTY_MOS[unc["rating"]],
        "wacc_reference": ref,
        "growth_evidence": {
            "historical": cagr if revenue.size >= 2 else float("nan"),
            "consensus": (g1, g2, cons["analysts"]) if has_consensus else None,
            "reinvestment_rate": reinvest_rate,
            "fundamental": reinvest_rate * roic,
        },
        "provenance": {
            "growth_y1": source,
            "growth_y2": source,
            "growth_y5": (
                "your view: seeded halfway between year-2 growth and terminal growth, "
                f"at most {MAX_SEED_GROWTH:.0%}. "
                "Years 3-4 move in a straight line from year 2 to this"
            ),
            "terminal_excess_return": (
                "0 = Morningstar's assumption that competition erodes excess returns by "
                "the end of the fade. Above 0 keeps new capital earning more than your "
                "required return forever: only for a moat you expect to last indefinitely"
            ),
            "ebit_margin": f"FY{revenue.index[-1]} operating margin",
            "target_ebit_margin": (
                f"median operating margin FY{margins.index[0]}-{margins.index[-1]}; "
                "the margin moves here in a straight line by year 5"
                if margins.size else "no margin history: set to the latest margin"
            ),
            "roic": (
                f"average ROIC FY{roic_hist.index[0]}-{roic_hist.index[-1]} (Panel C); "
                "sets what growth costs (reinvestment = growth / ROIC) and "
                "fades to the discount rate over the fade period"
                if roic_avg > 0 else "no positive ROIC history: set to the discount rate, "
                "so growth neither creates nor destroys value"
            ),
            "tax_rate": f"FY{revenue.index[-1]} effective tax rate",
            "fade_years": "default -- set from the moat evidence in Panel C",
            "terminal_growth": "default -- long-run GDP/inflation, 2-3%",
            "discount_rate": (
                f"required return of {DISCOUNT_RATE:.0%}; company WACC for "
                f"reference is {ref['wacc']:.1%}"
            ),
            "uncertainty": "; ".join(unc["reasons"]),
            "growth_swing": "bear/bull revenue growth is base growth minus/plus this",
            "margin_swing": (
                "bear/bull target margin is base minus/plus this; seeded from how much "
                "the operating margin has varied historically (at least 2pp)"
            ),
            "tail_probability": "chance of the bear case, and separately of the bull case",
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


def uncertainty_rating(provider, ticker: str) -> dict:
    """Score how uncertain the valuation is from four pieces of evidence.

    Each factor adds 0-2 points; the total maps to a rating that sets the
    margin of safety. A starting point for judgement, not a verdict.
    """
    inc = provider.income_statement(ticker)
    m = provider.fundamental_metrics(ticker)
    score, reasons = 0, []

    margins = (_col(inc, "operating_income") / _col(inc, "revenue").replace(0, pd.NA)).dropna()
    if margins.size >= 3:
        # relative, not absolute: value scales with margin, so a 1pp swing on a
        # 4% margin matters far more than on a 30% one
        margins = margins.astype(float)
        vol = float(margins.std() / abs(margins.mean())) if margins.mean() else float("inf")
        pts = 2 if vol > 0.30 else 1 if vol > 0.15 else 0
        score += pts
        swing = f"±{vol:.0%} of its average" if vol <= 1 else "by more than its average"
        reasons.append(f"operating margin varies {swing} (+{pts})")

    ebitda = m.get("ebitda", 0.0)
    if ebitda > 0:
        lev = m["net_debt"] / ebitda
        pts = 2 if lev > 3.5 else 1 if lev > 2.0 else 0
        reasons.append(f"net debt / EBITDA {lev:.1f}x (+{pts})")
    else:
        pts = 2
        reasons.append("negative EBITDA (+2)")
    score += pts

    beta = m.get("beta") or 1.0
    pts = 2 if beta > 1.6 else 1 if beta > 1.2 else 0
    score += pts
    reasons.append(f"beta {beta:.2f} (+{pts})")

    fcf = _fcf(provider.cash_flow(ticker)).dropna()
    negative = int((fcf < 0).sum())
    pts = 1 if negative else 0
    score += pts
    reasons.append(f"negative free cash flow in {negative} of {fcf.size} years (+{pts})")

    rating = "Low" if score <= 1 else "Medium" if score <= 3 else "High" if score <= 5 else "Very high"
    return {"rating": rating, "score": score, "reasons": reasons}
