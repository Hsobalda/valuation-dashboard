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


def update_entry(index: int, changes: dict, path: Path | None = None) -> None:
    """Change fields of one entry, numbered as load_entries returns them; every
    other line, damaged ones included, is written back as it was."""
    path = path or journal_path()
    lines = path.read_text(encoding="utf-8").splitlines()
    valid = -1
    for i, line in enumerate(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        valid += 1
        if valid == index:
            lines[i] = json.dumps({**entry, **changes})
            break
    else:
        raise IndexError(f"no journal entry {index}")
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
    tmp.replace(path)
