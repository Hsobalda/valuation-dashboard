import pytest

from engine.reverse import _value_per_share, implied_revenue_growth
from engine.valuation import Assumptions

A = Assumptions(revenue_growth=0.05, ebit_margin=0.20, tax_rate=0.21, da_pct_revenue=0.05,
                capex_pct_revenue=0.05, fade_years=10, terminal_growth=0.025, discount_rate=0.10)
BRIDGE = dict(net_debt=100.0, minority_interest=0.0, shares_diluted=10.0)


def test_round_trip_recovers_growth():
    price = _value_per_share(0.12, 1000.0, A, **BRIDGE)
    assert implied_revenue_growth(price, 1000.0, A, **BRIDGE) == pytest.approx(0.12, abs=1e-6)


def test_other_assumptions_held_fixed():
    price = _value_per_share(0.03, 1000.0, A, **BRIDGE)
    assert implied_revenue_growth(price, 1000.0, A, **BRIDGE) == pytest.approx(0.03, abs=1e-6)


def test_unreachable_price_returns_none():
    assert implied_revenue_growth(1e9, 1000.0, A, **BRIDGE) is None
