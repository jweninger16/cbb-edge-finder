"""
Post yesterday's results + today's (and upcoming) edges to Discord.

Features:
  • NCAA tournament mode: scans Thursday/Friday/Saturday/Sunday lookahead
  • Auto-logs picks when sent (no duplicates)
  • Confidence breakdown in morning recap (W-L by HIGH/MED/LOW/LEAN)
  • Deduplicates — won't send the same game twice in a day

Schedule:
  8:00 AM  — recap + early picks
  11:00 AM — new picks only (filters out 8 AM duplicates)

Run:  python discord_post.py
"""

import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import requests

# ── Your webhook URL (paste here or set env var) ─────────────────────────────
DISCORD_WEBHOOK_URL = os.environ.get(
    "DISCORD_WEBHOOK_URL",
    "PASTE_YOUR_WEBHOOK_URL_HERE",
)

# ── Sent-game tracking file ─────────────────────────────────────────────────
_SENT_FILE = Path(__file__).parent / "sent_today.json"

# ── Ensure imports work when run from any directory ──────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auto_settle import auto_settle_picks
from config import NCAA_TOURNEY_END, NCAA_TOURNEY_START
from elo_model import build_elo_model
from odds import get_edges
from sharp import get_sharp_data
from tracker import load_picks, save_picks


# ── Tournament detection ─────────────────────────────────────────────────────

def _is_ncaa_tournament() -> bool:
    """True if we're in the NCAA tournament window."""
    today = date.today()
    return NCAA_TOURNEY_START <= today <= NCAA_TOURNEY_END


# ── Sent-game tracking ───────────────────────────────────────────────────────

def _load_sent() -> set[str]:
    """Load game keys already sent today. Resets if it's a new day."""
    try:
        with open(_SENT_FILE, "r") as f:
            data = json.load(f)
        if data.get("date") != datetime.now().strftime("%Y-%m-%d"):
            return set()
        return set(data.get("games", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def _save_sent(game_keys: set[str]) -> None:
    """Save game keys sent today."""
    existing = _load_sent()
    merged = existing | game_keys
    with open(_SENT_FILE, "w") as f:
        json.dump({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "games": list(merged),
        }, f)


def _game_key(edge: dict) -> str:
    """Unique key for a game."""
    return f"{edge['away']}_{edge['home']}"


# ── Auto-log picks ──────────────────────────────────────────────────────────

def _auto_log_picks(edges: list[dict]) -> int:
    """
    Log edges as picks in the tracker. Skips duplicates.
    Returns number of newly logged picks.
    """
    if not edges:
        return 0

    picks = load_picks()
    existing_keys = {f"{p['away']}_{p['home']}" for p in picks}
    logged = 0

    for e in edges:
        key = _game_key(e)
        if key in existing_keys:
            continue  # Already logged — skip

        pick_team = get_edge_team(e)
        picks.append({
            "date": e.get("game_date", datetime.now().strftime("%Y-%m-%d")),
            "away": e["away"],
            "home": e["home"],
            "edge_team": pick_team,
            "model_margin": e["model_margin"],
            "vegas_margin": e["vegas_margin"],
            "vegas_favors": e["vegas_favors"],
            "edge_size": e["edge_size"],
            "confidence": e["confidence"],
            "bet_amount": 100,
            "result": None,
            "profit": None,
        })
        existing_keys.add(key)
        logged += 1

    if logged > 0:
        save_picks(picks)

    return logged


# ── Yesterday's recap ────────────────────────────────────────────────────────

def build_recap() -> str:
    """Auto-settle pending picks, then build a recap of yesterday's results."""
    just_settled = auto_settle_picks()

    picks = load_picks()
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    yesterdays_picks = [p for p in picks if p.get("date") == yesterday and p.get("result")]

    if not yesterdays_picks:
        return ""

    wins = sum(1 for p in yesterdays_picks if p["result"] == "W")
    losses = sum(1 for p in yesterdays_picks if p["result"] == "L")
    pushes = sum(1 for p in yesterdays_picks if p["result"] == "P")

    lines = []
    for p in yesterdays_picks:
        icon = {"W": "✅", "L": "❌", "P": "➖"}.get(p["result"], "❓")
        score_str = f" ({p['final_score']})" if p.get("final_score") else ""
        lines.append(
            f"{icon} {p['away']} @ {p['home']} → **{p['edge_team']}** "
            f"| {p['result']}{score_str}"
        )

    record = f"{wins}W-{losses}L"
    if pushes:
        record += f"-{pushes}P"

    header = (
        f"📊 **Yesterday's Results** ({record})\n"
        f"───────────────────────────"
    )

    return f"{header}\n" + "\n".join(lines) + "\n"


# ── Season record with confidence breakdown ──────────────────────────────────

def build_season_record() -> str:
    """Season summary with record broken down by confidence tier."""
    picks = load_picks()
    settled = [p for p in picks if p.get("result")]

    if len(settled) < 2:
        return ""

    wins = sum(1 for p in settled if p["result"] == "W")
    losses = sum(1 for p in settled if p["result"] == "L")

    lines = [f"📈 **Season: {wins}W-{losses}L**"]

    # Confidence breakdown
    tiers = ["HIGH", "MEDIUM", "LOW", "LEAN"]
    tier_lines = []
    for tier in tiers:
        tier_picks = [p for p in settled if p.get("confidence") == tier]
        if not tier_picks:
            continue
        tw = sum(1 for p in tier_picks if p["result"] == "W")
        tl = sum(1 for p in tier_picks if p["result"] == "L")
        tp = sum(1 for p in tier_picks if p["result"] == "P")
        total = tw + tl + tp
        pct = (tw / (tw + tl) * 100) if (tw + tl) > 0 else 0
        emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢", "LEAN": "⚪"}.get(tier, "")
        push_str = f"-{tp}P" if tp else ""
        tier_lines.append(f"{emoji} {tier}: {tw}W-{tl}L{push_str} ({pct:.0f}%)")

    if tier_lines:
        lines.append("  " + " | ".join(tier_lines))

    return "\n".join(lines)


# ── Today's edges ────────────────────────────────────────────────────────────

def get_edge_team(e: dict) -> str:
    """Determine which team the edge favors."""
    if e["model_favors"] != e["vegas_favors"]:
        return e["model_favors"]
    elif e["model_margin"] > e["vegas_margin"]:
        return e["model_favors"]
    else:
        return e["away"] if e["model_favors"] == e["home"] else e["home"]


def format_edge(e: dict) -> str:
    """Format a single edge into a Discord-friendly line."""
    pick = get_edge_team(e)
    conf_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢", "LEAN": "⚪"}.get(e["confidence"], "⚪")
    note = e["note"].strip()
    game_time = e.get("game_time", "")
    time_str = f" — {game_time}" if game_time else ""

    return (
        f"{conf_emoji} **{e['away']} @ {e['home']}**{time_str}\n"
        f"   Pick: **{pick}** | Edge: **{e['edge_size']} pts** ({e['confidence']})\n"
        f"   Model: {e['model_favors']} by {e['model_margin']} | "
        f"Vegas: {e['vegas_favors']} by {e['vegas_margin']}"
        f"{f' | {note}' if note else ''}"
    )


def _day_label(game_date_str: str) -> str:
    """
    Return a human-readable label for the game date.
    'today', 'tomorrow', or the day name like 'Thursday'.
    """
    try:
        game_date = date.fromisoformat(game_date_str)
    except (ValueError, TypeError):
        return "upcoming"

    today = date.today()
    diff = (game_date - today).days

    if diff == 0:
        return "today"
    elif diff == 1:
        return "tomorrow"
    else:
        return game_date.strftime("%A")  # "Thursday", "Friday", etc.


def build_edges_message(edges: list[dict], is_update: bool = False, day_label: str = "") -> str:
    """Build edges message, optionally labeled for a specific day."""
    date_str = datetime.now().strftime("%A, %B %d")

    if not edges:
        if is_update:
            return ""
        return f"🏀 **Today's Edges — {date_str}**\n\nNo edges found for today."

    if day_label and day_label != "today":
        title = f"Edges for {day_label.title()}'s games"
    elif is_update:
        title = f"New Edges — {date_str} (update)"
    else:
        title = f"Today's Edges — {date_str}"

    header = (
        f"🏀 **{title}**\n"
        f"Found **{len(edges)}** edge(s)!\n"
        f"───────────────────────────"
    )

    edge_lines = [format_edge(e) for e in edges]

    footer = (
        f"───────────────────────────\n"
        f"🔴 HIGH (7+) | 🟡 MED (5-7) | 🟢 LOW (3-5) | ⚪ LEAN (2-3)"
    )

    return f"{header}\n\n" + "\n\n".join(edge_lines) + f"\n\n{footer}"


# ── Discord sending ──────────────────────────────────────────────────────────

def send_to_discord(message: str) -> bool:
    """Send a message to Discord via webhook."""
    if "PASTE_YOUR" in DISCORD_WEBHOOK_URL:
        print("ERROR: Set your Discord webhook URL in discord_post.py or")
        print("       set the DISCORD_WEBHOOK_URL environment variable.")
        return False

    chunks = _split_message(message, 1900)

    for chunk in chunks:
        resp = requests.post(
            DISCORD_WEBHOOK_URL,
            json={"content": chunk},
            timeout=10,
        )
        if resp.status_code not in (200, 204):
            print(f"Discord webhook error: {resp.status_code} {resp.text}")
            return False

    return True


def _split_message(message: str, max_len: int) -> list[str]:
    """Split a message into chunks that fit Discord's limit."""
    if len(message) <= max_len:
        return [message]

    chunks = []
    lines = message.split("\n")
    current = ""

    for line in lines:
        if len(current) + len(line) + 1 > max_len:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}" if current else line

    if current:
        chunks.append(current)

    return chunks


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    print(f"[{datetime.now().strftime('%I:%M %p')}] CBB Edge Finder — Discord Post")

    # ── Part 1: Yesterday's recap ────────────────────────────────────────
    already_sent = _load_sent()
    is_update = len(already_sent) > 0

    if not is_update:
        print("Settling pending picks...")
        recap = build_recap()
        if recap:
            print("Posting yesterday's recap...")
            send_to_discord(recap)
        else:
            print("No settled picks from yesterday.")

    # ── Part 2: Fetch edges ──────────────────────────────────────────────
    print("Building model...")
    model = build_elo_model()

    print("Fetching odds and sharp data...")
    sharp_data = get_sharp_data()

    is_tourney = _is_ncaa_tournament()

    # During NCAA tournament: fetch ALL available games (multi-day lookahead)
    # Regular season: fetch Today only
    date_filter = "All" if is_tourney else "Today"

    all_edges = get_edges(
        model.elo_ratings,
        model.game_counts,
        model.hca_dict,
        model.form_dict,
        model.kenpom_dict,
        date_filter=date_filter,
        sharp_data=sharp_data,
        last_game_dict=model.last_game_dict,
    )

    # Filter out already-sent games
    new_edges = [e for e in all_edges if _game_key(e) not in already_sent]

    if is_update:
        print(f"Found {len(all_edges)} total, {len(new_edges)} new since last post.")
    else:
        print(f"Found {len(new_edges)} edge(s).")

    if not new_edges:
        print("No new edges to post.")
        # Still post season record on first run
        if not is_update:
            season = build_season_record()
            if season:
                send_to_discord(season)
        return

    # ── Part 3: Post edges (grouped by day during tournament) ────────────
    if is_tourney:
        # Group edges by game date
        from collections import defaultdict
        day_groups = defaultdict(list)
        for e in new_edges:
            gd = e.get("game_date", date.today().isoformat())
            day_groups[gd].append(e)

        # Sort days chronologically
        sorted_days = sorted(day_groups.keys())
        all_posted_keys = set()

        for game_day in sorted_days:
            day_edges = day_groups[game_day]
            label = _day_label(game_day)

            print(f"Posting {len(day_edges)} edge(s) for {label} ({game_day})...")
            msg = build_edges_message(day_edges, is_update=is_update, day_label=label)

            if msg:
                if send_to_discord(msg):
                    all_posted_keys |= {_game_key(e) for e in day_edges}
                    # Auto-log picks
                    logged = _auto_log_picks(day_edges)
                    if logged:
                        print(f"  Auto-logged {logged} pick(s)")

        # Save all sent keys
        if all_posted_keys:
            _save_sent(all_posted_keys)

    else:
        # Regular season: single message
        msg = build_edges_message(new_edges, is_update=is_update)

        if msg:
            season = build_season_record()
            if season:
                msg += f"\n\n{season}"

            print("Posting to Discord...")
            if send_to_discord(msg):
                print("Posted successfully!")
                _save_sent({_game_key(e) for e in new_edges})
                # Auto-log picks
                logged = _auto_log_picks(new_edges)
                if logged:
                    print(f"Auto-logged {logged} pick(s)")
            else:
                print("Failed to post.")
                sys.exit(1)

    # ── Part 4: Season record (tournament mode — post after all days) ────
    if is_tourney:
        season = build_season_record()
        if season:
            send_to_discord(season)

    print("Done!")


if __name__ == "__main__":
    main()
