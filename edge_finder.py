"""
🏀 College Basketball Edge Finder — Streamlit UI
Run with:  streamlit run app.py
"""

import re
from datetime import datetime

import pandas as pd
import streamlit as st

from auto_settle import auto_settle_picks
from elo_model import build_elo_model
from odds import get_edges
from sharp import get_sharp_data
from tracker import load_picks, save_picks

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(page_title="CBB Edge Finder", page_icon="🏀", layout="wide")
st.title("🏀 College Basketball Edge Finder")
st.caption(f"Last updated: {datetime.now().strftime('%B %d, %Y %I:%M %p')}")

# ── Build model (cached by Streamlit) ────────────────────────────────────────
@st.cache_data(show_spinner="Building ELO model…")
def _cached_model():
    return build_elo_model()


model = _cached_model()

# Unpack the named tuple for convenience
elo_ratings = model.elo_ratings
game_counts = model.game_counts
hca_dict = model.hca_dict
form_dict = model.form_dict
kenpom_dict = model.kenpom_dict
last_game_dict = model.last_game_dict
volatility_dict = model.volatility_dict


# ── Helper functions ─────────────────────────────────────────────────────────

def _normalize_for_match(name: str) -> set[str]:
    """Match the normalization logic used in odds.py for consistency."""
    name = re.sub(r"\([A-Z]{2}\)", "", name)
    words = set(re.split(r"[\s_]+", name.lower()))
    words -= {"state", "st.", "st", "university", "of", "the", "college", ""}
    return words


def _render_sharp_row(edge: dict, sharp_data: dict) -> None:
    """Show Action Network bet/money splits for a game."""
    home_words = _normalize_for_match(edge["home"])
    away_words = _normalize_for_match(edge["away"])

    for skey, sval in sharp_data.items():
        skey_words = _normalize_for_match(skey)
        if (home_words & skey_words) and (away_words & skey_words):
            c1, c2 = st.columns(2)
            with c1:
                st.caption(f"🏀 Bets: {sval['away_bets']}% Away | {sval['home_bets']}% Home")
            with c2:
                st.caption(f"💰 Money: {sval['away_money']}% Away | {sval['home_money']}% Home")
            if sval["sharp_team"]:
                st.warning(f"⚡ SHARP MONEY: {sval['sharp_team']} (+{sval['sharp_diff']}% money vs bets)")
            break


def _get_edge_team(edge: dict) -> str:
    """Determine which team the edge favors."""
    if edge["model_favors"] != edge["vegas_favors"]:
        return edge["model_favors"]
    elif edge["model_margin"] > edge["vegas_margin"]:
        return edge["model_favors"]
    else:
        return edge["away"] if edge["model_favors"] == edge["home"] else edge["home"]


def _log_pick(edge: dict) -> None:
    picks = load_picks()
    picks.append({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "away": edge["away"],
        "home": edge["home"],
        "edge_team": _get_edge_team(edge),
        "model_margin": edge["model_margin"],
        "vegas_margin": edge["vegas_margin"],
        "vegas_favors": edge["vegas_favors"],
        "edge_size": edge["edge_size"],
        "confidence": edge["confidence"],
        "bet_amount": 100,
        "result": None,
        "profit": None,
    })
    save_picks(picks)
    st.success("Pick logged!")


# ── Tabs ─────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs([
    "Tonight's Edges", "Pick Tracker", "Performance Dashboard", "ELO Rankings"
])

# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 1 — Tonight's Edges
# ═══════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("Tonight's Edges")

    if st.button("Refresh Odds"):
        st.cache_data.clear()

    date_filter = st.radio(
        "Show games for:",
        ["Today", "Tomorrow", "All"],
        horizontal=True,
    )

    with st.spinner("Fetching live odds…"):
        sharp_data = get_sharp_data()
        edges = get_edges(
            elo_ratings, game_counts, hca_dict, form_dict, kenpom_dict,
            date_filter, sharp_data, last_game_dict, volatility_dict,
        )

    if not edges:
        st.info("No edges found tonight or no games available.")
    else:
        st.success(f"Found {len(edges)} edges tonight!")

        for e in edges:
            with st.container():
                col1, col2, col3 = st.columns([3, 2, 2])
                with col1:
                    time_str = f" — {e['game_time']}" if e.get('game_time') else ""
                    st.markdown(f"**{e['away']} @ {e['home']}**{time_str}")
                    st.caption(f"{e['confidence']}{e['note']} | Edge: {e['edge_size']} pts")
                with col2:
                    st.metric("Model Favors", f"{e['model_favors']} by {e['model_margin']}")
                with col3:
                    st.metric("Vegas Favors", f"{e['vegas_favors']} by {e['vegas_margin']}")

                _render_sharp_row(e, sharp_data)

                btn_team = _get_edge_team(e)
                if st.button(f"Log Pick: {btn_team}", key=f"log_{e['away']}_{e['home']}"):
                    _log_pick(e)

                st.divider()


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 2 — Pick Tracker
# ═══════════════════════════════════════════════════════════════════════════════
with tab2:
    st.subheader("Pick Tracker")

    # ── Auto-settle on load ──────────────────────────────────────────────
    just_settled = auto_settle_picks()
    if just_settled:
        for p in just_settled:
            icon = "✅" if p["result"] == "W" else "❌" if p["result"] == "L" else "➖"
            st.toast(f"{icon} Auto-settled: {p['away']} @ {p['home']} → {p['result']} ({p.get('final_score', '?')})")
        st.success(f"Auto-settled {len(just_settled)} pick(s)!")

    picks = load_picks()
    settled = [p for p in picks if p["result"] is not None]
    pending = [p for p in picks if p["result"] is None]
    wins = sum(1 for p in settled if p["result"] == "W")
    losses = sum(1 for p in settled if p["result"] == "L")
    pushes = sum(1 for p in settled if p["result"] == "P")
    total_profit = sum(p["profit"] for p in settled) if settled else 0
    win_pct = (wins / len(settled) * 100) if settled else 0

    c1, c2, c3, c4 = st.columns(4)
    record_str = f"{wins}W - {losses}L" + (f" - {pushes}P" if pushes else "")
    c1.metric("Record", record_str)
    c2.metric("Win %", f"{round(win_pct, 1)}%")
    c3.metric("Total P&L", f"${round(total_profit, 2)}")
    c4.metric("Pending", len(pending))

    # ── Manual settle (fallback for games not found by API) ──────────────
    if pending:
        st.subheader("Pending Picks")
        st.caption("These will auto-settle once final scores are available (up to 3 days). "
                   "You can also settle manually below.")
        for i, p in enumerate(pending):
            with st.expander(f"{p['date']} | {p['away']} @ {p['home']} → {p['edge_team']}"):
                margin = st.number_input(
                    "Final margin (positive = home won, negative = away won)",
                    key=f"margin_{i}_{p['away']}_{p['home']}",
                    value=0,
                )
                if st.button("Settle Manually", key=f"settle_{i}_{p['away']}_{p['home']}"):
                    vegas_spread = -p["vegas_margin"] if p["vegas_favors"] == p["home"] else p["vegas_margin"]
                    ats_result = margin + vegas_spread
                    if ats_result == 0:
                        p["result"] = "P"
                        p["profit"] = 0.0
                    else:
                        if p["edge_team"] == p["home"]:
                            covered = ats_result > 0
                        else:
                            covered = ats_result < 0
                        p["result"] = "W" if covered else "L"
                        p["profit"] = p["bet_amount"] * 0.91 if covered else -p["bet_amount"]
                    save_picks(picks)
                    st.success(f"{p['result']} recorded!")
                    st.rerun()

    if settled:
        st.subheader("Settled Picks")
        df_settled = pd.DataFrame(settled)
        display_cols = ["date", "away", "home", "edge_team", "result", "profit"]
        if "final_score" in df_settled.columns:
            display_cols.insert(4, "final_score")
        st.dataframe(df_settled[[c for c in display_cols if c in df_settled.columns]])


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 3 — Performance Dashboard
# ═══════════════════════════════════════════════════════════════════════════════
with tab3:
    st.subheader("Performance Dashboard")
    picks = load_picks()
    settled = [p for p in picks if p["result"] is not None]

    if len(settled) < 3:
        st.info("Need at least 3 settled picks to show analytics. Keep logging and settling picks!")
    else:
        df_s = pd.DataFrame(settled)
        df_s["date"] = pd.to_datetime(df_s["date"])
        df_s = df_s.sort_values("date")

        # ── Headline metrics ─────────────────────────────────────────────
        total_wagered = df_s["bet_amount"].sum()
        total_profit = df_s["profit"].sum()
        roi = (total_profit / total_wagered * 100) if total_wagered > 0 else 0

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Total Picks", len(df_s))
        m2.metric("Total Wagered", f"${total_wagered:,.0f}")
        m3.metric("Net Profit", f"${total_profit:,.2f}")
        m4.metric("ROI", f"{roi:+.1f}%")

        st.divider()

        # ── Cumulative P&L chart ─────────────────────────────────────────
        st.subheader("Cumulative P&L Over Time")
        df_s["cumulative_pl"] = df_s["profit"].cumsum()
        chart_data = df_s[["date", "cumulative_pl"]].set_index("date")
        st.line_chart(chart_data, y="cumulative_pl", color="#2ecc71")

        st.divider()

        # ── ROI by confidence level ──────────────────────────────────────
        st.subheader("Performance by Confidence Level")
        if "confidence" in df_s.columns:
            conf_groups = df_s.groupby("confidence").agg(
                picks=("result", "count"),
                wins=("result", lambda x: (x == "W").sum()),
                profit=("profit", "sum"),
                wagered=("bet_amount", "sum"),
            ).reindex(["HIGH", "MEDIUM", "LOW"])

            conf_groups["win_pct"] = (conf_groups["wins"] / conf_groups["picks"] * 100).round(1)
            conf_groups["roi"] = (conf_groups["profit"] / conf_groups["wagered"] * 100).round(1)
            conf_groups = conf_groups.dropna()

            if not conf_groups.empty:
                col_a, col_b = st.columns(2)
                with col_a:
                    st.bar_chart(conf_groups["win_pct"], color="#3498db")
                    st.caption("Win Rate % by Confidence")
                with col_b:
                    st.bar_chart(conf_groups["roi"], color="#e74c3c")
                    st.caption("ROI % by Confidence")

                st.dataframe(
                    conf_groups[["picks", "wins", "win_pct", "profit", "roi"]].rename(columns={
                        "picks": "Picks", "wins": "Wins", "win_pct": "Win %",
                        "profit": "Profit", "roi": "ROI %",
                    }),
                    use_container_width=True,
                )
        else:
            st.caption("Confidence data not available for older picks.")

        st.divider()

        # ── ROI by edge size bucket ──────────────────────────────────────
        st.subheader("Performance by Edge Size")
        df_s["edge_bucket"] = pd.cut(
            df_s["edge_size"],
            bins=[0, 4, 5, 7, 10, 100],
            labels=["3-4", "4-5", "5-7", "7-10", "10+"],
            right=False,
        )
        edge_groups = df_s.groupby("edge_bucket", observed=True).agg(
            picks=("result", "count"),
            wins=("result", lambda x: (x == "W").sum()),
            profit=("profit", "sum"),
            wagered=("bet_amount", "sum"),
        )
        edge_groups["win_pct"] = (edge_groups["wins"] / edge_groups["picks"] * 100).round(1)
        edge_groups["roi"] = (edge_groups["profit"] / edge_groups["wagered"] * 100).round(1)

        if not edge_groups.empty:
            col_c, col_d = st.columns(2)
            with col_c:
                st.bar_chart(edge_groups["win_pct"], color="#9b59b6")
                st.caption("Win Rate % by Edge Size")
            with col_d:
                st.bar_chart(edge_groups["roi"], color="#f39c12")
                st.caption("ROI % by Edge Size")

            st.dataframe(
                edge_groups[["picks", "wins", "win_pct", "profit", "roi"]].rename(columns={
                    "picks": "Picks", "wins": "Wins", "win_pct": "Win %",
                    "profit": "Profit", "roi": "ROI %",
                }),
                use_container_width=True,
            )

        st.divider()

        # ── Monthly breakdown ────────────────────────────────────────────
        st.subheader("Monthly Breakdown")
        df_s["month"] = df_s["date"].dt.to_period("M").astype(str)
        monthly = df_s.groupby("month").agg(
            picks=("result", "count"),
            wins=("result", lambda x: (x == "W").sum()),
            profit=("profit", "sum"),
        )
        monthly["win_pct"] = (monthly["wins"] / monthly["picks"] * 100).round(1)

        if not monthly.empty:
            st.bar_chart(monthly["profit"], color="#1abc9c")
            st.caption("Net Profit by Month")
            st.dataframe(
                monthly[["picks", "wins", "win_pct", "profit"]].rename(columns={
                    "picks": "Picks", "wins": "Wins", "win_pct": "Win %", "profit": "Profit",
                }),
                use_container_width=True,
            )


# ═══════════════════════════════════════════════════════════════════════════════
#  TAB 4 — ELO Rankings
# ═══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.subheader("Current ELO Rankings")
    ratings_df = (
        pd.DataFrame(list(elo_ratings.items()), columns=["Team", "ELO"])
        .sort_values("ELO", ascending=False)
        .reset_index(drop=True)
    )
    ratings_df.index += 1
    ratings_df["ELO"] = ratings_df["ELO"].round(1)
    st.dataframe(ratings_df, use_container_width=True)
