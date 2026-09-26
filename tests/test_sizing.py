import numpy as np
import pandas as pd
import pytest

from engine.sizing import Candidate, conviction, portfolio_risk, size_positions


def test_conviction_zero_below_hurdle_and_scaled_by_uncertainty():
    assert conviction(Candidate("X", "S", 0.08, "Low", 0.2), 0.10) == 0.0
    assert conviction(Candidate("X", "S", 0.15, "Low", 0.2), 0.10) == pytest.approx(1.0)   # full edge
    assert conviction(Candidate("X", "S", 0.10, "Low", 0.2), 0.10) == pytest.approx(0.5)   # just clears
    assert conviction(Candidate("X", "S", 0.15, "High", 0.2), 0.10) == pytest.approx(0.5)


def test_weight_is_risk_budget_over_volatility_then_capped():
    calm = Candidate("CALM", "A", 0.15, "Low", 0.25)      # 1% / 25% = 4%, under the 5% cap
    wild = Candidate("WILD", "B", 0.15, "Low", 0.10)      # 1% / 10% = 10% -> capped at 5%
    df = size_positions([calm, wild], hurdle=0.10).set_index("ticker")
    assert df.loc["CALM", "weight"] == pytest.approx(0.04)
    assert df.loc["WILD", "weight"] == pytest.approx(0.05) and df.loc["WILD", "limit"] == "stock cap"


def test_sector_and_satellite_caps():
    tech = [Candidate(f"T{i}", "Tech", 0.20, "Low", 0.20) for i in range(4)]   # 4 x 5% = 20% tech
    df = size_positions(tech, hurdle=0.10, sector_cap=0.10)
    assert df["weight"].sum() == pytest.approx(0.10)
    many = [Candidate(f"S{i}", f"Sector{i}", 0.20, "Low", 0.20) for i in range(8)]  # 8 x 5% = 40%
    assert size_positions(many, hurdle=0.10, satellite_cap=0.25)["weight"].sum() == pytest.approx(0.25)


def test_negatively_correlated_holding_contributes_less_risk_than_its_weight():
    rng = np.random.default_rng(0)
    core = rng.normal(0, 0.02, 500)
    returns = pd.DataFrame({"CORE": core, "HEDGE": -0.5 * core + rng.normal(0, 0.02, 500)})
    vol, contrib = portfolio_risk(pd.Series({"CORE": 0.9, "HEDGE": 0.1}), returns)
    assert contrib.sum() == pytest.approx(1.0)
    assert contrib["HEDGE"] < 0.1   # diversifies: under its 10% money weight
    assert vol > 0
