"""
Fetch sharp-money splits from Action Network.

Fix from v1: removed abs() from sharp detection — negative sharp values
mean money is flowing AWAY from that team, not toward it.
"""

from datetime import datetime, timedelta, timezone

import requests

from config import SHARP_THRESHOLD

_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://www.actionnetwork.com/",
}
_TIMEOUT = 5
_BASE_URL = "https://api.actionnetwork.com/web/v1/scoreboard/ncaab"


def get_sharp_data() -> dict:
    """
    Returns a dict keyed by "{away}_{home}" with:
        away_bets, away_money, home_bets, home_money,
        sharp_team (str|None), sharp_diff (int)
    """
    sharp_dict: dict = {}

    for delta in (0, 1):
        date_str = (datetime.now(timezone.utc) + timedelta(days=delta)).strftime("%Y%m%d")
        url = f"{_BASE_URL}?period=game&bookIds=15&date={date_str}"

        try:
            resp = requests.get(url, headers=_HEADERS, timeout=_TIMEOUT)
            resp.raise_for_status()
            data = resp.json()
        except (requests.RequestException, ValueError):
            continue

        for game in data.get("games", []):
            odds_list = game.get("odds")
            if not odds_list:
                continue

            odds = odds_list[0]
            teams = {t["id"]: t["display_name"] for t in game["teams"]}
            home_name = teams.get(game["home_team_id"], "Home")
            away_name = teams.get(game["away_team_id"], "Away")

            away_bets = odds.get("spread_away_public") or 0
            away_money = odds.get("spread_away_money") or 0
            home_bets = odds.get("spread_home_public") or 0
            home_money = odds.get("spread_home_money") or 0

            if away_bets == 0 and home_bets == 0:
                continue

            # Positive sharp = more money% than bet% → smart money on that side
            away_sharp = away_money - away_bets
            home_sharp = home_money - home_bets

            sharp_team = None
            sharp_diff = 0
            # FIX: no abs() — only flag when money EXCEEDS bets (positive value)
            if away_sharp >= SHARP_THRESHOLD:
                sharp_team = away_name
                sharp_diff = away_sharp
            elif home_sharp >= SHARP_THRESHOLD:
                sharp_team = home_name
                sharp_diff = home_sharp

            key = f"{away_name}_{home_name}"
            sharp_dict[key] = {
                "away_bets": away_bets,
                "away_money": away_money,
                "home_bets": home_bets,
                "home_money": home_money,
                "sharp_team": sharp_team,
                "sharp_diff": sharp_diff,
            }

    return sharp_dict
