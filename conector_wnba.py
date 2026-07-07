"""
Conector WNBA — ESPN public API (sin key).
Base: https://site.api.espn.com/apis/site/v2/sports/basketball/wnba

La WNBA se modela como deporte de alto marcador (Normal), igual que la NBA.
Temporada regular: mayo → septiembre.
"""
import time
import requests
import pandas as pd
from datetime import date, timedelta

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/wnba"


def _get_scoreboard(date_str: str):
    """date_str: YYYYMMDD o rango YYYYMMDD-YYYYMMDD."""
    r = requests.get(f"{BASE}/scoreboard", params={"dates": date_str}, timeout=20)
    r.raise_for_status()
    return r.json().get("events", [])


def _parse_event(ev):
    comp = ev["competitions"][0]
    competitors = comp["competitors"]
    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[1])
    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[0])
    return {
        "home":    home["team"]["displayName"],
        "away":    away["team"]["displayName"],
        "home_score": int(home.get("score", 0) or 0),
        "away_score": int(away.get("score", 0) or 0),
        "status":  comp["status"]["type"]["name"],
        "date":    ev["date"][:10],
        "game_id": ev["id"],
    }


def fetch_wnba_finished(season_year: int) -> pd.DataFrame:
    """
    Partidos finalizados de una temporada WNBA (mayo-septiembre del año dado).
    ESPN acepta rangos de fecha, así que descargamos mes por mes (rápido).
    """
    frames = []
    for month_start, month_end in [
        (date(season_year, 5, 1),  date(season_year, 5, 31)),
        (date(season_year, 6, 1),  date(season_year, 6, 30)),
        (date(season_year, 7, 1),  date(season_year, 7, 31)),
        (date(season_year, 8, 1),  date(season_year, 8, 31)),
        (date(season_year, 9, 1),  date(season_year, 9, 30)),
        (date(season_year, 10, 1), date(season_year, 10, 20)),  # playoffs
    ]:
        rng = f"{month_start.strftime('%Y%m%d')}-{month_end.strftime('%Y%m%d')}"
        try:
            events = _get_scoreboard(rng)
            for ev in events:
                p = _parse_event(ev)
                if p["status"] == "STATUS_FINAL" and (p["home_score"] + p["away_score"]) > 0:
                    frames.append(p)
            time.sleep(0.2)
        except Exception as e:
            print(f"  [WNBA] {rng}: {e}")

    df = pd.DataFrame(frames)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df = df.drop_duplicates(subset=["game_id"])
    return df[["home", "away", "home_score", "away_score", "date", "game_id"]].reset_index(drop=True)


def fetch_wnba_upcoming(days: int = 3) -> pd.DataFrame:
    """Partidos programados en los próximos N días."""
    today = date.today()
    rng = f"{today.strftime('%Y%m%d')}-{(today + timedelta(days=days)).strftime('%Y%m%d')}"
    rows = []
    try:
        for ev in _get_scoreboard(rng):
            p = _parse_event(ev)
            if p["status"] in ("STATUS_SCHEDULED", "STATUS_IN_PROGRESS"):
                rows.append(p)
    except Exception as e:
        print(f"  [WNBA upcoming] {e}")
    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
        return df[["home", "away", "date", "game_id"]].reset_index(drop=True)
    return pd.DataFrame()


def build_wnba_training(seasons: list) -> pd.DataFrame:
    """seasons: lista de años int, ej. [2024, 2025, 2026]."""
    frames = []
    for y in seasons:
        print(f"  Fetching WNBA season {y}...")
        try:
            df = fetch_wnba_finished(y)
            if not df.empty:
                frames.append(df)
                print(f"  WNBA {y}: {len(df)} partidos")
        except Exception as e:
            print(f"  Error WNBA {y}: {e}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


if __name__ == "__main__":
    up = fetch_wnba_upcoming(days=3)
    print("=== WNBA próximos ===")
    print(up.to_string(index=False) if not up.empty else "  Sin partidos")
