import pytest

from engine.segments import Segment, build


def test_single_segment_reproduces_its_own_path():
    b = build([Segment("All", 100.0, 0.10, 0.02)])
    assert b.growth == pytest.approx([0.10, 0.08, 0.06, 0.04, 0.02])


def test_mix_shift_raises_blended_growth_and_margin():
    # a slow, low-margin segment and a fast, high-margin one
    products = Segment("Products", 300.0, 0.02, 0.02, margin=0.25)
    services = Segment("Services", 100.0, 0.12, 0.12, margin=0.70)
    b = build([products, services])
    # year 1: (306 + 112) / 400 - 1 = 4.5%; blended growth rises as Services' share grows
    assert b.growth[0] == pytest.approx(0.045)
    assert all(later > earlier for earlier, later in zip(b.growth, b.growth[1:]))
    assert b.mix_start == pytest.approx([0.75, 0.25])
    assert b.mix_end[1] > 0.25
    assert b.margin_start == pytest.approx(0.75 * 0.25 + 0.25 * 0.70)
    assert b.margin_end > b.margin_start


def test_margin_blank_unless_every_segment_has_one():
    b = build([Segment("A", 50.0, 0.05, 0.05, margin=0.3), Segment("B", 50.0, 0.05, 0.05)])
    assert b.margin_start is None and b.margin_end is None


def test_empty_or_zero_revenue_rejected():
    with pytest.raises(ValueError):
        build([])
    with pytest.raises(ValueError):
        build([Segment("A", 0.0, 0.05, 0.05)])


def test_year_two_rate_matches_the_company_growth_path():
    from engine.valuation import Assumptions

    a = Assumptions(growth_y1=0.10, growth_y2=0.08, growth_y5=0.04)
    b = build([Segment("All", 100.0, 0.10, 0.04, growth_y2=0.08)])
    # an unsplit company reproduces the path the sliders would give
    assert b.growth == pytest.approx(a.growth_path())


def test_editor_rows_without_growth_are_left_out_not_zeroed():
    from ui.segments import to_segments

    segs, missing = to_segments([
        {"Segment": "A", "Revenue (bn)": 1.0, "Growth yr 1 (%)": 5.0, "Growth yr 2 (%)": None,
         "Growth yr 5 (%)": 3.0, "Operating margin (%)": float("nan")},
        {"Segment": "B", "Revenue (bn)": 1.0, "Growth yr 1 (%)": float("nan"), "Growth yr 5 (%)": 3.0},
    ])
    assert [s.name for s in segs] == ["A"] and missing == ["B"]
    assert segs[0].growth_y2 is None and segs[0].margin is None


def test_saved_rows_from_before_year_two_column_still_load():
    from ui.segments import to_segments

    segs, _ = to_segments([{"Segment": "A", "Revenue (bn)": 1.0, "Growth yr 1 (%)": 5.0,
                            "Growth yr 5 (%)": 3.0, "Operating margin (%)": 20.0}])
    assert build(segs).growth == pytest.approx([0.05, 0.045, 0.04, 0.035, 0.03])
