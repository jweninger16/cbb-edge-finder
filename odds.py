"""
Fetch live odds from The Odds API and compute model-vs-Vegas edges.

Improvements over v1:
  • Ensemble model: blends KenPom + ELO instead of either/or
  • Tempo-aware KenPom spread (uses adj_o, adj_d, adj_t)
  • Fixed form adjustment sign (hot teams now correctly boost spread)
  • Rest-day / back-to-back adjustments
  • Robust sharp-money matching (multi-word, not single first-word)
"""

from datetime import date, datetime, timedelta, timezone

import dateutil.parser
import pytz
import requests

from config import (
    B2B_PENALTY,
    CONF_TOURNEY_END,
    CONF_TOURNEY_START,
    EDGE_HIGH,
    EDGE_MEDIUM,
    EDGE_MINIMUM,
    ELO_DIVISOR,
    ENSEMBLE_ELO_WEIGHT,
    ENSEMBLE_KENPOM_WEIGHT,
    FORM_WEIGHT,
    HCA_CAP,
    HCA_DEFAULT,
    HCA_FLOOR,
    LONG_REST_BONUS,
    MIN_GAMES,
    NATIONAL_AVG_EFF,
    NCAA_TOURNEY_END,
    NCAA_TOURNEY_START,
    ODDS_API_KEY,
    SHARP_BOOST,
    SHARP_THRESHOLD,
    SHORT_REST_PENALTY,
    STARTING_ELO,
)
from name_maps import kenpom_to_elo, odds_to_kenpom

_CENTRAL = pytz.timezone("US/Central")


def fetch_odds() -> list[dict]:
    """Return raw odds data from The Odds API."""
    url = "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": "spreads",
        "oddsFormat": "american",
    }
    resp = requests.get(url, params=params, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if not isinstance(data, list):
        raise ValueError(f"Odds API error: {data}")
    return data


def get_edges(
    elo_ratings: dict,
    game_counts: dict,
    hca_dict: dict,
    form_dict: dict,
    kenpom_dict: dict,
    date_filter: str = "All",
    sharp_data: dict | None = None,
    last_game_dict: dict | None = None,
) -> list[dict]:
    """
    Compare ensemble model spread to Vegas and return edges ≥ EDGE_MINIMUM pts.
    """
    if sharp_data is None:
        sharp_data = {}
    if last_game_dict is None:
        last_game_dict = {}

    try:
        odds_data = fetch_odds()
    except (requests.RequestException, ValueError) as exc:
        print(f"Could not fetch odds: {exc}")
        return []

    now_utc = datetime.now(timezone.utc)
    now_central = now_utc.astimezone(_CENTRAL)
    today_date = now_central.date()
    tomorrow_date = today_date + timedelta(days=1)

    is_neutral = _is_neutral_site(today_date)
    edges: list[dict] = []

    for game in odds_data:
        if not isinstance(game, dict):
            continue

        # ── Date filtering ───────────────────────────────────────────────
        try:
            game_dt = dateutil.parser.parse(game["commence_time"])
        except (KeyError, ValueError):
            continue

        hours_until = (game_dt - now_utc).total_seconds() / 3600
        game_date = game_dt.astimezone(_CENTRAL).date()

        if date_filter == "Today" and not (game_date == today_date and hours_until >= 0):
            continue
        if date_filter == "Tomorrow" and game_date != tomorrow_date:
            continue

        # ── Name translation ─────────────────────────────────────────────
        home_kp = odds_to_kenpom(game["home_team"])
        away_kp = odds_to_kenpom(game["away_team"])
        home_elo = kenpom_to_elo(home_kp)
        away_elo = kenpom_to_elo(away_kp)

        # ── Parse Vegas spread ───────────────────────────────────────────
        try:
            outcomes = game["bookmakers"][0]["markets"][0]["outcomes"]
        except (IndexError, KeyError):
            continue

        spread_dict = {odds_to_kenpom(o["name"]): o["point"] for o in outcomes}
        home_spread = spread_dict.get(home_kp)
        away_spread = spread_dict.get(away_kp)
        if home_spread is None or away_spread is None:
            continue

        # ── Minimum-games filter ─────────────────────────────────────────
        if game_counts.get(home_elo, 0) < MIN_GAMES or game_counts.get(away_elo, 0) < MIN_GAMES:
            continue

        # ── Model spread (ensemble) ──────────────────────────────────────
        raw_spread = _compute_ensemble_spread(
            home_kp, away_kp, home_elo, away_elo,
            kenpom_dict, elo_ratings,
        )

        # ── Adjustments ──────────────────────────────────────────────────
        # Home-court advantage (0 at neutral sites)
        hca_raw = 0.0 if is_neutral else hca_dict.get(home_elo, HCA_DEFAULT)
        hca = max(HCA_FLOOR, min(HCA_CAP, hca_raw))

        # Form: positive form_adj means home team is hotter → boost home spread
        # FIX: v1 had this subtracted (inverted). Now correctly added.
        home_form = form_dict.get(home_elo, 0)
        away_form = form_dict.get(away_elo, 0)
        form_adj = (home_form - away_form) / FORM_WEIGHT

        # Rest: compute fatigue differential (positive = home more rested)
        rest_adj = _rest_adjustment(home_elo, away_elo, game_date, last_game_dict)

        our_spread = raw_spread + hca + form_adj + rest_adj

        model_favors = away_elo if our_spread < 0 else home_elo
        model_margin = abs(our_spread)

        vegas_favors = home_elo if home_spread < 0 else away_elo
        vegas_margin = abs(home_spread) if home_spread < 0 else abs(away_spread)

        # ── Edge size ────────────────────────────────────────────────────
        if model_favors == vegas_favors:
            edge_size = abs(round(model_margin - vegas_margin, 1))
            note = ""
        else:
            edge_size = round(model_margin + vegas_margin, 1)
            note = " (UPSET ALERT)"

        # ── Sharp money indicator (display only, no spread adjustment) ───
        sharp_boost = _check_sharp(
            sharp_data, home_kp, away_kp, home_elo, away_elo, model_favors
        )
        if sharp_boost > 0:
            note += " ⚡SHARP"
        elif sharp_boost < 0:
            note += " ⚠️FADE"

        # ── Threshold filter ─────────────────────────────────────────────
        if edge_size >= EDGE_MINIMUM:
            # Convert game time to Central (cross-platform formatting)
            game_cst = game_dt.astimezone(_CENTRAL)
            hour = game_cst.hour % 12 or 12
            minute = game_cst.strftime("%M")
            ampm = "AM" if game_cst.hour < 12 else "PM"
            game_time_cst = f"{hour}:{minute} {ampm} CST"
            edges.append({
                "away": away_elo,
                "home": home_elo,
                "model_favors": model_favors,
                "model_margin": round(model_margin, 1),
                "vegas_favors": vegas_favors,
                "vegas_margin": round(vegas_margin, 1),
                "edge_size": edge_size,
                "note": note,
                "game_time": game_time_cst,
                "confidence": (
                    "HIGH" if edge_size >= EDGE_HIGH
                    else "MEDIUM" if edge_size >= EDGE_MEDIUM
                    else "LOW" if edge_size >= 3.0
                    else "LEAN"
                ),
            })

    return sorted(edges, key=lambda x: x["edge_size"], reverse=True)


# ── Spread computation ───────────────────────────────────────────────────────

def _compute_ensemble_spread(
    home_kp: str, away_kp: str,
    home_elo: str, away_elo: str,
    kenpom_dict: dict, elo_ratings: dict,
) -> float:
    """
    Blend KenPom and ELO into a single raw spread prediction.
    Positive = home favored.
    """
    kp_home = kenpom_dict.get(home_kp)
    kp_away = kenpom_dict.get(away_kp)

    elo_spread = (
        elo_ratings.get(home_elo, STARTING_ELO)
        - elo_ratings.get(away_elo, STARTING_ELO)
    ) / ELO_DIVISOR

    if kp_home is not None and kp_away is not None:
        kenpom_spread = _kenpom_spread(kp_home, kp_away)
        # Ensemble: weighted blend
        return (ENSEMBLE_KENPOM_WEIGHT * kenpom_spread
                + ENSEMBLE_ELO_WEIGHT * elo_spread)
    else:
        # No KenPom data → pure ELO fallback
        return elo_spread


def _kenpom_spread(home_kp: dict, away_kp: dict) -> float:
    """
    Tempo-aware KenPom spread using offensive/defensive matchups.

    Standard KenPom prediction:
      home_eff = home_adj_o × away_adj_d / natl_avg_eff   (per 100 possessions)
      away_eff = away_adj_o × home_adj_d / natl_avg_eff   (per 100 possessions)
      game_tempo = avg(home_adj_t, away_adj_t)             (possessions per game)
      spread = (home_eff - away_eff) × game_tempo / 100

    This captures matchup-specific dynamics (e.g. elite defense vs high-offense)
    that the simple em_diff approach misses.
    """
    h_o = home_kp["adj_o"]
    h_d = home_kp["adj_d"]
    h_t = home_kp["adj_t"]
    a_o = away_kp["adj_o"]
    a_d = away_kp["adj_d"]
    a_t = away_kp["adj_t"]

    # Check for missing data
    if any(x is None or x != x for x in (h_o, h_d, h_t, a_o, a_d, a_t)):
        em_diff = (home_kp.get("adj_em") or 0) - (away_kp.get("adj_em") or 0)
        return 0.8072 * em_diff

    avg_eff = NATIONAL_AVG_EFF
    game_tempo = (h_t + a_t) / 2.0

    # Expected offensive efficiency when these specific teams play
    home_off_eff = h_o * a_d / avg_eff   # per 100 possessions
    away_off_eff = a_o * h_d / avg_eff   # per 100 possessions

    # Scale to expected game possessions
    home_pts = home_off_eff * game_tempo / 100.0
    away_pts = away_off_eff * game_tempo / 100.0

    return home_pts - away_pts


# ── Rest / fatigue ───────────────────────────────────────────────────────────

def _rest_adjustment(
    home_elo: str, away_elo: str,
    game_date: date,
    last_game_dict: dict,
) -> float:
    """
    Return a spread adjustment based on rest differential.
    Positive = helps home team.
    """
    home_rest = _days_of_rest(home_elo, game_date, last_game_dict)
    away_rest = _days_of_rest(away_elo, game_date, last_game_dict)

    if home_rest is None or away_rest is None:
        return 0.0

    home_adj = _rest_value(home_rest)
    away_adj = _rest_value(away_rest)
    return home_adj - away_adj


def _days_of_rest(team: str, game_date: date, last_game_dict: dict) -> int | None:
    """Days since team's last game, or None if unknown."""
    last = last_game_dict.get(team)
    if last is None:
        return None
    try:
        return (game_date - last.date()).days
    except (AttributeError, TypeError):
        return None


def _rest_value(days: int) -> float:
    """Convert rest days to a point-spread adjustment for one team."""
    if days <= 1:
        return -B2B_PENALTY
    elif days == 2:
        return -SHORT_REST_PENALTY
    elif days >= 7:
        return LONG_REST_BONUS
    return 0.0


# ── Neutral site ─────────────────────────────────────────────────────────────

def _is_neutral_site(today: date) -> bool:
    return (
        CONF_TOURNEY_START <= today <= CONF_TOURNEY_END
        or NCAA_TOURNEY_START <= today <= NCAA_TOURNEY_END
    )


# ── Sharp money ──────────────────────────────────────────────────────────────

def _normalize_for_match(name: str) -> set[str]:
    """
    Extract meaningful words from a team name for fuzzy matching.
    Strips parenthetical qualifiers, splits on spaces AND underscores.
    """
    import re
    name = re.sub(r"\([A-Z]{2}\)", "", name)
    # Split on both spaces and underscores (Action Network keys use underscores)
    words = set(re.split(r"[\s_]+", name.lower()))
    words -= {"state", "st.", "st", "university", "of", "the", "college", ""}
    return words


def _check_sharp(
    sharp_data: dict,
    home_kp: str, away_kp: str,
    home_elo: str, away_elo: str,
    model_favors: str,
) -> float:
    """
    Improved sharp-money matching using multi-word overlap.
    Returns +SHARP_BOOST, 0, or -SHARP_BOOST.
    """
    home_words = _normalize_for_match(home_kp) | _normalize_for_match(home_elo)
    away_words = _normalize_for_match(away_kp) | _normalize_for_match(away_elo)

    for skey, sval in sharp_data.items():
        skey_words = _normalize_for_match(skey)
        # Require at least one word match from EACH team
        home_match = bool(home_words & skey_words)
        away_match = bool(away_words & skey_words)

        if home_match and away_match:
            if sval["away_bets"] is None or sval["home_bets"] is None:
                return 0.0

            away_sharp = (sval["away_money"] or 0) - (sval["away_bets"] or 0)
            home_sharp = (sval["home_money"] or 0) - (sval["home_bets"] or 0)

            if away_sharp >= SHARP_THRESHOLD:
                sharp_side = away_elo
            elif home_sharp >= SHARP_THRESHOLD:
                sharp_side = home_elo
            else:
                return 0.0

            return SHARP_BOOST if sharp_side == model_favors else -SHARP_BOOST

    return 0.0
