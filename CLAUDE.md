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

_Last updated: 2026-09-30_

- Latest work: data-consistency fixes found while valuing NVDA. SEC share
  counts and EPS are now split-adjusted (`data/edgar.py`), panels D and E and
  the seeds use the latest unbroken run of cash-flow years when the SEC data
  has holes, and trailing multiples (Panel F and comps) use the last twelve
  months instead of the last fiscal year. Forward EPS for London listings that
  report in dollars or euros is no longer converted twice.
- Journal calls can now be edited (decision and thesis only) from section 6;
  price, fair value and assumptions stay as saved.
- Known limits: capex for years a company filed under its own XBRL label
  (NVDA FY2013-21) isn't in the SEC feed, so free cash flow is blank there.
  EPS history isn't split-adjusted when the filings carry no share count to
  confirm the split (GOOGL before 2020); nothing reads that history yet.
- Open question: the bear/bull growth swing is a flat +/-3 points, which is
  barely a bear case for a company growing 90% a year. Not changed yet.
- Untracked `portfolio-sizing.bundle` (a git bundle from the sizing merge) is
  still in the working tree, not reviewed for removal.
