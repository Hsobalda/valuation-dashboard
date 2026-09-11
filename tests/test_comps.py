import pytest

from data.provider import SampleProvider
from engine.comps import comps_analysis


@pytest.fixture(scope="module")
def provider():
    return SampleProvider()


def test_comps_table_shape(provider):
    result = comps_analysis(
        target_ticker="PEP",
        peers=["AAPL", "MSFT", "T"],
        metrics=["ev_ebitda", "pe", "ev_revenue", "pb"],
        provider=provider,
    )
    # target + 3 peers
    assert set(result.peer_table.index) == {"PEP", "AAPL", "MSFT", "T"}
    assert list(result.peer_table.columns) == ["EV/EBITDA", "P/E", "EV/Revenue", "P/B"]


def test_comps_medians_are_medians(provider):
    result = comps_analysis(
        target_ticker="PEP",
        peers=["AAPL", "MSFT", "T"],
        metrics=["ev_ebitda", "pe"],
        provider=provider,
    )
    pe = result.peer_table["P/E"].dropna()
    assert result.medians["P/E"] == pytest.approx(float(pe.median()))


def test_comps_implied_value_uses_target_metric(provider):
    result = comps_analysis(
        target_ticker="PEP",
        peers=["AAPL", "MSFT", "T"],
        metrics=["ev_ebitda", "pe"],
        provider=provider,
    )
    m = provider.fundamental_metrics("PEP")
    ev = m["market_cap"] + m["net_debt"] + m["minority_interest"] - m["cash"]
    # EV/EBITDA -> enterprise value -> bridge to per-share
    ev_implied = result.medians["EV/EBITDA"] * m["ebitda"]
    equity = ev_implied - m["net_debt"] - m["minority_interest"] + m["cash"]
    expected_ev_ps = equity / m["shares_outstanding"]
    assert result.implied_values["EV/EBITDA"] == pytest.approx(expected_ev_ps)
    # P/E -> price per share directly
    assert result.implied_values["P/E"] == pytest.approx(result.medians["P/E"] * m["eps"])
