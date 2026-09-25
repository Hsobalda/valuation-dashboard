"""Valuation dashboard -- Streamlit entry point.

Wires together the data layer, the pure engine, the research brief and the
assumption panel. No valuation math lives here.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import math
import os

import streamlit as st
import pandas as pd

from data import MultiProvider, sample_tickers
from brief import build_brief, dcf_applicable, derive_starting_assumptions, reinvestment_history, screen_peers
from engine import comps_analysis, implied_revenue_growth, run_scenarios, run_valuation
from ui import charts
from ui.tables import projection_table, reinvestment_history_table
from ui.assumptions import render_assumption_panel
from ui.excel_export import build_dcf_workbook
from ui.journal import render_history, render_save_form

st.set_page_config(page_title="Valuation Dashboard", layout="wide")

# the SEC requires a contact email on every request; kept in a git-ignored secret
try:
    if "SEC_CONTACT_EMAIL" in st.secrets:
        os.environ.setdefault("SEC_CONTACT_EMAIL", st.secrets["SEC_CONTACT_EMAIL"])
except FileNotFoundError:
    pass


def fmt_money(x: float, ccy: str) -> str:
    if x is None or (isinstance(x, float) and (x != x)):  # NaN
        return "—"
    return f"{ccy} {x:,.2f}"


def fmt_pct(x: float) -> str:
    if x is None or (isinstance(x, float) and (x != x)):
        return "—"
    return f"{x:.1%}"


# --- header + ticker --------------------------------------------------------

st.title("Valuation Dashboard")
st.caption("Evidence first, then assumptions, then the valuation. For education only, not investment advice.")

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

if source == "live":
    inc_years = provider.income_statement(ticker)["revenue"].dropna().index
    st.caption(
        f"Financial statements: {'SEC 10-K filings, gaps filled from Yahoo Finance' if provider.uses_sec_filings(ticker) else 'Yahoo Finance'}"
        f" (FY{inc_years.min()}–FY{inc_years.max()}). Prices, estimates and targets: Yahoo Finance."
    )

if source == "sample":
    st.warning(
        "Showing bundled **sample data** (no network access here, or ticker not "
        "fetched live). Figures are illustrative and anchored to recent public "
        "filings; verify against live data before relying on anything.",
        icon=":material/cloud_off:",
    )

info = provider.company_info(ticker)
metrics = provider.fundamental_metrics(ticker)
seed = derive_starting_assumptions(provider, ticker)
brief = build_brief(provider, ticker, reference_wacc=seed["wacc_reference"]["wacc"])

st.markdown(f"## {info.get('name', ticker)} ({ticker}) · {info.get('sector', '')} · {info.get('industry', '')}")
st.caption(f"Currency: {info.get('currency', '')} · Price: {fmt_money(metrics['price'], info.get('currency', ''))}")

# --- 1. research brief ------------------------------------------------------

st.markdown("### 1. Research brief: evidence before assumptions")

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
    if not dcf_applicable(info):
        st.caption(
            "For a bank or insurer, operating cash flow swings with loans, deposits and "
            "claims, so free cash flow isn't a meaningful measure. Judge capital allocation "
            "on dividends, buybacks and the share count against capital ratios instead."
        )
        st.caption(f"Diluted share count {fmt_pct(d['share_cagr'])} a year.")
    else:
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
        st.warning(flag, icon=":material/flag:")
    st.caption("Decision this feeds: " + r["decision"] + " · " + r["what_this_means"])

with st.expander("F. What's already priced in?", expanded=True):
    f = brief["priced_in"]
    st.dataframe(pd.DataFrame({
        "P/E": [f["pe"]], "EV/EBITDA": [f["ev_ebitda"]],
        "EV/Revenue": [f["ev_revenue"]], "P/B": [f["pb"]],
    }), width="stretch")
    st.caption("Decision this feeds: " + f["decision"] + " · " + f["what_this_means"])

# --- 2. assumptions + 3. valuation ------------------------------------------

ccy = info.get("currency", "")
price = metrics["price"]
run = None
buy_zone = None

if metrics.get("currency_mismatch"):
    st.markdown("### 2–3. Valuation")
    st.warning(
        f"{ticker} trades in {info.get('currency')} but reports in "
        f"{info.get('financial_currency')} (usually a foreign company's US listing). "
        "Per-share values can't be compared with the price without exchange-rate and "
        "ADR-ratio adjustments, so the valuation is skipped. Try its home listing "
        "instead, if it has one."
    )
elif not dcf_applicable(info):
    st.markdown("### 2–3. Valuation")
    st.info(
        f"A cash-flow DCF doesn't apply to {info.get('industry', 'this industry').lower()}: "
        "for a bank, lender or insurer, debt and deposits are the raw material of the business "
        "rather than financing, so free cash flow to the firm isn't meaningful. Value it "
        "on P/B and P/E against peers below, judging P/B against return on equity."
    )
else:
    assumptions = render_assumption_panel(seed, ticker)

    st.markdown("### 3. Valuation")
    try:
        run = run_valuation(
            base_revenue=metrics["revenue"],
            assumptions=assumptions,
            net_debt=metrics["net_debt"],
            minority_interest=metrics["minority_interest"],
            shares_diluted=metrics["shares_diluted"],
            years_since_fy_end=metrics["years_since_fy_end"],
        )
    except ValueError as e:
        st.error(f"Valuation failed: {e}")
        st.stop()

    res = run.result
    scen = run_scenarios(
        metrics["revenue"], assumptions, net_debt=metrics["net_debt"],
        minority_interest=metrics["minority_interest"], shares_diluted=metrics["shares_diluted"],
        years_since_fy_end=metrics["years_since_fy_end"],
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
        years_since_fy_end=metrics["years_since_fy_end"],
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

    mkt = provider.market_data(ticker)
    if mkt.get("analyst_count") and mkt.get("target_mean"):
        gap = fair_value / mkt["target_mean"] - 1
        st.caption(
            f"Analysts ({mkt['analyst_count']}): mean 12-month target "
            f"{fmt_money(mkt['target_mean'], ccy)} (range {fmt_money(mkt['target_low'], ccy)}–"
            f"{fmt_money(mkt['target_high'], ccy)}). Your fair value is {abs(gap):.0%} "
            f"{'above' if gap > 0 else 'below'} the street: that gap is your variant view, "
            "so be ready to say which assumption drives it."
        )

    yrs = metrics["years_since_fy_end"]
    current_nopat = metrics["revenue"] * assumptions.ebit_margin * (1 - assumptions.tax_rate)
    market_ev = metrics["market_cap"] + metrics["net_debt"] + metrics["minority_interest"]
    exit_multiple = res.terminal_value / res.final_nopat if res.final_nopat > 0 else float("nan")
    st.caption(
        f"Valued as of today: cash flows are discounted mid-year"
        + (f", and the last fiscal year ended {yrs * 12:.0f} months ago" if yrs else "")
        + f". The terminal value is {exit_multiple:.1f}× final-year NOPAT; the market "
        f"values the company at {market_ev / current_nopat:.1f}× today's NOPAT."
        if current_nopat > 0 and exit_multiple == exit_multiple else
        "Valued as of today: cash flows are discounted mid-year."
    )

    if res.terminal_share_of_ev > 0.8:
        st.warning(
            f"Terminal value is {res.terminal_share_of_ev:.0%} of enterprise value, so most of the "
            "value comes after the explicit forecast and rests on the fade period and terminal "
            "assumptions. Stress-test them with the scenarios and sensitivity table below."
        )

    st.markdown("#### Scenarios")
    st.dataframe(pd.DataFrame({
        "Probability": [f"{s.probability:.0%}" for s in scen.scenarios],
        "Growth, year 1 → 5": [f"{s.assumptions.growth_path()[0]:.1%} → {s.assumptions.growth_path()[-1]:.1%}"
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
        f"{assumptions.growth_path()[0]:.1%} ÷ {assumptions.roic:.1%} = "
        f"{assumptions.growth_path()[0] / assumptions.roic:.0%} of NOPAT reinvested."
    )
    prov = seed.get("provenance", {})
    notes = {
        k: (prov.get(k, "") if abs(getattr(assumptions, k) - seed[k]) < 1e-9
            else f"Your input. Starting point was {seed[k]:.4g}: {prov.get(k, 'default')}")
        for k in ("growth_y1", "growth_y2", "growth_y5", "ebit_margin", "target_ebit_margin", "tax_rate",
                  "roic", "fade_years", "terminal_excess_return", "terminal_growth", "discount_rate")
    }
    if assumptions.growth_override is not None:
        notes.update({f"growth_y{i}": "Segment build: blended growth of the segments" for i in range(1, 6)})
    notes.update(
        base_revenue="Latest fiscal year revenue", net_debt="Total debt less cash and short-term investments",
        shares_diluted="Current shares outstanding x latest diluted/basic ratio",
        price="Share price when exported",
        margin_of_safety=next((f"{r} uncertainty rating" for r, m in seed["uncertainty_mos"].items()
                               if m == assumptions.margin_of_safety), ""),
    )
    st.download_button(
        "Download this DCF as an Excel model", icon=":material/table_view:",
        data=build_dcf_workbook({
            "name": info.get("name", ticker), "ticker": ticker, "currency": ccy,
            "base_year": int(provider.income_statement(ticker)["revenue"].dropna().index[-1]),
            "base_revenue": metrics["revenue"], "net_debt": metrics["net_debt"],
            "minority_interest": metrics["minority_interest"], "shares_diluted": metrics["shares_diluted"],
            "price": price, "years_since_fy_end": metrics["years_since_fy_end"],
            "data_source": "sample data" if source == "sample" else
                           ("SEC filings + Yahoo" if provider.uses_sec_filings(ticker) else "Yahoo Finance"),
        }, assumptions, notes),
        file_name=f"{ticker}_DCF.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        help="The base case with every step as a live formula: change an input and the value updates.",
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

# --- 4. relative valuation + football field ---------------------------------

st.markdown("### 4. Relative valuation (context, not part of fair value)")

if metrics.get("currency_mismatch"):
    st.caption("Comparables skipped for the same currency reason as the valuation.")
else:
    target_profile = (provider.peer_profiles([ticker]) or [{}])[0]
    screened = screen_peers(target_profile, provider.peer_profiles(provider.peer_suggestions(ticker)))
    if screened:
        st.markdown("#### Candidate peers")
        st.dataframe(pd.DataFrame({
            "Name": [c["name"] for c in screened],
            "Industry": [c["industry"] for c in screened],
            f"Market cap ({ccy} bn)": [f"{c['market_cap'] / 1e9:,.0f}" for c in screened],
            "Operating margin": [fmt_pct(c["operating_margin"]) if c["operating_margin"] is not None else "—"
                                 for c in screened],
            "Suggested": ["Yes" if c["suggested"] else "No" for c in screened],
            "Why": [c["reason"] for c in screened],
        }, index=[c["ticker"] for c in screened]), width="stretch")
        st.caption(
            f"Candidates are the largest companies in {ticker}'s Yahoo industry (topped up from "
            f"its sector when the industry is thin). Target operating margin: "
            f"{fmt_pct(target_profile.get('operating_margin'))}. Suggested peers have a margin "
            "within 1.5× of it (or within 3 points), a rough test for the same business model."
        )

    peers = st.multiselect(
        "Peer set (your judgment call)", [c["ticker"] for c in screened],
        default=[c["ticker"] for c in screened if c["suggested"]],
        accept_new_options=True, key=f"{ticker}:peers",
        help="Starts with the suggested candidates. Type any ticker to add it, e.g. SBRY.L "
             "for Sainsbury's.",
    )
    peers = list(dict.fromkeys(p.strip().upper() for p in peers if p.strip()))

    # enterprise-value multiples mean nothing for banks and insurers
    multiples = (["ev_ebitda", "pe", "pe_fwd", "ev_revenue", "ev_revenue_fwd", "pb"]
                 if dcf_applicable(info) else ["pe", "pe_fwd", "pb"])
    if peers:
        comps = comps_analysis(ticker, peers, multiples, provider)
        missing = [p for p in peers if p not in comps.peer_table.index]
        if missing:
            st.warning(
                f"No usable data for {', '.join(missing)} (missing, or reported in a different "
                "currency from its share price), so left out of the medians."
            )
        table = comps.peer_table.map(lambda v: "—" if v != v else f"{v:,.1f}×")
        table.loc["Peer median"] = [f"{comps.medians[c]:,.1f}×" if comps.medians[c] == comps.medians[c] else "—"
                                    for c in table.columns]
        table.loc[f"{ticker} vs median"] = [
            "—" if comps.premium[c] != comps.premium[c]
            else f"{abs(comps.premium[c]):.0%} {'premium' if comps.premium[c] > 0 else 'discount'}"
            for c in table.columns
        ]
        st.dataframe(table, width="stretch")
        st.caption(
            "A premium isn't a sell signal and a discount isn't a buy signal: the question is "
            "whether the business earns it (compare growth, margins and ROIC in the brief)."
        )
    else:
        st.caption("No peers selected. Add tickers above to compare multiples.")

ranges = {}
if run is not None:
    dcf_vals = [v for row in run.sensitivity.values for v in row if v is not None and v == v]
    ranges["DCF (bear–bull)"] = (scen.scenarios[0].value_per_share, scen.scenarios[-1].value_per_share)
    ranges["DCF (sensitivity)"] = (min(dcf_vals), max(dcf_vals))
mkt = provider.market_data(ticker)
if mkt.get("target_low") and mkt.get("target_high"):
    ranges["Analyst targets"] = (mkt["target_low"], mkt["target_high"])
if ranges:
    st.markdown("#### Football field")
    st.plotly_chart(charts.football_field(ranges, price, buy_zone, ccy), width="stretch")

# --- 5. margin of safety ----------------------------------------------------

if run is not None:
    st.markdown("### 5. Margin of safety")
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

# --- 6. journal --------------------------------------------------------------

st.markdown("### 6. Valuation journal")
if run is not None:
    render_save_form({
        "date": dt.date.today().isoformat(),
        "ticker": ticker,
        "name": info.get("name", ticker),
        "currency": ccy,
        "price": price,
        "fair_value": fair_value,
        **{s.name.lower(): s.value_per_share for s in scen.scenarios},
        "buy_zone": buy_zone,
        "margin_of_safety": assumptions.margin_of_safety,
        "assumptions": dataclasses.asdict(assumptions),
        "data": "sample" if source == "sample" else
                ("SEC filings + Yahoo" if provider.uses_sec_filings(ticker) else "Yahoo"),
    })
render_history(provider, ticker)

st.markdown("---")
st.caption(
    "For education only, not investment advice. Data: SEC EDGAR filings and Yahoo Finance "
    "(live), or bundled illustrative sample data (offline). A valuation is a range of "
    "judgement, not a single number."
)
