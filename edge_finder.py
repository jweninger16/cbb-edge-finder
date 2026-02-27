
import streamlit as st
import pandas as pd
import glob
import os
import requests
import json
from datetime import datetime

ODDS_API_KEY = "c2cabc199688380f72d916b3761d6d05"
DATA_FOLDER = r"C:\Users\jww9t\OneDrive\Desktop\Basketball Scores 21-25"
TRACKER_FILE = os.path.join(DATA_FOLDER, "pick_tracker.json")
STARTING_ELO = 1500
K_FACTOR = 20

name_map = {
    "Alabama Crimson Tide": "Alabama",
    "Arizona Wildcats": "Arizona",
    "Arizona St Sun Devils": "Arizona State",
    "Arkansas Razorbacks": "Arkansas",
    "Auburn Tigers": "Auburn",
    "Baylor Bears": "Baylor",
    "Boston College Eagles": "Boston College",
    "Brown Bears": "Brown",
    "California Golden Bears": "California",
    "Canisius Golden Griffins": "Canisius",
    "Cincinnati Bearcats": "Cincinnati",
    "Coastal Carolina Chanticleers": "Coastal Carolina",
    "Colorado Buffaloes": "Colorado",
    "Columbia Lions": "Columbia",
    "Cornell Big Red": "Cornell",
    "Dartmouth Big Green": "Dartmouth",
    "Dayton Flyers": "Dayton",
    "Duke Blue Devils": "Duke",
    "Duquesne Dukes": "Duquesne",
    "Evansville Purple Aces": "Evansville",
    "Fairfield Stags": "Fairfield",
    "Florida Gators": "Florida",
    "Florida St Seminoles": "Florida State",
    "Fordham Rams": "Fordham",
    "Georgetown Hoyas": "Georgetown",
    "Georgia Bulldogs": "Georgia",
    "Georgia Southern Eagles": "Georgia Southern",
    "Georgia St Panthers": "Georgia State",
    "Georgia Tech Yellow Jackets": "Georgia Tech",
    "Grand Canyon Antelopes": "Grand Canyon",
    "GW Revolutionaries": "George Washington",
    "Harvard Crimson": "Harvard",
    "Houston Cougars": "Houston",
    "Illinois Fighting Illini": "Illinois",
    "Iona Gaels": "Iona",
    "Iowa Hawkeyes": "Iowa",
    "Iowa State Cyclones": "Iowa State",
    "James Madison Dukes": "James Madison",
    "Kansas Jayhawks": "Kansas",
    "Kansas St Wildcats": "Kansas State",
    "Kent State Golden Flashes": "Kent State",
    "Louisiana Ragin Cajuns": "Louisiana",
    "Manhattan Jaspers": "Manhattan",
    "Marshall Thundering Herd": "Marshall",
    "Merrimack Warriors": "Merrimack",
    "Miami Hurricanes": "Miami (FL)",
    "Miami (OH) RedHawks": "Miami (OH)",
    "Michigan Wolverines": "Michigan",
    "Michigan St Spartans": "Michigan State",
    "Mt. St. Marys Mountaineers": "Mount St. Mary's",
    "Nebraska Cornhuskers": "Nebraska",
    "NC State Wolfpack": "NC State",
    "Niagara Purple Eagles": "Niagara",
    "North Carolina Tar Heels": "North Carolina",
    "Northwestern Wildcats": "Northwestern",
    "Notre Dame Fighting Irish": "Notre Dame",
    "Ohio St Buckeyes": "Ohio State",
    "Oklahoma St Cowboys": "Oklahoma State",
    "Ole Miss Rebels": "Mississippi",
    "Old Dominion Monarchs": "Old Dominion",
    "Oregon Ducks": "Oregon",
    "Penn State Nittany Lions": "Penn State",
    "Pennsylvania Quakers": "Pennsylvania",
    "Pittsburgh Panthers": "Pittsburgh",
    "Princeton Tigers": "Princeton",
    "Purdue Boilermakers": "Purdue",
    "Quinnipiac Bobcats": "Quinnipiac",
    "Rhode Island Rams": "Rhode Island",
    "Rider Broncs": "Rider",
    "Sacred Heart Pioneers": "Sacred Heart",
    "Saint Josephs Hawks": "Saint Joseph's",
    "Saint Louis Billikens": "Saint Louis",
    "Saint Peters Peacocks": "Saint Peter's",
    "Seton Hall Pirates": "Seton Hall",
    "Siena Saints": "Siena",
    "South Alabama Jaguars": "South Alabama",
    "South Carolina Gamecocks": "South Carolina",
    "Southern Miss Golden Eagles": "Southern Miss",
    "St. Bonaventure Bonnies": "St. Bonaventure",
    "St. Johns Red Storm": "St. John's (NY)",
    "TCU Horned Frogs": "TCU",
    "Tennessee Volunteers": "Tennessee",
    "Texas A&M Aggies": "Texas A&M",
    "Texas Longhorns": "Texas",
    "Texas St Bobcats": "Texas State",
    "Texas Tech Red Raiders": "Texas Tech",
    "Troy Trojans": "Troy",
    "UCF Knights": "UCF",
    "UCLA Bruins": "UCLA",
    "UConn Huskies": "Connecticut",
    "UL Monroe Warhawks": "Louisiana-Monroe",
    "USC Trojans": "Southern California",
    "Utah Utes": "Utah",
    "Utah State Aggies": "Utah State",
    "Valparaiso Beacons": "Valparaiso",
    "VCU Rams": "VCU",
    "Villanova Wildcats": "Villanova",
    "Virginia Cavaliers": "Virginia",
    "Virginia Tech Hokies": "Virginia Tech",
    "Washington St Cougars": "Washington State",
    "Western Michigan Broncos": "Western Michigan",
    "Xavier Musketeers": "Xavier",
    "Yale Bulldogs": "Yale",
    "Appalachian St Mountaineers": "Appalachian State",
}

def translate_name(name):
    return name_map.get(name, name)

@st.cache_data
def build_elo_model():
    csv_path = "basketball_data.csv"
    combined = pd.read_csv(csv_path)
    combined.columns = ["_".join(col).strip() if isinstance(col, tuple) else col for col in combined.columns]
    df = combined[[
        "Unnamed: 1_level_0_Team",
        "Unnamed: 2_level_0_Date",
        "Unnamed: 5_level_0_Opp",
        "Unnamed: 6_level_0_Result",
        "Team_PTS",
        "Opponent_PTS"
    ]].copy()
    df.columns = ["team", "date", "opponent", "result", "team_score", "opp_score"]
    df = df.dropna(subset=["team", "date"])
    df = df[df["team"] != "Team"]
    df["team_score"] = pd.to_numeric(df["team_score"], errors="coerce")
    df["opp_score"] = pd.to_numeric(df["opp_score"], errors="coerce")
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna()
    df = df.sort_values("date").reset_index(drop=True)
    elo_ratings = {}
    game_counts = {}
    def get_elo(team):
        if team not in elo_ratings:
            elo_ratings[team] = STARTING_ELO
        return elo_ratings[team]
    def expected_score(elo_a, elo_b):
        return 1 / (1 + 10 ** ((elo_b - elo_a) / 400))
    for _, row in df.iterrows():
        if row["team_score"] > row["opp_score"]:
            winner, loser = row["team"], row["opponent"]
        else:
            winner, loser = row["opponent"], row["team"]
        margin = abs(row["team_score"] - row["opp_score"])
        winner_elo = get_elo(winner)
        loser_elo = get_elo(loser)
        expected_win = expected_score(winner_elo, loser_elo)
        mov_multiplier = (margin ** 0.6) / 10
        change = K_FACTOR * mov_multiplier * (1 - expected_win)
        elo_ratings[winner] = winner_elo + change
        elo_ratings[loser] = loser_elo - change
        for t in [row["team"], row["opponent"]]:
            game_counts[t] = game_counts.get(t, 0) + 1
    return elo_ratings, game_counts

def get_edges(elo_ratings, game_counts):
    url = "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": "spreads",
        "oddsFormat": "american"
    }
    response = requests.get(url, params=params)
    odds_data = response.json()
    edges = []
    for game in odds_data:
        home = translate_name(game["home_team"])
        away = translate_name(game["away_team"])
        try:
            outcomes = game["bookmakers"][0]["markets"][0]["outcomes"]
            spread_dict = {translate_name(o["name"]): o["point"] for o in outcomes}
            home_spread = spread_dict.get(home)
            away_spread = spread_dict.get(away)
            if home_spread is None or away_spread is None:
                continue
            home_games = game_counts.get(home, 0)
            away_games = game_counts.get(away, 0)
            if home_games < 20 or away_games < 20:
                continue
            # Our model spread: negative = home favored, positive = away favored
            our_spread = (elo_ratings.get(home, STARTING_ELO) - elo_ratings.get(away, STARTING_ELO)) / 25
            model_favors = away if our_spread < 0 else home
            model_margin = abs(our_spread)
            # Vegas: whoever has negative spread is the favorite
            vegas_favors = home if home_spread < 0 else away
            vegas_margin = abs(home_spread) if home_spread < 0 else abs(away_spread)
            # Calculate edge
            if model_favors == vegas_favors:
                edge_size = abs(round(model_margin - vegas_margin, 1))
                note = ""
            else:
                edge_size = round(model_margin + vegas_margin, 1)
                note = " (UPSET ALERT)"
            if edge_size >= 3:
                edges.append({
                    "away": away,
                    "home": home,
                    "model_favors": model_favors,
                    "model_margin": round(model_margin, 1),
                    "vegas_favors": vegas_favors,
                    "vegas_margin": round(vegas_margin, 1),
                    "edge_size": edge_size,
                    "note": note,
                    "confidence": "HIGH" if edge_size >= 7 else "MEDIUM" if edge_size >= 5 else "LOW"
                })
        except:
            continue
    return sorted(edges, key=lambda x: x["edge_size"], reverse=True)

def load_picks():
    if os.path.exists(TRACKER_FILE):
        with open(TRACKER_FILE, "r") as f:
            return json.load(f)
    return []

def save_picks(picks):
    with open(TRACKER_FILE, "w") as f:
        json.dump(picks, f, indent=2)

st.set_page_config(page_title="CBB Edge Finder", page_icon="\U0001f3c0", layout="wide")
st.title("\U0001f3c0 College Basketball Edge Finder")
st.caption(f"Last updated: {datetime.now().strftime('%B %d, %Y %I:%M %p')}")

with st.spinner("Building ELO model..."):
    elo_ratings, game_counts = build_elo_model()

tab1, tab2, tab3 = st.tabs(["Tonights Edges", "Pick Tracker", "ELO Rankings"])

with tab1:
    st.subheader("Tonights Edges")
    if st.button("Refresh Odds"):
        st.cache_data.clear()
    with st.spinner("Fetching live odds..."):
        edges = get_edges(elo_ratings, game_counts)
    if not edges:
        st.info("No edges found tonight or no games available.")
    else:
        st.success(f"Found {len(edges)} edges tonight!")
        for e in edges:
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 2])
                with col1:
                    st.markdown(f"**{e['away']} @ {e['home']}**")
                    st.caption(f"{e['confidence']}{e['note']} | Edge: {e['edge_size']} pts")
                with col2:
                    st.metric("Model Favors", f"{e['model_favors']} by {e['model_margin']}")
                with col3:
                    st.metric("Vegas Favors", f"{e['vegas_favors']} by {e['vegas_margin']}")
                if st.button(f"Log Pick: {e['model_favors']}", key=f"log_{e['away']}_{e['home']}"):
                    picks = load_picks()
                    picks.append({
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "away": e["away"],
                        "home": e["home"],
                        "edge_team": e["model_favors"],
                        "model_margin": e["model_margin"],
                        "vegas_margin": e["vegas_margin"],
                        "vegas_favors": e["vegas_favors"],
                        "edge_size": e["edge_size"],
                        "bet_amount": 100,
                        "result": None,
                        "profit": None
                    })
                    save_picks(picks)
                    st.success("Pick logged!")
                st.divider()

with tab2:
    st.subheader("Pick Tracker")
    picks = load_picks()
    settled = [p for p in picks if p["result"] is not None]
    pending = [p for p in picks if p["result"] is None]
    wins = len([p for p in settled if p["result"] == "W"])
    losses = len([p for p in settled if p["result"] == "L"])
    total_profit = sum(p["profit"] for p in settled) if settled else 0
    win_pct = (wins / len(settled) * 100) if settled else 0
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Record", f"{wins}W - {losses}L")
    col2.metric("Win %", f"{round(win_pct, 1)}%")
    col3.metric("Total P&L", f"${round(total_profit, 2)}")
    col4.metric("Pending", len(pending))
    if pending:
        st.subheader("Settle Pending Picks")
        for p in pending:
            with st.expander(f"{p['date']} | {p['away']} @ {p['home']} -> {p['edge_team']}"):
                margin = st.number_input(
                    "Final margin (positive = home won, negative = away won)",
                    key=f"margin_{p['away']}_{p['home']}",
                    value=0
                )
                if st.button("Settle", key=f"settle_{p['away']}_{p['home']}"):
                    vegas_spread = -p["vegas_margin"] if p["vegas_favors"] == p["home"] else p["vegas_margin"]
                    if p["edge_team"] == p["home"]:
                        covered = margin > vegas_spread
                    else:
                        covered = margin < vegas_spread
                    p["result"] = "W" if covered else "L"
                    p["profit"] = p["bet_amount"] * 0.91 if covered else -p["bet_amount"]
                    save_picks(picks)
                    st.success(f"{'WIN' if covered else 'LOSS'} recorded!")
                    st.rerun()
    if settled:
        st.subheader("Settled Picks")
        st.dataframe(pd.DataFrame(settled)[[
            "date", "away", "home", "edge_team", "result", "profit"
        ]])

with tab3:
    st.subheader("Current ELO Rankings")
    ratings_df = pd.DataFrame(
        list(elo_ratings.items()), columns=["Team", "ELO"]
    ).sort_values("ELO", ascending=False).reset_index(drop=True)
    ratings_df.index += 1
    ratings_df["ELO"] = ratings_df["ELO"].round(1)
    st.dataframe(ratings_df, use_container_width=True)
