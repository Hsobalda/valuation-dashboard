"""Financial-statement style tables: line items as rows, years as columns."""

from __future__ import annotations

import pandas as pd

from engine.projection import Projection


def _scale(values) -> tuple[float, str]:
    biggest = max((abs(v) for v in values if v == v), default=0.0)
    return (1e9, "bn") if biggest >= 1e9 else (1e6, "m")


def _money(v: float, scale: float) -> str:
    return "—" if v != v else f"{v / scale:,.1f}"


def _pct(v: float) -> str:
    return "—" if v != v else f"{v:.1%}"


def projection_table(proj: Projection, currency: str) -> pd.DataFrame:
    scale, unit = _scale(proj.revenue)
    cols = [f"Year {t}" for t in range(1, len(proj.revenue) + 1)]
    rows = {
        f"Revenue ({currency} {unit})": [_money(v, scale) for v in proj.revenue],
        "Revenue growth": [_pct(g) for g in proj.growth],
        "EBIT margin": [_pct(v) for v in proj.ebit_margin],
        f"NOPAT ({currency} {unit})": [_money(v, scale) for v in proj.nopat],
        f"Reinvestment ({currency} {unit})": [_money(v, scale) for v in proj.reinvestment],
        "Reinvestment % of NOPAT": [_pct(r / n) if n else "—" for r, n in zip(proj.reinvestment, proj.nopat)],
        f"Free cash flow ({currency} {unit})": [_money(v, scale) for v in proj.fcff],
    }
    return pd.DataFrame.from_dict(rows, orient="index", columns=cols)


def reinvestment_history_table(df: pd.DataFrame, currency: str) -> pd.DataFrame:
    scale, unit = _scale(df["nopat"].tolist() + df["capex"].tolist())
    rows = {
        "Revenue growth": [_pct(v) for v in df["revenue_growth"]],
        f"NOPAT ({currency} {unit})": [_money(v, scale) for v in df["nopat"]],
        f"Capex ({currency} {unit})": [_money(v, scale) for v in df["capex"]],
        f"D&A ({currency} {unit})": [_money(v, scale) for v in df["da"]],
        f"Net capex ({currency} {unit})": [_money(v, scale) for v in df["net_capex"]],
        "Net capex % of NOPAT": [_pct(v) for v in df["net_capex_pct_nopat"]],
    }
    return pd.DataFrame.from_dict(rows, orient="index", columns=[f"FY{y}" for y in df.index])
