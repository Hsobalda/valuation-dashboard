import numpy as np
import pandas as pd
import pytest

from engine.sizing import Candidate, conviction, portfolio_risk, size_positions


def test_conviction_zero_below_hurdle_and_scaled_by_uncertainty():
    assert conviction(Candidate("X", "S", 0.08, "Low", 0.2), 0.10) == 0.0
    assert conviction(Candidate("X", "S", 0.15, "Low", 0.2), 0.10) == pytest.approx(1.0)   # full edge
    assert conviction(Candidate("X", "S", 0.10, "Low", 0.2), 0.10) == pytest.approx(0.5)   # just clears
    assert conviction(Candidate("X", "S", 0.15, "High", 0.2), 0.10) == pytest.approx(0.5)


def test_standard_stock_gets_one_slot():
    # just clears the hurdle (conviction 0.5 -> 1.0x), typical volatility -> exactly 1/N
    df = size_positions([Candidate("A", "S", 0.10, "Low", 0.25)], hurdle=0.10, holdings=10)
    assert df["weight"].iloc[0] == pytest.approx(0.10)


def test_high_conviction_calm_stock_sized_up_but_capped_by_uncertainty():
    strong = Candidate("STRONG", "A", 0.20, "Low", 0.15)     # 1.5x conviction, 1.5x vol adj = 2.25 slots
    medium = Candidate("MED", "B", 0.20, "Medium", 0.15)
    fails = Candidate("FAIL", "C", 0.05, "Low", 0.15)
    df = size_positions([strong, medium, fails], hurdle=0.10, holdings=10).set_index("ticker")
    assert df.loc["STRONG", "weight"] == pytest.approx(0.20) and df.loc["STRONG", "limit"] == "stock cap"
    assert df.loc["MED", "weight"] == pytest.approx(0.15)
    assert df.loc["FAIL", "weight"] == 0.0


def test_above_buy_zone_gets_half_size_starter():
    full = size_positions([Candidate("A", "S", 0.10, "Low", 0.25)], hurdle=0.10)["weight"].iloc[0]
    df = size_positions([Candidate("A", "S", 0.10, "Low", 0.25, passes_margin_of_safety=False)], hurdle=0.10)
    assert df["weight"].iloc[0] == pytest.approx(full / 2)
    assert df["limit"].iloc[0].startswith("starter")


def test_sector_cap_and_never_over_100pct():
    same = [Candidate(f"T{i}", "Tech", 0.20, "Low", 0.15) for i in range(3)]    # 3 x 20% = 60% tech
    assert size_positions(same, hurdle=0.10, sector_cap=0.30)["weight"].sum() == pytest.approx(0.30)
    many = [Candidate(f"S{i}", f"S{i}", 0.20, "Low", 0.15) for i in range(8)]    # 8 x 20% = 160%
    assert size_positions(many, hurdle=0.10, sector_cap=1.0)["weight"].sum() == pytest.approx(1.0)


def test_negatively_correlated_holding_contributes_less_risk_than_its_weight():
    rng = np.random.default_rng(0)
    core = rng.normal(0, 0.02, 500)
    returns = pd.DataFrame({"CORE": core, "HEDGE": -0.5 * core + rng.normal(0, 0.02, 500)})
    vol, contrib = portfolio_risk(pd.Series({"CORE": 0.9, "HEDGE": 0.1}), returns)
    assert contrib.sum() == pytest.approx(1.0)
    assert contrib["HEDGE"] < 0.1
    assert vol > 0


def test_base_currency_returns_compound_stock_and_fx_moves():
    from engine.sizing import in_base_currency

    idx = pd.to_datetime(["2026-01-05", "2026-01-12"])
    usd_price = pd.Series([100.0, 110.0], index=idx)      # +10% in dollars
    usd_to_gbp = pd.Series([0.80, 0.76], index=idx)       # dollar falls 5% against sterling
    gbp = in_base_currency(usd_price, usd_to_gbp)
    assert gbp.pct_change().iloc[-1] == pytest.approx(1.10 * 0.95 - 1)   # +4.5% in sterling
