import streamlit as st
from prediction_helper import predict, TEAMS, BATTERS, BOWLERS, VENUES

st.set_page_config(page_title="Cricket Match Winner Prediction", page_icon="🏏", layout="wide")
st.title("🏏 IPL Match Winner Prediction")
st.markdown("Live 2nd-innings win probability using career stats, Bayesian shrinkage, "
            "in-match form, partnership context, next batter, remaining bowlers, and venue factors.")
st.divider()

# ── Match Setup ────────────────────────────────────────────────────────────────
st.subheader("Match Setup")
col1, col2, col3, col4 = st.columns(4)
with col1:
    bat_second   = st.selectbox("Chasing Team", sorted(TEAMS))
with col2:
    venue        = st.selectbox("Venue", VENUES)
with col3:
    target_score = st.number_input("Target Score", min_value=50, max_value=300, value=170, step=1)
with col4:
    innings_runs = st.number_input("Current Score", min_value=0, max_value=299, value=80, step=1)

# ── Current Situation ──────────────────────────────────────────────────────────
st.subheader("Current Situation")
col5, col6 = st.columns(2)
with col5:
    balls_remaining = st.number_input("Balls Remaining", min_value=1, max_value=119, value=60, step=1)
with col6:
    wickets_fallen  = st.number_input("Wickets Fallen", min_value=0, max_value=9, value=2, step=1)

# ── Players at the Crease ──────────────────────────────────────────────────────
st.subheader("Batting — Players at the Crease")
st.caption("Career stats loaded automatically using Bayesian shrinkage.")
col7, col8, col9 = st.columns(3)
with col7:
    default_batter = BATTERS.index('MS Dhoni') if 'MS Dhoni' in BATTERS else 0
    batter_name    = st.selectbox("Striker", BATTERS, index=default_batter)
with col8:
    default_ns = BATTERS.index('SR Watson') if 'SR Watson' in BATTERS else 1
    non_striker = st.selectbox("Non-Striker", BATTERS, index=default_ns)
with col9:
    default_next = BATTERS.index('AB de Villiers') if 'AB de Villiers' in BATTERS else 2
    next_batter  = st.selectbox("Next Batter (Coming In)", BATTERS, index=default_next)

# ── Bowling ────────────────────────────────────────────────────────────────────
st.subheader("Bowling")
bcol1, bcol2 = st.columns(2)
with bcol1:
    default_bowler = BOWLERS.index('JJ Bumrah') if 'JJ Bumrah' in BOWLERS else 0
    bowler_name    = st.selectbox("Current Bowler", BOWLERS, index=default_bowler)
with bcol2:
    remaining_bowlers = st.multiselect(
        "Remaining Bowlers (still have overs left)",
        options=BOWLERS,
        help="Select all bowlers who still have overs left to bowl (excluding current bowler). "
             "Their career economy is averaged to estimate bowling strength remaining."
    )

st.caption("Bowler's performance this match — set balls to 0 to use career stats only.")
bc1, bc2 = st.columns(2)
with bc1:
    bowler_match_balls = st.slider("Bowler Balls Bowled This Match", 0, 24, 0)
with bc2:
    bowler_match_runs  = st.slider("Bowler Runs Conceded This Match", 0, 72, 0)

# ── Momentum ───────────────────────────────────────────────────────────────────
st.subheader("Recent Momentum (Last 12 Balls)")
mc1, mc2, mc3 = st.columns(3)
with mc1:
    recent_runs    = st.slider("Runs Scored", 0, 60, 14)
with mc2:
    dot_count      = st.slider("Dot Balls", 0, 12, 4)
with mc3:
    boundary_count = st.slider("Boundaries (4s + 6s)", 0, 12, 2)

# ── Partnership ────────────────────────────────────────────────────────────────
st.subheader("Current Partnership")
partnership_runs = st.number_input("Partnership Runs (since last wicket)",
                                    min_value=0, max_value=200, value=20, step=1)

# ── Live Stats ─────────────────────────────────────────────────────────────────
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

# ── Predict ────────────────────────────────────────────────────────────────────
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
