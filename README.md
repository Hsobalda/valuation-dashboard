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
- Assumption panel: a revenue growth path (years 1-2 from analyst consensus, year 5
  your view), current and target margin, return on capital, discount rate, terminal
  growth, fade period and any lasting excess return, each labelled with its source
  (e.g. "consensus of 40 analysts"). A cross-check sets historical, consensus and
  fundamental growth (reinvestment rate × ROIC) side by side.
- Stage 1 projection table (revenue, margin, NOPAT, reinvestment, free cash flow)
  beside the company's actual capex, D&A and net capex history.
- Three-stage DCF with a discount rate × terminal growth sensitivity table, and a warning
  when terminal value makes up most of the valuation.
- Reverse DCF: the revenue growth the current share price implies, given the other
  assumptions.
- Relative valuation, as context rather than a price: a candidate peer table
  showing which companies are suggested and why, then EV/EBITDA, P/E, forward P/E,
  EV/Revenue, forward EV/Revenue and P/B against the peer median, with the
  target's premium or discount.
- Football field: the DCF scenario and sensitivity ranges, analysts' price targets
  and the current price.
- Analyst comparison: your fair value against the mean price target, so the gap
  (your variant view) is explicit.
- Banks, lenders and insurers get no DCF, since free cash flow to the firm isn't
  meaningful when debt is the raw material of the business. Card lenders share
  Yahoo's "Credit Services" industry with Visa and Mastercard; they're told apart
  because Yahoo reports no EBITDA for lenders.
- Bear / base / bull scenarios on growth and margin, with a probability-weighted
  fair value.
- Valuation journal: save a valuation with a Buy / Watch / Pass decision and a
  thesis, then track the return since each call and a scorecard by decision.
  Kept locally in `journal/` (git-ignored) as a record against hindsight bias.
- Buy price after a margin of safety set by an uncertainty rating (Low 20%, Medium
  30%, High 40%, Very high 50%, the scale Morningstar uses), seeded from margin
  stability, leverage, beta and free cash flow history.

## Methodology

Growth has to be paid for. A company growing at g, earning a return of ROIC on
new capital, must reinvest g / ROIC of its after-tax operating profit (NOPAT) in
net capex and working capital, so

    FCFF = NOPAT × (1 − g / ROIC)

The same rule runs through every stage, so the model can't assume growth for
free. NOPAT comes from a revenue growth path and an EBIT margin that moves from
its latest level to a target (seeded with the historical median) over five years.
Growth in years 1 and 2 is seeded from analyst consensus where available, then
moves in a straight line to a year-5 rate that is the analyst's own view.

Cash flows are discounted at a fixed 10% required return rather than each
company's WACC. A WACC measures what capital costs the company; the discount
rate here is the return an investor wants before committing money, and holding
it constant makes valuations comparable across companies. Each company's WACC
is still calculated for reference (CAPM cost of equity with a 4% risk-free rate
and 5% equity risk premium, cost of debt from interest expense / total debt,
market-value weights) and used as the hurdle in the ROIC comparison.

| Stage | Period | Treatment |
|---|---|---|
| 1 | Years 1–5 | Explicit projection at today's ROIC |
| 2 | Fade period | Growth declines linearly to terminal growth; ROIC declines linearly to the discount rate |
| 3 | Terminal | Value driver formula: NOPAT × (1 − g / RONIC) / (r − g), with RONIC = r |

The length of Stage 2 reflects competitive advantage: roughly 5 years for a company
with no moat, 10 for a narrow moat and 20 for a wide one, following the approach
Morningstar uses. In the terminal stage new investment earns exactly the required
return, so the terminal value reduces to NOPAT / r and terminal growth adds
almost no value: competition is assumed to have eroded excess returns by then.
For a moat expected to last indefinitely, a "lasting excess return" keeps the
return on new capital above r in the terminal value; it defaults to zero, and
setting it is an explicit bet on durability, which is what a high multiple for
a company like Apple implies.
A company whose ROIC is below the discount rate destroys value by growing.

Cash flows are discounted mid-year (they arrive through the year, not on its last
day) and from today rather than from the last fiscal year end. The app also
shows the terminal value as a multiple of final-year NOPAT beside the multiple
the market pays today, which makes the terminal assumption easy to challenge.

Starting assumptions come from the company's history with guards against
distorted years: historical and year-5 growth seeds are capped at 15%, the target margin is the median
rather than the mean, and with no positive ROIC history the seed is the discount
rate. Fair value is the probability-weighted value of bear, base and bull cases
(25/50/25 by default), each floored at zero since shareholders can't lose more
than they invest. Enterprise value less net debt and minority interest gives
equity value, which is divided by diluted shares (current shares outstanding
scaled by the latest year's diluted/basic ratio).

Quality metrics include ROIC, gross/operating/net margins, margin volatility and
FCF conversion (FCF / net income).

Accounting adjustments:

- **Stock-based pay** is already an expense in operating income, so the DCF counts
  it. Free cash flow elsewhere (capital allocation, FCF conversion) deducts it
  too, since operating cash flow adds it back as "non-cash"; buybacks that only
  offset stock pay aren't counted as returns to shareholders.
- **Leases** are debt for IFRS reporters (IFRS 16 puts lease cost below EBIT) but
  not for US GAAP companies, whose operating-lease rent is already inside EBIT;
  counting the liability as well would charge for the leases twice.

Comparables are deliberately kept out of the fair value: a peer median is only as
good as the peer set, and industry labels mix business models (Yahoo puts
Mastercard alongside card lenders trading at a sixth of its revenue multiple).
Candidates come from the same industry; those with a similar operating margin
(within 1.5x, or 3 percentage points) are suggested, and the rest are shown with
the reason they were left out. Medians exclude the target itself and any negative
multiples (e.g. P/E for a loss-making peer). Companies whose
share price and financial statements are in different currencies (typically a
foreign company's US listing) are left out rather than compared on meaningless
ratios; valuing them properly needs exchange-rate and ADR-ratio adjustments.

## Data

- **Financial statements for US companies** come from SEC EDGAR (XBRL data from
  10-K filings), typically 15-19 years, with any gaps filled from Yahoo. The
  parser merges the tags a company has used over time (e.g. Apple's switch from
  `SalesRevenueNet` to `RevenueFromContractWithCustomer...` in 2017), keeps only
  full fiscal years, and takes restated figures over originals.
- **Everything else** (prices, market data, analyst estimates and targets, and
  statements for non-US companies) comes from Yahoo Finance via `yfinance`.
- **Offline**, the app falls back to bundled sample data for AAPL, MSFT, PEP, T
  and TSCO.L and shows a banner saying so.

Starting assumptions use the last 10 fiscal years, roughly one business cycle.
Data access sits behind a `DataProvider` interface so other sources can be added
without changing the engine.

The SEC requires every request to carry a contact email. Set it in
`.streamlit/secrets.toml` (git-ignored) or as an environment variable:

```toml
SEC_CONTACT_EMAIL = "you@example.com"
```

Without it the app uses Yahoo's statements only.

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
