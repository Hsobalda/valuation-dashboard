import pytest

from engine.reverse import implied_revenue_growth
from engine.valuation import Assumptions, value_per_share

A = Assumptions(growth_y1=0.05, growth_y2=0.05, growth_y5=0.05, ebit_margin=0.20, tax_rate=0.21,
                roic=0.25, fade_years=10, terminal_growth=0.025, discount_rate=0.10)
BRIDGE = dict(net_debt=100.0, minority_interest=0.0, shares_diluted=10.0)


def test_round_trip_recovers_growth():
    price = value_per_share(1000.0, A.with_flat_growth(0.12), **BRIDGE)
    assert implied_revenue_growth(price, 1000.0, A, **BRIDGE) == pytest.approx(0.12, abs=1e-6)


def test_other_assumptions_held_fixed():
    price = value_per_share(1000.0, A.with_flat_growth(0.03), **BRIDGE)
    assert implied_revenue_growth(price, 1000.0, A, **BRIDGE) == pytest.approx(0.03, abs=1e-6)


def test_unreachable_price_returns_none():
    assert implied_revenue_growth(1e9, 1000.0, A, **BRIDGE) is None
