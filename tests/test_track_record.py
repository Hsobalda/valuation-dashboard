import pytest

from engine.track_record import scorecard, track_record

ENTRIES = [
    {"date": "2026-01-02", "ticker": "AAA", "decision": "Buy", "price": 100.0, "fair_value": 150.0},
    {"date": "2026-02-02", "ticker": "BBB", "decision": "Pass", "price": 50.0, "fair_value": 40.0},
    {"date": "2026-03-02", "ticker": "AAA", "decision": "Buy", "price": 120.0, "fair_value": 150.0},
]


def test_return_since_each_call():
    rec = track_record(ENTRIES, {"AAA": 132.0, "BBB": 45.0})
    assert rec["return_since"].tolist() == pytest.approx([0.32, -0.10, 0.10])
    assert rec["upside_then"].tolist() == pytest.approx([0.5, -0.2, 0.25])


def test_scorecard_averages_by_decision():
    card = scorecard(track_record(ENTRIES, {"AAA": 132.0, "BBB": 45.0}))
    assert card.loc["Buy", "calls"] == 2
    assert card.loc["Buy", "average_return"] == pytest.approx(0.21)
    assert card.loc["Pass", "average_return"] == pytest.approx(-0.10)


def test_missing_current_price_leaves_return_blank():
    rec = track_record(ENTRIES[:1], {})
    assert rec["return_since"].isna().all()
