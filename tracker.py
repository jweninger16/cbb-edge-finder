"""
Pick tracker backed by Google Sheets (persistent) with local JSON fallback.

Setup:
  1. Create a Google Cloud service account with Sheets API enabled
  2. Download the JSON key file
  3. Create a Google Sheet and share it with the service account email
  4. Set GOOGLE_SHEET_URL in config.py, or the GOOGLE_SHEET_URL env var

Credentials:
  - Streamlit Cloud: paste the JSON key contents into .streamlit/secrets.toml
    under [gcp_service_account]
  - Local: save the JSON key as "gcp_credentials.json" in the project folder
"""

import json
import os
from pathlib import Path

# ── Column order for the spreadsheet ─────────────────────────────────────────
_COLUMNS = [
    "date", "away", "home", "edge_team", "model_margin", "vegas_margin",
    "vegas_favors", "edge_size", "confidence", "bet_amount", "result",
    "profit", "final_score",
]


# ── Google Sheets backend ────────────────────────────────────────────────────

def _get_gsheet():
    """
    Connect to Google Sheets. Returns a gspread Worksheet or None.
    Tries Streamlit secrets first, then a local JSON key file.
    """
    try:
        import gspread
        from google.oauth2.service_account import Credentials
    except ImportError:
        return None

    creds_dict = None

    # Option 1: Streamlit Cloud secrets
    try:
        import streamlit as st
        if hasattr(st, "secrets") and "gcp_service_account" in st.secrets:
            creds_dict = dict(st.secrets["gcp_service_account"])
    except Exception:
        pass

    # Option 2: Local JSON key file
    if creds_dict is None:
        key_path = Path(__file__).parent / "gcp_credentials.json"
        if key_path.exists():
            with open(key_path, "r") as f:
                creds_dict = json.load(f)

    if creds_dict is None:
        return None

    # Option 3: Sheet URL from env or config
    sheet_url = os.environ.get("GOOGLE_SHEET_URL", "")
    if not sheet_url:
        try:
            from config import GOOGLE_SHEET_URL
            sheet_url = GOOGLE_SHEET_URL
        except (ImportError, AttributeError):
            pass

    if not sheet_url or "PASTE" in sheet_url:
        return None

    try:
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_url(sheet_url)

        # Use the first worksheet
        ws = sh.sheet1

        # Initialize headers if sheet is empty
        if not ws.row_values(1):
            ws.update("A1", [_COLUMNS])

        return ws
    except Exception as e:
        print(f"Google Sheets connection failed: {e}")
        return None


def _picks_from_rows(rows: list[list]) -> list[dict]:
    """Convert sheet rows (including header) to list of pick dicts."""
    if len(rows) < 2:
        return []

    headers = rows[0]
    picks = []
    for row in rows[1:]:
        pick = {}
        for i, col in enumerate(headers):
            val = row[i] if i < len(row) else ""
            # Type conversions
            if col in ("model_margin", "vegas_margin", "edge_size", "profit"):
                try:
                    val = float(val) if val != "" else None
                except (ValueError, TypeError):
                    val = None
            elif col == "bet_amount":
                try:
                    val = float(val) if val != "" else 100
                except (ValueError, TypeError):
                    val = 100
            elif col in ("result", "final_score"):
                val = val if val else None
            pick[col] = val
        picks.append(pick)
    return picks


def _picks_to_rows(picks: list[dict]) -> list[list]:
    """Convert list of pick dicts to sheet rows (with header)."""
    rows = [_COLUMNS]
    for p in picks:
        row = []
        for col in _COLUMNS:
            val = p.get(col, "")
            if val is None:
                val = ""
            row.append(str(val))
        rows.append(row)
    return rows


# ── Local JSON fallback ──────────────────────────────────────────────────────

def _load_json() -> list[dict]:
    try:
        from config import TRACKER_FILE
        with open(TRACKER_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, ImportError):
        return []


def _save_json(picks: list[dict]) -> None:
    try:
        from config import TRACKER_FILE
        with open(TRACKER_FILE, "w") as f:
            json.dump(picks, f, indent=2)
    except ImportError:
        pass


# ── Public API (same interface as before) ────────────────────────────────────

def load_picks() -> list[dict]:
    """Load all picks. Tries Google Sheets first, then local JSON."""
    ws = _get_gsheet()
    if ws is not None:
        try:
            rows = ws.get_all_values()
            return _picks_from_rows(rows)
        except Exception as e:
            print(f"Failed to read Google Sheet: {e}")

    return _load_json()


def save_picks(picks: list[dict]) -> None:
    """Save all picks. Writes to Google Sheets and local JSON."""
    ws = _get_gsheet()
    if ws is not None:
        try:
            rows = _picks_to_rows(picks)
            ws.clear()
            ws.update("A1", rows)
        except Exception as e:
            print(f"Failed to write Google Sheet: {e}")

    # Always also save locally as backup
    _save_json(picks)
