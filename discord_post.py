"""
Post yesterday's results + today's edges to Discord via webhook.

Recommended schedule:
  8:00 AM  — early picks (recap + whatever lines are available)
  11:00 AM — new picks only (filters out anything already sent at 8 AM)

Tracks which games were already posted today in sent_today.json.
Resets automatically each new day.

Run via Task Scheduler or manually:  python discord_post.py

Setup:
  1. In Discord: Server Settings → Integrations → Webhooks → New Webhook
  2. Copy the webhook URL
  3. Paste it below or set the DISCORD_WEBHOOK_URL environment variable
"""

import json
import os
import sys
from datetime import datetime, timedelta
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
from elo_model import build_elo_model
from odds import get_edges
from sharp import get_sharp_data
from tracker import load_picks


# ── Sent-game tracking ───────────────────────────────────────────────────────

def _load_sent() -> set[str]:
    """Load game keys already sent today. Resets if it's a new day."""
    try:
        with open(_SENT_FILE, "r") as f:
            data = json.load(f)
        # Reset if it's a different day
        if data.get("date") != datetime.now().strftime("%Y-%m-%d"):
            return set()
        return set(data.get("games", []))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def _save_sent(game_keys: set[str]) -> None:
    """Save game keys sent today."""
    # Merge with any existing (in case another run happened)
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


def build_edges_message(edges: list[dict], is_update: bool = False) -> str:
    """Build today's edges message."""
    date_str = datetime.now().strftime("%A, %B %d")

    if not edges:
        if is_update:
            return ""  # Don't post "no new edges" for the update run
        return f"🏀 **Today's Edges — {date_str}**\n\nNo edges found for today."

    if is_update:
        header = (
            f"🏀 **New Edges — {date_str}** (update)\n"
            f"Found **{len(edges)}** new edge(s)!\n"
            f"───────────────────────────"
        )
    else:
        header = (
            f"🏀 **Today's Edges — {date_str}**\n"
            f"Found **{len(edges)}** edge(s) today!\n"
            f"───────────────────────────"
        )

    edge_lines = [format_edge(e) for e in edges]

    footer = (
        f"───────────────────────────\n"
        f"🔴 HIGH (7+) | 🟡 MED (5-7) | 🟢 LOW (3-5) | ⚪ LEAN (2-3)"
    )

    return f"{header}\n\n" + "\n\n".join(edge_lines) + f"\n\n{footer}"


# ── Season record ────────────────────────────────────────────────────────────

def build_season_record() -> str:
    """One-line season summary."""
    picks = load_picks()
    settled = [p for p in picks if p.get("result")]

    if len(settled) < 2:
        return ""

    wins = sum(1 for p in settled if p["result"] == "W")
    losses = sum(1 for p in settled if p["result"] == "L")

    return f"📈 **Season: {wins}W-{losses}L**"


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

    # Part 1: Yesterday's recap (auto-settles first)
    # Only post recap on the first run of the day
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

    # Part 2: Today's edges
    print("Building model...")
    model = build_elo_model()

    print("Fetching odds and sharp data...")
    sharp_data = get_sharp_data()
    all_edges = get_edges(
        model.elo_ratings,
        model.game_counts,
        model.hca_dict,
        model.form_dict,
        model.kenpom_dict,
        date_filter="Today",
        sharp_data=sharp_data,
        last_game_dict=model.last_game_dict,
    )

    # Filter out already-sent games
    new_edges = [e for e in all_edges if _game_key(e) not in already_sent]
    total_found = len(all_edges)
    new_count = len(new_edges)

    if is_update:
        print(f"Found {total_found} total edge(s), {new_count} new since last post.")
    else:
        print(f"Found {new_count} edge(s).")

    # Build and send message
    edges_msg = build_edges_message(new_edges, is_update=is_update)

    if edges_msg:
        season = build_season_record()
        if season:
            edges_msg += f"\n\n{season}"

        print("Posting to Discord...")
        if send_to_discord(edges_msg):
            print("Posted successfully!")
            # Save these games as sent
            new_keys = {_game_key(e) for e in new_edges}
            _save_sent(new_keys)
        else:
            print("Failed to post.")
            sys.exit(1)
    else:
        print("No new edges to post.")


if __name__ == "__main__":
    main()
