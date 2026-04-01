import time
import streamlit as st
from prediction_helper import predict, TEAMS, BATTERS, BOWLERS, VENUES
from live_score import fetch_live_matches, fetch_match_scorecard, parse_live_data

st.set_page_config(page_title="Cricket Match Winner Prediction", page_icon="🏏", layout="wide")
st.title("🏏 IPL Match Winner Prediction")
st.markdown("Live 2nd-innings win probability using career stats, Bayesian shrinkage, "
            "in-match form, partnership context, next batter, remaining bowlers, and venue factors.")
st.divider()

# ── Live Score Integration ────────────────────────────────────────────────────
live_data = {}

API_KEY = "8466f49f-1334-4c8b-aab3-d4db2be92632"
CACHE_TTL = 120  # seconds — don't re-fetch within 2 minutes

with st.expander("📡 Fetch Live Match Data (Optional)", expanded=False):
    st.caption("Auto-fill match info from a live game using CricAPI. "
               "Data is cached for 2 minutes to save API credits (100/day limit).")

    if st.button("Fetch Live Matches"):
        # Check cache — skip API call if fresh data exists
        last_fetch = st.session_state.get("matches_fetched_at", 0)
        if time.time() - last_fetch < CACHE_TTL and "live_matches" in st.session_state:
            remaining = CACHE_TTL - int(time.time() - last_fetch)
            placeholder = st.empty()
            placeholder.info(f"Using cached match list. Refreshable in {remaining}s...")
            while remaining > 0:
                time.sleep(1)
                remaining -= 1
                placeholder.info(f"Using cached match list. Refreshable in {remaining}s...")
            placeholder.success("Cache expired! Click **Fetch Live Matches** again for fresh data.")
        else:
            with st.spinner("Fetching live matches..."):
                matches, err = fetch_live_matches(API_KEY)
            if err:
                st.error(f"API Error: {err}")
            elif not matches:
                st.warning("No live matches found.")
            else:
                # Filter to live IPL matches only (started + not ended)
                live_matches = [
                    m for m in matches
                    if ("ipl" in m.get("name", "").lower()
                        or "indian premier league" in m.get("name", "").lower())
                    and m.get("matchStarted", False)
                    and not m.get("matchEnded", False)
                ]
                if not live_matches:
                    st.warning("No live IPL matches right now. Check back during a match.")

                st.session_state["live_matches"] = live_matches
                st.session_state["matches_fetched_at"] = time.time()
                st.rerun()

    if "live_matches" in st.session_state:
        match_options = {
            f"{m.get('name', 'Unknown')} — {m.get('status', '')}": m.get("id", "")
            for m in st.session_state["live_matches"]
        }
        selected = st.selectbox("Select Match", list(match_options.keys()))

        if selected and st.button("Load Match Data"):
            match_id = match_options[selected]
            # Check cache — skip if same match scorecard fetched recently
            cached_id = st.session_state.get("scorecard_match_id")
            last_sc_fetch = st.session_state.get("scorecard_fetched_at", 0)
            if (match_id == cached_id
                    and time.time() - last_sc_fetch < CACHE_TTL
                    and "live_data" in st.session_state):
                remaining = CACHE_TTL - int(time.time() - last_sc_fetch)
                placeholder = st.empty()
                placeholder.info(f"Using cached scorecard. Refreshable in {remaining}s...")
                while remaining > 0:
                    time.sleep(1)
                    remaining -= 1
                    placeholder.info(f"Using cached scorecard. Refreshable in {remaining}s...")
                placeholder.success("Cache expired! Click **Load Match Data** again for fresh data.")
            else:
                with st.spinner("Fetching scorecard..."):
                    scorecard, err = fetch_match_scorecard(API_KEY, match_id)
                if err:
                    st.error(f"API Error: {err}")
                elif scorecard:
                    live_data = parse_live_data(scorecard)
                    st.session_state["live_data"] = live_data
                    st.session_state["scorecard_match_id"] = match_id
                    st.session_state["scorecard_fetched_at"] = time.time()
                    st.rerun()
                else:
                    st.error("Could not fetch scorecard. Try again or enter data manually.")

    if "live_data" in st.session_state:
        live_data = st.session_state["live_data"]
        ld = live_data
        if ld.get("innings") == 1:
            st.warning(
                f"🏏 **1st Innings in progress** — {ld.get('team_bowling','-')} batting\n\n"
                f"Score: **{ld.get('first_innings_score',0)}/{ld.get('first_innings_wickets',0)}** "
                f"({ld.get('first_innings_overs','0')} ov)\n\n"
                f"Chasing team: **{ld.get('team_batting','-')}** | Venue: {ld.get('venue','-')}\n\n"
                f"Prediction will be available once 2nd innings starts. "
                f"Click **Load Match Data** again after innings break."
            )
        else:
            st.info(
                f"Loaded: **{ld.get('team_batting','-')}** chasing vs {ld.get('team_bowling','-')} | "
                f"Score: {ld.get('innings_runs',0)}/{ld.get('wickets_fallen',0)} | "
                f"Target: {ld.get('target',0)} | Venue: {ld.get('venue','-')} | "
                f"Batters: {ld.get('current_batters',[])} | Bowler: {ld.get('current_bowler','-')}"
            )

# ── Helper: match live names to our dropdown lists ────────────────────────────
def _find_closest(name: str, options: list[str]) -> int:
    """Find the best matching index in options for a player/team/venue name."""
    if not name:
        return 0
    name_lower = name.lower()
    # Exact match
    for i, opt in enumerate(options):
        if opt.lower() == name_lower:
            return i
    # Partial match (last name or substring)
    parts = name_lower.split()
    for i, opt in enumerate(options):
        opt_lower = opt.lower()
        for part in parts:
            if len(part) > 2 and part in opt_lower:
                return i
    return 0

# ── Defaults from live data ───────────────────────────────────────────────────
def_team   = _find_closest(live_data.get("team_batting", ""), sorted(TEAMS))
def_venue  = _find_closest(live_data.get("venue", ""), VENUES)
def_target = live_data.get("target", 170) or 170
def_runs   = live_data.get("innings_runs", 80) or 80
def_balls  = live_data.get("balls_remaining", 60) or 60
def_wkts   = live_data.get("wickets_fallen", 2) or 2

# Player defaults from live data
live_batters = live_data.get("current_batters", [])
def_striker = _find_closest(live_batters[0] if len(live_batters) > 0 else "", BATTERS)
def_ns      = _find_closest(live_batters[1] if len(live_batters) > 1 else "", BATTERS)
def_bowler  = _find_closest(live_data.get("current_bowler", ""), BOWLERS)
def_bowl_balls = live_data.get("bowler_match_balls", 0) or 0
def_bowl_runs  = live_data.get("bowler_match_runs", 0) or 0

# Fallback defaults if no live data
if not live_data:
    def_striker = BATTERS.index('MS Dhoni') if 'MS Dhoni' in BATTERS else 0
    def_ns      = BATTERS.index('SR Watson') if 'SR Watson' in BATTERS else 1
    def_bowler  = BOWLERS.index('JJ Bumrah') if 'JJ Bumrah' in BOWLERS else 0

# ── Auto-fill guide ───────────────────────────────────────────────────────────
_live = bool(live_data and live_data.get("innings") == 2)
_auto = " :green[Auto-filled]" if _live else ""
_manual = " :orange[Update manually]" if _live else ""

if _live:
    st.info("**Auto-filled fields** are marked :green[green]. "
            "Fields marked :orange[orange] need your manual input.")

# ── Match Setup ───────────────────────────────────────────────────────────────
st.subheader("Match Setup")
col1, col2, col3, col4 = st.columns(4)
with col1:
    bat_second   = st.selectbox(f"Chasing Team{_auto}", sorted(TEAMS), index=def_team)
with col2:
    venue        = st.selectbox(f"Venue{_auto}", VENUES, index=def_venue)
with col3:
    target_score = st.number_input(f"Target Score{_auto}", min_value=50, max_value=300,
                                   value=min(max(def_target, 50), 300), step=1)
with col4:
    innings_runs = st.number_input(f"Current Score{_auto}", min_value=0, max_value=299,
                                   value=min(max(def_runs, 0), 299), step=1)

# ── Current Situation ─────────────────────────────────────────────────────────
st.subheader("Current Situation")
col5, col6 = st.columns(2)
with col5:
    balls_remaining = st.number_input(f"Balls Remaining{_auto}", min_value=1, max_value=119,
                                      value=min(max(def_balls, 1), 119), step=1)
with col6:
    wickets_fallen  = st.number_input(f"Wickets Fallen{_auto}", min_value=0, max_value=9,
                                      value=min(max(def_wkts, 0), 9), step=1)

# ── Players at the Crease ────────────────────────────────────────────────────
st.subheader("Batting — Players at the Crease")
st.caption("Career stats loaded automatically using Bayesian shrinkage.")
_batter_tag = _auto if (_live and live_data.get("current_batters")) else _manual
col7, col8, col9 = st.columns(3)
with col7:
    batter_name    = st.selectbox(f"Striker{_batter_tag}", BATTERS, index=def_striker)
with col8:
    non_striker = st.selectbox(f"Non-Striker{_batter_tag}", BATTERS, index=def_ns)
with col9:
    default_next_idx = BATTERS.index('AB de Villiers') if 'AB de Villiers' in BATTERS else 2
    next_batter  = st.selectbox(f"Next Batter (Coming In){_manual}", BATTERS, index=default_next_idx)

# ── Bowling ───────────────────────────────────────────────────────────────────
st.subheader("Bowling")
_bowler_tag = _auto if (_live and live_data.get("current_bowler")) else _manual
bcol1, bcol2 = st.columns(2)
with bcol1:
    bowler_name    = st.selectbox(f"Current Bowler{_bowler_tag}", BOWLERS, index=def_bowler)
with bcol2:
    remaining_bowlers = st.multiselect(
        f"Remaining Bowlers (still have overs left){_manual}",
        options=BOWLERS,
        help="Select all bowlers who still have overs left to bowl (excluding current bowler). "
             "Their career economy is averaged to estimate bowling strength remaining."
    )

st.caption("Bowler's performance this match — set balls to 0 to use career stats only.")
_bowl_match_tag = _auto if (_live and live_data.get("bowler_match_balls", 0) > 0) else _manual
bc1, bc2 = st.columns(2)
with bc1:
    bowler_match_balls = st.slider(f"Bowler Balls Bowled This Match{_bowl_match_tag}", 0, 24,
                                   min(def_bowl_balls, 24))
with bc2:
    bowler_match_runs  = st.slider(f"Bowler Runs Conceded This Match{_bowl_match_tag}", 0, 72,
                                   min(def_bowl_runs, 72))

# ── Momentum ──────────────────────────────────────────────────────────────────
st.subheader(f"Recent Momentum (Last 12 Balls)")
if _live:
    st.caption(":orange[These fields are NOT available from the API — update manually from the live broadcast.]")
mc1, mc2, mc3 = st.columns(3)
with mc1:
    recent_runs    = st.slider(f"Runs Scored{_manual}", 0, 60, 14)
with mc2:
    dot_count      = st.slider(f"Dot Balls{_manual}", 0, 12, 4)
with mc3:
    boundary_count = st.slider(f"Boundaries (4s + 6s){_manual}", 0, 12, 2)

# ── Partnership ───────────────────────────────────────────────────────────────
st.subheader("Current Partnership")
partnership_runs = st.number_input(f"Partnership Runs (since last wicket){_manual}",
                                    min_value=0, max_value=200, value=20, step=1)

# ── Live Stats ────────────────────────────────────────────────────────────────
runs_to_get  = target_score - innings_runs
overs_bowled = round((120 - balls_remaining) / 6, 1)
crr_display  = round(innings_runs / (overs_bowled if overs_bowled > 0 else 0.1), 2)
rrr_display  = min(round(runs_to_get / (balls_remaining / 6), 2), 36)

st.divider()
st.subheader("Live Match Stats")
m1, m2, m3, m4 = st.columns(4)
m1.metric("Runs to Get",  runs_to_get)
m2.metric("Overs Bowled", overs_bowled)
m3.metric("Current RR",   crr_display)
m4.metric("Required RR",  rrr_display)

st.divider()

# ── Predict ───────────────────────────────────────────────────────────────────
if st.button("Predict Win Probability", type="primary"):
    if innings_runs >= target_score:
        st.error("Current score already equals or exceeds target — match is over!")
    elif next_batter in (batter_name, non_striker):
        st.warning(f"⚠️ Next batter cannot be the same as a current batter at the crease. "
                   f"Please select a different player.")
    else:
        (win_prob, crr, rrr, rtg, phase,
         career_sr, phase_sr, bowler_eco,
         ns_sr, next_sr, rem_eco, venue_pct) = predict(
            bat_second, target_score, innings_runs, balls_remaining, wickets_fallen,
            batter_name, non_striker, next_batter, bowler_name,
            bowler_match_runs, bowler_match_balls,
            remaining_bowlers,
            partnership_runs, recent_runs,
            dot_count, boundary_count,
            venue
        )
        lose_prob = round(100 - win_prob, 1)

        st.subheader("Prediction Result")
        col_a, col_b = st.columns(2)
        with col_a:
            st.metric(f"🏏 {bat_second} Win %", f"{win_prob}%")
        with col_b:
            st.metric("🎳 Bowling Team Win %", f"{lose_prob}%")

        st.progress(int(win_prob), text=f"Win Probability: {win_prob}%")

        st.divider()
        if win_prob >= 70:
            st.success(f"✅ {bat_second} are in a strong position! (Phase: {phase})")
        elif win_prob >= 45:
            st.warning(f"⚖️ Close match — could go either way! (Phase: {phase})")
        else:
            st.error(f"❌ Bowling team has the edge. (Phase: {phase})")

        st.divider()
        st.subheader("Stats Used by Model")
        s1, s2, s3, s4 = st.columns(4)
        s1.metric(f"{batter_name} Career SR",    f"{career_sr:.1f}")
        s2.metric(f"{batter_name} {phase} SR",   f"{phase_sr:.1f}")
        s3.metric(f"{non_striker} SR",            f"{ns_sr:.1f}")
        s4.metric(f"{next_batter} (Next) SR",     f"{next_sr:.1f}")

        s5, s6, s7, s8 = st.columns(4)
        s5.metric(f"{bowler_name} Eff. Economy",  f"{bowler_eco:.2f}")
        s6.metric("Remaining Bowlers Avg Eco",     f"{rem_eco:.2f}")
        s7.metric("Venue Chase Win %",             f"{venue_pct:.1f}%")
        s8.metric("Match Phase",                   phase)
