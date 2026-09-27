import numpy as np
import pandas as pd
import pytest

from ui.portfolio import plan_pie


def _prices(seed, drift=0.001, vol=0.03, base=None, beta=0.0):
    rng = np.random.default_rng(seed)
    r = rng.normal(drift, vol, 156) + (beta * base if base is not None else 0)
    return pd.Series(100 * np.cumprod(1 + r), index=pd.date_range("2023-10-02", periods=156, freq="W-MON"))


def _candidate(er, unc="Low", safe=True, sector="A"):
    return {"expected_return": er, "uncertainty": unc, "passes_margin_of_safety": safe, "sector": sector}


def test_plan_sizes_passing_names_and_normalises_the_pie_today():
    bench_r = np.random.default_rng(0).normal(0.001, 0.02, 156)
    closes = {"BENCH": _prices(0, vol=0.02), "GOOD": _prices(1, base=bench_r, beta=0.5),
              "OKAY": _prices(2, base=bench_r), "FAIL": _prices(3)}
    pool = {"GOOD": _candidate(0.16, sector="A"), "OKAY": _candidate(0.11, safe=False, sector="B"),
            "FAIL": _candidate(0.05, sector="C")}
    plan = plan_pie(closes, "BENCH", pool, hurdle=0.10, holdings=10, sector_cap=0.30)

    sized = plan["sized"].set_index("ticker")
    assert sized.loc["FAIL", "weight"] == 0.0                        # below required return: no position
    assert sized.loc["OKAY", "limit"].startswith("starter")          # above buy zone: half size
    assert sized.loc["GOOD", "weight"] > sized.loc["OKAY", "weight"]
    assert list(plan["today"].index) == ["GOOD", "OKAY"]             # only held names in today's pie
    assert plan["today"].sum() == pytest.approx(1.0)                 # what to type into the pie now
    assert plan["filled"] == pytest.approx(sized["weight"].sum())    # share of the planned full pie
    assert plan["contrib"].sum() == pytest.approx(1.0)
    assert -1 <= plan["pie_corr"] <= 1


def test_nothing_passes_means_nothing_to_buy():
    closes = {"BENCH": _prices(0), "X": _prices(1)}
    plan = plan_pie(closes, "BENCH", {"X": _candidate(0.04)}, hurdle=0.10, holdings=10, sector_cap=0.3)
    assert plan["today"].empty and plan["filled"] == 0.0
