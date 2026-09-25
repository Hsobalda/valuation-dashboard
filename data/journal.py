"""Valuation journal: a dated record of each valuation, so calls can be checked later.

Stored as JSON lines in journal/valuations.jsonl (git-ignored: it's a personal
investing record) or wherever VALUATION_JOURNAL points.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parent.parent / "journal" / "valuations.jsonl"


def journal_path() -> Path:
    return Path(os.environ.get("VALUATION_JOURNAL", DEFAULT_PATH))


def save_entry(entry: dict, path: Path | None = None) -> None:
    path = path or journal_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def load_entries(path: Path | None = None) -> list[dict]:
    """All entries, oldest first. A damaged line is skipped rather than losing the rest."""
    path = path or journal_path()
    if not path.exists():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries
