# CLAUDE.md

## Project overview

A Streamlit app that values listed companies with a three-stage DCF built on
returns on capital. It pulls up to 19 years of financials (SEC EDGAR for US
companies, Yahoo Finance otherwise), shows the historical evidence, and seeds
every assumption from that evidence or analyst consensus before the user
changes anything. It also runs a relative valuation panel, a buy decision
against margin of safety and required return, a personal valuation journal,
and a stock pie sizing tool for a concentrated portfolio.

Repo layout:

```
app.py        Streamlit entry point
engine/       Valuation maths, no I/O: projection, DCF, scenarios, reverse DCF,
              sensitivity, segments, comps, WACC, quality, track record
data/         Yahoo and SEC EDGAR providers, caching, journal storage
brief/        Research brief panels, starting assumptions, peer screening
ui/           Streamlit widgets, Plotly charts, tables, Excel export
tests/        pytest suite
journal/      Local valuation journal data (git-ignored)
```

Public repo: https://github.com/Hsobalda/valuation-dashboard. It's an
internship application portfolio piece reviewed by finance professionals, and
the user (Oliver Baldaro) designs the valuation methodology and reviews every
change to learn and be able to defend it in interviews.

## Running locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

SEC EDGAR requests need a contact email, set in `.streamlit/secrets.toml`
(git-ignored) or as an env var:

```toml
SEC_CONTACT_EMAIL = "you@example.com"
```

Without it the app falls back to Yahoo's statements only.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

Tests run offline: a DCF checked against a hand-built spreadsheet, a
fade-period worked example, a zero-growth perpetuity check, the Excel export
recalculated and compared against the engine, the SEC filing parser on tag
changes and restatements, and edge cases for sparse data and misaligned
fiscal years.

## Rules

- This repo is public and read by finance professionals as part of an
  internship application. Nothing should read as AI-generated: no bold
  lead-in bullets, no slogan-style phrasing, no template tells, no
  references to files or code that don't exist in the repo.
- Do not add `Co-Authored-By: Claude` (or similar AI attribution) to commits
  in this repo. Commits are authored as Oliver Baldaro
  (258120641+Hsobalda@users.noreply.github.com).
- Commit messages are short and human: a concise subject line, at most a
  sentence or two of body. Not long structured multi-paragraph explanations.
- When changing valuation logic, briefly explain the finance reasoning behind
  the change, not just the code, since the user needs to be able to defend
  modelling choices in interviews.
- Pace new sophistication against the user's ability to explain it — don't
  add features or complexity beyond what they can currently walk through.
- After any set of changes the user approves: commit with a descriptive
  message, then offer to push to `main`. Never push without asking first,
  even if a previous push was approved.
- At the end of each session: commit and push (after asking), then update
  the Status section below to reflect the repo's current state.

## Status

_Last updated: 2026-10-03_

- Latest work (PR #3): share count covers every share class (Alphabet had been
  valued ~2x too high; Novo, Meta and Visa less); order backlog panel H from SEC
  remaining performance obligations, also in the growth cross-check; commodity
  warning extended to independent power producers; warning when seeds rest on
  fewer than five years of statements or a loss-making median margin; seeded tax
  rate floored at the 15% global minimum. Earlier: split-adjusted SEC share
  counts and EPS, gap-aware cash-flow panels, trailing-twelve-month multiples,
  editable journal calls. 139 tests.
- Known limit: Visa's diluted/basic ratio (1.13) likely double counts its other
  share classes.
- Journal (local, git-ignored) holds calls on JD.L, IMB.L, NVDA, CTSH, ACN and
  2330.TW. Theses are short and in the user's voice. Open points the user
  still has to fix in their own notes: IMB.L is marked Buy but fails the
  margin of safety test; JD.L's quoted model range and 9.6% discount rate
  don't match or explain the saved numbers.
- Next ideas, in order:
  1. Real bear-case scenarios written per stock (a growth path and margin,
     not the flat +/-3 points of growth swing, which is barely a bear case for
     a company growing 90% a year).
  2. Then set the margin of safety from how far the bear case sits below fair
     value, rounded to the 20/30/40/50 ladder. The current uncertainty score
     is the dashboard's own four-factor rule, not Morningstar's method, and it
     counts beta twice (discount rate and uncertainty score).
  3. A "sell above" price on each journal call: the price where the expected
     return falls to the user's 10% required return (trim there, exit at 8%).
- Known limits: capex for years a company filed under its own XBRL label
  (NVDA FY2013-21) isn't in the SEC feed. EPS history isn't split-adjusted
  when no share count confirms the split (GOOGL before 2020); nothing reads it.
  Non-US filers that report under IFRS (e.g. TSMC) get only Yahoo's ~4 years.
- Untracked `portfolio-sizing.bundle` (a git bundle from the sizing merge) is
  still in the working tree, not reviewed for removal.
