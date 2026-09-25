from data.journal import load_entries, save_entry


def test_round_trip_keeps_order(tmp_path):
    path = tmp_path / "j.jsonl"
    save_entry({"ticker": "AAPL", "price": 336.0}, path)
    save_entry({"ticker": "MSFT", "price": 498.0}, path)
    assert [e["ticker"] for e in load_entries(path)] == ["AAPL", "MSFT"]


def test_missing_file_is_an_empty_journal(tmp_path):
    assert load_entries(tmp_path / "none.jsonl") == []


def test_damaged_line_is_skipped(tmp_path):
    path = tmp_path / "j.jsonl"
    save_entry({"ticker": "AAPL"}, path)
    with path.open("a") as f:
        f.write("{not json\n")
    save_entry({"ticker": "KO"}, path)
    assert [e["ticker"] for e in load_entries(path)] == ["AAPL", "KO"]


def test_segments_round_trip_per_ticker(tmp_path):
    from data.segments import load_segments, save_segments

    rows = [{"Segment": "Services", "Revenue": 100.0}]
    save_segments("TSCO.L", rows, tmp_path)
    assert load_segments("TSCO.L", tmp_path) == rows
    assert load_segments("AAPL", tmp_path) is None
