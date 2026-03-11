"""
Fetch completed game scores from The Odds API.

The same API key used for odds also provides scores.
Endpoint:  /v4/sports/basketball_ncaab/scores/
"""

import requests

from config import ODDS_API_KEY
from name_maps import kenpom_to_elo, odds_to_kenpom

_TIMEOUT = 10


def fetch_scores(days_from: int = 3) -> list[dict]:
    """
    Fetch recent completed game scores.

    Parameters
    ----------
    days_from : int
        How many days back to look (default 3, max 3 on free tier).

    Returns
    -------
    List of dicts, each with:
        away  : str   (ELO name)
        home  : str   (ELO name)
        away_score : int
        home_score : int
        completed  : bool
    """
    url = "https://api.the-odds-api.com/v4/sports/basketball_ncaab/scores/"
    params = {
        "apiKey": ODDS_API_KEY,
        "daysFrom": days_from,
    }

    try:
        resp = requests.get(url, params=params, timeout=_TIMEOUT)
        resp.raise_for_status()
        data = resp.json()
    except (requests.RequestException, ValueError) as exc:
        print(f"Could not fetch scores: {exc}")
        return []

    if not isinstance(data, list):
        print(f"Scores API returned unexpected data: {data}")
        return []

    results = []
    for game in data:
        if not game.get("completed", False):
            continue

        scores = game.get("scores")
        if not scores or len(scores) < 2:
            continue

        # Build a name→score lookup from the scores array
        score_map = {}
        for s in scores:
            name = s.get("name", "")
            try:
                score_map[name] = int(s["score"])
            except (KeyError, ValueError, TypeError):
                continue

        home_raw = game.get("home_team", "")
        away_raw = game.get("away_team", "")

        home_score = score_map.get(home_raw)
        away_score = score_map.get(away_raw)

        if home_score is None or away_score is None:
            continue

        # Translate to ELO names (same chain as odds.py)
        home_elo = kenpom_to_elo(odds_to_kenpom(home_raw))
        away_elo = kenpom_to_elo(odds_to_kenpom(away_raw))

        results.append({
            "away": away_elo,
            "home": home_elo,
            "away_score": away_score,
            "home_score": home_score,
            "completed": True,
        })

    return results
