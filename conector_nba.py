"""
Conector NBA — ESPN public API (sin key, sin SSL issues).
Base: https://site.api.espn.com/apis/site/v2/sports/basketball/nba
"""
import time
import requests
import pandas as pd
from datetime import date, timedelta

BASE = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba"


def _get_scoreboard(date_str: str):
    """date_str: YYYYMMDD"""
    r = requests.get(f"{BASE}/scoreboard", params={"dates": date_str}, timeout=20)
    r.raise_for_status()
    return r.json().get("events", [])


def _parse_event(ev):
    comp = ev["competitions"][0]
    competitors = comp["competitors"]
    # ESPN: index 0 = away, index 1 = home (o según homeAway flag)
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


def fetch_nba_finished(season_str: str) -> pd.DataFrame:
    """
    Partidos finalizados de una temporada regular NBA.
    season_str: ej. "2024-25" → descarga oct-jun de esa temporada.
    """
    start_year = int(season_str.split("-")[0])
    # Temporada regular: oct inicio → abr fin
    start = date(start_year, 10, 1)
    end   = date(start_year + 1, 4, 30)

    rows = []
    current = start
    while current <= end:
        date_str = current.strftime("%Y%m%d")
        try:
            events = _get_scoreboard(date_str)
            for ev in events:
                parsed = _parse_event(ev)
                if parsed["status"] == "STATUS_FINAL" and parsed["home_score"] > 0:
                    rows.append(parsed)
            time.sleep(0.15)
        except Exception as e:
            print(f"  [NBA] {date_str}: {e}")
        current += timedelta(days=1)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df[["home", "away", "home_score", "away_score", "date", "game_id"]].reset_index(drop=True)


def fetch_nba_upcoming(days: int = 7) -> pd.DataFrame:
    """Partidos programados en los próximos N días."""
    today = date.today()
    rows  = []
    for delta in range(days + 1):
        d = today + timedelta(days=delta)
        try:
            events = _get_scoreboard(d.strftime("%Y%m%d"))
            for ev in events:
                parsed = _parse_event(ev)
                if parsed["status"] in ("STATUS_SCHEDULED", "STATUS_IN_PROGRESS"):
                    rows.append(parsed)
            time.sleep(0.15)
        except Exception as e:
            print(f"  [NBA upcoming] {d}: {e}")

    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df[["home", "away", "date", "game_id"]].reset_index(drop=True) if not df.empty else pd.DataFrame()


def build_nba_training(seasons: list) -> pd.DataFrame:
    """
    seasons: lista de strings ej. ["2022-23", "2023-24", "2024-25"]
    AVISO: descarga día a día → puede tardar varios minutos por temporada.
    """
    frames = []
    for s in seasons:
        print(f"  Fetching NBA season {s} (puede tardar ~1-2 min)...")
        try:
            df = fetch_nba_finished(s)
            if not df.empty:
                frames.append(df)
                print(f"  NBA {s}: {len(df)} partidos")
            else:
                print(f"  NBA {s}: sin datos")
        except Exception as e:
            print(f"  Error NBA {s}: {e}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


if __name__ == "__main__":
    print("=== NBA Upcoming (próx. 7 días) ===")
    up = fetch_nba_upcoming(days=7)
    print(up.to_string(index=False) if not up.empty else "  Sin partidos programados")

    print("\n=== NBA muestra (3 días enero 2025) ===")
    rows = []
    for d in ["20250115", "20250116", "20250117"]:
        evs = _get_scoreboard(d)
        for ev in evs:
            p = _parse_event(ev)
            if p["status"] == "STATUS_FINAL":
                rows.append(p)
        time.sleep(0.2)
    df = pd.DataFrame(rows)[["home", "away", "home_score", "away_score", "date"]]
    print(f"Juegos encontrados: {len(df)}")
    print(df.to_string(index=False))
