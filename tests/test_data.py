import pytest

from data.provider import SampleProvider, derive_metrics


@pytest.fixture(scope="module")
def provider():
    return SampleProvider()


def test_sample_tickers_available(provider):
    assert "AAPL" in provider._tickers()
    assert "TSCO.L" in provider._tickers()


def test_statements_have_expected_columns(provider):
    inc = provider.income_statement("AAPL")
    bal = provider.balance_sheet("AAPL")
    cf = provider.cash_flow("AAPL")
    assert "revenue" in inc.columns
    assert "net_income" in inc.columns
    assert "total_debt" in bal.columns
    assert "operating_cash_flow" in cf.columns
    # 6 years of sample history
    assert len(inc) == 6


def test_cash_flow_sign_convention(provider):
    cf = provider.cash_flow("AAPL")
    assert (cf["capital_expenditure"] >= 0).all()
    assert (cf["dividends_paid"] >= 0).all()


def test_derive_metrics(provider):
    m = provider.fundamental_metrics("PEP")
    # raw units: ebitda = operating_income + d&a (latest: 11365 + 2900, in millions -> raw)
    assert m["ebitda"] == pytest.approx((11365 + 2900) * 1_000_000)
    assert m["revenue"] == pytest.approx(93925 * 1_000_000)
    # net debt = total debt - cash - st investments (latest: 49000 - 8000 - 2000)
    assert m["net_debt"] == pytest.approx((49000 - 8000 - 2000) * 1_000_000)
    assert m["eps"] == pytest.approx(6.05)


def test_unknown_ticker_raises(provider):
    with pytest.raises(KeyError):
        provider.income_statement("NOPE")


def test_derive_metrics_handles_missing_columns():
    import pandas as pd

    info = {"beta": 1.0}
    market = {"price": 10.0, "market_cap": 1000.0, "shares_outstanding": 100.0}
    inc = pd.DataFrame({"revenue": [100.0], "operating_income": [20.0],
                        "depreciation_amortization": [5.0], "eps_diluted": [1.0],
                        "net_income": [15.0]}, index=[2020])
    bal = pd.DataFrame({"cash_and_equiv": [10.0], "short_term_investments": [0.0],
                        "total_debt": [50.0], "stockholder_equity": [80.0],
                        "minority_interest": [0.0]}, index=[2020])
    cf = pd.DataFrame({"operating_cash_flow": [25.0],
                       "capital_expenditure": [5.0]}, index=[2020])
    m = derive_metrics(info, market, inc, bal, cf)
    assert m["ebitda"] == pytest.approx(25.0)
    assert m["net_debt"] == pytest.approx(40.0)
    assert m["fcf"] == pytest.approx(20.0)
    assert m["bvps"] == pytest.approx(0.8)
    assert m["shares_diluted"] == pytest.approx(100.0)  # no share data -> no dilution
    assert m["eps_ttm"] == 1.0 and m["revenue_ttm"] == 100.0  # no trailing figures: last fiscal year


def test_multiples_use_the_last_twelve_months_when_reported():
    import pandas as pd

    from brief.panels import panel_priced_in

    inc = pd.DataFrame({"revenue": [100.0], "operating_income": [20.0], "eps_diluted": [1.0]}, index=[2025])
    market = {"price": 30.0, "market_cap": 3000.0, "shares_outstanding": 100.0,
              "eps_ttm": 1.5, "ebitda_ttm": 40.0, "revenue_ttm": 150.0}
    m = derive_metrics({}, market, inc, pd.DataFrame(index=[2025]), pd.DataFrame(index=[2025]))
    assert m["eps"] == 1.0 and m["revenue"] == 100.0  # the DCF still starts from the fiscal year

    class _Stub:
        fundamental_metrics = staticmethod(lambda t: m)
        company_info = staticmethod(lambda t: {})

    f = panel_priced_in(_Stub(), "X")
    assert f["pe"] == pytest.approx(20.0)          # 30 / 1.5, not 30 / 1.0
    assert f["ev_revenue"] == pytest.approx(20.0)  # 3000 / 150


def test_stale_optional_balance_sheet_field_treated_as_zero_not_carried_forward():
    """A company (like PayPal after 2021) that stops reporting an optional field
    once it holds none files no XBRL fact for it in later years: that must read
    as zero for the current year, not fall back to an old year's non-zero value."""
    import pandas as pd

    info = {"beta": 1.0}
    market = {"price": 10.0, "market_cap": 1000.0, "shares_outstanding": 100.0}
    inc = pd.DataFrame({"revenue": [100.0, 105.0], "operating_income": [20.0, 21.0],
                        "eps_diluted": [1.0, 1.05], "net_income": [15.0, 16.0]}, index=[2021, 2022])
    bal = pd.DataFrame({
        "cash_and_equiv": [10.0, 12.0], "total_debt": [50.0, 50.0], "stockholder_equity": [80.0, 90.0],
        "long_term_investments": [35.0, float("nan")],  # reported in 2021, gone by 2022
        "minority_interest": [0.0, float("nan")],
    }, index=[2021, 2022])
    cf = pd.DataFrame({"operating_cash_flow": [25.0, 26.0], "capital_expenditure": [5.0, 5.0]},
                      index=[2021, 2022])
    m = derive_metrics(info, market, inc, bal, cf)
    assert m["net_debt"] == pytest.approx(50.0 - 12.0)  # not 50 - 12 - 35
    assert m["minority_interest"] == pytest.approx(0.0)


def test_diluted_shares_use_current_count_times_dilution_ratio():
    import pandas as pd

    market = {"price": 10.0, "market_cap": 1000.0, "shares_outstanding": 95.0}
    # last year: 100 basic, 102 diluted on average; since then buybacks cut
    # the count to 95, so diluted today is 95 * 1.02, not the stale 102
    inc = pd.DataFrame({"shares_basic_avg": [100.0], "shares_diluted_avg": [102.0]}, index=[2024])
    empty = pd.DataFrame(index=[2024])
    m = derive_metrics({}, market, inc, empty, empty)
    assert m["shares_diluted"] == pytest.approx(96.9)


def _fake_yf(industry_weights, sector_tickers):
    import pandas as pd

    class Industry:
        def __init__(self, key):
            self.top_companies = pd.DataFrame({"market weight": industry_weights})

    class Sector:
        def __init__(self, key):
            self.top_companies = pd.DataFrame(index=sector_tickers)

    return type("yf", (), {"Industry": Industry, "Sector": Sector})


def test_peer_suggestions_drop_tiny_industry_peers_and_top_up_from_sector():
    from data.provider import YFinanceProvider

    p = YFinanceProvider()
    # target is ~99% of its industry, so no industry peer clears 1/20th of its size
    p._yf = _fake_yf({"BIG": 0.99, "TINY1": 0.006, "TINY2": 0.004}, ["S1", "BIG", "S2", "S3"])
    assert p.peer_suggestions("BIG", "ind", "sec") == ["S1", "S2", "S3"]


def test_peer_suggestions_keep_comparable_industry_peers():
    from data.provider import YFinanceProvider

    p = YFinanceProvider()
    p._yf = _fake_yf({"KO": 0.5, "PEP": 0.25, "MNST": 0.12, "KDP": 0.06, "SMALL": 0.01}, ["X"])
    assert p.peer_suggestions("KO", "ind", "sec") == ["PEP", "MNST", "KDP"]


def test_us_operating_leases_taken_out_of_debt():
    import pandas as pd

    from data.provider import exclude_operating_leases

    bal = pd.DataFrame({"total_debt": [26.6], "lease_liabilities": [10.5]}, index=[2025])
    assert exclude_operating_leases(bal)["total_debt"].iloc[0] == pytest.approx(16.1)
    no_leases = pd.DataFrame({"total_debt": [5.0]}, index=[2025])
    assert exclude_operating_leases(no_leases)["total_debt"].iloc[0] == 5.0


def test_years_since_fiscal_year_end():
    import datetime as dt

    from data.provider import _years_since

    half_year_ago = (dt.date.today() - dt.timedelta(days=183)).isoformat()
    assert _years_since(half_year_ago) == pytest.approx(0.5, abs=0.01)
    assert _years_since(None) == 0.0
    assert _years_since("2000-01-01") == 1.5  # stale data capped


def test_currency_conversion_scales_money_not_share_counts():
    import pandas as pd

    from data.provider import convert_currency

    df = pd.DataFrame({"revenue": [100.0], "eps_diluted": [2.0], "shares_diluted_avg": [50.0]}, index=[2025])
    out = convert_currency(df, 0.75)
    assert out.loc[2025].to_dict() == {"revenue": 75.0, "eps_diluted": 1.5, "shares_diluted_avg": 50.0}


def test_foreign_us_listings_are_not_converted():
    from data.provider import is_foreign_us_listing

    assert is_foreign_us_listing("Taiwan", "USD")          # TSMC's ADR
    assert not is_foreign_us_listing("United Kingdom", "GBP")  # Shell in London
    assert not is_foreign_us_listing("United States", "USD")


def test_share_count_covers_every_share_class():
    from data.provider import YFinanceProvider

    info = {"currency": "USD", "financialCurrency": "USD", "currentPrice": 338.0,
            "marketCap": 4.13e12, "sharesOutstanding": 5.87e9, "impliedSharesOutstanding": 12.23e9}
    p = YFinanceProvider()
    p._yf = type("yf", (), {"Ticker": staticmethod(lambda t: type("T", (), {"info": info})())})
    p._fx_cache["GOOGL"] = 1.0
    assert p.market_data("GOOGL")["shares_outstanding"] == 12.23e9  # Class A alone halves it
