"""Bear / base / bull scenarios and their probability-weighted value."""

from __future__ import annotations

from dataclasses import dataclass, replace

from .valuation import Assumptions, value_per_share


@dataclass
class Scenario:
    name: str
    probability: float
    assumptions: Assumptions
    value_per_share: float  # floored at zero: shareholders can't lose more than they put in


@dataclass
class ScenarioRun:
    scenarios: list[Scenario]
    weighted_value: float


def run_scenarios(base_revenue: float, a: Assumptions, net_debt: float = 0.0,
                  minority_interest: float = 0.0, shares_diluted: float = 1.0) -> ScenarioRun:
    """Bear and bull move revenue growth and the target margin by the swings in
    `a`; each gets `a.tail_probability`, the base case the rest."""
    target = a.ebit_margin if a.target_ebit_margin is None else a.target_ebit_margin
    cases = [
        ("Bear", a.tail_probability, -1),
        ("Base", 1.0 - 2 * a.tail_probability, 0),
        ("Bull", a.tail_probability, 1),
    ]
    scenarios = []
    for name, prob, sign in cases:
        s = replace(a, revenue_growth=a.revenue_growth + sign * a.growth_swing,
                    target_ebit_margin=target + sign * a.margin_swing)
        v = value_per_share(base_revenue, s, net_debt, minority_interest, shares_diluted)
        scenarios.append(Scenario(name, prob, s, max(v, 0.0)))
    return ScenarioRun(scenarios, sum(s.probability * s.value_per_share for s in scenarios))
