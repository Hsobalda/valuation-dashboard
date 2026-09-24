"""Valuation dashboard -- Streamlit entry point.

Wires together the data layer, the pure engine, the research brief and the
assumption panel. No valuation math lives here.
"""

from __future__ import annotations

import streamlit as st
import pandas as pd

from data import MultiProvider, sample_tickers
from brief import build_brief, derive_starting_assumptions
from engine import run_valuation, comps_analysis
from ui import charts
from ui.assumptions import render_assumption_panel

st.set_page_config(page_title="Valuation Dashboard", layout="wide")


def fmt_money(x: float, ccy: str) -> str:
    if x is None or (isinstance(x, float) and (x != x)):  # NaN
        return "—"
    return f"{ccy} {x:,.2f}"


def fmt_pct(x: float) -> str:
    if x is None or (isinstance(x, float) and (x != x)):
        return "—"
    return f"{x:.1%}"


# --- header + ticker --------------------------------------------------------

st.title("Equity Analysis & Valuation Dashboard")
st.caption("Research first, then judgment, then math. Informational only — not investment advice.")

avail = sample_tickers()
c1, c2 = st.columns([1, 3])
with c1:
    idx = avail.index("AAPL") if "AAPL" in avail else 0
    chosen = st.selectbox("Company (offline samples)", avail, index=idx)
with c2:
    custom = st.text_input("…or type any ticker (uses live data)", "", placeholder="e.g. MSFT, KO, JNJ")

ticker = (custom.strip().upper() if custom.strip() else chosen)

provider = MultiProvider()
try:
    source = provider.source(ticker)
except Exception as e:
    st.error(f"Could not load {ticker}: {e}")
    st.stop()

if source == "sample":
    st.warning(
        "⚠️ Showing bundled **sample data** (no network access here, or ticker not "
        "fetched live). Figures are illustrative and anchored to recent public "
        "filings — verify against live data before relying on anything."
    )

info = provider.company_info(ticker)
market = provider.market_data(ticker)
metrics = provider.fundamental_metrics(ticker)
seed = derive_starting_assumptions(provider, ticker)
brief = build_brief(provider, ticker, reference_wacc=seed["wacc_reference"]["wacc"])

st.markdown(f"## {info.get('name', ticker)} ({ticker}) — {info.get('sector', '')} · {info.get('industry', '')}")
st.caption(f"Currency: {info.get('currency', '')} · Live price: {fmt_money(metrics['price'], info.get('currency',''))}")

# --- 2. research brief ------------------------------------------------------

st.markdown("### 2. Research brief — evidence before assumptions")

with st.expander("A. What is this business?", expanded=True):
    st.write(brief["business"]["summary"] or "*(no summary available)*")
    st.caption("Decision this feeds: " + brief["business"]["decision"])
    st.caption(brief["business"]["what_this_means"])

with st.expander("B. What has it done? (history)", expanded=True):
    b = brief["history"]
    st.plotly_chart(charts.history_indexed_chart(b), width="stretch")
    st.plotly_chart(charts.margin_chart(b), width="stretch")
    st.caption(
        f"Revenue CAGR: {fmt_pct(b['revenue_cagr'])} · Latest FCF/income: "
        f"{fmt_pct(b['fcf_conversion'].dropna().iloc[-1] if b['fcf_conversion'].dropna().size else float('nan'))}"
    )
    st.caption(b["what_this_means"])

with st.expander("C. How good is it? (quality / moat)", expanded=True):
    q = brief["quality"]
    st.plotly_chart(charts.roic_chart(q), width="stretch")
    st.caption(
        f"Avg ROIC {fmt_pct(q['avg_roic'])} · ROIC > WACC in {q['years_above_wacc']} of "
        f"{q['years_total']} years · gross-margin volatility {fmt_pct(q['gross_margin_std'])} · "
        f"goodwill {q['goodwill_pct_assets']:.0%} of assets"
    )
    st.caption("Decision this feeds: " + q["decision"] + " · " + q["what_this_means"])

with st.expander("E. What could go wrong? (risk)", expanded=True):
    r = brief["risk"]
    st.caption(
        f"Net debt / EBITDA: {r['latest_nd_ebitda']:.1f}x · Debt / equity: "
        f"{r['debt_to_equity']:.1f}x · Beta: {r['beta']:.2f}"
    )
    for flag in r["flags"]:
        st.warning("🚩 " + flag)
    st.caption("Decision this feeds: " + r["decision"] + " · " + r["what_this_means"])

with st.expander("F. What's already priced in?", expanded=True):
    f = brief["priced_in"]
    st.dataframe(pd.DataFrame({
        "P/E": [f["pe"]], "EV/EBITDA": [f["ev_ebitda"]],
        "EV/Revenue": [f["ev_revenue"]], "P/B": [f["pb"]],
    }), width="stretch")
    st.caption("Decision this feeds: " + f["decision"] + " · " + f["what_this_means"])

# --- 3. assumptions ---------------------------------------------------------

assumptions = render_assumption_panel(seed, ticker)

# --- 4. valuation -----------------------------------------------------------

st.markdown("### 4. Valuation")

try:
    run = run_valuation(
        base_revenue=metrics["revenue"],
        assumptions=assumptions,
        net_debt=metrics["net_debt"],
        minority_interest=metrics["minority_interest"],
        shares_diluted=metrics["shares_diluted"],
    )
except ValueError as e:
    st.error(f"Valuation failed: {e}")
    st.stop()

res = run.result
ccy = info.get("currency", "")
price = metrics["price"]
upside = res.equity_value_per_share / price - 1 if price else float("nan")
buy_zone = res.equity_value_per_share * (1.0 - assumptions.margin_of_safety)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Est. fair value / share", fmt_money(res.equity_value_per_share, ccy))
m2.metric("Upside / downside vs price", fmt_pct(upside))
m3.metric("Buy zone (≤)", fmt_money(buy_zone, ccy))
m4.metric("Terminal value % of EV", fmt_pct(res.terminal_share_of_ev))

if res.terminal_share_of_ev > 0.8:
    st.warning(
        f"Terminal value is {res.terminal_share_of_ev:.0%} of enterprise value — the "
        "model is effectively a single bet on long-run growth. Stress-test it (below)."
    )

st.plotly_chart(charts.sensitivity_heatmap(run.sensitivity), width="stretch")

# --- 5. comps + football field ---------------------------------------------

st.markdown("### 5. Comparables & football field")

peer_options = [t for t in avail if t != ticker]
default_peers = peer_options[:4]
peers = st.multiselect("Peer set (your judgment call)", peer_options, default=default_peers)

if peers:
    comps = comps_analysis(ticker, peers, ["ev_ebitda", "pe", "ev_revenue", "pb"], provider)
    st.dataframe(comps.peer_table.round(1), width="stretch")
    st.caption("Implied per-share value from each median multiple:")
    st.dataframe(pd.DataFrame({"implied value/share": comps.implied_values}), width="stretch")

    dcf_vals = [v for row in run.sensitivity.values for v in row if v is not None and v == v]
    dcf_lo, dcf_hi = min(dcf_vals), max(dcf_vals)
    comp_vals = [v for v in comps.implied_values.values() if v is not None and v == v]
    ranges = {"DCF (sensitivity)": (dcf_lo, dcf_hi)}
    if comp_vals:
        ranges["Comps (multiples)"] = (min(comp_vals), max(comp_vals))
    st.plotly_chart(charts.football_field(ranges, price, buy_zone, ccy), width="stretch")
else:
    st.caption("Add at least one peer to see the comps table and football field.")

# --- 6. margin of safety ----------------------------------------------------

st.markdown("### 6. Margin of safety")
mos = assumptions.margin_of_safety
st.write(
    f"Required margin of safety: **{mos:.0%}** → you'd want to pay no more than "
    f"**{fmt_money(buy_zone, ccy)}** for a value estimate of "
    f"{fmt_money(res.equity_value_per_share, ccy)}."
)
if price <= buy_zone:
    st.success(f"Current price {fmt_money(price, ccy)} is at or below the buy zone.")
else:
    st.info(f"Current price {fmt_money(price, ccy)} is above the buy zone of {fmt_money(buy_zone, ccy)}.")

st.markdown("---")
st.caption(
    "Informational and educational only — not investment advice. Data via Yahoo "
    "Finance (live) or bundled illustrative sample data (offline). Valuation is a "
    "range of judgment, not a single number."
)
