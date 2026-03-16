"""
ELO rating engine + efficiency ratings loader.

Improvements over v1:
  • Season-boundary ELO regression (handles roster turnover)
  • Margin-weighted recent form (not just W/L)
  • Last-game tracking for rest-day calculations
  • Auto-fetches fresh Barttorvik ratings (falls back to KenPom CSV)

Public API:
    build_elo_model() → ModelData (named tuple)
"""

from datetime import timedelta
from typing import NamedTuple

import numpy as np
import pandas as pd

from config import (
    COMBINED_CSV,
    ELO_DIVISOR,
    ENSEMBLE_ELO_WEIGHT,
    ENSEMBLE_KENPOM_WEIGHT,
    FORM_LOOKBACK_DAYS,
    FORM_WEIGHT,
    HCA_CAP,
    HCA_DEFAULT,
    HCA_FLOOR,
    K_FACTOR,
    MIN_FORM_GAMES,
    MIN_HCA_GAMES,
    MIN_GAMES,
    NATIONAL_AVG_EFF,
    RECENCY_DECAY,
    SEASON_REGRESS_FRACTION,
    SEASON_START_MONTH,
    STARTING_ELO,
)


class ModelData(NamedTuple):
    elo_ratings: dict          # team → current ELO
    game_counts: dict          # team → total games played
    hca_dict: dict             # team → home-court advantage (points)
    form_dict: dict            # team → margin-weighted recent form
    kenpom_dict: dict          # team → {adj_em, adj_o, adj_d, adj_t}
    last_game_dict: dict       # team → last game date (pd.Timestamp)
    volatility_dict: dict      # team → std dev of scoring margins
    residual_dict: dict        # team → avg prediction error (positive = we overrate them)


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

    # ── Volatility (std dev of scoring margins) ──────────────────────────
    # High volatility = unpredictable team = more upset potential as underdog
    team_margins: dict[str, list[float]] = {}
    for row in df.itertuples(index=False):
        m = row.team_score - row.opp_score
        team_margins.setdefault(row.team, []).append(m)
        team_margins.setdefault(row.opponent, []).append(-m)

    volatility_dict: dict[str, float] = {}
    for team, margins in team_margins.items():
        if len(margins) >= 10:
            volatility_dict[team] = round(float(np.std(margins)), 2)

    # ── Efficiency ratings (auto-fetch from Barttorvik, fallback to KenPom CSV)
    from ratings_fetch import fetch_ratings
    kenpom_dict = fetch_ratings()

    # ── Prediction residuals (learning from mistakes) ────────────────────
    # Walk through last 10 games per team, predict each using current model,
    # and track how much we over/underestimate each team.
    # Positive residual = we overrate them (predicted them too strong).
    # This correction factor gets subtracted from future predictions.
    residual_dict = _compute_residuals(
        df, elo_ratings, game_counts, hca_dict, form_dict, kenpom_dict,
    )

    return ModelData(
        elo_ratings=elo_ratings,
        game_counts=game_counts,
        hca_dict=hca_dict,
        form_dict=form_dict,
        kenpom_dict=kenpom_dict,
        last_game_dict=last_game_dict,
        volatility_dict=volatility_dict,
        residual_dict=residual_dict,
    )


# ── Residual tracking (learning from mistakes) ──────────────────────────────

# How many recent games to look at per team
_RESIDUAL_WINDOW = 10
# How much of the measured residual to apply as correction (0-1)
# 0.5 = apply half the error as correction. Conservative to avoid overfit.
_RESIDUAL_CORRECTION_SCALE = 0.50


def _compute_residuals(
    df: pd.DataFrame,
    elo_ratings: dict,
    game_counts: dict,
    hca_dict: dict,
    form_dict: dict,
    kenpom_dict: dict,
) -> dict[str, float]:
    """
    For each team, look at their last N games, predict each using
    the current model, and compute the average prediction error.

    Returns dict of team → residual, where:
      positive = we overrate this team (predict them too strong)
      negative = we underrate this team (predict them too weak)

    The calling code should SUBTRACT this from future predictions.
    """
    max_date = df["date"].max()

    # Gather last N games per team (as home team in the data)
    team_residuals: dict[str, list[float]] = {}

    # Only look at recent games (last 45 days) to keep it current
    lookback = max_date - timedelta(days=45)
    recent = df[df["date"] >= lookback].copy()

    for row in recent.itertuples(index=False):
        team, opp = row.team, row.opponent

        # Skip teams with too few total games
        if game_counts.get(team, 0) < MIN_GAMES or game_counts.get(opp, 0) < MIN_GAMES:
            continue

        # ── Predict ──────────────────────────────────────────────────
        predicted = _predict_margin(team, opp, elo_ratings, hca_dict, form_dict, kenpom_dict)
        actual = row.team_score - row.opp_score

        # Residual: how much we OVERESTIMATED the home team (team)
        error = predicted - actual

        # Attribute half to each team:
        # If we predicted Home -8 but actual was Home -2, error = -6
        # → we overrated Home by ~3 pts AND underrated Away by ~3 pts
        team_residuals.setdefault(team, []).append(error / 2.0)
        team_residuals.setdefault(opp, []).append(-error / 2.0)

    # Average last N residuals per team
    residual_dict: dict[str, float] = {}
    for team, errors in team_residuals.items():
        # Take only the most recent N
        recent_errors = errors[-_RESIDUAL_WINDOW:]
        if len(recent_errors) >= 5:  # need at least 5 games
            avg_error = sum(recent_errors) / len(recent_errors)
            # Apply scale factor to avoid overcorrection
            correction = avg_error * _RESIDUAL_CORRECTION_SCALE
            # Only store meaningful corrections (> 0.5 pts)
            if abs(correction) >= 0.5:
                residual_dict[team] = round(correction, 2)

    if residual_dict:
        # Show top corrections
        sorted_r = sorted(residual_dict.items(), key=lambda x: x[1])
        print(f"Residual corrections for {len(residual_dict)} teams "
              f"(range: {sorted_r[0][1]:+.1f} to {sorted_r[-1][1]:+.1f})")

    return residual_dict


def _predict_margin(
    home: str, away: str,
    elo_ratings: dict, hca_dict: dict, form_dict: dict, kenpom_dict: dict,
) -> float:
    """
    Predict home margin using current model components.
    Same formula as odds.py but without rest/conf/upset adjustments
    (those are game-specific, not team-specific).
    """
    # ELO component
    elo_spread = (
        elo_ratings.get(home, STARTING_ELO) -
        elo_ratings.get(away, STARTING_ELO)
    ) / ELO_DIVISOR

    # Efficiency component
    kp_home = kenpom_dict.get(home)
    kp_away = kenpom_dict.get(away)

    if kp_home and kp_away and isinstance(kp_home, dict) and isinstance(kp_away, dict):
        h_o = kp_home.get("adj_o")
        h_d = kp_home.get("adj_d")
        h_t = kp_home.get("adj_t")
        a_o = kp_away.get("adj_o")
        a_d = kp_away.get("adj_d")
        a_t = kp_away.get("adj_t")

        if all(v is not None and v == v for v in (h_o, h_d, h_t, a_o, a_d, a_t)):
            avg_eff = NATIONAL_AVG_EFF
            game_tempo = (h_t + a_t) / 2.0
            home_off = h_o * a_d / avg_eff
            away_off = a_o * h_d / avg_eff
            kp_spread = (home_off * game_tempo / 100.0) - (away_off * game_tempo / 100.0)
            raw_spread = ENSEMBLE_KENPOM_WEIGHT * kp_spread + ENSEMBLE_ELO_WEIGHT * elo_spread
        else:
            raw_spread = elo_spread
    else:
        raw_spread = elo_spread

    # HCA
    hca_raw = hca_dict.get(home, HCA_DEFAULT)
    hca = max(HCA_FLOOR, min(HCA_CAP, hca_raw))

    # Form
    home_form = form_dict.get(home, 0)
    away_form = form_dict.get(away, 0)
    form_adj = (home_form - away_form) / FORM_WEIGHT

    return raw_spread + hca + form_adj

