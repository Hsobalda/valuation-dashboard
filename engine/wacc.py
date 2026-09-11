"""WACC and cost of capital. Pure functions, no I/O."""


def cost_of_equity(risk_free: float, beta: float, erp: float) -> float:
    """Cost of equity via CAPM: risk-free + beta * equity risk premium.

    All inputs are decimals (e.g. 0.04, 1.1, 0.05).
    """
    return risk_free + beta * erp


def wacc(
    equity_value: float,
    debt_value: float,
    cost_equity: float,
    cost_debt: float,
    tax_rate: float,
) -> float:
    """Weighted average cost of capital, weights on market values.

    Returns a decimal discount rate. If the firm has no debt, falls back to
    cost of equity.
    """
    total = equity_value + debt_value
    if total <= 0:
        return cost_equity
    weight_equity = equity_value / total
    weight_debt = debt_value / total
    return weight_equity * cost_equity + weight_debt * cost_debt * (1.0 - tax_rate)
