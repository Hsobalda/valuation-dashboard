"""Portfolio sizing panel: core index fund plus risk-budgeted satellite stocks."""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
import streamlit as st

from brief.seeds import UNCERTAINTY_MOS
from data.journal import load_entries
from engine import implied_return
from engine.sizing import Candidate, portfolio_risk, size_positions
from engine.valuation import Assumptions

CORE_EXPECTED_RETURN = 0.07  # long-run assumption for a global equity index, for display only


def _rating_for(mos: float) -> str:
    return next((r for r, m in UNCERTAINTY_MOS.items() if abs(m - mos) < 1e-9), "Medium")


def _journal_candidates(provider) -> dict[str, dict]:
    """Latest Buy/Watch call per ticker, re-priced: expected return at today's price
    from the assumptions saved with the call."""
    latest = {e["ticker"]: e for e in load_entries() if e.get("decision") in ("Buy", "Watch")}
    out = {}
    for t, e in latest.items():
        saved = {k: v for k, v in e.get("assumptions", {}).items() if k in Assumptions.__dataclass_fields__}
        if saved.get("growth_override") is not None:
            saved["growth_override"] = tuple(saved["growth_override"])
        try:
            a = Assumptions(**saved)
            m = provider.fundamental_metrics(t)
            er = implied_return(m["price"], m["revenue"], a, m["net_debt"], m["minority_interest"],
                                m["shares_diluted"], m["years_since_fy_end"])
        except Exception:
            continue
        out[t] = {"expected_return": er, "uncertainty": _rating_for(e.get("margin_of_safety", 0.3)),
                  "source": f"journal ({e['decision']}, {e['date']})"}
    return out


def render_portfolio(provider, current: dict | None) -> None:
    c1, c2, c3 = st.columns(3)
    value = c1.number_input("Portfolio value (£)", min_value=0.0, value=10_000.0, step=500.0, key="pf:value")
    core = c2.text_input("Core index fund", "VWRL.L", key="pf:core",
                         help="Vanguard FTSE All-World by default: the diversified base the picks sit on").strip().upper()
    hurdle = c3.number_input("Required return (%)", 0.0, 30.0,
                             (current or {}).get("hurdle", 0.10) * 100, 0.5, key="pf:hurdle") / 100
    c4, c5, c6 = st.columns(3)
    budget = c4.number_input("Risk budget per stock (%)", 0.25, 3.0, 1.0, 0.25, key="pf:budget",
                             help="Target standalone risk per position, as a share of the portfolio: "
                                  "weight x volatility. 1% on a 20%-volatility stock = a 5% position") / 100
    sat_cap = c5.number_input("Satellite cap (%)", 0.0, 50.0, 25.0, 5.0, key="pf:sat") / 100
    sector_cap = c6.number_input("Sector cap (%)", 0.0, 50.0, 10.0, 1.0, key="pf:sector") / 100

    pool = _journal_candidates(provider)
    if current and current.get("expected_return") is not None:
        pool.setdefault(current["ticker"], {**current, "source": "this page (current sliders)"})
    if not pool:
        st.caption("Save Buy or Watch calls in the journal (or value a company above) to size them here.")
        return

    core_closes = provider.weekly_closes(core)
    closes = {t: provider.weekly_closes(t) for t in pool}
    missing = [t for t, s in closes.items() if s is None]
    if core_closes is None or missing:
        st.warning(f"No usable price history for {', '.join(([core] if core_closes is None else []) + missing)} "
                   "(needs live data and a year or more of prices).")
        if core_closes is None:
            return
    tickers = [t for t in pool if closes[t] is not None]
    returns = pd.DataFrame({core: core_closes, **{t: closes[t] for t in tickers}}).pct_change(fill_method=None).dropna()
    vols = returns.std() * np.sqrt(52)

    cands = [Candidate(t, provider.company_info(t).get("sector", "") or "Unknown", pool[t]["expected_return"],
                       pool[t]["uncertainty"], float(vols[t])) for t in tickers]
    sized = size_positions(cands, hurdle, budget, sat_cap, sector_cap)
    weights = pd.Series({core: 1.0 - sized["weight"].sum(), **dict(zip(sized["ticker"], sized["weight"]))})
    port_vol, contrib = portfolio_risk(weights, returns)
    corr = returns.corr()[core]

    rows = [{"Holding": core, "Role": "Core", "Expected return": f"{CORE_EXPECTED_RETURN:.1%} (assumed)",
             "Uncertainty": "—", "Volatility": f"{vols[core]:.1%}", "Corr. with core": "1.00",
             "Weight": f"{weights[core]:.1%}", "£": f"{weights[core] * value:,.0f}",
             "Share of risk": f"{contrib[core]:.0%}", "Note": ""}]
    for _, r in sized.iterrows():
        rows.append({
            "Holding": r["ticker"], "Role": r["sector"],
            "Expected return": f"{r['expected_return']:.1%}" if r["expected_return"] is not None else "—",
            "Uncertainty": r["uncertainty"], "Volatility": f"{r['volatility']:.1%}",
            "Corr. with core": f"{corr[r['ticker']]:.2f}", "Weight": f"{r['weight']:.1%}",
            "£": f"{r['weight'] * value:,.0f}", "Share of risk": f"{contrib[r['ticker']]:.0%}",
            "Note": r["limit"] or pool[r["ticker"]]["source"],
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    exp = (weights[core] * CORE_EXPECTED_RETURN
           + sum(w * (pool[t]["expected_return"] or 0) for t, w in weights.items() if t != core))
    st.caption(
        f"Portfolio volatility {port_vol:.1%} a year (the core alone: {vols[core]:.1%}) · blended expected return "
        f"~{exp:.1%}. Each stock gets risk budget × conviction ÷ its volatility, then the caps (stock cap by "
        "uncertainty: Low 5%, Medium 4%, High 2%, Very high 1%). 'Share of risk' uses 3 years of weekly returns, "
        "so correlation counts: a stock that moves against the core adds less risk than its weight. Returns are "
        "in each listing's own currency; currency risk isn't modelled. Stocks below your required return get 0%."
    )
