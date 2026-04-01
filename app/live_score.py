"""
Live IPL score fetcher using CricAPI (cricketdata.org).
Free tier: 100 requests/day. Sign up at https://cricketdata.org/
"""
import requests


API_BASE = "https://api.cricapi.com/v1"


def fetch_live_matches(api_key: str) -> list[dict]:
    """Return list of current/recent cricket matches."""
    try:
        resp = requests.get(
            f"{API_BASE}/currentMatches",
            params={"apikey": api_key, "offset": 0},
            timeout=10,
        )
        data = resp.json()
        if data.get("status") != "success":
            return []
        return data.get("data", [])
    except Exception:
        return []


def fetch_match_scorecard(api_key: str, match_id: str) -> dict | None:
    """Return scorecard for a specific match."""
    try:
        resp = requests.get(
            f"{API_BASE}/match_scorecard",
            params={"apikey": api_key, "id": match_id},
            timeout=10,
        )
        data = resp.json()
        if data.get("status") != "success":
            return None
        return data.get("data", {})
    except Exception:
        return None


def fetch_match_info(api_key: str, match_id: str) -> dict | None:
    """Return match info (venue, teams, toss, etc.)."""
    try:
        resp = requests.get(
            f"{API_BASE}/match_info",
            params={"apikey": api_key, "id": match_id},
            timeout=10,
        )
        data = resp.json()
        if data.get("status") != "success":
            return None
        return data.get("data", {})
    except Exception:
        return None


def parse_live_data(scorecard: dict) -> dict:
    """
    Parse scorecard into fields our model needs.
    Returns dict with available fields (caller fills the rest manually).
    """
    result = {
        "venue": "",
        "team_batting": "",
        "team_bowling": "",
        "target": 0,
        "innings_runs": 0,
        "balls_remaining": 120,
        "wickets_fallen": 0,
        "current_batters": [],
        "current_bowler": "",
        "bowler_match_balls": 0,
        "bowler_match_runs": 0,
        "innings": 0,           # 1 = 1st innings, 2 = 2nd innings
        "first_innings_score": 0,
        "first_innings_wickets": 0,
        "first_innings_overs": "",
    }

    result["venue"] = scorecard.get("venue", "")

    # Get teams
    teams = scorecard.get("teams", [])
    team_info = scorecard.get("teamInfo", [])

    # Parse scorecard for 2nd innings
    score_list = scorecard.get("score", [])
    if not score_list:
        return result

    # Find 2nd innings score
    inn2_score = None
    inn1_score = None
    for s in score_list:
        inning_str = s.get("inning", "")
        if "2nd" in inning_str.lower() or "Inning 2" in inning_str:
            inn2_score = s
        elif "1st" in inning_str.lower() or "Inning 1" in inning_str:
            inn1_score = s

    # If no explicit 2nd innings, try by order (2nd in list)
    if inn2_score is None and len(score_list) >= 2:
        inn1_score = score_list[0]
        inn2_score = score_list[1]
    elif inn2_score is None and len(score_list) == 1:
        inn1_score = score_list[0]
        # 1st innings still in progress
        result["innings"] = 1
        result["first_innings_score"] = inn1_score.get("r", 0)
        result["first_innings_wickets"] = inn1_score.get("w", 0)
        result["first_innings_overs"] = str(inn1_score.get("o", "0"))

        # Extract teams and venue even during 1st innings
        inning_label = inn1_score.get("inning", "")
        teams = scorecard.get("teams", [])
        for team in teams:
            if team in inning_label:
                result["team_bowling"] = team  # batting first = will bowl in 2nd
                break
        for team in teams:
            if team != result["team_bowling"]:
                result["team_batting"] = team  # batting second = chasing team
                break
        return result

    # 1st innings total = target
    result["innings"] = 2
    if inn1_score:
        result["target"] = inn1_score.get("r", 0) + 1  # target = 1st inn runs + 1
        result["first_innings_score"] = inn1_score.get("r", 0)
        result["first_innings_wickets"] = inn1_score.get("w", 0)
        result["first_innings_overs"] = str(inn1_score.get("o", "0"))

    # 2nd innings current state
    if inn2_score:
        result["innings_runs"] = inn2_score.get("r", 0)
        result["wickets_fallen"] = inn2_score.get("w", 0)
        overs_str = str(inn2_score.get("o", "0"))
        try:
            overs = float(overs_str)
            completed_overs = int(overs)
            balls_in_over = round((overs - completed_overs) * 10)
            total_balls_bowled = completed_overs * 6 + balls_in_over
            result["balls_remaining"] = max(120 - total_balls_bowled, 1)
        except (ValueError, TypeError):
            pass

        # Extract team batting in 2nd innings from inning label
        inning_label = inn2_score.get("inning", "")
        for team in teams:
            if team in inning_label:
                result["team_batting"] = team
                break

    # Set bowling team
    if result["team_batting"] and teams:
        for team in teams:
            if team != result["team_batting"]:
                result["team_bowling"] = team
                break

    # Parse batsmen currently at crease from scorecard
    scorecard_list = scorecard.get("scorecard", [])
    if len(scorecard_list) >= 2:
        inn2_card = scorecard_list[1]  # 2nd innings
        batting = inn2_card.get("batting", [])
        bowling = inn2_card.get("bowling", [])

        # Find batters who are "not out"
        for b in batting:
            dismissal = b.get("dismissal-text", "")
            if "not out" in dismissal.lower() or dismissal == "":
                name = b.get("batsman", {}).get("name", "")
                if name:
                    result["current_batters"].append(name)

        # Last bowler in the bowling list is likely current bowler
        if bowling:
            last_bowler = bowling[-1]
            result["current_bowler"] = last_bowler.get("bowler", {}).get("name", "")
            # Parse bowler match stats
            try:
                overs_bowled_str = str(last_bowler.get("o", "0"))
                overs_f = float(overs_bowled_str)
                comp = int(overs_f)
                part = round((overs_f - comp) * 10)
                result["bowler_match_balls"] = comp * 6 + part
            except (ValueError, TypeError):
                pass
            result["bowler_match_runs"] = last_bowler.get("r", 0)

    return result
