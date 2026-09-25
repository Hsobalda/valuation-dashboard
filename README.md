# Valuation Dashboard

[![CI](https://github.com/Hsobalda/valuation-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/Hsobalda/valuation-dashboard/actions/workflows/ci.yml)

A Streamlit app for valuing listed companies with a three-stage DCF, cross-checked
against trading comparables. It pulls financials from Yahoo Finance, shows the
historical evidence, and seeds each assumption from the company's own history so
the user can see where every input came from before changing it.

<!-- Live demo: add Streamlit Community Cloud link once deployed -->

## Features

- Research brief: business overview, financial history, quality indicators, capital
  allocation (free cash flow vs dividends and buybacks, share count trend), risk,
  and the current P/E, EV/EBITDA, EV/Revenue and P/B.
- Assumption panel: growth, margins, reinvestment, discount rate, terminal growth and fade
  period, each labelled with its source (e.g. "FY2024 operating margin").
- Three-stage DCF with a discount rate × terminal growth sensitivity table, and a warning
  when terminal value makes up most of the valuation.
- Reverse DCF: the revenue growth the current share price implies, given the other
  assumptions.
- Comparables: EV/Revenue, EV/EBITDA, P/E and P/B against peers suggested from the
  same industry (or any tickers typed in), shown on a football-field chart next to
  the DCF value and current price.
- Banks and insurers are valued on comparables only, since free cash flow to the
  firm isn't meaningful when debt is the raw material of the business.
- Buy price after applying a required margin of safety.

## Methodology

Unlevered free cash flow is projected from revenue growth, EBIT margin, tax rate,
D&A, capex and working capital:

    FCFF = EBIT × (1 − t) + D&A − capex − ΔNWC

Cash flows are discounted at a fixed 10% required return rather than each
company's WACC. A WACC measures what capital costs the company; the discount
rate here is the return an investor wants before committing money, and holding
it constant makes valuations comparable across companies. Each company's WACC
is still calculated for reference (CAPM cost of equity with a 4% risk-free rate
and 5% equity risk premium, cost of debt from interest expense / total debt,
market-value weights) and used as the hurdle in the ROIC comparison.

| Stage | Period | Treatment |
|---|---|---|
| 1 | Years 1–n | Explicit FCFF projections |
| 2 | Fade period | Growth declines linearly from the Stage 1 exit rate to terminal growth |
| 3 | Terminal | Gordon Growth on the final fade-year cash flow |

The length of Stage 2 reflects competitive advantage: roughly 5 years for a company
with no moat, 10 for a narrow moat and 20 for a wide one, following the approach
Morningstar uses. Enterprise value less net debt and minority interest gives
equity value, which is divided by diluted shares (current shares outstanding
scaled by the latest year's diluted/basic ratio).

Quality metrics include ROIC, gross/operating/net margins, margin volatility and
FCF conversion (FCF / net income).

Comparables use the median multiple of the peer set, excluding the target itself
and any negative multiples (e.g. P/E for a loss-making peer).

## Data

Live data comes from Yahoo Finance via `yfinance`. If it can't be reached, the app
falls back to bundled sample data for AAPL, MSFT, PEP, T and TSCO.L and shows a
banner saying so. Data access sits behind a `DataProvider` interface so other
sources can be added without changing the engine.

## Running locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Tests

```bash
python -m pytest -q
```

Tests run offline. They include a DCF checked against a hand-built spreadsheet, a
zero-growth perpetuity check (value = FCF / r), and cases for sparse data and
misaligned fiscal years.

## Structure

```
app.py        Streamlit entry point
engine/       Valuation maths (no I/O): WACC, projection, DCF, sensitivity, comps, quality
data/         Data providers, schema and caching
brief/        Research brief panels and starting assumptions
ui/           Streamlit widgets and Plotly charts
tests/        pytest suite
```

## About

Built by Oliver Baldaro, second-year Economics student at the University of
Liverpool. I designed the valuation methodology and used AI-assisted
development to write most of the code, then audited it myself: the commit
history includes a cash-double-count bug and a comps benchmarking error I
found and fixed during review. This is an active project I keep researching
and improving as I learn more about how professional valuation models are
built.

## Disclaimer

For educational purposes only. Not investment advice.
