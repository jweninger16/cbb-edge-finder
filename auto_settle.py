"""
Auto-settle pending picks by matching them against completed game scores.

Called on app startup. Fetches recent scores from The Odds API, matches
them to pending picks by team names, and settles wins/losses automatically.
"""

from scores import fetch_scores
from tracker import load_picks, save_picks


def auto_settle_picks() -> list[dict]:
    """
    Attempt to settle all pending picks using recent final scores.

    Returns
    -------
    List of picks that were just settled (for display to user).
    """
    picks = load_picks()
    pending = [p for p in picks if p["result"] is None]

    if not pending:
        return []

    scores = fetch_scores(days_from=3)
    if not scores:
        return []

    # Index scores by (away, home) for fast lookup
    score_lookup: dict[tuple[str, str], dict] = {}
    for s in scores:
        key = (s["away"], s["home"])
        score_lookup[key] = s

    just_settled = []

    for pick in pending:
        key = (pick["away"], pick["home"])
        game = score_lookup.get(key)

        if game is None:
            continue

        # Actual margin: positive = home won
        margin = game["home_score"] - game["away_score"]

        # Vegas spread from the home team's perspective
        # Home favorite by 5.5 → vegas_spread = -5.5 (they must overcome this)
        if pick["vegas_favors"] == pick["home"]:
            vegas_spread = -pick["vegas_margin"]
        else:
            vegas_spread = pick["vegas_margin"]

        # Against-the-spread result: positive = home covered, negative = away covered
        ats_result = margin + vegas_spread

        # Did the edge_team cover?
        if ats_result == 0:
            pick["result"] = "P"
            pick["profit"] = 0.0
        else:
            if pick["edge_team"] == pick["home"]:
                covered = ats_result > 0
            else:
                covered = ats_result < 0
            pick["result"] = "W" if covered else "L"
            pick["profit"] = pick["bet_amount"] * 0.91 if covered else -pick["bet_amount"]

        # Store the final score for reference
        pick["final_score"] = f"{game['away_score']}-{game['home_score']}"

        just_settled.append(pick)

    if just_settled:
        save_picks(picks)

    return just_settled
