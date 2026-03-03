
import streamlit as st
import pandas as pd
import glob
import os
import tempfile
import requests
import json
from datetime import datetime

ODDS_API_KEY = "c2cabc199688380f72d916b3761d6d05"
DATA_FOLDER = r"C:\Users\jww9t\OneDrive\Desktop\Basketball Scores 21-25"
# Use local path if it exists, otherwise use a temp path for cloud
if os.path.exists(DATA_FOLDER):
    TRACKER_FILE = os.path.join(DATA_FOLDER, "pick_tracker.json")
else:
    TRACKER_FILE = os.path.join(tempfile.gettempdir(), "pick_tracker.json")
STARTING_ELO = 1500

# Load optimized parameters from file
import json as _json
_params_local = r"C:\Users\jww9t\OneDrive\Desktop\Basketball Scores 21-25\model_params.json"
_params_cloud = "model_params.json"
_params_path = _params_local if os.path.exists(_params_local) else _params_cloud
try:
    with open(_params_path, 'r') as _f:
        _p = _json.load(_f)
    K_FACTOR = _p['k_factor']
    RECENCY_DECAY = _p['recency_decay']
    ELO_DIVISOR = _p['elo_divisor']
    KENPOM_DIVISOR = _p['kenpom_divisor']
    KENPOM_WEIGHT = _p['kenpom_weight']
    HCA_DEFAULT = _p['hca_default']
    FORM_WEIGHT = _p['form_weight']
    print(f"Loaded optimized params (RMSE: {_p.get('validation_rmse', 'N/A')})")
except:
    K_FACTOR = 44.73
    RECENCY_DECAY = 0.006
    ELO_DIVISOR = 10.0
    KENPOM_DIVISOR = 5.0
    KENPOM_WEIGHT = 0.39
    HCA_DEFAULT = 3.94
    FORM_WEIGHT = 13.71
    print("Using default params")

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
        harmonize = {
            "Alabama State": "Alabama St.", "Alcorn State": "Alcorn St.",
            "Appalachian State": "Appalachian St.", "Arizona State": "Arizona St.",
            "Arkansas State": "Arkansas St.", "Ball State": "Ball St.",
            "Boise State": "Boise St.", "Cal State Bakersfield": "Cal St. Bakersfield",
            "Cal State Fullerton": "Cal St. Fullerton", "Cal State Northridge": "CSUN",
            "Central Connecticut State": "Central Connecticut", "Chicago State": "Chicago St.",
            "Cleveland State": "Cleveland St.", "Colorado State": "Colorado St.",
            "Coppin State": "Coppin St.", "Delaware State": "Delaware St.",
            "East Tennessee State": "East Tennessee St.", "Florida State": "Florida St.",
            "Fresno State": "Fresno St.", "Georgia State": "Georgia St.",
            "Grambling State": "Grambling St.", "Idaho State": "Idaho St.",
            "Illinois State": "Illinois St.", "Indiana State": "Indiana St.",
            "Iowa State": "Iowa St.", "Jackson State": "Jackson St.",
            "Jacksonville State": "Jacksonville St.", "Kansas State": "Kansas St.",
            "Kennesaw State": "Kennesaw St.", "Kent State": "Kent St.",
            "Long Beach State": "Long Beach St.", "Louisiana State": "LSU",
            "McNeese State": "McNeese", "Michigan State": "Michigan St.",
            "Mississippi State": "Mississippi St.", "Mississippi Valley State": "Mississippi Valley St.",
            "Missouri State": "Missouri St.", "Montana State": "Montana St.",
            "Morehead State": "Morehead St.", "Morgan State": "Morgan St.",
            "Murray State": "Murray St.", "NC State": "N.C. State",
            "New Mexico State": "New Mexico St.", "Nicholls State": "Nicholls",
            "Norfolk State": "Norfolk St.", "North Dakota State": "North Dakota St.",
            "Northwestern State": "Northwestern St.", "Ohio State": "Ohio St.",
            "Oklahoma State": "Oklahoma St.", "Oregon State": "Oregon St.",
            "Penn State": "Penn St.", "Portland State": "Portland St.",
            "Sacramento State": "Sacramento St.", "Sam Houston State": "Sam Houston St.",
            "San Diego State": "San Diego St.", "San Jose State": "San Jose St.",
            "South Carolina State": "South Carolina St.", "South Dakota State": "South Dakota St.",
            "Southeast Missouri State": "Southeast Missouri", "Southern Mississippi": "Southern Miss",
            "Tarleton State": "Tarleton St.", "Tennessee State": "Tennessee St.",
            "Texas State": "Texas St.", "Utah State": "Utah St.",
            "Washington State": "Washington St.", "Weber State": "Weber St.",
            "Wichita State": "Wichita St.", "Wright State": "Wright St.",
            "Youngstown State": "Youngstown St.", "Ole Miss": "Mississippi",
            "SIU Edwardsville": "SIUE", "Illinois-Chicago": "Illinois Chicago",
            "St. John's (NY)": "St. John's", "Miami (FL)": "Miami FL",
            "Miami (OH)": "Miami OH", "St. Mary's (CA)": "Saint Mary's",
            "Texas A&M-Corpus Christi": "Texas A&M Corpus Chris",
            "Louisiana-Monroe": "Louisiana Monroe",
            "Arkansas-Pine Bluff": "Arkansas Pine Bluff",
            "Texas-Rio Grande Valley": "UT Rio Grande Valley",
            "Albany (NY)": "Albany", "Brigham Young": "BYU",
            "UMass": "Massachusetts", "Gardner-Webb": "Gardner Webb",
            "North Carolina A&T": "North Carolina A&T",
            "College of Charleston": "Charleston",
        }
        for dataset_name, kenpom_name in harmonize.items():
            if kenpom_name in kenpom_dict:
                kenpom_dict[dataset_name] = kenpom_dict[kenpom_name]
    except:
        kenpom_dict = {}
    return elo_ratings, game_counts, hca_dict, form_dict, kenpom_dict

def get_sharp_data():
    sharp_dict = {}
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.actionnetwork.com/"}
    from datetime import datetime, timezone, timedelta
    for delta in [0, 1]:
        date = (datetime.now(timezone.utc) + timedelta(days=delta)).strftime("%Y%m%d")
        url = f"https://api.actionnetwork.com/web/v1/scoreboard/ncaab?period=game&bookIds=15&date={date}"
        try:
            r = requests.get(url, headers=headers, timeout=5)
            data = r.json()
            for game in data.get("games", []):
                if not game.get("odds"):
                    continue
                odds = game["odds"][0]
                teams = {t["id"]: t["display_name"] for t in game["teams"]}
                home_name = teams.get(game["home_team_id"], "Home")
                away_name = teams.get(game["away_team_id"], "Away")
                away_bets = odds.get("spread_away_public") or 0
                away_money = odds.get("spread_away_money") or 0
                home_bets = odds.get("spread_home_public") or 0
                home_money = odds.get("spread_home_money") or 0
                if away_bets == 0 and home_bets == 0:
                    continue
                away_sharp = away_money - away_bets
                home_sharp = home_money - home_bets
                sharp_team = None
                sharp_diff = 0
                if abs(away_sharp) >= 15:
                    sharp_team = away_name
                    sharp_diff = abs(away_sharp)
                elif abs(home_sharp) >= 15:
                    sharp_team = home_name
                    sharp_diff = abs(home_sharp)
                key = f"{away_name}_{home_name}"
                sharp_dict[key] = {
                    "away_bets": away_bets, "away_money": away_money,
                    "home_bets": home_bets, "home_money": home_money,
                    "sharp_team": sharp_team, "sharp_diff": sharp_diff
                }
        except:
            continue
    return sharp_dict

def get_edges(elo_ratings, game_counts, hca_dict, form_dict, kenpom_dict, date_filter="All", sharp_data=None):
    if sharp_data is None:
        sharp_data = {}
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

        from datetime import datetime, timezone, timedelta
        game_dt = dateutil.parser.parse(game["commence_time"])
        now_utc = datetime.now(timezone.utc)
        hours_until = (game_dt - now_utc).total_seconds() / 3600

        if date_filter == "Today" and not (0 <= hours_until <= 24):
            continue
        if date_filter == "Tomorrow" and not (24 < hours_until <= 48):
            continue

        home_kenpom = translate_name(game["home_team"])
        away_kenpom = translate_name(game["away_team"])

        # ELO uses Sports Reference names (full "State" not "St.")
        elo_name_map = {
            "Iowa St.": "Iowa State", "Michigan St.": "Michigan State",
            "Florida St.": "Florida State", "Ohio St.": "Ohio State",
            "Penn St.": "Penn State", "Arizona St.": "Arizona State",
            "Kansas St.": "Kansas State", "Oklahoma St.": "Oklahoma State",
            "Oregon St.": "Oregon State", "Washington St.": "Washington State",
            "Colorado St.": "Colorado State", "Utah St.": "Utah State",
            "N.C. State": "NC State", "San Diego St.": "San Diego State",
            "Fresno St.": "Fresno State", "Boise St.": "Boise State",
            "Ball St.": "Ball State", "Kent St.": "Kent State",
            "Wright St.": "Wright State", "Wichita St.": "Wichita State",
            "Weber St.": "Weber State", "Tarleton St.": "Tarleton State",
            "Tennessee St.": "Tennessee State", "Texas St.": "Texas State",
            "Missouri St.": "Missouri State", "Montana St.": "Montana State",
            "Morehead St.": "Morehead State", "Morgan St.": "Morgan State",
            "Murray St.": "Murray State", "Norfolk St.": "Norfolk State",
            "North Dakota St.": "North Dakota State", "Northwestern St.": "Northwestern State",
            "New Mexico St.": "New Mexico State", "Mississippi St.": "Mississippi State",
            "Louisiana St.": "Louisiana State", "LSU": "Louisiana State",
            "Long Beach St.": "Long Beach State", "Jacksonville St.": "Jacksonville State",
            "Jackson St.": "Jackson State", "Idaho St.": "Idaho State",
            "Illinois St.": "Illinois State", "Indiana St.": "Indiana State",
            "Georgia St.": "Georgia State", "Grambling St.": "Grambling State",
            "Delaware St.": "Delaware State", "Coppin St.": "Coppin State",
            "Cleveland St.": "Cleveland State", "Chicago St.": "Chicago State",
            "Arkansas St.": "Arkansas State", "Alabama St.": "Alabama State",
            "Alcorn St.": "Alcorn State", "Appalachian St.": "Appalachian State",
            "Sacramento St.": "Sacramento State", "Sam Houston St.": "Sam Houston State",
            "South Carolina St.": "South Carolina State", "South Dakota St.": "South Dakota State",
            "Portland St.": "Portland State", "Mississippi Valley St.": "Mississippi Valley State",
            "Kennesaw St.": "Kennesaw State", "Iowa St.": "Iowa State",
            "SIUE": "SIU Edwardsville", "Illinois Chicago": "Illinois-Chicago",
            "Saint Mary's": "St. Mary's (CA)", "Miami FL": "Miami (FL)",
            "Miami OH": "Miami (OH)", "Mississippi": "Ole Miss",
            "Louisiana Monroe": "Louisiana-Monroe", "Southeast Missouri": "Southeast Missouri State",
            "Southern Miss": "Southern Mississippi", "Albany": "Albany (NY)",
            "BYU": "Brigham Young", "Massachusetts": "UMass",
            "Cal St. Bakersfield": "Cal State Bakersfield",
            "Cal St. Fullerton": "Cal State Fullerton",
            "CSUN": "Cal State Northridge",
        }
        home = elo_name_map.get(home_kenpom, home_kenpom)
        away = elo_name_map.get(away_kenpom, away_kenpom)
        try:
            outcomes = game["bookmakers"][0]["markets"][0]["outcomes"]
            spread_dict = {translate_name(o["name"]): o["point"] for o in outcomes}
            home_spread = spread_dict.get(home_kenpom)
            away_spread = spread_dict.get(away_kenpom)
            if home_spread is None or away_spread is None:
                continue
            home_games = game_counts.get(home, 0)
            away_games = game_counts.get(away, 0)
            if home_games < 20 or away_games < 20:
                continue
            # ELO spread
            elo_spread = (elo_ratings.get(home, STARTING_ELO) - elo_ratings.get(away, STARTING_ELO)) / ELO_DIVISOR

            # KenPom spread
            kp_home = kenpom_dict.get(home_kenpom, None)
            kp_away = kenpom_dict.get(away_kenpom, None)
            if kp_home is not None and kp_away is not None:
                kp_spread = (kp_home - kp_away) / KENPOM_DIVISOR
                raw_spread = (elo_spread * (1 - KENPOM_WEIGHT)) + (kp_spread * KENPOM_WEIGHT)
            else:
                raw_spread = elo_spread

            # Apply team-specific home court advantage
            hca_adjustment = hca_dict.get(home, HCA_DEFAULT)

            # Apply recent form adjustment
            home_form = form_dict.get(home, 0)
            away_form = form_dict.get(away, 0)
            form_adjustment = (home_form - away_form) / FORM_WEIGHT

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

            # Sharp money adjustment
            # Check if Action Network has data for this game
            sharp_boost = 0
            for skey, sval in sharp_data.items():
                home_short = home_kenpom.split()[-1].lower()
                away_short = away_kenpom.split()[-1].lower()
                if home_short in skey.lower() and away_short in skey.lower():
                    if sval['away_bets'] == 0:
                        break
                    # Figure out which side our model likes
                    bet_team = away_kenpom if model_favors == away else home_kenpom
                    bet_is_away = model_favors == away

                    # Sharp money %
                    bet_money = sval['away_money'] if bet_is_away else sval['home_money']
                    bet_bets = sval['away_bets'] if bet_is_away else sval['home_bets']
                    sharp_diff = bet_money - bet_bets

                    if sharp_diff >= 15:
                        # Sharp money agrees with our model - boost edge
                        sharp_boost = 2.0
                        note += " ⚡SHARP"
                    elif sharp_diff <= -15:
                        # Sharp money disagrees - reduce edge
                        sharp_boost = -2.0
                        note += " ⚠️FADE"
                    break

            edge_size = round(edge_size + sharp_boost, 1)
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

# Load sharp data
sharp_data = get_sharp_data()

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
        sharp_data = get_sharp_data()
        edges = get_edges(elo_ratings, game_counts, hca_dict, form_dict, kenpom_dict, date_filter, sharp_data)
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
                # Show sharp data if available
                for skey, sval in sharp_data.items():
                    home_short = e['home'].split()[-1].lower()
                    away_short = e['away'].split()[-1].lower()
                    if home_short in skey.lower() or away_short in skey.lower():
                        col_s1, col_s2 = st.columns(2)
                        with col_s1:
                            st.caption(f"🏈 Bets: {sval['away_bets']}% Away | {sval['home_bets']}% Home")
                        with col_s2:
                            st.caption(f"💰 Money: {sval['away_money']}% Away | {sval['home_money']}% Home")
                        if sval['sharp_team']:
                            st.warning(f"⚡ SHARP MONEY: {sval['sharp_team']} (+{sval['sharp_diff']}% money vs bets)")
                        break

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
        for i, p in enumerate(pending):
            with st.expander(f"{p['date']} | {p['away']} @ {p['home']} -> {p['edge_team']}"):
                margin = st.number_input(
                    "Final margin (positive = home won, negative = away won)",
                    key=f"margin_{i}_{p['away']}_{p['home']}",
                    value=0
                )
                if st.button("Settle", key=f"settle_{i}_{p['away']}_{p['home']}"):
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
