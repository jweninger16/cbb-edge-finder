"""
ELO rating engine + KenPom loader.

Improvements over v1:
  • Season-boundary ELO regression (handles roster turnover)
  • Margin-weighted recent form (not just W/L)
  • Last-game tracking for rest-day calculations
  • Full KenPom data (O, D, tempo) — not just efficiency margin

Public API:
    build_elo_model() → ModelData (named tuple)
"""

from datetime import timedelta
from typing import NamedTuple

import numpy as np
import pandas as pd

from config import (
    COMBINED_CSV,
    FORM_LOOKBACK_DAYS,
    K_FACTOR,
    KENPOM_CSV,
    MIN_FORM_GAMES,
    MIN_HCA_GAMES,
    RECENCY_DECAY,
    SEASON_REGRESS_FRACTION,
    SEASON_START_MONTH,
    STARTING_ELO,
)
from name_maps import KENPOM_CSV_HARMONIZE


class ModelData(NamedTuple):
    elo_ratings: dict          # team → current ELO
    game_counts: dict          # team → total games played
    hca_dict: dict             # team → home-court advantage (points)
    form_dict: dict            # team → margin-weighted recent form
    kenpom_dict: dict          # team → {adj_em, adj_o, adj_d, adj_t}
    last_game_dict: dict       # team → last game date (pd.Timestamp)


# ── ELO helpers ──────────────────────────────────────────────────────────────

def _expected_score(elo_a: float, elo_b: float) -> float:
    return 1.0 / (1.0 + 10.0 ** ((elo_b - elo_a) / 400.0))


def _detect_season_boundary(prev_date: pd.Timestamp, curr_date: pd.Timestamp) -> bool:
    """True if we've crossed into a new season (Nov start)."""
    if prev_date is None:
        return False
    # New season = crossed a November boundary with a big gap
    gap_days = (curr_date - prev_date).days
    if gap_days > 90 and curr_date.month >= SEASON_START_MONTH:
        return True
    # Also detect: previous game was March/April, current is November+
    if prev_date.month <= 4 and curr_date.month >= SEASON_START_MONTH:
        return True
    return False


def _regress_elo(elo_ratings: dict) -> None:
    """Regress all ELO ratings toward the mean between seasons."""
    for team in elo_ratings:
        elo_ratings[team] = (
            STARTING_ELO * SEASON_REGRESS_FRACTION
            + elo_ratings[team] * (1.0 - SEASON_REGRESS_FRACTION)
        )


# ── Main builder ─────────────────────────────────────────────────────────────

def build_elo_model() -> ModelData:
    # ── Load & clean ─────────────────────────────────────────────────────
    df = pd.read_csv(COMBINED_CSV, usecols=[
        "team", "date", "opponent", "team_score", "opp_score",
    ])
    df = df.dropna(subset=["team", "date"])
    df = df[df["team"] != "Team"]
    df["team_score"] = pd.to_numeric(df["team_score"], errors="coerce")
    df["opp_score"] = pd.to_numeric(df["opp_score"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna().sort_values("date").reset_index(drop=True)

    # ── ELO with season resets ───────────────────────────────────────────
    elo_ratings: dict[str, float] = {}
    game_counts: dict[str, int] = {}
    max_date = df["date"].max()
    prev_game_date: pd.Timestamp | None = None

    for row in df.itertuples(index=False):
        # Check for season boundary → regress ratings
        if _detect_season_boundary(prev_game_date, row.date):
            _regress_elo(elo_ratings)
        prev_game_date = row.date

        team, opp = row.team, row.opponent
        t_score, o_score = row.team_score, row.opp_score

        if t_score > o_score:
            winner, loser = team, opp
        else:
            winner, loser = opp, team

        margin = abs(t_score - o_score)
        w_elo = elo_ratings.setdefault(winner, STARTING_ELO)
        l_elo = elo_ratings.setdefault(loser, STARTING_ELO)

        expected_win = _expected_score(w_elo, l_elo)
        mov_mult = (margin ** 0.6) / 10.0
        days_ago = (max_date - row.date).days
        recency = np.exp(-RECENCY_DECAY * days_ago)

        change = K_FACTOR * mov_mult * (1.0 - expected_win) * recency
        elo_ratings[winner] = w_elo + change
        elo_ratings[loser] = l_elo - change

        game_counts[team] = game_counts.get(team, 0) + 1
        game_counts[opp] = game_counts.get(opp, 0) + 1

    # ── Home-court advantage ─────────────────────────────────────────────
    home_margins: dict[str, list[float]] = {}
    road_margins: dict[str, list[float]] = {}

    for row in df.itertuples(index=False):
        m = row.team_score - row.opp_score
        home_margins.setdefault(row.team, []).append(m)
        road_margins.setdefault(row.opponent, []).append(-m)

    hca_dict: dict[str, float] = {}
    for team in set(home_margins) & set(road_margins):
        hm, rm = home_margins[team], road_margins[team]
        if len(hm) >= MIN_HCA_GAMES and len(rm) >= MIN_HCA_GAMES:
            hca = (sum(hm) / len(hm)) - (sum(rm) / len(rm))
            if hca != 0.0:
                hca_dict[team] = hca

    # ── Margin-weighted recent form ──────────────────────────────────────
    # Instead of just win%, use average scoring margin over last N days.
    # Capped to ±25 per game to limit blowout noise.
    lookback = max_date - timedelta(days=FORM_LOOKBACK_DAYS)
    form_dict: dict[str, float] = {}

    for team in df["team"].unique():
        recent = df[(df["team"] == team) & (df["date"] >= lookback)]
        if len(recent) < MIN_FORM_GAMES:
            continue
        margins = (recent["team_score"] - recent["opp_score"]).clip(-25, 25)
        form_dict[team] = round(margins.mean(), 2)

    # ── Last game date (for rest-day calculations) ───────────────────────
    last_game_dict: dict[str, pd.Timestamp] = {}
    for row in df.itertuples(index=False):
        last_game_dict[row.team] = row.date
        last_game_dict[row.opponent] = row.date

    # ── KenPom data (full: O, D, tempo) ─────────────────────────────────
    kenpom_dict = _load_kenpom()

    return ModelData(
        elo_ratings=elo_ratings,
        game_counts=game_counts,
        hca_dict=hca_dict,
        form_dict=form_dict,
        kenpom_dict=kenpom_dict,
        last_game_dict=last_game_dict,
    )


def _load_kenpom() -> dict[str, dict]:
    """
    Load full KenPom data. Returns dict of:
        team → {"adj_em": float, "adj_o": float, "adj_d": float, "adj_t": float}
    """
    try:
        kp = pd.read_csv(KENPOM_CSV)
        kp.columns = ["team", "conf", "record", "adj_em", "adj_o", "adj_o_rank", "adj_d", "adj_t"]
        for col in ("adj_em", "adj_o", "adj_d", "adj_t"):
            kp[col] = pd.to_numeric(kp[col], errors="coerce")

        kp_dict: dict[str, dict] = {}
        for _, row in kp.iterrows():
            kp_dict[row["team"]] = {
                "adj_em": row["adj_em"],
                "adj_o": row["adj_o"],
                "adj_d": row["adj_d"],
                "adj_t": row["adj_t"],
            }

        # Add alternate-name aliases
        for alt, kp_name in KENPOM_CSV_HARMONIZE.items():
            if kp_name in kp_dict:
                kp_dict[alt] = kp_dict[kp_name]

        return kp_dict
    except (FileNotFoundError, pd.errors.EmptyDataError) as exc:
        print(f"KenPom data unavailable: {exc}")
        return {}
