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
