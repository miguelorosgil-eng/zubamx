"""
Statcast data desde Baseball Savant — gratis, sin API key.
Exit velocity, spin rate, xwOBA, hard hit % para MLB.
"""

import os
import io
import requests
import pandas as pd
from difflib import get_close_matches

STATCAST_BASE = "https://baseballsavant.mlb.com/leaderboard/custom"
CACHE_DIR = "_cache"

TEAM_ABBR = {
    "Arizona Diamondbacks": "ARI", "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL", "Boston Red Sox": "BOS",
    "Chicago Cubs": "CHC", "Chicago White Sox": "CWS",
    "Cincinnati Reds": "CIN", "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL", "Detroit Tigers": "DET",
    "Houston Astros": "HOU", "Kansas City Royals": "KC",
    "Los Angeles Angels": "LAA", "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA", "Milwaukee Brewers": "MIL",
    "Minnesota Twins": "MIN", "New York Mets": "NYM",
    "New York Yankees": "NYY", "Athletics": "OAK",
    "Philadelphia Phillies": "PHI", "Pittsburgh Pirates": "PIT",
    "San Diego Padres": "SD", "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA", "St. Louis Cardinals": "STL",
    "Tampa Bay Rays": "TB", "Texas Rangers": "TEX",
    "Toronto Blue Jays": "TOR", "Washington Nationals": "WSH",
}


def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def _get_pitcher_df(season: int) -> pd.DataFrame:
    """Descarga o lee del cache el CSV de pitchers para la temporada."""
    _ensure_cache_dir()
    cache_path = os.path.join(CACHE_DIR, f"statcast_pitchers_{season}.csv")
    if os.path.exists(cache_path):
        return pd.read_csv(cache_path)

    url = (
        f"{STATCAST_BASE}?year={season}&type=pitcher&filter=&sort=4&sortDir=asc"
        f"&min=10&selections=p_spin_rate,p_k_percent,xfip,hard_hit_percent&csv=true"
    )
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    df.to_csv(cache_path, index=False)
    return df


def _get_batter_df(season: int) -> pd.DataFrame:
    """Descarga o lee del cache el CSV de bateadores para la temporada."""
    _ensure_cache_dir()
    cache_path = os.path.join(CACHE_DIR, f"statcast_batters_{season}.csv")
    if os.path.exists(cache_path):
        return pd.read_csv(cache_path)

    url = (
        f"{STATCAST_BASE}?year={season}&type=batter&filter=&sort=4&sortDir=asc"
        f"&min=50&selections=xwoba,hard_hit_percent,k_percent,bb_percent&csv=true"
    )
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    df.to_csv(cache_path, index=False)
    return df


def _fuzzy_find_pitcher(df: pd.DataFrame, pitcher_name: str):
    """Fuzzy match del nombre del pitcher en el DataFrame."""
    name_col = None
    for col in ["last_name, first_name", "player_name", "name", "last_name"]:
        if col in df.columns:
            name_col = col
            break
    if name_col is None:
        return None

    names = df[name_col].astype(str).tolist()
    matches = get_close_matches(pitcher_name, names, n=1, cutoff=0.6)
    if not matches:
        # intenta con apellido
        last = pitcher_name.split()[-1] if pitcher_name else ""
        matches = get_close_matches(last, names, n=1, cutoff=0.5)
    if not matches:
        return None
    return df[df[name_col] == matches[0]].iloc[0]


def get_pitcher_statcast(pitcher_name: str, season: int) -> dict:
    """
    Spin rate, xFIP, hard_hit_pct_against del pitcher.
    URL: https://baseballsavant.mlb.com/leaderboard/custom
         ?year={season}&type=pitcher&filter=&sort=4&sortDir=asc
         &min=10&selections=p_spin_rate,p_k_percent,xfip,hard_hit_percent
         &csv=true
    Parsea el CSV, fuzzy-match por nombre. Devuelve dict o {} si falla.
    """
    try:
        df = _get_pitcher_df(season)
        row = _fuzzy_find_pitcher(df, pitcher_name)
        if row is None:
            return {}

        result = {}
        spin_cols = [c for c in df.columns if "spin" in c.lower()]
        k_cols = [c for c in df.columns if "k_percent" in c.lower() or "k%" in c.lower()]
        xfip_cols = [c for c in df.columns if "xfip" in c.lower()]
        hh_cols = [c for c in df.columns if "hard_hit" in c.lower()]

        if spin_cols:
            result["spin_rate"] = float(row[spin_cols[0]]) if pd.notna(row[spin_cols[0]]) else None
        if k_cols:
            result["k_pct"] = float(row[k_cols[0]]) if pd.notna(row[k_cols[0]]) else None
        if xfip_cols:
            result["xfip"] = float(row[xfip_cols[0]]) if pd.notna(row[xfip_cols[0]]) else None
        if hh_cols:
            result["hard_hit_pct"] = float(row[hh_cols[0]]) if pd.notna(row[hh_cols[0]]) else None

        return result
    except Exception:
        return {}


def get_team_batting_statcast(team_abbr: str, season: int) -> dict:
    """
    xwOBA, hard_hit_pct, k_pct, bb_pct del lineup del equipo.
    URL: https://baseballsavant.mlb.com/leaderboard/custom
         ?year={season}&type=batter&filter=&sort=4&sortDir=asc
         &min=50&team={team_abbr}&selections=xwoba,hard_hit_percent,k_percent,bb_percent
         &csv=true
    Agrupa por equipo y promedia. Devuelve dict o defaults si falla.
    """
    defaults = {
        "xwoba": 0.320,
        "hard_hit_pct": 38.0,
        "k_pct": 22.0,
        "bb_pct": 8.5,
    }
    try:
        _ensure_cache_dir()
        cache_path = os.path.join(CACHE_DIR, f"statcast_batters_{season}_{team_abbr}.csv")

        if os.path.exists(cache_path):
            df = pd.read_csv(cache_path)
        else:
            url = (
                f"{STATCAST_BASE}?year={season}&type=batter&filter=&sort=4&sortDir=asc"
                f"&min=50&team={team_abbr}"
                f"&selections=xwoba,hard_hit_percent,k_percent,bb_percent&csv=true"
            )
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text))
            df.to_csv(cache_path, index=False)

        if df.empty:
            return defaults

        result = {}
        col_map = {
            "xwoba": [c for c in df.columns if "xwoba" in c.lower()],
            "hard_hit_pct": [c for c in df.columns if "hard_hit" in c.lower()],
            "k_pct": [c for c in df.columns if "k_percent" in c.lower() or "k%" in c.lower()],
            "bb_pct": [c for c in df.columns if "bb_percent" in c.lower() or "bb%" in c.lower()],
        }

        for key, cols in col_map.items():
            if cols:
                vals = pd.to_numeric(df[cols[0]], errors="coerce").dropna()
                result[key] = float(vals.mean()) if len(vals) > 0 else defaults[key]
            else:
                result[key] = defaults[key]

        return result
    except Exception:
        return defaults


def get_statcast_game_score(home: str, away: str,
                             home_pitcher: str, away_pitcher: str,
                             season: int) -> dict:
    """
    Combina stats del pitcher y del lineup rival para generar un score.
    Retorna:
    {
      home_pitcher_score: float,  # 0-100, mayor = mejor pitcher
      away_pitcher_score: float,
      home_batting_score: float,  # 0-100, mayor = mejor lineup
      away_batting_score: float,
      total_adj: float,  # ajuste de carreras al total esperado
      nrfi_boost: float, # ajuste adicional a prob NRFI
    }
    Fórmula:
      pitcher_score = (100 - xfip*10) * 0.4 + (k_pct*100) * 0.3 + (100 - hard_hit_pct) * 0.3
      batting_score = xwoba*200 * 0.4 + hard_hit_pct * 0.3 + bb_pct*100 * 0.3
      total_adj = (batting_score_home - 50)/100 + (batting_score_away - 50)/100
                - (pitcher_score_home - 50)/100 - (pitcher_score_away - 50)/100
    """
    defaults_out = {
        "home_pitcher_score": 50.0,
        "away_pitcher_score": 50.0,
        "home_batting_score": 50.0,
        "away_batting_score": 50.0,
        "total_adj": 0.0,
        "nrfi_boost": 0.0,
    }

    def pitcher_score(stats: dict) -> float:
        xfip = stats.get("xfip", 4.0)
        k_pct = stats.get("k_pct", 22.0)
        hard_hit = stats.get("hard_hit_pct", 38.0)
        # normalizar k_pct: si viene como fracción (0-1), convertir a %
        if k_pct is not None and k_pct <= 1.0:
            k_pct = k_pct * 100
        if hard_hit is not None and hard_hit <= 1.0:
            hard_hit = hard_hit * 100
        score = (100 - (xfip or 4.0) * 10) * 0.4 + (k_pct or 22.0) * 0.3 + (100 - (hard_hit or 38.0)) * 0.3
        return max(0.0, min(100.0, score))

    def batting_score(stats: dict) -> float:
        xwoba = stats.get("xwoba", 0.320)
        hard_hit = stats.get("hard_hit_pct", 38.0)
        bb_pct = stats.get("bb_pct", 8.5)
        if hard_hit is not None and hard_hit <= 1.0:
            hard_hit = hard_hit * 100
        if bb_pct is not None and bb_pct <= 1.0:
            bb_pct = bb_pct * 100
        score = (xwoba or 0.320) * 200 * 0.4 + (hard_hit or 38.0) * 0.3 + (bb_pct or 8.5) * 100 * 0.3
        return max(0.0, min(100.0, score))

    try:
        home_abbr = TEAM_ABBR.get(home, home)
        away_abbr = TEAM_ABBR.get(away, away)

        hp_stats = get_pitcher_statcast(home_pitcher, season)
        ap_stats = get_pitcher_statcast(away_pitcher, season)
        hb_stats = get_team_batting_statcast(home_abbr, season)
        ab_stats = get_team_batting_statcast(away_abbr, season)

        hp_score = pitcher_score(hp_stats) if hp_stats else 50.0
        ap_score = pitcher_score(ap_stats) if ap_stats else 50.0
        hb_score = batting_score(hb_stats)
        ab_score = batting_score(ab_stats)

        total_adj = (
            (hb_score - 50) / 100
            + (ab_score - 50) / 100
            - (hp_score - 50) / 100
            - (ap_score - 50) / 100
        )

        # nrfi_boost: pitchers dominantes y lineups débiles aumentan prob NRFI
        nrfi_boost = ((hp_score - 50) + (ap_score - 50) - (hb_score - 50) - (ab_score - 50)) / 400

        return {
            "home_pitcher_score": round(hp_score, 2),
            "away_pitcher_score": round(ap_score, 2),
            "home_batting_score": round(hb_score, 2),
            "away_batting_score": round(ab_score, 2),
            "total_adj": round(total_adj, 4),
            "nrfi_boost": round(nrfi_boost, 4),
        }
    except Exception:
        return defaults_out
