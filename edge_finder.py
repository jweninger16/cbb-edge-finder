
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
    # First try the full KenPom mapping
    kenpom_map = {
        "Abilene Christian Wildcats": "Abilene Christian",
        "Air Force Falcons": "Air Force",
        "Akron Zips": "Akron",
        "American Eagles": "American",
        "Arkansas St Red Wolves": "Arkansas St.",
        "Arkansas-Little Rock Trojans": "Little Rock",
        "Army Knights": "Army",
        "BYU Cougars": "BYU",
        "Ball State Cardinals": "Ball St.",
        "Boise State Broncos": "Boise St.",
        "Boston Univ. Terriers": "Boston University",
        "Bowling Green Falcons": "Bowling Green",
        "Buffalo Bulls": "Buffalo",
        "CSU Bakersfield Roadrunners": "Cal St. Bakersfield",
        "CSU Fullerton Titans": "Cal St. Fullerton",
        "CSU Northridge Matadors": "CSUN",
        "Cal Baptist Lancers": "Cal Baptist",
        "Cal Poly Mustangs": "Cal Poly",
        "Campbell Fighting Camels": "Campbell",
        "Central Arkansas Bears": "Central Arkansas",
        "Central Connecticut St Blue Devils": "Central Connecticut",
        "Central Michigan Chippewas": "Central Michigan",
        "Charleston Southern Buccaneers": "Charleston Southern",
        "Chattanooga Mocs": "Chattanooga",
        "Clemson Tigers": "Clemson",
        "Cleveland St Vikings": "Cleveland St.",
        "Colorado St Rams": "Colorado St.",
        "Creighton Bluejays": "Creighton",
        "Delaware Blue Hens": "Delaware",
        "Detroit Mercy Titans": "Detroit Mercy",
        "East Tennessee St Buccaneers": "East Tennessee St.",
        "Eastern Illinois Panthers": "Eastern Illinois",
        "Eastern Washington Eagles": "Eastern Washington",
        "Elon Phoenix": "Elon",
        "Florida Int'l Golden Panthers": "FIU",
        "Fort Wayne Mastodons": "Purdue Fort Wayne",
        "Fresno St Bulldogs": "Fresno St.",
        "Furman Paladins": "Furman",
        "George Mason Patriots": "George Mason",
        "Gonzaga Bulldogs": "Gonzaga",
        "Green Bay Phoenix": "Green Bay",
        "Hampton Pirates": "Hampton",
        "Hawai'i Rainbow Warriors": "Hawaii",
        "Hofstra Pride": "Hofstra",
        "Holy Cross Crusaders": "Holy Cross",
        "IUPUI Jaguars": "IU Indy",
        "Idaho State Bengals": "Idaho St.",
        "Idaho Vandals": "Idaho",
        "Incarnate Word Cardinals": "Incarnate Word",
        "Jacksonville St Gamecocks": "Jacksonville St.",
        "Kennesaw St Owls": "Kennesaw St.",
        "Kentucky Wildcats": "Kentucky",
        "LSU Tigers": "LSU",
        "Lafayette Leopards": "Lafayette",
        "Lamar Cardinals": "Lamar",
        "Liberty Flames": "Liberty",
        "Lindenwood Lions": "Lindenwood",
        "Long Beach St 49ers": "Long Beach St.",
        "Louisiana Ragin' Cajuns": "Louisiana",
        "Louisiana Tech Bulldogs": "Louisiana Tech",
        "Louisville Cardinals": "Louisville",
        "Loyola (Chi) Ramblers": "Loyola Chicago",
        "Loyola (MD) Greyhounds": "Loyola MD",
        "Loyola Marymount Lions": "Loyola Marymount",
        "Massachusetts Minutemen": "Massachusetts",
        "McNeese Cowboys": "McNeese",
        "Mercer Bears": "Mercer",
        "Mercyhurst Lakers": "Mercyhurst",
        "Middle Tennessee Blue Raiders": "Middle Tennessee",
        "Minnesota Golden Gophers": "Minnesota",
        "Mississippi St Bulldogs": "Mississippi St.",
        "Missouri St Bears": "Missouri St.",
        "Missouri Tigers": "Missouri",
        "Monmouth Hawks": "Monmouth",
        "Montana Grizzlies": "Montana",
        "Montana St Bobcats": "Montana St.",
        "N Colorado Bears": "Northern Colorado",
        "Nevada Wolf Pack": "Nevada",
        "New Mexico Lobos": "New Mexico",
        "New Mexico St Aggies": "New Mexico St.",
        "New Orleans Privateers": "New Orleans",
        "North Carolina A&T Aggies": "North Carolina A&T",
        "North Dakota Fighting Hawks": "North Dakota",
        "North Dakota St Bison": "North Dakota St.",
        "Northeastern Huskies": "Northeastern",
        "Northern Arizona Lumberjacks": "Northern Arizona",
        "Northern Illinois Huskies": "Northern Illinois",
        "Northern Kentucky Norse": "Northern Kentucky",
        "Oakland Golden Grizzlies": "Oakland",
        "Ohio Bobcats": "Ohio",
        "Oklahoma Sooners": "Oklahoma",
        "Omaha Mavericks": "Nebraska Omaha",
        "Oral Roberts Golden Eagles": "Oral Roberts",
        "Oregon St Beavers": "Oregon St.",
        "Pacific Tigers": "Pacific",
        "Pepperdine Waves": "Pepperdine",
        "Portland Pilots": "Portland",
        "Portland St Vikings": "Portland St.",
        "Providence Friars": "Providence",
        "Queens University Royals": "Queens",
        "Richmond Spiders": "Richmond",
        "Robert Morris Colonials": "Robert Morris",
        "SE Missouri St Redhawks": "Southeast Missouri",
        "SIU-Edwardsville Cougars": "SIUE",
        "SMU Mustangs": "SMU",
        "Sacramento St Hornets": "Sacramento St.",
        "Saint Joseph's Hawks": "Saint Joseph's",
        "Saint Mary's Gaels": "Saint Mary's",
        "Sam Houston St Bearkats": "Sam Houston St.",
        "Samford Bulldogs": "Samford",
        "San Diego St Aztecs": "San Diego St.",
        "San Diego Toreros": "San Diego",
        "San Francisco Dons": "San Francisco",
        "San Jose St Spartans": "San Jose St.",
        "Santa Clara Broncos": "Santa Clara",
        "Seattle Redhawks": "Seattle",
        "South Dakota Coyotes": "South Dakota",
        "South Dakota St Jackrabbits": "South Dakota St.",
        "Southern Indiana Screaming Eagles": "Southern Indiana",
        "Southern Utah Thunderbirds": "Southern Utah",
        "St. Francis (PA) Red Flash": "Saint Francis",
        "St. John's Red Storm": "St. John's",
        "St. Thomas (MN) Tommies": "St. Thomas",
        "Stanford Cardinal": "Stanford",
        "Stonehill Skyhawks": "Stonehill",
        "Stony Brook Seawolves": "Stony Brook",
        "Syracuse Orange": "Syracuse",
        "Tarleton State Texans": "Tarleton St.",
        "Tenn-Martin Skyhawks": "Tennessee Martin",
        "Tennessee St Tigers": "Tennessee St.",
        "Tennessee Tech Golden Eagles": "Tennessee Tech",
        "Texas State Bobcats": "Texas St.",
        "The Citadel Bulldogs": "The Citadel",
        "Toledo Rockets": "Toledo",
        "Towson Tigers": "Towson",
        "UC Irvine Anteaters": "UC Irvine",
        "UC Riverside Highlanders": "UC Riverside",
        "UC San Diego Tritons": "UC San Diego",
        "UC Santa Barbara Gauchos": "UC Santa Barbara",
        "UMBC Retrievers": "UMBC",
        "UMKC Kangaroos": "Kansas City",
        "UMass Lowell River Hawks": "UMass Lowell",
        "UNC Asheville Bulldogs": "UNC Asheville",
        "UNC Greensboro Spartans": "UNC Greensboro",
        "UNLV Rebels": "UNLV",
        "UTEP Miners": "UTEP",
        "Utah Tech Trailblazers": "Utah Tech",
        "Utah Valley Wolverines": "Utah Valley",
        "VMI Keydets": "VMI",
        "Vanderbilt Commodores": "Vanderbilt",
        "Wake Forest Demon Deacons": "Wake Forest",
        "Washington Huskies": "Washington",
        "Weber State Wildcats": "Weber St.",
        "West Virginia Mountaineers": "West Virginia",
        "Western Carolina Catamounts": "Western Carolina",
        "Western Illinois Leathernecks": "Western Illinois",
        "Western Kentucky Hilltoppers": "Western Kentucky",
        "William & Mary Tribe": "William & Mary",
        "Wisconsin Badgers": "Wisconsin",
        "Wofford Terriers": "Wofford",
        "Wright St Raiders": "Wright St.",
        "Wyoming Cowboys": "Wyoming",
        "Youngstown St Penguins": "Youngstown St.",
        "Alabama Crimson Tide": "Alabama",
        "Arizona Wildcats": "Arizona",
        "Arizona St Sun Devils": "Arizona St.",
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
        "Florida St Seminoles": "Florida St.",
        "Fordham Rams": "Fordham",
        "Georgetown Hoyas": "Georgetown",
        "Georgia Bulldogs": "Georgia",
        "Georgia Southern Eagles": "Georgia Southern",
        "Georgia St Panthers": "Georgia St.",
        "Georgia Tech Yellow Jackets": "Georgia Tech",
        "Grand Canyon Antelopes": "Grand Canyon",
        "GW Revolutionaries": "George Washington",
        "Harvard Crimson": "Harvard",
        "Houston Cougars": "Houston",
        "Illinois Fighting Illini": "Illinois",
        "Iona Gaels": "Iona",
        "Iowa Hawkeyes": "Iowa",
        "Iowa State Cyclones": "Iowa St.",
        "James Madison Dukes": "James Madison",
        "Kansas Jayhawks": "Kansas",
        "Kansas St Wildcats": "Kansas St.",
        "Kent State Golden Flashes": "Kent St.",
        "Manhattan Jaspers": "Manhattan",
        "Marshall Thundering Herd": "Marshall",
        "Merrimack Warriors": "Merrimack",
        "Miami Hurricanes": "Miami FL",
        "Miami (OH) RedHawks": "Miami OH",
        "Michigan Wolverines": "Michigan",
        "Michigan St Spartans": "Michigan St.",
        "Mt. St. Marys Mountaineers": "Mount St. Mary's",
        "Nebraska Cornhuskers": "Nebraska",
        "NC State Wolfpack": "N.C. State",
        "Niagara Purple Eagles": "Niagara",
        "North Carolina Tar Heels": "North Carolina",
        "Northwestern Wildcats": "Northwestern",
        "Notre Dame Fighting Irish": "Notre Dame",
        "Ohio St Buckeyes": "Ohio St.",
        "Oklahoma St Cowboys": "Oklahoma St.",
        "Ole Miss Rebels": "Mississippi",
        "Old Dominion Monarchs": "Old Dominion",
        "Oregon Ducks": "Oregon",
        "Penn State Nittany Lions": "Penn St.",
        "Pennsylvania Quakers": "Penn",
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
        "St. Johns Red Storm": "St. John's",
        "TCU Horned Frogs": "TCU",
        "Tennessee Volunteers": "Tennessee",
        "Texas A&M Aggies": "Texas A&M",
        "Texas Longhorns": "Texas",
        "Texas St Bobcats": "Texas St.",
        "Texas Tech Red Raiders": "Texas Tech",
        "Troy Trojans": "Troy",
        "UCF Knights": "UCF",
        "UCLA Bruins": "UCLA",
        "UConn Huskies": "Connecticut",
        "UL Monroe Warhawks": "Louisiana Monroe",
        "USC Trojans": "USC",
        "Utah Utes": "Utah",
        "Utah State Aggies": "Utah St.",
        "Valparaiso Beacons": "Valparaiso",
        "VCU Rams": "VCU",
        "Villanova Wildcats": "Villanova",
        "Virginia Cavaliers": "Virginia",
        "Virginia Tech Hokies": "Virginia Tech",
        "Washington St Cougars": "Washington St.",
        "Western Michigan Broncos": "Western Michigan",
        "Xavier Musketeers": "Xavier",
        "Yale Bulldogs": "Yale",
        "Appalachian St Mountaineers": "Appalachian St.",
        "San José St Spartans": "San Jose St.",
    }
    return kenpom_map.get(name, name)

@st.cache_data
def build_elo_model():
    # Use full path locally, relative path on Streamlit Cloud
    local_path = r"C:\Users\jww9t\OneDrive\Desktop\Basketball Scores 21-25\combined_basketball_data.csv"
    cloud_path = "basketball_data.csv"
    csv_path = local_path if os.path.exists(local_path) else cloud_path
    combined = pd.read_csv(csv_path)
    df = combined[["team", "date", "opponent", "result", "team_score", "opp_score"]].copy()
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
    import numpy as np
    max_date = df["date"].max()

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

        # Recency weight — recent games matter more
        days_ago = (max_date - row["date"]).days
        recency_weight = np.exp(-0.005 * days_ago)

        change = K_FACTOR * mov_multiplier * (1 - expected_win) * recency_weight
        elo_ratings[winner] = winner_elo + change
        elo_ratings[loser] = loser_elo - change
        for t in [row["team"], row["opponent"]]:
            game_counts[t] = game_counts.get(t, 0) + 1
    # Calculate home court advantage per team
    home_margin = {}
    road_margin = {}
    for _, row in df.iterrows():
        team = row['team']
        opp = row['opponent']
        margin = row['team_score'] - row['opp_score']
        home_margin[team] = home_margin.get(team, []) + [margin]
        road_margin[opp] = road_margin.get(opp, []) + [-margin]

    hca_dict = {}
    for team in set(home_margin.keys()) & set(road_margin.keys()):
        hm = sum(home_margin[team]) / len(home_margin[team])
        rm = sum(road_margin[team]) / len(road_margin[team])
        hca = hm - rm
        if hca != 0.0 and len(home_margin[team]) >= 10 and len(road_margin[team]) >= 10:
            hca_dict[team] = hca

    # Calculate recent form adjustment (last 30 days)
    from datetime import timedelta
    max_date = df["date"].max()
    lookback = max_date - timedelta(days=30)
    form_dict = {}

    for team in df["team"].unique():
        recent = df[
            (df["team"] == team) &
            (df["date"] >= lookback)
        ].copy()
        if len(recent) < 3:
            continue
        wins = len(recent[recent["team_score"] > recent["opp_score"]])
        total = len(recent)
        win_pct = wins / total
        form_dict[team] = round((win_pct - 0.5) * 30, 1)

    # Load KenPom data
    kenpom_path = r"C:\Users\jww9t\OneDrive\Desktop\Basketball Scores 21-25\kenpom.csv"
    kenpom_cloud = "kenpom.csv"
    kp_path = kenpom_path if os.path.exists(kenpom_path) else kenpom_cloud
    try:
        kenpom_raw = pd.read_csv(kp_path)
        kenpom_raw.columns = ['team', 'conf', 'record', 'adj_em', 'adj_o', 'adj_o_rank', 'adj_d', 'adj_t']
        kenpom_raw['adj_em'] = pd.to_numeric(kenpom_raw['adj_em'], errors='coerce')
        kenpom_dict = dict(zip(kenpom_raw['team'], kenpom_raw['adj_em']))
    except:
        kenpom_dict = {}

    return elo_ratings, game_counts, hca_dict, form_dict, kenpom_dict

def get_edges(elo_ratings, game_counts, hca_dict, form_dict, kenpom_dict, date_filter="All"):
    url = "https://api.the-odds-api.com/v4/sports/basketball_ncaab/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": "us",
        "markets": "spreads",
        "oddsFormat": "american"
    }
    response = requests.get(url, params=params)
    odds_data = response.json()
    from datetime import date, timedelta, timezone
    import dateutil.parser
    today = date.today()
    tomorrow = today + timedelta(days=1)

    edges = []
    for game in odds_data:
        # Filter by date
        try:
            game_date = dateutil.parser.parse(game["commence_time"]).date()
        except:
            game_date = None

        if date_filter == "Today" and game_date != today:
            continue
        if date_filter == "Tomorrow" and game_date != tomorrow:
            continue

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
            # ELO spread
            elo_spread = (elo_ratings.get(home, STARTING_ELO) - elo_ratings.get(away, STARTING_ELO)) / 25

            # KenPom spread
            kp_home = kenpom_dict.get(home, None)
            kp_away = kenpom_dict.get(away, None)
            if kp_home is not None and kp_away is not None:
                kp_spread = (kp_home - kp_away) / 11
                # Blend 50/50
                raw_spread = (elo_spread * 0.5) + (kp_spread * 0.5)
            else:
                raw_spread = elo_spread

            # Apply team-specific home court advantage
            DEFAULT_HCA = 3.03
            hca_adjustment = hca_dict.get(home, DEFAULT_HCA)

            # Apply recent form adjustment
            home_form = form_dict.get(home, 0)
            away_form = form_dict.get(away, 0)
            form_adjustment = (home_form - away_form) / 25

            our_spread = raw_spread + hca_adjustment - form_adjustment

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
    elo_ratings, game_counts, hca_dict, form_dict, kenpom_dict = build_elo_model()

tab1, tab2, tab3 = st.tabs(["Tonights Edges", "Pick Tracker", "ELO Rankings"])

with tab1:
    st.subheader("Tonights Edges")
    if st.button("Refresh Odds"):
        st.cache_data.clear()
    # Date filter
    from datetime import date, timedelta
    today = date.today()
    tomorrow = today + timedelta(days=1)
    date_filter = st.radio(
        "Show games for:",
        ["Today", "Tomorrow", "All"],
        horizontal=True
    )

    with st.spinner("Fetching live odds..."):
        edges = get_edges(elo_ratings, game_counts, hca_dict, form_dict, kenpom_dict, date_filter)
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
                if st.button(f"Log Pick: {e['model_favors'] if 'UPSET' in e.get('note', '') else (e['away'] if e['model_favors'] == e['home'] else e['home'])}", key=f"log_{e['away']}_{e['home']}"):
                    picks = load_picks()
                    picks.append({
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "away": e["away"],
                        "home": e["home"],
                        "edge_team": e["model_favors"] if "UPSET" in e.get("note", "") else (e["away"] if e["model_favors"] == e["home"] else e["home"]),
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
