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
