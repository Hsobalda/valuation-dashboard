# Valuation Dashboard

[![CI](https://github.com/Hsobalda/valuation-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/Hsobalda/valuation-dashboard/actions/workflows/ci.yml)

A Streamlit app for valuing listed companies with a three-stage DCF, cross-checked
against trading comparables. It pulls financials from Yahoo Finance, shows the
historical evidence, and seeds each assumption from the company's own history so
the user can see where every input came from before changing it.

<!-- Live demo: add Streamlit Community Cloud link once deployed -->

## Features

- Research brief: business overview, financial history, quality indicators, risk,
  and the current P/E, EV/EBITDA, EV/Revenue and P/B.
- Assumption panel: growth, margins, reinvestment, WACC, terminal growth and fade
  period, each labelled with its source (e.g. "FY2024 operating margin").
- Three-stage DCF with a WACC × terminal growth sensitivity table, and a warning
  when terminal value makes up most of the valuation.
- Comparables: EV/Revenue, EV/EBITDA and P/E against a chosen peer set, shown on a
  football-field chart next to the DCF value and current price.
- Buy price after applying a required margin of safety.

## Methodology

Unlevered free cash flow is projected from revenue growth, EBIT margin, tax rate,
D&A, capex and working capital:

    FCFF = EBIT × (1 − t) + D&A − capex − ΔNWC

The discount rate (WACC) is set by the user, starting from 8%. The engine
includes CAPM and market-value WACC functions, which are not yet wired into the
app.

| Stage | Period | Treatment |
|---|---|---|
| 1 | Years 1–n | Explicit FCFF projections |
| 2 | Fade period | Growth declines linearly from the Stage 1 exit rate to terminal growth |
| 3 | Terminal | Gordon Growth on the final fade-year cash flow |

The length of Stage 2 reflects competitive advantage: roughly 5 years for a company
with no moat, 10 for a narrow moat and 20 for a wide one, following the approach
Morningstar uses. Enterprise value less net debt and minority interest gives
equity value, which is divided by diluted shares.

Quality metrics include ROIC, gross/operating/net margins, margin volatility and
FCF conversion (FCF / net income).

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
zero-growth perpetuity check (value = FCF / WACC), and cases for sparse data and
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
Liverpool, to learn company valuation by building the model from scratch.

## Disclaimer

For educational purposes only. Not investment advice.
