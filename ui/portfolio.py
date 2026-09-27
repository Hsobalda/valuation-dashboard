"""Stock-pie sizing panel: about N high-conviction holdings, sized by risk and conviction.

The pie is a separate pot of individual stocks (the index fund, if any, lives
elsewhere). Candidates are the latest Buy/Watch call per ticker in the journal,
re-priced at today's price, plus the company on the page, which takes priority
over its own journal entry since the sliders are the most recent view.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from brief.seeds import UNCERTAINTY_MOS
from data.journal import load_entries
from engine import implied_return, run_scenarios
from engine.sizing import Candidate, in_base_currency, portfolio_risk, size_positions
from engine.valuation import Assumptions

BASE_CURRENCY = "GBP"
BENCHMARK_EXPECTED_RETURN = 0.07  # long-run assumption for a global equity index, for comparison only


def _rating_for(mos: float) -> str:
    return next((r for r, m in UNCERTAINTY_MOS.items() if abs(m - mos) < 1e-9), "Medium")


def _reprice(provider, ticker: str, a: Assumptions) -> dict:
    """Both buy tests at today's price, from a set of assumptions."""
    m = provider.fundamental_metrics(ticker)
    bridge = (m["net_debt"], m["minority_interest"], m["shares_diluted"], m["years_since_fy_end"])
    er = implied_return(m["price"], m["revenue"], a, *bridge)
    buy_zone = run_scenarios(m["revenue"], a, *bridge).weighted_value * (1 - a.margin_of_safety)
    return {"expected_return": er, "passes_margin_of_safety": m["price"] <= buy_zone,
            "uncertainty": _rating_for(a.margin_of_safety)}


def _journal_candidates(provider) -> tuple[dict[str, dict], list[str]]:
    latest = {e["ticker"]: e for e in load_entries() if e.get("decision") in ("Buy", "Watch")}
    pool, failed = {}, []
    for t, e in latest.items():
        saved = {k: v for k, v in e.get("assumptions", {}).items() if k in Assumptions.__dataclass_fields__}
        if saved.get("growth_override") is not None:
            saved["growth_override"] = tuple(saved["growth_override"])
        try:
            pool[t] = {**_reprice(provider, t, Assumptions(**saved)),
                       "source": f"journal: {e['decision']} on {e['date']}"}
        except Exception:
            failed.append(t)
    return pool, failed


def _base_closes(provider, ticker: str) -> pd.Series | None:
    """Weekly closes in sterling: a US stock's risk to a UK investor includes the dollar."""
    closes = provider.weekly_closes(ticker)
    # the light profile lookup: works for index funds, which have no statements to load
    profile = (provider.peer_profiles([ticker]) or [{}])[0]
    ccy = profile.get("currency") or BASE_CURRENCY
    if closes is None or ccy == BASE_CURRENCY:
        return closes
    fx = provider.weekly_closes(f"{ccy}{BASE_CURRENCY}=X")
    return None if fx is None else in_base_currency(closes, fx)


def plan_pie(closes: dict[str, pd.Series], benchmark: str, pool: dict[str, dict], hurdle: float,
             holdings: int, sector_cap: float) -> dict:
    """Size the pie from sterling price histories and each candidate's buy-test
    results. No Streamlit here, so the whole calculation can be tested."""
    tickers = [t for t in pool if t in closes]
    returns = pd.DataFrame({t: closes[t] for t in [benchmark, *tickers]}).pct_change(fill_method=None).dropna()
    vols = returns.std() * np.sqrt(52)
    cands = [Candidate(t, pool[t]["sector"], pool[t]["expected_return"], pool[t]["uncertainty"],
                       float(vols[t]), pool[t]["passes_margin_of_safety"]) for t in tickers]
    sized = size_positions(cands, hurdle, holdings, sector_cap)
    held = sized[sized["weight"] > 0] if not sized.empty else sized
    out = {"sized": sized, "vols": vols, "corr": returns.corr()[benchmark], "contrib": pd.Series(dtype=float),
           "today": pd.Series(dtype=float), "filled": 0.0, "expected": float("nan"),
           "pie_vol": float("nan"), "pie_corr": float("nan")}
    if held.empty:
        return out
    today = held.set_index("ticker")["weight"] / held["weight"].sum()
    pie_vol, contrib = portfolio_risk(today, returns)
    pie_returns = returns[list(today.index)].to_numpy() @ today.to_numpy()
    return {**out, "today": today, "contrib": contrib, "filled": float(held["weight"].sum()),
            "expected": float(sum(today[t] * pool[t]["expected_return"] for t in today.index)),
            "pie_vol": pie_vol, "pie_corr": float(np.corrcoef(pie_returns, returns[benchmark])[0, 1])}


def render_portfolio(provider, current: dict | None) -> None:
    c1, c2, c3 = st.columns(3)
    value = c1.number_input("Planned pie size when full (£)", min_value=0.0, value=5_000.0, step=250.0,
                            key="pf:value", help="What the pie will hold once it has its target number of "
                                                 "holdings. Each stock is bought at its planned size of this")
    holdings = c2.number_input("Target number of holdings", 3, 25, 10, 1, key="pf:holdings",
                               help="Sets the standard position: 10 holdings = 10% each, before adjustments")
    hurdle = c3.number_input("Required return (%)", 0.0, 30.0,
                             (current or {}).get("hurdle", 0.10) * 100, 0.5, key="pf:hurdle") / 100
    c4, c5, _ = st.columns(3)
    sector_cap = c4.number_input("Sector cap (% of pie)", 10.0, 100.0, 30.0, 5.0, key="pf:sector") / 100
    benchmark = c5.text_input("Benchmark", "VWRL.L", key="pf:bench",
                              help="Vanguard FTSE All-World: what the pie has to beat").strip().upper()

    pool, failed = _journal_candidates(provider)
    if current and current.get("expected_return") is not None:
        pool[current["ticker"]] = {**current, "source": "this page (current sliders)"}
    if failed:
        st.warning(f"Couldn't re-price journal calls for {', '.join(failed)}; left out.")
    if not pool:
        st.caption("Save Buy or Watch calls in the journal (or value a company above) to size them here.")
        return

    closes = {t: _base_closes(provider, t) for t in [benchmark, *pool]}
    missing = [t for t, c in closes.items() if c is None]
    if missing:
        st.warning(f"No usable price history for {', '.join(missing)} (needs live data and a year of prices).")
    if closes[benchmark] is None:
        return
    sectors = {t: provider.company_info(t).get("sector") or "Unknown" for t in pool}
    plan = plan_pie({t: c for t, c in closes.items() if c is not None}, benchmark,
                    {t: {**pool[t], "sector": sectors[t]} for t in pool if closes[t] is not None},
                    hurdle, int(holdings), sector_cap)
    sized, today, vols, corr, contrib = plan["sized"], plan["today"], plan["vols"], plan["corr"], plan["contrib"]
    if sized.empty:
        st.caption("None of the candidates has enough price history to size.")
        return

    rows = []
    for _, r in sized.sort_values("weight", ascending=False).iterrows():
        t, er = r["ticker"], r["expected_return"]
        rows.append({
            "Stock": t, "Sector": r["sector"],
            "Expected return": "—" if er is None else f"{er:.1%}",
            "Uncertainty": r["uncertainty"],
            "Buy tests": ("✓" if er is not None and er >= hurdle else "✗") + " return · "
                         + ("✓" if pool[t]["passes_margin_of_safety"] else "✗") + " safety",
            "Volatility (£)": f"{r['volatility']:.1%}",
            "Corr. with benchmark": f"{corr[t]:.2f}",
            "Planned weight": f"{r['weight']:.1%}",
            "£ to invest now": f"{r['weight'] * value:,.0f}",
            "Pie %": f"{today.get(t, 0):.1%}",
            "Share of pie risk": f"{contrib[t]:.0%}" if t in today.index else "—",
            "Note": r["limit"] or pool[t]["source"],
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")

    if today.empty:
        st.info("Nothing clears your required return at today's prices, so nothing to buy yet.")
        return
    filled, expected, pie_vol, pie_corr = plan["filled"], plan["expected"], plan["pie_vol"], plan["pie_corr"]
    st.caption(
        f"Invest £{filled * value:,.0f} now across {len(today)} holdings, each at its planned size, and keep "
        f"£{(1 - filled) * value:,.0f} back for the other {int(holdings) - len(today)} slots until more ideas pass "
        f"your tests; putting it all in now would make each position about {1 / filled:.1f}× its planned size. "
        f"'Pie %' is the split to enter in the pie. Pie: expected return ~{expected:.1%} a year (benchmark assumed "
        f"{BENCHMARK_EXPECTED_RETURN:.0%}), volatility {pie_vol:.1%} (benchmark {vols[benchmark]:.1%}), "
        f"correlation with the benchmark {pie_corr:.2f}."
    )
    st.caption(
        "How sizes are set: the standard position is 1/N of the pie, scaled by conviction (0.6-1.5×: expected "
        "return above your required return, and uncertainty) and by volatility against a typical 25%-volatility "
        "stock (0.5-1.5×). Failing the required return means no position; failing only the margin of safety means "
        "a half-size starter. Caps: 2× the standard for Low uncertainty, 1.5× Medium, 1× High, 0.5× Very high, "
        "and the sector cap. Volatility and correlation use 3 years of weekly returns in sterling, so the dollar's "
        "moves count for US stocks."
    )
