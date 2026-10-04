# Audit log

Errors found while auditing the code and its outputs, with the commit that fixed
each one and the test that now covers it. Commit hashes refer to this
repository's history.

## 1. Cash counted twice

Problem: net debt is already debt less cash, but cash was taken off again. The
comps table built enterprise value as market cap plus net debt plus minority
interest minus cash, and the DCF's bridge from enterprise value to equity added
cash back after subtracting net debt.

Effect: comps enterprise values were understated by the company's cash, and DCF
equity values were overstated by it.

Fix: `9fea168` (2026-09-25), "v2: sparse data handling, cash fix, CI and
README". Cash is now counted once, through net debt.

Tests: `tests/test_comps.py::test_ev_counts_cash_once`, added in that commit,
rebuilds enterprise value from raw balance-sheet lines and checks the comps
figure against it. `tests/test_dcf.py::test_equity_bridge` was corrected in the
same commit to expect equity = enterprise value minus net debt minus minority interest.

## 2. The company being valued included in its own peer median

Problem: the comps medians were taken over the whole table, target included.
Negative multiples, such as a loss-maker's P/E, were also counted.

Effect: the target's own multiple pulled the benchmark towards its current
price, shrinking any premium or discount shown against peers.

Fix: `999cba6` (2026-09-25), "Discount at 10% required return, show WACC for
reference", whose message notes "Also exclude the target and negative multiples
from the comps median".

Tests: `tests/test_comps.py::test_target_excluded_from_peer_median` and
`tests/test_comps.py::test_negative_multiples_excluded`, both added in that
commit.

## 3. Share counts and EPS not adjusted for stock splits

Problem: a 10-K restates share counts and EPS for a stock split only for the
three years it presents. The SEC parser took the latest filed value for each
year, so older years stayed on their pre-split basis.

Effect: share-count history mixed bases. Nvidia's diluted share count appeared
to grow 80% a year when it had fallen about 0.8% a year, and the capital
allocation panel flagged dilution that hadn't happened.

Fix: `41154d9` (2026-10-01), "Split-adjust SEC share counts, skip cash flow
gaps, use trailing twelve months for multiples". Where a later filing reports a
different count for the same year, the ratio is taken as the split and applied
to every year last reported before that filing. A change in the share count
that EPS doesn't mirror is treated as a correction of units, not a split.

Tests: `tests/test_edgar.py::test_share_counts_and_eps_are_put_on_todays_share_basis_after_a_split`
and `tests/test_edgar.py::test_share_count_refiled_in_different_units_leaves_eps_alone`,
both added in that commit.

## 4. Multiples using the last fiscal year instead of the trailing twelve months

Problem: P/E, EV/EBITDA and EV/Revenue, in the research brief and the comps
table, divided today's price by the last fiscal year's figures.

Effect: a multiple could rest on a year that ended a year or more earlier, and
peers with different fiscal year ends weren't compared over the same period.
Nvidia's P/E read 46x on its January year-end earnings against 29x on the last
four quarters.

Fix: `41154d9` (2026-10-01), the same commit as entry 3. Trailing multiples now
use Yahoo's trailing-twelve-month EPS, EBITDA and revenue, falling back to the
fiscal year where Yahoo reports none. The DCF still starts from the fiscal year.

Test: `tests/test_data.py::test_multiples_use_the_last_twelve_months_when_reported`,
added in that commit.

## 5. A share count covering one of three share classes

Problem: value per share divided the whole company's equity by Yahoo's
`sharesOutstanding`, which for Alphabet counts Class A only (5.9bn of the 12.2bn
shares across its three classes).

Effect: Alphabet's value per share came out roughly double.

Fix: `5a9f306` (2026-10-02), "Count every share class when valuing per share",
merged in PR #3. The app now uses Yahoo's total across classes, which matches
market cap.

Test: `tests/test_data.py::test_share_count_covers_every_share_class`, added in
that commit.
