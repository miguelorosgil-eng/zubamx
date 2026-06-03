"""
Stats avanzados por deporte para enriquecer predicciones.
MLB: xFIP (FanGraphs), OPS+, ERA bullpen
NBA: Net Rating, Pace (NBA Stats API)
NHL: Corsi%, PDO (NHL API)
Todas las funciones fallan silenciosamente si la API no responde.
"""
import requests
import pandas as pd
import numpy as np
from difflib import SequenceMatcher

_CACHE = {}

def _sim(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def _get(url, params=None, headers=None, timeout=15):
    key = (url, str(sorted((params or {}).items())))
    if key in _CACHE:
        return _CACHE[key]
    try:
        r = requests.get(url, params=params, headers=headers, timeout=timeout)
        r.raise_for_status()
        data = r.json()
        _CACHE[key] = data
        return data
    except Exception:
        return None

# ─── MLB ────────────────────────────────────────────────────────────────────

def get_mlb_pitcher_xfip(pitcher_name: str, season: int) -> float | None:
    """xFIP desde FanGraphs. Más predictivo que ERA (elimina suerte en BABIP y HR/FB)."""
    url = "https://www.fangraphs.com/api/leaders/major-league/data"
    params = {
        "age": "", "pos": "all", "stats": "pit", "lg": "all",
        "qual": "0", "season": season, "season1": season,
        "ind": "0", "team": "0", "pageitems": "2000", "pagenum": "1",
        "type": "1", "sortdir": "default", "sortstat": "xFIP",
    }
    headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://www.fangraphs.com"}
    data = _get(url, params, headers)
    if not data:
        return None
    try:
        rows = data.get("data", [])
        best, best_score = None, 0
        for row in rows:
            name = row.get("PlayerName", "")
            score = _sim(pitcher_name, name)
            if score > best_score:
                best, best_score = row, score
        if best and best_score > 0.75:
            val = best.get("xFIP")
            return float(val) if val is not None else None
    except Exception:
        pass
    return None


_MLB_TEAM_IDS = {}

def _get_mlb_team_id(team_name: str) -> int | None:
    if not _MLB_TEAM_IDS:
        data = _get("https://statsapi.mlb.com/api/v1/teams", {"sportId": 1})
        if data:
            for t in data.get("teams", []):
                _MLB_TEAM_IDS[t["name"]] = t["id"]
    best, best_score, best_id = None, 0, None
    for name, tid in _MLB_TEAM_IDS.items():
        s = _sim(team_name, name)
        if s > best_score:
            best, best_score, best_id = name, s, tid
    return best_id if best_score > 0.6 else None


def get_mlb_bullpen_era(team_name: str, season: int) -> float:
    """ERA del bullpen (pitchers sin starts) del equipo."""
    tid = _get_mlb_team_id(team_name)
    if not tid:
        return 4.50
    try:
        data = _get(f"https://statsapi.mlb.com/api/v1/teams/{tid}/stats",
                    {"stats": "season", "group": "pitching", "season": season,
                     "gameType": "R", "sitCodes": "r"})
        splits = (data or {}).get("stats", [{}])[0].get("splits", [])
        if splits:
            era_str = splits[0]["stat"].get("era", "4.50")
            return float(era_str) if era_str else 4.50
    except Exception:
        pass
    return 4.50


def get_mlb_team_ops_plus(team_name: str, season: int) -> float:
    """OPS+ del lineup. >100 = mejor que promedio."""
    tid = _get_mlb_team_id(team_name)
    if not tid:
        return 100.0
    try:
        data = _get(f"https://statsapi.mlb.com/api/v1/teams/{tid}/stats",
                    {"stats": "season", "group": "hitting", "season": season})
        splits = (data or {}).get("stats", [{}])[0].get("splits", [])
        if splits:
            s = splits[0]["stat"]
            ab = float(s.get("atBats", 1) or 1)
            h  = float(s.get("hits", 0) or 0)
            bb = float(s.get("baseOnBalls", 0) or 0)
            hr = float(s.get("homeRuns", 0) or 0)
            slg_num = float(s.get("totalBases", 0) or 0)
            obp = (h + bb) / max(ab + bb, 1)
            slg = slg_num / max(ab, 1)
            ops = obp + slg
            league_ops = 0.720
            return round(ops / league_ops * 100, 1)
    except Exception:
        pass
    return 100.0


# ─── NBA ────────────────────────────────────────────────────────────────────

def get_nba_net_rating(team_name: str, season_str: str = "2025-26") -> dict:
    """Net rating desde NBA Stats API."""
    default = {"off_rtg": 110.0, "def_rtg": 110.0, "net_rtg": 0.0, "pace": 100.0}
    url = "https://stats.nba.com/stats/leaguedashteamstats"
    params = {
        "Season": season_str, "MeasureType": "Advanced",
        "PerMode": "PerGame", "SeasonType": "Regular Season",
        "DateFrom": "", "DateTo": "", "GameScope": "",
        "GameSegment": "", "LastNGames": "0", "LeagueID": "00",
        "Location": "", "Month": "0", "OpponentTeamID": "0",
        "Outcome": "", "PORound": "0", "PaceAdjust": "N",
        "Period": "0", "PlusMinus": "N", "Rank": "N",
        "TeamID": "0", "VsConference": "", "VsDivision": "",
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.nba.com",
        "Accept": "application/json",
        "x-nba-stats-origin": "stats",
        "x-nba-stats-token": "true",
    }
    data = _get(url, params, headers)
    if not data:
        return default
    try:
        rs = data["resultSets"][0]
        headers_list = rs["headers"]
        rows = rs["rowSet"]
        idx_name = headers_list.index("TEAM_NAME")
        idx_off  = headers_list.index("OFF_RATING")
        idx_def  = headers_list.index("DEF_RATING")
        idx_net  = headers_list.index("NET_RATING")
        idx_pace = headers_list.index("PACE")
        best, best_score = None, 0
        for row in rows:
            s = _sim(team_name, row[idx_name])
            if s > best_score:
                best, best_score = row, s
        if best and best_score > 0.6:
            return {
                "off_rtg": float(best[idx_off]),
                "def_rtg": float(best[idx_def]),
                "net_rtg": float(best[idx_net]),
                "pace":    float(best[idx_pace]),
            }
    except Exception:
        pass
    return default


def get_nba_rest_days(team_name: str, schedule_df: pd.DataFrame, game_date) -> int:
    """Días desde el último partido del equipo. Cap 7."""
    if schedule_df is None or schedule_df.empty:
        return 3
    try:
        game_date = pd.Timestamp(game_date)
        mask = ((schedule_df["home"] == team_name) | (schedule_df["away"] == team_name))
        prev = schedule_df[mask & (schedule_df["date"] < game_date)]["date"]
        if prev.empty:
            return 3
        last = pd.Timestamp(prev.max())
        return min(int((game_date - last).days), 7)
    except Exception:
        return 3


# ─── NHL ────────────────────────────────────────────────────────────────────

def get_nhl_corsi(team_name: str, season: str = "20252026") -> dict:
    """Corsi% y PDO desde NHL API. PDO > 1.02 = sobreperformance (regresión inminente)."""
    default = {"corsi_pct": 0.50, "pdo": 1.000, "shots_for": 30.0, "shots_against": 30.0}
    url = "https://api.nhle.com/stats/rest/en/team/summary"
    params = {"cayenneExp": f"seasonId={season}&gameTypeId=2"}
    data = _get(url, params)
    if not data:
        return default
    try:
        best, best_score = None, 0
        for team in data.get("data", []):
            name = team.get("teamFullName", "")
            s = _sim(team_name, name)
            if s > best_score:
                best, best_score = team, s
        if best and best_score > 0.5:
            sf  = float(best.get("shotsForPerGame", 30))
            sa  = float(best.get("shotsAgainstPerGame", 30))
            corsi = sf / max(sf + sa, 1)
            spct = float(best.get("shootingPct", 9.0)) / 100
            svpct = float(best.get("savePct", 0.910))
            pdo  = spct + svpct
            return {"corsi_pct": round(corsi, 3), "pdo": round(pdo, 3),
                    "shots_for": sf, "shots_against": sa}
    except Exception:
        pass
    return default


# ─── Enriquecedor universal ─────────────────────────────────────────────────

def enrich_prediction(sport: str, home: str, away: str,
                      pred: dict, season=None) -> dict:
    """Añade warnings y stats avanzados al dict de predicción."""
    pred = dict(pred)
    warnings_list = []
    sport = sport.lower()

    if sport == "nhl":
        season_str = str(season) if season else "20252026"
        c_h = get_nhl_corsi(home, season_str)
        c_a = get_nhl_corsi(away, season_str)
        pred["home_corsi"] = c_h["corsi_pct"]
        pred["away_corsi"] = c_a["corsi_pct"]
        pred["home_pdo"]   = c_h["pdo"]
        pred["away_pdo"]   = c_a["pdo"]
        if c_h["pdo"] > 1.020:
            warnings_list.append(f"⚠️ {home} PDO={c_h['pdo']:.3f} — sobreperformando, esperar regresión")
        if c_a["pdo"] > 1.020:
            warnings_list.append(f"⚠️ {away} PDO={c_a['pdo']:.3f} — sobreperformando, esperar regresión")
        if c_h["corsi_pct"] < 0.46:
            warnings_list.append(f"⚠️ {home} Corsi={c_h['corsi_pct']:.0%} — control de juego deficiente")

    elif sport == "nba":
        season_str = f"{(season or 2025)}-{str((season or 2025)+1)[2:]}"
        nr_h = get_nba_net_rating(home, season_str)
        nr_a = get_nba_net_rating(away, season_str)
        pred["home_net_rtg"] = nr_h["net_rtg"]
        pred["away_net_rtg"] = nr_a["net_rtg"]
        pred["home_pace"]    = nr_h["pace"]
        if abs(nr_h["net_rtg"] - nr_a["net_rtg"]) > 8:
            better = home if nr_h["net_rtg"] > nr_a["net_rtg"] else away
            warnings_list.append(f"💡 Net Rating gap grande — {better} claramente superior")

    elif sport == "mlb":
        s = season or 2025
        bull_h = get_mlb_bullpen_era(home, s)
        bull_a = get_mlb_bullpen_era(away, s)
        pred["home_bullpen_era"] = bull_h
        pred["away_bullpen_era"] = bull_a
        if bull_h > 5.0:
            warnings_list.append(f"⚠️ Bullpen {home} ERA={bull_h:.2f} — riesgo en entradas tardías")
        if bull_a > 5.0:
            warnings_list.append(f"⚠️ Bullpen {away} ERA={bull_a:.2f} — riesgo en entradas tardías")

    pred["adv_warnings"] = warnings_list
    return pred


if __name__ == "__main__":
    print("=== Test NHL Corsi (Carolina Hurricanes) ===")
    c = get_nhl_corsi("Carolina Hurricanes")
    print(c)
    print("\n=== Test NBA Net Rating (New York Knicks) ===")
    nr = get_nba_net_rating("New York Knicks")
    print(nr)
