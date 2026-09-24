import pandas as pd
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
    peers_pe = result.peer_table.loc[["AAPL", "MSFT", "T"], "P/E"]
    assert result.medians["P/E"] == pytest.approx(float(peers_pe.median()))


def test_comps_implied_value_uses_target_metric(provider):
    result = comps_analysis(
        target_ticker="PEP",
        peers=["AAPL", "MSFT", "T"],
        metrics=["ev_ebitda", "pe"],
        provider=provider,
    )
    m = provider.fundamental_metrics("PEP")
    ev = m["market_cap"] + m["net_debt"] + m["minority_interest"]
    # EV/EBITDA -> enterprise value -> bridge to per-share
    ev_implied = result.medians["EV/EBITDA"] * m["ebitda"]
    equity = ev_implied - m["net_debt"] - m["minority_interest"]
    expected_ev_ps = equity / m["shares_diluted"]
    assert result.implied_values["EV/EBITDA"] == pytest.approx(expected_ev_ps)
    # P/E -> price per share directly
    assert result.implied_values["P/E"] == pytest.approx(result.medians["P/E"] * m["eps"])


def test_ev_counts_cash_once(provider):
    """EV built from raw balance-sheet lines must match the EV used in comps."""
    m = provider.fundamental_metrics("PEP")
    bal = provider.balance_sheet("PEP").iloc[-1]
    st_inv = bal.get("short_term_investments", 0.0)
    expected_ev = (m["market_cap"] + bal["total_debt"] - bal["cash_and_equiv"]
                   - st_inv + m["minority_interest"])
    result = comps_analysis("PEP", ["AAPL"], ["ev_revenue"], provider)
    assert result.peer_table.loc["PEP", "EV/Revenue"] == pytest.approx(expected_ev / m["revenue"])


class _StubProvider:
    def __init__(self, metrics):
        self._metrics = metrics

    def fundamental_metrics(self, ticker):
        return self._metrics[ticker]


def _metrics(eps, price=100.0):
    return dict(market_cap=1000.0, net_debt=0.0, minority_interest=0.0, ebitda=100.0,
                revenue=500.0, price=price, eps=eps, bvps=10.0, shares_diluted=10.0)


def test_target_excluded_from_peer_median():
    stub = _StubProvider({"TGT": _metrics(eps=1.0), "P1": _metrics(eps=10.0),
                          "P2": _metrics(eps=5.0)})
    result = comps_analysis("TGT", ["P1", "P2"], ["pe"], stub)
    # peers trade on 10x and 20x; the target's 100x must not move the median
    assert result.medians["P/E"] == pytest.approx(15.0)


def test_negative_multiples_excluded():
    stub = _StubProvider({"TGT": _metrics(eps=5.0), "P1": _metrics(eps=10.0),
                          "P2": _metrics(eps=5.0), "LOSS": _metrics(eps=-2.0)})
    result = comps_analysis("TGT", ["P1", "P2", "LOSS"], ["pe"], stub)
    assert pd.isna(result.peer_table.loc["LOSS", "P/E"])
    assert result.medians["P/E"] == pytest.approx(15.0)
