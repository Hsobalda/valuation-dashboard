import pytest

from engine.wacc import cost_of_equity, wacc


def test_cost_of_equity_capm():
    assert cost_of_equity(0.04, 1.2, 0.05) == pytest.approx(0.10)


def test_cost_of_equity_zero_beta_is_risk_free():
    assert cost_of_equity(0.03, 0.0, 0.05) == pytest.approx(0.03)


def test_wacc_market_value_weights():
    # 70% equity at 10%, 30% debt at 5%, 21% tax
    result = wacc(70.0, 30.0, 0.10, 0.05, 0.21)
    expected = 0.7 * 0.10 + 0.3 * 0.05 * (1 - 0.21)
    assert result == pytest.approx(expected)


def test_wacc_no_debt_is_cost_of_equity():
    assert wacc(100.0, 0.0, 0.10, 0.05, 0.21) == pytest.approx(0.10)


def test_wacc_no_capital_falls_back_to_equity():
    assert wacc(0.0, 0.0, 0.10, 0.05, 0.21) == pytest.approx(0.10)
