"""The Excel export must value the company exactly as the engine does."""

import dataclasses

import pytest

from data.provider import SampleProvider
from engine.valuation import Assumptions, value_per_share
from ui.excel_export import build_dcf_workbook

formulas = pytest.importorskip("formulas")

A = Assumptions(growth_y1=0.12, growth_y2=0.09, growth_y5=0.05, ebit_margin=0.30,
                target_ebit_margin=0.28, tax_rate=0.16, roic=0.40, fade_years=10,
                terminal_excess_return=0.02, terminal_growth=0.025, discount_rate=0.10)


def _excel_value(tmp_path, a: Assumptions, company: dict) -> float:
    path = tmp_path / "dcf.xlsx"
    path.write_bytes(build_dcf_workbook(company, a, {}))
    sol = formulas.ExcelModel().loads(str(path)).finish().calculate()
    errors = [k for k, v in sol.items() if str(v.value[0, 0]).startswith("#")]
    assert not errors, errors[:5]
    label = next(k for k, v in sol.items() if v.value[0, 0] == "Value per share (base case)")
    return sol[label.replace("!A", "!B")].value[0, 0]


@pytest.mark.parametrize("fade_years", [5, 20])
def test_excel_matches_engine(tmp_path, fade_years):
    m = SampleProvider().fundamental_metrics("AAPL")
    company = dict(name="Apple", ticker="AAPL", currency="USD", base_year=2025,
                   base_revenue=m["revenue"], net_debt=m["net_debt"],
                   minority_interest=m["minority_interest"], shares_diluted=m["shares_diluted"],
                   price=m["price"], years_since_fy_end=0.4, data_source="sample")
    a = dataclasses.replace(A, fade_years=fade_years)
    engine = value_per_share(m["revenue"], a, m["net_debt"], m["minority_interest"],
                             m["shares_diluted"], years_since_fy_end=0.4)
    assert _excel_value(tmp_path, a, company) == pytest.approx(engine, rel=1e-9)
