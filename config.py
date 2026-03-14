"""
Configuration for CBB Edge Finder.
Edit DATA_DIR below to point to your local data folder.
"""

import json
import os
from datetime import date
from pathlib import Path

# ── Data directory ───────────────────────────────────────────────────────────
# Priority: env var → local data/ folder → repo root (Streamlit Cloud)
_local_data = Path(__file__).parent / "data"
_repo_root = Path(__file__).parent

DATA_DIR = Path(os.environ.get("CBB_DATA_DIR", ""))
if not DATA_DIR.exists() or str(DATA_DIR) == ".":
    DATA_DIR = _local_data if _local_data.exists() else _repo_root

# ── File paths ───────────────────────────────────────────────────────────────
# Handle both filenames: local uses combined_basketball_data.csv,
# GitHub/Cloud uses basketball_data.csv
_csv_name1 = DATA_DIR / "combined_basketball_data.csv"
_csv_name2 = DATA_DIR / "basketball_data.csv"
COMBINED_CSV = _csv_name1 if _csv_name1.exists() else _csv_name2

KENPOM_CSV = DATA_DIR / "kenpom.csv"
PARAMS_FILE = DATA_DIR / "model_params.json"
TRACKER_FILE = DATA_DIR / "pick_tracker.json"

# ── API keys ─────────────────────────────────────────────────────────────────
ODDS_API_KEY = os.environ.get("ODDS_API_KEY", "4ad99d9b0d88ecf91a5ae129e36fdf65")

# ── Google Sheets pick tracker ───────────────────────────────────────────────
# Paste your Google Sheet URL here (or set GOOGLE_SHEET_URL env var).
# Leave as-is to use local JSON file only.
GOOGLE_SHEET_URL = os.environ.get(
    "GOOGLE_SHEET_URL",
    "PASTE_YOUR_GOOGLE_SHEET_URL_HERE",
)

# ── Model defaults (overridden by model_params.json if present) ──────────────
STARTING_ELO = 1500

_DEFAULTS = {
    "k_factor": 44.73,
    "recency_decay": 0.005,
    "elo_divisor": 10.0,
    "kenpom_divisor": 5.0,
    "kenpom_weight": 0.39,
    "hca_default": 2.5,
    "form_weight": 20.0,
}


def load_params() -> dict:
    """Load model parameters from JSON, falling back to defaults."""
    try:
        with open(PARAMS_FILE, "r") as f:
            params = json.load(f)
        print(f"Loaded optimized params (RMSE: {params.get('validation_rmse', 'N/A')})")
        return {k: params.get(k, v) for k, v in _DEFAULTS.items()}
    except (FileNotFoundError, json.JSONDecodeError):
        print("Using default params")
        return dict(_DEFAULTS)


PARAMS = load_params()

K_FACTOR = PARAMS["k_factor"]
RECENCY_DECAY = PARAMS["recency_decay"]
ELO_DIVISOR = PARAMS["elo_divisor"]
KENPOM_DIVISOR = PARAMS["kenpom_divisor"]
KENPOM_WEIGHT = PARAMS["kenpom_weight"]

# These override model_params.json — tuned from backtest results
HCA_DEFAULT = 1.5        # fixed from 3.94 — modern CBB HCA is ~1.5-2.5
FORM_WEIGHT = 15.0       # was 20.0 — form streaks are a real edge vs Vegas

# ── Ensemble blending ────────────────────────────────────────────────────────
# Barttorvik is the core, but ELO captures mid-season momentum and trajectory
# that static efficiency ratings miss. 85/15 is the sweet spot with 1 season
# of data — enough ELO to create disagreements with Vegas, not so much
# that noisy early-season ratings hurt us.
ENSEMBLE_KENPOM_WEIGHT = 0.85
ENSEMBLE_ELO_WEIGHT = 1.0 - ENSEMBLE_KENPOM_WEIGHT

# ── ELO season handling ─────────────────────────────────────────────────────
# Regress ELO toward 1500 between seasons by this fraction.
# 0.0 = full carryover, 1.0 = full reset.
# College rosters turn over ~40%/yr in the transfer portal era.
SEASON_REGRESS_FRACTION = 0.40
SEASON_START_MONTH = 11  # November

# ── Rest / fatigue ───────────────────────────────────────────────────────────
B2B_PENALTY = 1.2        # back-to-back — Vegas often underprices fatigue
SHORT_REST_PENALTY = 0.4  # 2 days rest
LONG_REST_BONUS = 0.4     # 7+ days rest (bye week)

# ── Tournament dates (update yearly) ────────────────────────────────────────
CONF_TOURNEY_START = date(2026, 3, 4)
CONF_TOURNEY_END = date(2026, 3, 15)
NCAA_TOURNEY_START = date(2026, 3, 19)
NCAA_TOURNEY_END = date(2026, 4, 6)

# ── Edge thresholds ──────────────────────────────────────────────────────────
EDGE_MINIMUM = 2.0       # was 3.0 — lowered to surface more picks
EDGE_HIGH = 7.0
EDGE_MEDIUM = 5.0
SHARP_THRESHOLD = 15
SHARP_BOOST = 2.0
MIN_GAMES = 20
MIN_HCA_GAMES = 10
HCA_CAP = 3.5              # max team-specific HCA (prevent outliers)
HCA_FLOOR = 0.0            # min (some teams have no real HCA)
FORM_LOOKBACK_DAYS = 30
MIN_FORM_GAMES = 3

# ── KenPom baselines ─────────────────────────────────────────────────────────
# Average D1 efficiency per 100 possessions (KenPom normalises around this).
# Used to estimate matchup-specific scoring.
NATIONAL_AVG_EFF = 105.0
