# Valuation Dashboard (v1)

An interactive equity valuation tool built to the [`BUILD-SPEC.md`](../BUILD-SPEC.md).
**Research first, then judgment, then math** — the engine does the arithmetic; you do
the analysis.

## Quick start

```bash
python3 -m venv .venv
.venv/bin/pip install -r dashboard/requirements.txt
.venv/bin/streamlit run dashboard/app.py
```

## What it does

1. **Research brief** — six evidence panels (business, history, quality/moat, risk,
   what's-priced-in) assembled from normalized financials. They show evidence, never
   draw conclusions.
2. **Assumption panel** — sliders pre-filled from the company's own history, each with
   a provenance label (where the number came from). No silent defaults.
3. **Valuation** — a 3-stage DCF where the *fade period* is your moat judgment
   (5 = none, 10 = narrow, 20 = wide), plus a WACC × terminal-growth sensitivity
   heatmap and a terminal-value share warning.
4. **Comparables + football field** — pick a peer set, get median multiples, implied
   per-share values, and a football-field chart vs. current price and buy zone.
5. **Margin of safety** — the buy-zone price = fair value × (1 − required margin).

## Data: live vs sample

- **Live** — `YFinanceProvider` fetches Yahoo Finance (statements, market data, info).
  Used automatically when a network connection to Yahoo is available.
- **Sample** — `SampleProvider` serves bundled, clearly-labelled illustrative data for
  `AAPL, MSFT, PEP, T, TSCO.L`. Used automatically when live data is unreachable (e.g.
  offline/sandboxed). A banner is shown so you're never misled.

The data layer is behind a `DataProvider` interface — swap in FMP / Alpha Vantage later
without touching the engine or UI.

## Structure

```
dashboard/
├── app.py            # Streamlit entry point (wiring only, no math)
├── engine/           # PURE valuation math -- zero I/O
│   ├── wacc.py  projection.py  dcf.py  sensitivity.py
│   ├── quality.py  comps.py  valuation.py
├── data/             # data access -- the only layer touching yfinance
│   ├── provider.py  schema.py  sample_data.py  cache.py  loader.py
├── brief/            # research-brief evidence panels + assumption seeds
├── ui/               # Streamlit widgets + Plotly charts
└── tests/            # pytest (offline, deterministic)
```

## Tests

```bash
.venv/bin/python -m pytest dashboard/tests -q
```

Includes a spreadsheet cross-check and a perpetuity sanity test (g=0 → value = FCF/WACC)
per the acceptance criteria.

## Disclaimer

Informational and educational only — not investment advice. Always verify sample data
against live filings before relying on any output.
