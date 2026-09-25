import pandas as pd

from brief.seeds import uncertainty_rating


class _Stub:
    def __init__(self, margins, net_debt, ebitda, beta, fcf):
        idx = list(range(2021, 2021 + len(margins)))
        self.inc = pd.DataFrame({"revenue": [100.0] * len(idx), "operating_income": [m * 100 for m in margins]}, index=idx)
        self.cf = pd.DataFrame({"operating_cash_flow": fcf, "capital_expenditure": [0.0] * len(idx)}, index=idx)
        self.m = {"net_debt": net_debt, "ebitda": ebitda, "beta": beta}

    def income_statement(self, t):
        return self.inc

    def cash_flow(self, t):
        return self.cf

    def fundamental_metrics(self, t):
        return self.m


def test_steady_unlevered_business_is_low():
    u = uncertainty_rating(_Stub([0.30, 0.31, 0.30, 0.31], 0.0, 50.0, 0.9, [10.0] * 4), "X")
    assert (u["rating"], u["score"]) == ("Low", 0)


def test_volatile_levered_high_beta_business_is_very_high():
    u = uncertainty_rating(_Stub([0.02, 0.15, -0.05, 0.10], 400.0, 100.0, 1.8, [5.0, -3.0, 4.0, 2.0]), "X")
    assert (u["rating"], u["score"]) == ("Very high", 7)


def test_margin_volatility_is_relative_to_the_margin():
    # the same 2pp swing is small on a 30% margin but large on a 4% margin
    thick = uncertainty_rating(_Stub([0.28, 0.32, 0.28, 0.32], 0.0, 50.0, 1.0, [10.0] * 4), "X")
    thin = uncertainty_rating(_Stub([0.02, 0.06, 0.02, 0.06], 0.0, 50.0, 1.0, [10.0] * 4), "X")
    assert thick["score"] == 0 and thin["score"] == 2
