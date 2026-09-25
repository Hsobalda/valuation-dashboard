"""Saved segment builds, one JSON file per company in journal/segments/ (git-ignored)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from .journal import journal_path


def _path(ticker: str, folder: Path | None = None) -> Path:
    folder = folder or journal_path().parent / "segments"
    return folder / (re.sub(r"[^A-Za-z0-9._-]", "_", ticker) + ".json")


def load_segments(ticker: str, folder: Path | None = None) -> list[dict] | None:
    path = _path(ticker, folder)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def save_segments(ticker: str, rows: list[dict], folder: Path | None = None) -> None:
    path = _path(ticker, folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
