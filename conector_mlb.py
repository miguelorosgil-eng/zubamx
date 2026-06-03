"""
Conector MLB Stats API (gratis, sin API key)
Base: https://statsapi.mlb.com/api/v1
"""
import time
import requests
import pandas as pd
from datetime import date, timedelta

BASE = "https://statsapi.mlb.com/api/v1"


def _get(path: str, params: dict = None) -> dict:
    url = BASE + path
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


_ERA_CACHE = {}


def _pitcher_era(pitcher_id, season):
    """ERA de temporada de un pitcher (con cache). Devuelve None si no hay datos."""
    if not pitcher_id:
        return None
    key = (pitcher_id, season)
    if key in _ERA_CACHE:
        return _ERA_CACHE[key]
    try:
        data = _get(f"/people/{pitcher_id}/stats",
                    {"stats": "season", "group": "pitching", "season": season})
        splits = data.get("stats", [{}])[0].get("splits", [])
        era = float(splits[0]["stat"]["era"]) if splits else None
    except Exception:
        era = None
    _ERA_CACHE[key] = era
    return era


def fetch_probable_pitchers(target_date=None, season=None):
    """
    Pitchers abridores probables + su ERA para los juegos de una fecha.
    Devuelve lista: [{home, away, home_sp, away_sp, era_home_sp, era_away_sp}].
    Usado para el mercado NRFI (No-Run First Inning).
    """
    d = target_date or date.today().isoformat()
    season = season or int(d[:4])
    data = _get("/schedule", {"sportId": 1, "date": d, "hydrate": "probablePitcher"})
    rows = []
    for day in data.get("dates", []):
        for g in day.get("games", []):
            home_t = g["teams"]["home"]
            away_t = g["teams"]["away"]
            hp = home_t.get("probablePitcher", {}) or {}
            ap = away_t.get("probablePitcher", {}) or {}
            # ERA: intenta temporada actual; si no hay, la anterior
            era_h = _pitcher_era(hp.get("id"), season) or _pitcher_era(hp.get("id"), season - 1)
            era_a = _pitcher_era(ap.get("id"), season) or _pitcher_era(ap.get("id"), season - 1)
            time.sleep(0.1)
            rows.append({
                "home": home_t["team"]["name"],
                "away": away_t["team"]["name"],
                "home_sp": hp.get("fullName"),
                "away_sp": ap.get("fullName"),
                "era_home_sp": era_h,
                "era_away_sp": era_a,
            })
    return rows


def fetch_mlb_finished(season: int) -> pd.DataFrame:
    """Devuelve partidos finalizados de una temporada regular."""
    params = {
        "sportId": 1,
        "gameType": "R",
        "season": season,
        "hydrate": "linescore",
    }
    data = _get("/schedule", params)
    rows = []
    for day in data.get("dates", []):
        for game in day.get("games", []):
            if game.get("status", {}).get("abstractGameState") != "Final":
                continue
            ls = game.get("linescore", {})
            teams = game.get("teams", {})
            home_score = ls.get("teams", {}).get("home", {}).get("runs")
            away_score = ls.get("teams", {}).get("away", {}).get("runs")
            if home_score is None or away_score is None:
                continue
            rows.append({
                "home": teams["home"]["team"]["name"],
                "away": teams["away"]["team"]["name"],
                "home_score": int(home_score),
                "away_score": int(away_score),
                "date": day["date"],
                "game_id": game["gamePk"],
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
    return df


def fetch_mlb_upcoming(days: int = 7) -> pd.DataFrame:
    """Devuelve partidos programados para los próximos N días."""
    today = date.today()
    end = today + timedelta(days=days)
    params = {
        "sportId": 1,
        "gameType": "R",
        "startDate": today.isoformat(),
        "endDate": end.isoformat(),
    }
    data = _get("/schedule", params)
    rows = []
    for day in data.get("dates", []):
        for game in day.get("games", []):
            state = game.get("status", {}).get("abstractGameState", "")
            if state == "Final":
                continue
            teams = game.get("teams", {})
            rows.append({
                "home": teams["home"]["team"]["name"],
                "away": teams["away"]["team"]["name"],
                "date": day["date"],
                "game_id": game["gamePk"],
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)
    return df


def build_mlb_training(seasons: list) -> pd.DataFrame:
    """Concatena temporadas para entrenamiento."""
    frames = []
    for s in seasons:
        print(f"  Fetching MLB season {s}...")
        try:
            df = fetch_mlb_finished(s)
            if not df.empty:
                df["season"] = s
                frames.append(df)
        except Exception as e:
            print(f"  Error season {s}: {e}")
        time.sleep(0.5)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


if __name__ == "__main__":
    print("=== MLB Upcoming ===")
    upcoming = fetch_mlb_upcoming()
    print(upcoming.head(10))

    print("\n=== MLB 2024 sample ===")
    hist = fetch_mlb_finished(2024)
    print(f"Total games: {len(hist)}")
    print(hist.tail(5))
