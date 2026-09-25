"""Valuation dashboard -- Streamlit entry point.

Wires together the data layer, the pure engine, the research brief and the
assumption panel. No valuation math lives here.
"""

from __future__ import annotations

import math

import streamlit as st
import pandas as pd

from data import MultiProvider, sample_tickers
from brief import build_brief, dcf_applicable, derive_starting_assumptions, reinvestment_history
from engine import comps_analysis, implied_revenue_growth, run_scenarios, run_valuation
from ui import charts
from ui.tables import projection_table, reinvestment_history_table
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

with st.expander("D. How does it use its cash? (capital allocation)", expanded=True):
    d = brief["capital_allocation"]
    st.plotly_chart(charts.capital_allocation_chart(d, info.get("currency", "")), width="stretch")
    st.caption(
        f"Returned to shareholders: {fmt_pct(d['payout_of_fcf'])} of free cash flow, net of "
        f"buybacks that only offset stock pay ({fmt_pct(d['sbc_share_of_buybacks'])} of buybacks) · "
        f"diluted share count {fmt_pct(d['share_cagr'])} a year · net debt "
        f"{d['net_debt_start'] / 1e9:,.1f}bn → {d['net_debt_end'] / 1e9:,.1f}bn"
    )
    for flag in d["flags"]:
        st.warning(flag, icon=":material/flag:")
    st.caption("Decision this feeds: " + d["decision"] + " · " + d["what_this_means"])

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

# --- 3. assumptions + 4. valuation ------------------------------------------

ccy = info.get("currency", "")
price = metrics["price"]
run = None
buy_zone = None

if not dcf_applicable(info.get("industry", "")):
    st.markdown("### 3–4. Valuation")
    st.info(
        f"A cash-flow DCF doesn't apply to {info.get('industry', 'this industry').lower()}: "
        "for a bank or insurer, debt and deposits are the raw material of the business "
        "rather than financing, so free cash flow to the firm isn't meaningful. Value it "
        "on P/B and P/E against peers below, judging P/B against return on equity."
    )
else:
    assumptions = render_assumption_panel(seed, ticker)

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
    scen = run_scenarios(
        metrics["revenue"], assumptions, net_debt=metrics["net_debt"],
        minority_interest=metrics["minority_interest"], shares_diluted=metrics["shares_diluted"],
    )
    fair_value = scen.weighted_value
    upside = fair_value / price - 1 if price else float("nan")
    buy_zone = fair_value * (1.0 - assumptions.margin_of_safety)

    if res.equity_value_per_share <= 0:
        st.warning(
            "In the base case debt exceeds the value of the operations, so the equity is "
            "worth nothing (shareholders can't lose more than they put in). Any value "
            "shown comes from the bull case; check the assumptions first."
        )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Fair value / share", fmt_money(fair_value, ccy),
              help="Probability-weighted across the bear, base and bull cases below")
    m2.metric("Upside / downside vs price", fmt_pct(upside))
    m3.metric("Buy zone (≤)", fmt_money(buy_zone, ccy))
    m4.metric("Terminal value % of EV", fmt_pct(res.terminal_share_of_ev))

    implied = implied_revenue_growth(
        price, metrics["revenue"], assumptions, net_debt=metrics["net_debt"],
        minority_interest=metrics["minority_interest"], shares_diluted=metrics["shares_diluted"],
    )
    if implied is None and assumptions.roic <= assumptions.discount_rate:
        st.markdown(
            f"**Reverse DCF:** no growth rate justifies {fmt_money(price, ccy)}. With ROIC "
            f"({assumptions.roic:.1%}) at or below your discount rate "
            f"({assumptions.discount_rate:.1%}), each unit of growth costs more than it "
            "earns, so faster growth lowers value. The market is either expecting higher "
            "returns on capital or accepting a lower return than you require."
        )
    elif implied is None:
        st.markdown(
            "**Reverse DCF:** no growth rate between −10% and 40% a year justifies the "
            "current price with your other assumptions, so the gap is in margins, "
            "returns on capital or the discount rate rather than growth."
        )
    else:
        path = assumptions.growth_path()
        path_avg = math.prod(1 + g for g in path) ** (1 / len(path)) - 1
        st.markdown(
            f"**Reverse DCF:** at {fmt_money(price, ccy)} the market is pricing in about "
            f"**{implied:.1%}** revenue growth a year for the next {assumptions.years} years "
            f"(your path averages {path_avg:.1%}), holding your other assumptions fixed."
        )

    if res.terminal_share_of_ev > 0.8:
        st.warning(
            f"Terminal value is {res.terminal_share_of_ev:.0%} of enterprise value — the "
            "model is effectively a single bet on long-run growth. Stress-test it (below)."
        )

    st.markdown("#### Scenarios")
    st.dataframe(pd.DataFrame({
        "Probability": [f"{s.probability:.0%}" for s in scen.scenarios],
        "Growth, year 1 → 5": [f"{s.assumptions.growth_y1:.1%} → {s.assumptions.growth_y5:.1%}"
                               for s in scen.scenarios],
        "Target EBIT margin": [f"{s.assumptions.target_ebit_margin:.1%}" for s in scen.scenarios],
        "Value / share": [fmt_money(s.value_per_share, ccy) for s in scen.scenarios],
        "vs price": [fmt_pct(s.value_per_share / price - 1) if price else "—" for s in scen.scenarios],
    }, index=[s.name for s in scen.scenarios]), width="stretch")

    st.plotly_chart(charts.sensitivity_heatmap(run.sensitivity), width="stretch")

    st.markdown("#### Stage 1 projection")
    st.dataframe(projection_table(run.projection, ccy), width="stretch")
    st.caption(
        f"Reinvestment = NOPAT × growth ÷ ROIC: the net capex and working capital needed "
        f"to grow if new capital earns {assumptions.roic:.1%}. Year 1: "
        f"{assumptions.growth_y1:.1%} ÷ {assumptions.roic:.1%} = "
        f"{assumptions.growth_y1 / assumptions.roic:.0%} of NOPAT reinvested."
    )
    hist = reinvestment_history(provider, ticker)
    if not hist.empty:
        st.markdown("#### What it has actually reinvested")
        st.dataframe(reinvestment_history_table(hist, ccy), width="stretch")
        st.caption(
            "Net capex = capex − D&A: spending beyond replacing worn-out assets. It "
            "excludes working capital and acquisitions, so it understates total "
            "reinvestment. Under IFRS 16, D&A includes depreciation on leased assets "
            "that capex doesn't, which can make net capex look negative."
        )

# --- 5. comps + football field ---------------------------------------------

st.markdown("### 5. Comparables & football field")

suggested = provider.peer_suggestions(ticker)
peers = st.multiselect(
    "Peer set (your judgment call)", suggested, default=suggested[:4],
    accept_new_options=True, key=f"{ticker}:peers",
    help="Suggestions are the largest companies in the same Yahoo industry, mostly "
         "US-listed. Type any ticker to add it, e.g. SBRY.L for Sainsbury's.",
)
peers = list(dict.fromkeys(p.strip().upper() for p in peers if p.strip()))

if peers:
    comps = comps_analysis(ticker, peers, ["ev_ebitda", "pe", "ev_revenue", "pb"], provider)
    missing = [p for p in peers if p not in comps.peer_table.index]
    if missing:
        st.warning(f"No data for {', '.join(missing)}, so left out of the medians.")
    st.dataframe(comps.peer_table.round(1), width="stretch")
    st.caption("Implied per-share value from each median multiple:")
    st.dataframe(pd.DataFrame({"implied value/share": comps.implied_values}), width="stretch")

    ranges = {}
    if run is not None:
        dcf_vals = [v for row in run.sensitivity.values for v in row if v is not None and v == v]
        ranges["DCF (bear–bull)"] = (scen.scenarios[0].value_per_share, scen.scenarios[-1].value_per_share)
        ranges["DCF (sensitivity)"] = (min(dcf_vals), max(dcf_vals))
    comp_vals = [v for v in comps.implied_values.values() if v is not None and v == v]
    if comp_vals:
        ranges["Comps (multiples)"] = (min(comp_vals), max(comp_vals))
    if ranges:
        st.plotly_chart(charts.football_field(ranges, price, buy_zone, ccy), width="stretch")
else:
    st.caption("Add at least one peer to see the comps table and football field.")

# --- 6. margin of safety ----------------------------------------------------

if run is not None:
    st.markdown("### 6. Margin of safety")
    mos = assumptions.margin_of_safety
    st.write(
        f"Required margin of safety: **{mos:.0%}** → you'd want to pay no more than "
        f"**{fmt_money(buy_zone, ccy)}** for a value estimate of "
        f"{fmt_money(fair_value, ccy)}."
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
