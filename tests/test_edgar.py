import pytest

from data.edgar import statements_from_facts


def _fact(val, end, start=None, form="10-K", filed="2025-11-01"):
    f = {"val": val, "end": end, "form": form, "filed": filed}
    if start:
        f["start"] = start
    return f


def _tag(*facts, unit="USD"):
    return {"units": {unit: list(facts)}}


FACTS = {"facts": {"us-gaap": {
    # tag switch: old revenue tag for 2016, new one from 2017
    "SalesRevenueNet": _tag(_fact(100.0, "2016-09-30", "2015-10-01")),
    "RevenueFromContractWithCustomerExcludingAssessedTax": _tag(
        _fact(110.0, "2017-09-30", "2016-10-01"),
        _fact(30.0, "2017-06-30", "2017-04-01", form="10-Q"),       # quarterly: ignored
        _fact(28.0, "2017-06-30", "2016-10-01"),                     # 9 months in a 10-K: ignored
    ),
    "OperatingIncomeLoss": _tag(
        _fact(20.0, "2016-09-30", "2015-10-01", filed="2016-11-01"),
        _fact(21.0, "2016-09-30", "2015-10-01", filed="2017-11-01"),  # restated later: wins
        _fact(25.0, "2017-09-30", "2016-10-01"),
    ),
    "LongTermDebtNoncurrent": _tag(_fact(50.0, "2017-09-30"), _fact(45.0, "2017-06-30")),
    "LongTermDebtCurrent": _tag(_fact(5.0, "2017-09-30")),
    "CommercialPaper": _tag(_fact(3.0, "2017-09-30")),
    "EarningsPerShareDiluted": _tag(_fact(2.5, "2017-09-30", "2016-10-01"), unit="USD/shares"),
}}}


def test_revenue_merges_tags_across_years_and_ignores_partial_periods():
    inc = statements_from_facts(FACTS)["income"]
    assert inc["revenue"].to_dict() == {2016: 100.0, 2017: 110.0}


def test_restated_value_wins():
    inc = statements_from_facts(FACTS)["income"]
    assert inc.loc[2016, "operating_income"] == 21.0


def test_debt_adds_long_term_parts_and_commercial_paper_at_year_end_only():
    bal = statements_from_facts(FACTS)["balance"]
    assert bal.loc[2017, "total_debt"] == pytest.approx(58.0)  # 50 + 5 + 3, not the June 45


def test_per_share_units_are_read():
    assert statements_from_facts(FACTS)["income"].loc[2017, "eps_diluted"] == 2.5


def test_no_us_gaap_facts_returns_none():
    assert statements_from_facts({"facts": {"ifrs-full": {}}}) is None


def test_cross_check_drops_sec_lines_that_disagree_with_yahoo():
    import pandas as pd

    from data.loader import cross_check

    years = [2023, 2024, 2025]
    sec = pd.DataFrame({"total_debt": [1.5, 1.6, 1.5], "cash_and_equiv": [10.0, 11.0, 12.0],
                        "goodwill": [5.0, 5.0, 5.0]}, index=years)
    yahoo = pd.DataFrame({"total_debt": [44.0, 45.0, 45.5], "cash_and_equiv": [10.2, 10.9, 12.1]},
                         index=years)
    kept, rejected = cross_check(sec, yahoo)
    assert rejected == ["total_debt"]            # Coca-Cola-style miss: $1.5bn vs $45bn
    assert list(kept.columns) == ["cash_and_equiv", "goodwill"]  # close match kept; unchecked kept


def test_grand_total_debt_tag_preferred():
    facts = {"facts": {"us-gaap": {
        "Revenues": _tag(_fact(100.0, "2025-12-31", "2025-01-01")),
        "DebtLongtermAndShorttermCombinedAmount": _tag(_fact(158.0, "2025-12-31")),
        "LongTermDebtCurrent": _tag(_fact(19.0, "2025-12-31")),
    }}}
    assert statements_from_facts(facts)["balance"].loc[2025, "total_debt"] == 158.0


def _year(val, year, filed):
    return _fact(val, f"{year}-12-31", f"{year}-01-01", filed=filed)


def test_share_counts_and_eps_are_put_on_todays_share_basis_after_a_split():
    # 4-for-1 split in 2023: the 2023 10-K restates 2022 but not 2021
    facts = {"facts": {"us-gaap": {
        "Revenues": _tag(_year(10.0, 2021, "2022-02-01"), _year(11.0, 2022, "2023-02-01"),
                         _year(12.0, 2023, "2024-02-01")),
        "WeightedAverageNumberOfDilutedSharesOutstanding": _tag(
            _year(100.0, 2021, "2022-02-01"),
            _year(98.0, 2022, "2023-02-01"), _year(392.0, 2022, "2024-02-01"),
            _year(388.0, 2023, "2024-02-01"), unit="shares"),
        "EarningsPerShareDiluted": _tag(
            _year(4.0, 2021, "2022-02-01"),
            _year(4.4, 2022, "2023-02-01"), _year(1.1, 2022, "2024-02-01"),
            _year(1.2, 2023, "2024-02-01"), unit="USD/shares"),
    }}}
    inc = statements_from_facts(facts)["income"]
    assert inc["shares_diluted_avg"].to_dict() == {2021: 400.0, 2022: 392.0, 2023: 388.0}
    assert inc["eps_diluted"].to_dict() == {2021: 1.0, 2022: 1.1, 2023: 1.2}


def test_share_count_refiled_in_different_units_leaves_eps_alone():
    # 2021 first filed in thousands, 2022 corrected in the next 10-K: not a split
    facts = {"facts": {"us-gaap": {
        "Revenues": _tag(_year(10.0, 2021, "2022-02-01"), _year(11.0, 2022, "2023-02-01"),
                         _year(12.0, 2023, "2024-02-01")),
        "WeightedAverageNumberOfDilutedSharesOutstanding": _tag(
            _year(0.1, 2021, "2022-02-01"),
            _year(0.098, 2022, "2023-02-01"), _year(98.0, 2022, "2024-02-01"),
            _year(97.0, 2023, "2024-02-01"), unit="shares"),
        "EarningsPerShareDiluted": _tag(
            _year(4.0, 2021, "2022-02-01"), _year(4.4, 2022, "2023-02-01"),
            _year(4.4, 2022, "2024-02-01"), _year(4.8, 2023, "2024-02-01"), unit="USD/shares"),
    }}}
    inc = statements_from_facts(facts)["income"]
    assert inc["shares_diluted_avg"].to_dict() == pytest.approx({2021: 100.0, 2022: 98.0, 2023: 97.0})
    assert inc["eps_diluted"].to_dict() == {2021: 4.0, 2022: 4.4, 2023: 4.8}
