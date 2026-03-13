import os
import joblib
import numpy as np
import pandas as pd

BASE       = os.path.dirname(__file__)
model_data = joblib.load(os.path.join(BASE, 'artifacts', 'cricket_model.joblib'))

model        = model_data['model']
scaler       = model_data['scaler']
model_type   = model_data.get('model_type', 'logistic_regression')
features     = model_data['features']
numeric_cols = model_data['numeric_cols']

MEDIAN = {
    'career_sr':     model_data['median_career_sr'],
    'sr_powerplay':  model_data['median_sr_powerplay'],
    'sr_middle':     model_data['median_sr_middle'],
    'sr_death':      model_data['median_sr_death'],
    'eco':           model_data['median_eco'],
    'wicket_rate':   model_data['median_wicket_rate'],
    'eco_powerplay': model_data['median_eco_powerplay'],
    'eco_middle':    model_data['median_eco_middle'],
    'eco_death':     model_data['median_eco_death'],
}
GLOBAL_CHASE_WIN_PCT = model_data['global_chase_win_pct']

# ── Load lookup tables ─────────────────────────────────────────────────────────
batter_stats = pd.read_csv(os.path.join(BASE, 'artifacts', 'batter_stats.csv'))
bowler_stats  = pd.read_csv(os.path.join(BASE, 'artifacts', 'bowler_stats.csv'))
venue_stats   = pd.read_csv(os.path.join(BASE, 'artifacts', 'venue_stats.csv'))

BATTERS = sorted(batter_stats[batter_stats['career_balls'] >= 50]['Batter'].tolist())
BOWLERS = sorted(bowler_stats[bowler_stats['b_balls']     >= 60]['Bowler'].tolist())
VENUES  = sorted(venue_stats['Venue'].tolist())

_team_cols = [f for f in features if f.startswith('Bat Second_')]
# Use full teams list from artifact (includes reference team dropped by drop_first=True)
TEAMS = model_data.get('all_teams', sorted([c.replace('Bat Second_', '') for c in _team_cols]))

PHASE_SR_COL  = {'Powerplay': 'shrunk_sr_powerplay',
                 'Middle Overs': 'shrunk_sr_middle',
                 'Death Overs':  'shrunk_sr_death'}
PHASE_ECO_COL = {'Powerplay': 'shrunk_eco_powerplay',
                 'Middle Overs': 'shrunk_eco_middle',
                 'Death Overs':  'shrunk_eco_death'}

# Pre-build bowler eco lookup for fast access
# Raw career_economy for remaining bowlers (averaging smooths noise better than shrinkage)
_bowler_eco_map = bowler_stats.set_index('Bowler')['career_economy'].to_dict()


def _get_batter_stats(name, phase):
    row = batter_stats[batter_stats['Batter'] == name]
    if row.empty:
        return MEDIAN['career_sr'], MEDIAN[PHASE_SR_COL[phase].replace('shrunk_', '')]
    r        = row.iloc[0]
    career   = r.get('shrunk_career_sr', np.nan)
    career   = career if not pd.isna(career) else MEDIAN['career_sr']
    phase_sr = r.get(PHASE_SR_COL[phase], np.nan)
    if pd.isna(phase_sr):
        phase_sr = career
    return career, phase_sr


def _get_batter_career_sr(name):
    row = batter_stats[batter_stats['Batter'] == name]
    if row.empty:
        return MEDIAN['career_sr']
    v = row.iloc[0].get('shrunk_career_sr', np.nan)
    return v if not pd.isna(v) else MEDIAN['career_sr']


def _get_bowler_stats(name, phase):
    row = bowler_stats[bowler_stats['Bowler'] == name]
    if row.empty:
        return MEDIAN['eco'], MEDIAN['wicket_rate'], MEDIAN[PHASE_ECO_COL[phase].replace('shrunk_', '')]
    r     = row.iloc[0]
    eco   = r.get('shrunk_career_eco', np.nan)
    wr    = r.get('career_wicket_rate', np.nan)
    p_eco = r.get(PHASE_ECO_COL[phase], np.nan)
    eco   = eco   if not pd.isna(eco)   else MEDIAN['eco']
    wr    = wr    if not pd.isna(wr)    else MEDIAN['wicket_rate']
    p_eco = p_eco if not pd.isna(p_eco) else eco
    return eco, wr, p_eco


def _get_venue_chase_pct(venue):
    row = venue_stats[venue_stats['Venue'] == venue]
    if row.empty:
        return GLOBAL_CHASE_WIN_PCT
    return row.iloc[0]['venue_chase_win_pct']


def predict(bat_second, target_score, innings_runs, balls_remaining, wickets_fallen,
            batter_name, non_striker_name, next_batter_name, bowler_name,
            bowler_match_runs, bowler_match_balls,
            remaining_bowlers,
            partnership_runs, recent_runs,
            dot_count, boundary_count,
            venue):

    # ── Match situation ────────────────────────────────────────────────────────
    runs_to_get        = target_score - innings_runs
    overs_bowled       = (120 - balls_remaining) / 6
    crr                = round(innings_runs / overs_bowled, 2) if overs_bowled > 0 else 0
    rrr                = min(round(runs_to_get / (balls_remaining / 6), 2), 36)
    wickets_in_hand    = 10 - wickets_fallen
    run_rate_pressure  = min(round(rrr / crr, 2), 20) if crr > 0 else rrr
    resource_remaining = round((20 - overs_bowled) * (wickets_in_hand / 10), 3)

    phase = ('Powerplay'    if overs_bowled <= 6
             else 'Middle Overs' if overs_bowled <= 15
             else 'Death Overs')

    # ── Momentum ───────────────────────────────────────────────────────────────
    dot_pct      = round(dot_count / 12, 3)
    boundary_pct = round(boundary_count / 12, 3)

    # ── Batter stats ───────────────────────────────────────────────────────────
    career_sr, batter_phase_sr = _get_batter_stats(batter_name, phase)
    ns_sr, _                   = _get_batter_stats(non_striker_name, phase)
    next_batter_sr             = _get_batter_career_sr(next_batter_name)

    # ── Bowler stats ───────────────────────────────────────────────────────────
    eco, wicket_rate, p_eco = _get_bowler_stats(bowler_name, phase)
    if bowler_match_balls >= 12:
        match_eco            = round(bowler_match_runs / (bowler_match_balls / 6), 2)
        effective_bowler_eco = round(0.6 * match_eco + 0.4 * p_eco, 2)
    else:
        effective_bowler_eco = p_eco

    # ── Remaining bowlers avg eco ──────────────────────────────────────────────
    if remaining_bowlers:
        rem_ecos = [_bowler_eco_map.get(b, MEDIAN['eco']) for b in remaining_bowlers]
        remaining_bowler_avg_eco = round(float(np.mean(rem_ecos)), 2)
    else:
        remaining_bowler_avg_eco = MEDIAN['eco']

    # ── Interaction features ───────────────────────────────────────────────────
    required_sr          = rrr * 100 / 6
    batter_advantage     = round(batter_phase_sr - required_sr, 2)
    batter_vs_bowler     = round(batter_phase_sr - (effective_bowler_eco / 6 * 100), 2)
    pair_sr              = round((career_sr + ns_sr) / 2, 1)
    partnership_momentum = round(min(partnership_runs / (resource_remaining + 0.1), 30), 2)

    # ── Venue ──────────────────────────────────────────────────────────────────
    venue_chase_win_pct = _get_venue_chase_pct(venue)

    # ── Build input row ────────────────────────────────────────────────────────
    input_data = {
        'Target Score':              target_score,
        'overs_bowled':              overs_bowled,
        'crr':                       crr,
        'rrr':                       rrr,
        'wickets_in_hand':           wickets_in_hand,
        'run_rate_pressure':         run_rate_pressure,
        'resource_remaining':        resource_remaining,
        'recent_runs':               recent_runs,
        'dot_pct':                   dot_pct,
        'boundary_pct':              boundary_pct,
        'shrunk_career_sr':          career_sr,
        'batter_phase_sr':           batter_phase_sr,
        'non_striker_sr':            ns_sr,
        'next_batter_sr':            next_batter_sr,
        'shrunk_career_eco':         eco,
        'career_wicket_rate':        wicket_rate,
        'effective_bowler_eco':      effective_bowler_eco,
        'bowler_match_wickets':      0,
        'remaining_bowler_avg_eco':  remaining_bowler_avg_eco,
        'batter_advantage':          batter_advantage,
        'batter_vs_bowler':          batter_vs_bowler,
        'pair_sr':                   pair_sr,
        'partnership_runs':          partnership_runs,
        'partnership_momentum':      partnership_momentum,
        'venue_chase_win_pct':       venue_chase_win_pct,
    }

    for col in _team_cols:
        input_data[col] = 1 if col == f'Bat Second_{bat_second}' else 0

    input_data['match_phase_Middle Overs'] = 1 if phase == 'Middle Overs' else 0
    input_data['match_phase_Death Overs']  = 1 if phase == 'Death Overs'  else 0

    df_input = pd.DataFrame([input_data])[features]
    if scaler is not None:
        df_input[numeric_cols] = scaler.transform(df_input[numeric_cols])

    win_prob = model.predict_proba(df_input)[0][1]
    return (round(win_prob * 100, 1), crr, rrr, runs_to_get,
            phase, career_sr, batter_phase_sr, effective_bowler_eco,
            ns_sr, next_batter_sr, remaining_bowler_avg_eco, venue_chase_win_pct)
