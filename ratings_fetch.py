"""
Auto-fetch current team efficiency ratings from Barttorvik (T-Rank).

Barttorvik publishes team data as direct CSV/JSON files that update
throughout the season. No API key or subscription needed.

Priority:
  1. Fetch fresh Barttorvik data (free, updates constantly)
  2. Fall back to local kenpom.csv if fetch fails

The returned dict uses KenPom-style names so the rest of the model
works without changes.
"""

import io
from datetime import datetime

import pandas as pd
import requests

from config import KENPOM_CSV
from name_maps import KENPOM_CSV_HARMONIZE

_TIMEOUT = 15
_YEAR = datetime.now().year if datetime.now().month >= 10 else datetime.now().year

# Barttorvik's direct data file — endorsed by Bart himself for bulk access
_TORVIK_CSV_URL = f"https://barttorvik.com/{_YEAR}_team_results.csv"
_TORVIK_JSON_URL = f"https://barttorvik.com/{_YEAR}_team_results.json"

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def fetch_ratings() -> dict[str, dict]:
    """
    Fetch fresh team ratings. Returns dict of:
        team_name → {"adj_em": float, "adj_o": float, "adj_d": float, "adj_t": float}

    Tries Barttorvik first, then falls back to local kenpom.csv.
    """
    # Try Barttorvik
    ratings = _fetch_barttorvik()
    if ratings:
        print(f"Loaded {len(ratings)} teams from Barttorvik (live data)")
        return ratings

    # Fall back to local KenPom CSV
    print("Barttorvik unavailable, falling back to local kenpom.csv")
    return _load_kenpom_csv()


def _fetch_barttorvik() -> dict[str, dict] | None:
    """Try to fetch current ratings from Barttorvik."""
    # Try JSON first (more structured)
    ratings = _try_barttorvik_json()
    if ratings:
        return ratings

    # Try CSV fallback
    return _try_barttorvik_csv()


def _try_barttorvik_json() -> dict[str, dict] | None:
    """Fetch from Barttorvik JSON endpoint."""
    try:
        resp = requests.get(_TORVIK_JSON_URL, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()

        if not isinstance(data, list) or len(data) < 100:
            return None

        ratings = {}
        for team_data in data:
            try:
                # Barttorvik JSON format: list of lists
                # Typical fields: team, conf, record, adj_oe, adj_de, barthag,
                #                  adj_tempo, wins, losses, ...
                # Field positions can vary — we look for the team name and numeric fields
                if isinstance(team_data, list):
                    name = str(team_data[0]).strip()
                    # Try to find adj_o, adj_d, adj_t from the data
                    # Common positions: adj_oe=3 or 4, adj_de=5 or 6, adj_t=7 or 8
                    # We need to be flexible here
                    floats = []
                    for val in team_data[1:]:
                        try:
                            floats.append(float(val))
                        except (ValueError, TypeError):
                            floats.append(None)

                    # Barttorvik typically has: conf, record, adj_oe, adj_de, barthag, adj_t
                    # After filtering, the first few floats are usually:
                    # [adj_oe, adj_de, barthag_or_other, adj_t, ...]
                    if len(floats) >= 6:
                        adj_o = floats[2] if floats[2] and 80 < floats[2] < 140 else None
                        adj_d = floats[3] if floats[3] and 80 < floats[3] < 140 else None
                        adj_t = floats[5] if floats[5] and 50 < floats[5] < 85 else None

                        if adj_o and adj_d:
                            adj_em = adj_o - adj_d
                            ratings[name] = {
                                "adj_em": round(adj_em, 2),
                                "adj_o": round(adj_o, 2),
                                "adj_d": round(adj_d, 2),
                                "adj_t": round(adj_t, 2) if adj_t else 67.5,
                            }
                elif isinstance(team_data, dict):
                    name = team_data.get("team", "").strip()
                    adj_o = _safe_float(team_data.get("adjoe") or team_data.get("adj_o"))
                    adj_d = _safe_float(team_data.get("adjde") or team_data.get("adj_d"))
                    adj_t = _safe_float(team_data.get("adjt") or team_data.get("adj_t"))

                    if name and adj_o and adj_d:
                        ratings[name] = {
                            "adj_em": round(adj_o - adj_d, 2),
                            "adj_o": round(adj_o, 2),
                            "adj_d": round(adj_d, 2),
                            "adj_t": round(adj_t, 2) if adj_t else 67.5,
                        }
            except (IndexError, TypeError, ValueError):
                continue

        if len(ratings) >= 100:
            # Add name harmonization aliases
            _add_aliases(ratings)
            return ratings

        return None

    except (requests.RequestException, ValueError) as e:
        print(f"Barttorvik JSON fetch failed: {e}")
        return None


def _try_barttorvik_csv() -> dict[str, dict] | None:
    """Fetch from Barttorvik CSV endpoint."""
    try:
        resp = requests.get(_TORVIK_CSV_URL, headers=_HEADERS, timeout=_TIMEOUT)
        resp.raise_for_status()

        # Parse CSV
        df = pd.read_csv(io.StringIO(resp.text))

        if len(df) < 100:
            return None

        # Find columns by name patterns
        cols = df.columns.tolist()
        team_col = _find_col(cols, ["team", "school", "name"])
        adj_o_col = _find_col(cols, ["adjoe", "adj_o", "adj_oe", "oe"])
        adj_d_col = _find_col(cols, ["adjde", "adj_d", "adj_de", "de"])
        adj_t_col = _find_col(cols, ["adjt", "adj_t", "tempo", "adj_tempo"])

        if not team_col or not adj_o_col or not adj_d_col:
            # Try positional fallback (Barttorvik CSV column order)
            # Typical: team, conf, g, w, l, adj_oe, adj_de, barthag, ...
            print("Using positional column mapping for Barttorvik CSV")
            df.columns = [f"col_{i}" for i in range(len(df.columns))]
            team_col = "col_0"
            # Find the first columns with efficiency-range values (80-140)
            for i in range(1, len(df.columns)):
                try:
                    vals = pd.to_numeric(df[f"col_{i}"], errors="coerce")
                    mean_val = vals.mean()
                    if 85 < mean_val < 130 and adj_o_col is None:
                        adj_o_col = f"col_{i}"
                    elif 85 < mean_val < 130 and adj_d_col is None:
                        adj_d_col = f"col_{i}"
                    elif 55 < mean_val < 80 and adj_t_col is None:
                        adj_t_col = f"col_{i}"
                except (ValueError, TypeError):
                    continue

        if not team_col or not adj_o_col or not adj_d_col:
            return None

        ratings = {}
        for _, row in df.iterrows():
            name = str(row[team_col]).strip()
            adj_o = _safe_float(row.get(adj_o_col))
            adj_d = _safe_float(row.get(adj_d_col))
            adj_t = _safe_float(row.get(adj_t_col)) if adj_t_col else 67.5

            if name and adj_o and adj_d:
                ratings[name] = {
                    "adj_em": round(adj_o - adj_d, 2),
                    "adj_o": round(adj_o, 2),
                    "adj_d": round(adj_d, 2),
                    "adj_t": round(adj_t, 2) if adj_t else 67.5,
                }

        if len(ratings) >= 100:
            _add_aliases(ratings)
            return ratings

        return None

    except (requests.RequestException, ValueError) as e:
        print(f"Barttorvik CSV fetch failed: {e}")
        return None


# ── KenPom CSV fallback ──────────────────────────────────────────────────────

def _load_kenpom_csv() -> dict[str, dict]:
    """Load from local kenpom.csv as fallback."""
    try:
        kp = pd.read_csv(KENPOM_CSV)
        kp.columns = ["team", "conf", "record", "adj_em", "adj_o", "adj_o_rank", "adj_d", "adj_t"]
        for col in ("adj_em", "adj_o", "adj_d", "adj_t"):
            kp[col] = pd.to_numeric(kp[col], errors="coerce")

        ratings: dict[str, dict] = {}
        for _, row in kp.iterrows():
            ratings[row["team"]] = {
                "adj_em": row["adj_em"],
                "adj_o": row["adj_o"],
                "adj_d": row["adj_d"],
                "adj_t": row["adj_t"],
            }

        _add_aliases(ratings)
        print(f"Loaded {len(ratings)} teams from local kenpom.csv")
        return ratings

    except (FileNotFoundError, pd.errors.EmptyDataError) as exc:
        print(f"KenPom CSV unavailable: {exc}")
        return {}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _add_aliases(ratings: dict) -> None:
    """Add name harmonization aliases so teams can be found by either name."""
    for alt, primary in KENPOM_CSV_HARMONIZE.items():
        if primary in ratings and alt not in ratings:
            ratings[alt] = ratings[primary]
        elif alt in ratings and primary not in ratings:
            ratings[primary] = ratings[alt]


def _safe_float(val) -> float | None:
    try:
        f = float(val)
        return f if f == f else None  # NaN check
    except (ValueError, TypeError):
        return None


def _find_col(columns: list[str], patterns: list[str]) -> str | None:
    """Find a column name matching any of the patterns (case-insensitive)."""
    for col in columns:
        for pat in patterns:
            if pat.lower() in col.lower():
                return col
    return None
