"""Derive evidence-based starting assumptions from a company's own history.

These are *starting points*, not silent defaults: each carries a provenance
string so the UI can show exactly where the number came from (e.g. "FY2025
operating margin"). The analyst overrides them; the override is the point.
"""

from __future__ import annotations

import pandas as pd

from engine.wacc import cost_of_equity, wacc

from .panels import _col, _fcf, reinvestment_history, roic_history

HURDLE_RATE = 0.10  # your required return: a buy test, not a valuation input
RISK_FREE = 0.04
EQUITY_RISK_PREMIUM = 0.05
DISCOUNT_RANGE = (0.04, 0.16)  # discount-rate slider range

SEED_YEARS = 10
MAX_SEED_GROWTH = 0.15
GROWTH_FLOOR, GROWTH_CEILING = -0.20, 1.00  # growth slider range
# Margin of safety by uncertainty rating, modelled on Morningstar's uncertainty ratings
UNCERTAINTY_MOS = {"Low": 0.20, "Medium": 0.30, "High": 0.40, "Very high": 0.50}


def _latest(df, field):
    if field not in df.columns:
        return 0.0
    s = df[field].dropna()
    return float(s.iloc[-1]) if s.size else 0.0


def derive_starting_assumptions(provider, ticker: str) -> dict:
    # the last 10 years: roughly one business cycle, so seeds reflect today's
    # business rather than, say, Apple's early-iPhone growth
    inc = provider.income_statement(ticker).tail(SEED_YEARS)

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
    # target: halfway from today's margin to the 10-year median. Margins tend to
    # revert, but only partly; full reversion would halve Amazon's margin and
    # nearly halve Nvidia's. The median keeps one abnormal year out of "normal".
    margins = ((inc["operating_income"] / inc["revenue"]).dropna()
               if "operating_income" in inc.columns else pd.Series(dtype=float))
    median_margin = float(margins.median()) if margins.size else ebit_margin
    target_margin = (ebit_margin + median_margin) / 2
    ebit_margin, target_margin = (min(max(m, -0.30), 0.75) for m in (ebit_margin, target_margin))
    # bear/bull margin swing: how much the margin has actually moved, at least 2pp
    margin_swing = min(max(float(margins.std()) if margins.size >= 3 else 0.0, 0.02), 0.10)

    # tax: median effective rate over the last 5 profitable years. One year is
    # often distorted by one-off charges (Intel's hit a 50% cap); a whole decade
    # can reach back to a different tax regime (Nvidia's 2016-22 rates were far
    # below today's)
    pretax, tax = _col(inc, "pretax_income"), _col(inc, "income_tax")
    rates = (tax / pretax)[pretax > 0].dropna().tail(5)
    tax_rate = min(max(float(rates.median()), 0.0), 0.40) if rates.size else 0.21

    # discount rate: the company's cost of capital, so fair value is what the
    # business is worth to the market; your own required return is a buy test
    ref = wacc_reference(provider, ticker, tax_rate)
    discount_rate = min(max(ref["wacc"], DISCOUNT_RANGE[0], terminal_growth + 0.02), DISCOUNT_RANGE[1])

    # no positive ROIC history -> assume new capital earns the cost of capital,
    # so growth neither creates nor destroys value
    roic_hist = roic_history(provider, ticker).dropna().tail(SEED_YEARS)
    roic_avg = float(roic_hist.mean()) if roic_hist.size else float("nan")
    roic = min(max(roic_avg, 0.01), 1.0) if roic_avg > 0 else discount_rate
    moat = moat_rating(roic_hist, discount_rate)

    # fundamental growth = reinvestment rate x ROIC: the growth the company's own
    # reinvestment can fund (net capex only; excludes working capital and M&A)
    reinvest_rate = reinvestment_history(provider, ticker)["net_capex_pct_nopat"].dropna().tail(SEED_YEARS)
    reinvest_rate = float(reinvest_rate.mean()) if reinvest_rate.size else float("nan")

    unc = uncertainty_rating(provider, ticker)

    return {
        "growth_y1": g1,
        "growth_y2": g2,
        "growth_y5": g5,
        "base_revenue": latest_rev,
        "ebit_margin": ebit_margin,
        "target_ebit_margin": target_margin,
        "tax_rate": tax_rate,
        "roic": roic,
        "fade_years": moat["fade_years"],
        "terminal_growth": terminal_growth,
        "terminal_excess_return": 0.0,
        "discount_rate": discount_rate,
        "hurdle_rate": HURDLE_RATE,
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
                "the end of the fade. Above 0 keeps new capital earning more than the "
                "cost of capital forever: only for a moat you expect to last indefinitely"
            ),
            "ebit_margin": f"FY{revenue.index[-1]} operating margin",
            "target_ebit_margin": (
                f"halfway between today's margin and the FY{margins.index[0]}-{margins.index[-1]} "
                f"median of {median_margin:.1%} (margins revert, but only partly); "
                "the margin moves here in a straight line by year 5"
                if margins.size else "no margin history: set to the latest margin"
            ),
            "roic": (
                f"average ROIC FY{roic_hist.index[0]}-{roic_hist.index[-1]} (Panel C); "
                "sets what growth costs (reinvestment = growth / ROIC) and "
                "fades to the cost of capital over the fade period"
                if roic_avg > 0 else "no positive ROIC history: set to the cost of capital, "
                "so growth neither creates nor destroys value"
            ),
            "tax_rate": (f"median effective tax rate over {rates.size} profitable years"
                         if rates.size else "no profitable years: US federal rate of 21%"),
            "fade_years": moat["reason"],
            "terminal_growth": "default: long-run nominal GDP growth, typically 2-3%",
            "discount_rate": (
                f"company WACC: CAPM cost of equity {ref['cost_of_equity']:.1%} "
                f"(risk-free {RISK_FREE:.0%} + adjusted beta {ref['beta_adjusted']:.2f} x "
                f"{EQUITY_RISK_PREMIUM:.0%} equity risk premium) and after-tax cost of debt, "
                "weighted by market values"
            ),
            "hurdle_rate": (
                "the return you require before buying. It doesn't change the fair value; "
                "the buy decision compares it with the expected return at today's price"
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
    """Company WACC from CAPM (adjusted beta) and market-value weights: the seed for the discount rate.

    Cost of debt is interest expense / total debt, bounded to 2-15% so a stale
    or tiny debt balance can't produce an absurd rate; with no usable data it
    falls back to the risk-free rate.
    """
    m = provider.fundamental_metrics(ticker)
    inc = provider.income_statement(ticker)
    bal = provider.balance_sheet(ticker)

    beta = m.get("beta") or 1.0
    # adjusted beta (as Bloomberg shows): betas drift toward the market's 1.0, and
    # raw betas like Exxon's 0.17 would imply an unrealistic ~5% cost of equity
    beta_adj = 0.67 * beta + 0.33
    debt = _latest(bal, "total_debt")
    interest = _latest(inc, "interest_expense")
    cost_debt = min(max(interest / debt, 0.02), 0.15) if debt > 0 and interest > 0 else RISK_FREE

    ke = cost_of_equity(RISK_FREE, beta_adj, EQUITY_RISK_PREMIUM)
    return {
        "wacc": wacc(m["market_cap"], debt, ke, cost_debt, tax_rate),
        "cost_of_equity": ke,
        "cost_of_debt": cost_debt,
        "beta": beta,
        "beta_adjusted": beta_adj,
        "risk_free": RISK_FREE,
        "equity_risk_premium": EQUITY_RISK_PREMIUM,
    }


def uncertainty_rating(provider, ticker: str) -> dict:
    """Score how uncertain the valuation is from four pieces of evidence.

    Each factor adds 0-2 points; the total maps to a rating that sets the
    margin of safety. A starting point for judgement, not a verdict.
    """
    inc = provider.income_statement(ticker).tail(SEED_YEARS)
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

    fcf = _fcf(provider.cash_flow(ticker)).dropna().tail(SEED_YEARS)
    negative = int((fcf < 0).sum())
    pts = 1 if negative else 0
    score += pts
    reasons.append(f"negative free cash flow in {negative} of {fcf.size} years (+{pts})")

    rating = "Low" if score <= 1 else "Medium" if score <= 3 else "High" if score <= 5 else "Very high"
    return {"rating": rating, "score": score, "reasons": reasons}


def moat_rating(roic_hist: pd.Series, cost_of_capital: float) -> dict:
    """Fade period from how consistently and by how much ROIC has beaten the cost
    of capital: Morningstar's wide / narrow / no moat, read from the evidence.
    """
    if roic_hist.size < 3:
        return {"fade_years": 10, "reason": "too little ROIC history to judge the moat: narrow by default"}
    n_above = int((roic_hist > cost_of_capital).sum())
    spread = float(roic_hist.mean()) - cost_of_capital
    share = n_above / roic_hist.size
    fade, label = ((20, "wide") if share >= 0.9 and spread >= 0.10 else
                   (10, "narrow") if share >= 0.6 else (5, "no"))
    return {
        "fade_years": fade,
        "reason": (f"{label} moat: ROIC beat the {cost_of_capital:.1%} cost of capital in {n_above} of "
                   f"{roic_hist.size} years, by {spread * 100:+.0f} points on average. Wide (20 years) "
                   "needs nearly every year and 10+ points; narrow (10) most years; otherwise 5"),
    }
