"""
Simple JSON-backed pick tracker.
"""

import json

from config import TRACKER_FILE


def load_picks() -> list[dict]:
    try:
        with open(TRACKER_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_picks(picks: list[dict]) -> None:
    with open(TRACKER_FILE, "w") as f:
        json.dump(picks, f, indent=2)
