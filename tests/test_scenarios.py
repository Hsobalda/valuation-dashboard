import pytest

from engine.scenarios import run_scenarios
from engine.valuation import Assumptions, value_per_share

A = Assumptions(revenue_growth=0.06, ebit_margin=0.20, target_ebit_margin=0.22, roic=0.25,
                growth_swing=0.03, margin_swing=0.02, tail_probability=0.25)


def test_base_case_matches_headline_value():
    run = run_scenarios(1000.0, A, shares_diluted=10.0)
    base = next(s for s in run.scenarios if s.name == "Base")
    assert base.value_per_share == pytest.approx(value_per_share(1000.0, A, shares_diluted=10.0))


def test_bear_and_bull_move_growth_and_target_margin():
    bear, _, bull = run_scenarios(1000.0, A).scenarios
    assert (bear.assumptions.revenue_growth, bear.assumptions.target_ebit_margin) == pytest.approx((0.03, 0.20))
    assert (bull.assumptions.revenue_growth, bull.assumptions.target_ebit_margin) == pytest.approx((0.09, 0.24))
    assert bear.value_per_share < bull.value_per_share


def test_weighted_value_is_probability_weighted():
    run = run_scenarios(1000.0, A)
    assert sum(s.probability for s in run.scenarios) == pytest.approx(1.0)
    assert run.weighted_value == pytest.approx(sum(s.probability * s.value_per_share for s in run.scenarios))


def test_scenario_values_floored_at_zero():
    run = run_scenarios(1000.0, A, net_debt=1e9)
    assert all(s.value_per_share == 0.0 for s in run.scenarios)
