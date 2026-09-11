"""Bundled offline sample data.

Used only when live data is unavailable (e.g. sandboxed/offline) so the app is
still demonstrable and the tests stay deterministic. Figures are ILLUSTRATIVE
-- approximate real-world values anchored to public filings and to the real
snapshots in v02_draft/snapshots/, NOT exact. The UI labels this clearly.

Conventions: statement values in millions; capex/dividends/buybacks are positive
cash-outflow magnitudes; per-share and share-count figures unscaled.
"""

from __future__ import annotations

import pandas as pd

YEARS = [2020, 2021, 2022, 2023, 2024, 2025]


def _company(name, sector, industry, summary, currency, beta, price, market_cap,
             shares, revenue, cogs, operating_income, d_and_a, interest_expense,
             net_income, eps, tax_rate, cash, st_inv, total_debt, total_assets,
             total_liabilities, equity, minority, goodwill, ocf, capex,
             dividends, buybacks):
    n = len(YEARS)
    income = {
        "revenue": revenue,
        "cost_of_revenue": cogs,
        "gross_profit": [r - c for r, c in zip(revenue, cogs)],
        "operating_income": operating_income,
        "depreciation_amortization": d_and_a,
        "interest_expense": interest_expense,
        "net_income": net_income,
        "eps_diluted": eps,
    }
    # Derive pretax/tax consistently from net income and the effective tax rate
    # (guarding non-positive income years).
    pretax, tax = [], []
    for ni in net_income:
        if ni <= 0:
            pretax.append(ni); tax.append(0.0)
        else:
            p = ni / (1.0 - tax_rate)
            pretax.append(round(p, 1)); tax.append(round(p - ni, 1))
    income["pretax_income"] = pretax
    income["income_tax"] = tax

    balance = {
        "cash_and_equiv": cash,
        "short_term_investments": st_inv,
        "total_debt": total_debt,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "stockholder_equity": equity,
        "minority_interest": minority,
        "goodwill": goodwill,
    }
    cashflow = {
        "operating_cash_flow": ocf,
        "capital_expenditure": capex,
        "dividends_paid": dividends,
        "stock_buybacks": buybacks,
    }

    # Schema stores money in RAW units (dollars/GBP); arrays above are in
    # millions for readability, so scale them up here. eps_diluted is per-share
    # and stays raw.
    SCALE = 1_000_000
    income_money = [k for k in income if k != "eps_diluted"]
    for k in income_money:
        income[k] = [v * SCALE for v in income[k]]
    for k in balance:
        balance[k] = [v * SCALE for v in balance[k]]
    for k in cashflow:
        cashflow[k] = [v * SCALE for v in cashflow[k]]

    return {
        "info": {"name": name, "sector": sector, "industry": industry,
                 "summary": summary, "currency": currency, "beta": beta},
        "market": {"price": price, "market_cap": market_cap * SCALE,
                   "shares_outstanding": shares, "shares_diluted": shares},
        "years": list(YEARS),
        "income": {k: v[:n] for k, v in income.items()},
        "balance": {k: v[:n] for k, v in balance.items()},
        "cashflow": {k: v[:n] for k, v in cashflow.items()},
    }


# Values in millions unless noted. Illustrative.
COMPANIES = {
    "AAPL": _company(
        name="Apple Inc.", sector="Technology", industry="Consumer Electronics",
        summary="Designs and sells the iPhone, Mac, iPad, wearables and a fast-growing services business.",
        currency="USD", beta=1.24, price=245.0, market_cap=3_700_000, shares=15_200_000_000,
        revenue=[274_515, 365_817, 394_328, 383_285, 391_035, 400_000],
        cogs=[169_559, 212_981, 223_546, 214_137, 210_352, 215_000],
        operating_income=[66_288, 108_949, 119_437, 114_301, 123_216, 126_000],
        d_and_a=[11_056, 11_284, 11_104, 11_519, 11_445, 12_000],
        interest_expense=[2_873, 2_645, 2_931, 3_933, 2_500, 2_500],
        net_income=[57_411, 94_680, 99_803, 96_995, 93_736, 100_000],
        eps=[3.28, 5.61, 6.11, 6.13, 6.08, 6.60], tax_rate=0.16,
        cash=[38_016, 34_940, 23_646, 29_965, 29_943, 32_000],
        st_inv=[52_927, 27_699, 24_658, 31_590, 33_190, 30_000],
        total_debt=[112_436, 124_719, 120_069, 111_088, 106_629, 100_000],
        total_assets=[323_888, 351_002, 352_755, 352_583, 364_980, 370_000],
        total_liabilities=[258_549, 287_912, 302_083, 290_437, 308_030, 300_000],
        equity=[65_339, 63_090, 50_672, 62_146, 56_950, 70_000],
        minority=[0, 0, 0, 0, 0, 0], goodwill=[0, 0, 0, 0, 0, 0],
        ocf=[80_674, 104_038, 122_151, 110_543, 118_254, 120_000],
        capex=[7_309, 11_085, 10_708, 10_959, 9_447, 10_000],
        dividends=[14_081, 14_467, 14_841, 15_025, 15_234, 15_500],
        buybacks=[72_358, 85_971, 89_402, 77_550, 94_949, 80_000],
    ),
    "MSFT": _company(
        name="Microsoft Corporation", sector="Technology", industry="Software - Infrastructure",
        summary="Cloud (Azure), Office, Windows and LinkedIn; a diversified software + cloud compounder.",
        currency="USD", beta=0.90, price=480.0, market_cap=3_500_000, shares=7_400_000_000,
        revenue=[143_015, 168_088, 198_270, 211_915, 245_122, 260_000],
        cogs=[46_078, 52_232, 62_787, 65_863, 74_114, 78_000],
        operating_income=[52_959, 69_916, 83_383, 88_523, 109_433, 116_000],
        d_and_a=[12_796, 11_686, 14_460, 13_861, 22_287, 23_000],
        interest_expense=[2_591, 2_346, 2_063, 1_968, 1_874, 1_800],
        net_income=[44_281, 61_271, 72_738, 72_361, 88_136, 95_000],
        eps=[5.76, 8.05, 9.65, 9.68, 11.80, 12.70], tax_rate=0.18,
        cash=[13_652, 14_224, 13_931, 34_704, 18_419, 25_000],
        st_inv=[122_951, 116_110, 90_392, 76_558, 57_303, 50_000],
        total_debt=[59_578, 50_074, 47_032, 42_357, 42_300, 40_000],
        total_assets=[301_311, 333_779, 364_840, 411_976, 512_163, 540_000],
        total_liabilities=[183_007, 191_791, 198_298, 205_753, 243_686, 250_000],
        equity=[118_304, 141_988, 166_542, 206_223, 268_477, 290_000],
        minority=[0, 0, 0, 0, 0, 0], goodwill=[43_000, 49_683, 67_300, 67_300, 67_300, 67_300],
        ocf=[60_675, 76_740, 89_035, 87_582, 118_548, 125_000],
        capex=[15_441, 20_622, 23_886, 28_107, 44_477, 46_000],
        dividends=[15_137, 16_521, 18_135, 19_444, 21_824, 23_000],
        buybacks=[22_968, 27_401, 32_290, 22_102, 17_440, 18_000],
    ),
    "PEP": _company(
        name="Pepsico, Inc.", sector="Consumer Defensive", industry="Beverages - Non-Alcoholic",
        summary="Global snacks (Frito-Lay) and beverages (Pepsi, Gatorade) franchise.",
        currency="USD", beta=0.60, price=136.69, market_cap=186_718, shares=1_366_000_000,
        revenue=[70_372, 79_474, 86_392, 91_471, 91_854, 93_925],
        cogs=[31_797, 37_075, 40_576, 41_881, 41_744, 43_066],
        operating_income=[10_080, 11_298, 11_512, 11_986, 12_809, 11_365],
        d_and_a=[2_539, 2_645, 2_682, 2_803, 2_879, 2_900],
        interest_expense=[1_128, 1_396, 939, 872, 1_121, 1_100],
        net_income=[7_120, 7_618, 8_910, 9_074, 9_578, 8_240],
        eps=[5.12, 5.49, 6.42, 6.56, 6.95, 6.05], tax_rate=0.20,
        cash=[10_233, 5_509, 5_348, 10_004, 9_159, 8_000],
        st_inv=[1_892, 3_664, 1_389, 1_869, 2_500, 2_000],
        total_debt=[40_786, 40_048, 38_296, 44_404, 49_901, 49_000],
        total_assets=[92_918, 92_377, 92_187, 100_495, 99_467, 107_399],
        total_liabilities=[79_464, 76_334, 75_038, 82_014, 79_061, 86_999],
        equity=[13_454, 16_043, 17_149, 18_481, 20_406, 20_400],
        minority=[118, 97, 92, 85, 80, 80], goodwill=[18_757, 19_490, 19_197, 19_214, 19_200, 19_200],
        ocf=[10_413, 11_788, 10_811, 13_442, 12_507, 12_087],
        capex=[4_657, 4_731, 5_207, 5_518, 5_318, 4_415],
        dividends=[5_509, 5_712, 5_993, 6_348, 6_803, 7_000],
        buybacks=[4_000, 3_000, 2_000, 1_500, 1_000, 1_000],
    ),
    "T": _company(
        name="AT&T Inc.", sector="Communication Services", industry="Telecom Services",
        summary="US telecom (wireless + fiber) and media-trimmed after the WarnerMedia spin.",
        currency="USD", beta=0.55, price=25.15, market_cap=172_337, shares=6_852_000_000,
        revenue=[171_760, 168_864, 120_741, 122_428, 122_336, 125_648],
        cogs=[80_200, 82_000, 50_848, 50_123, 49_221, 50_820],
        operating_income=[24_100, 27_000, 23_000, 24_000, 25_000, 33_811],
        d_and_a=[27_200, 25_000, 18_021, 18_777, 20_580, 20_886],
        interest_expense=[7_925, 6_884, 6_108, 6_700, 6_804, 6_800],
        net_income=[-5_384, 20_081, -8_524, 14_400, 10_948, 21_953],
        eps=[-0.75, 2.76, -1.10, 1.97, 1.52, 2.98], tax_rate=0.22,
        cash=[9_740, 21_044, 18_234, 6_722, 9_000, 18_000],
        st_inv=[2_000, 2_500, 2_000, 2_000, 2_000, 2_000],
        total_debt=[158_000, 155_000, 155_043, 153_000, 150_000, 150_000],
        total_assets=[525_761, 551_622, 402_853, 407_060, 394_795, 420_198],
        total_liabilities=[364_088, 385_290, 292_320, 293_060, 274_795, 295_198],
        equity=[161_673, 166_332, 110_533, 114_000, 120_000, 125_000],
        minority=[1_000, 1_000, 1_000, 1_000, 1_000, 1_000],
        goodwill=[135_000, 137_000, 70_000, 70_000, 70_000, 70_000],
        ocf=[43_130, 39_804, 32_023, 38_314, 38_771, 40_284],
        capex=[15_675, 15_462, 19_626, 17_853, 20_263, 20_842],
        dividends=[14_960, 15_510, 11_000, 8_000, 8_000, 8_000],
        buybacks=[0, 0, 0, 0, 0, 0],
    ),
    "TSCO.L": _company(
        name="Tesco PLC", sector="Consumer Defensive", industry="Grocery Stores",
        summary="The UK's largest grocery retailer, also in Central Europe and Ireland.",
        currency="GBP", beta=0.40, price=3.50, market_cap=26_500, shares=7_600_000_000,
        revenue=[53_400, 53_300, 61_300, 65_700, 68_000, 70_000],
        cogs=[49_800, 49_700, 57_000, 61_000, 63_100, 65_000],
        operating_income=[1_800, 1_900, 2_500, 2_800, 2_900, 3_000],
        d_and_a=[1_900, 1_900, 2_100, 2_200, 2_300, 2_400],
        interest_expense=[700, 650, 600, 550, 500, 480],
        net_income=[1_000, 6_000, 1_200, 2_000, 2_200, 2_400],
        eps=[0.08, 0.60, 0.15, 0.26, 0.29, 0.31], tax_rate=0.20,
        cash=[1_400, 2_400, 2_200, 2_300, 2_600, 2_800],
        st_inv=[200, 200, 200, 200, 200, 200],
        total_debt=[13_000, 12_000, 11_000, 10_500, 10_000, 9_800],
        total_assets=[47_000, 45_000, 44_000, 43_000, 43_000, 43_500],
        total_liabilities=[33_000, 30_500, 31_500, 30_000, 29_500, 29_700],
        equity=[14_000, 14_500, 12_500, 13_000, 13_500, 13_800],
        minority=[0, 0, 0, 0, 0, 0], goodwill=[4_000, 4_000, 4_000, 4_000, 4_000, 4_000],
        ocf=[2_800, 3_200, 3_000, 3_400, 3_600, 3_800],
        capex=[1_500, 1_400, 1_300, 1_300, 1_400, 1_500],
        dividends=[1_200, 1_300, 1_000, 1_100, 1_200, 1_300],
        buybacks=[300, 500, 500, 500, 600, 600],
    ),
}


def to_dataframes(company: dict) -> dict[str, pd.DataFrame]:
    """Convert a company dict into normalized statement DataFrames."""
    years = company["years"]
    return {
        "income": pd.DataFrame(company["income"], index=years),
        "balance": pd.DataFrame(company["balance"], index=years),
        "cashflow": pd.DataFrame(company["cashflow"], index=years),
    }
