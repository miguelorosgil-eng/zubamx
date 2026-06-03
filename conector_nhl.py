"""
Conector NHL — ESPN public API (sin key, sin SSL issues).
Base: https://site.api.espn.com/apis/site/v2/sports/hockey/nhl
"""
import time
import requests
import pandas as pd
from datetime import date, timedelta

BASE = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl"


def _get_scoreboard(date_str: str):
    """date_str: YYYYMMDD"""
    r = requests.get(f"{BASE}/scoreboard", params={"dates": date_str}, timeout=20)
    r.raise_for_status()
    return r.json().get("events", [])


def _parse_event(ev):
    comp = ev["competitions"][0]
    competitors = comp["competitors"]
    home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[1])
    away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[0])
    return {
        "home":       home["team"]["displayName"],
        "away":       away["team"]["displayName"],
        "home_score": int(home.get("score", 0) or 0),
        "away_score": int(away.get("score", 0) or 0),
        "status":     comp["status"]["type"]["name"],
        "date":       ev["date"][:10],
        "game_id":    ev["id"],
    }


def fetch_nhl_finished(season: str) -> pd.DataFrame:
    """
    Partidos finalizados de temporada regular NHL.
    season: "20242025" → temporada oct 2024 - abr 2025.
    """
    start_year = int(season[:4])
    start = date(start_year, 10, 1)
    end   = date(start_year + 1, 4, 30)

    rows = []
    current = start
    while current <= end:
        date_str = current.strftime("%Y%m%d")
        try:
            for ev in _get_scoreboard(date_str):
                p = _parse_event(ev)
                if p["status"] == "STATUS_FINAL" and (p["home_score"] + p["away_score"]) > 0:
                    rows.append(p)
            time.sleep(0.12)
        except Exception as e:
            print(f"  [NHL] {date_str}: {e}")
        current += timedelta(days=1)

    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    return df[["home", "away", "home_score", "away_score", "date", "game_id"]].reset_index(drop=True)


def fetch_nhl_upcoming(days: int = 7) -> pd.DataFrame:
    """Partidos programados en los próximos N días."""
    today = date.today()
    rows = []
    for delta in range(days + 1):
        d = today + timedelta(days=delta)
        try:
            for ev in _get_scoreboard(d.strftime("%Y%m%d")):
                p = _parse_event(ev)
                if p["status"] in ("STATUS_SCHEDULED", "STATUS_IN_PROGRESS"):
                    rows.append(p)
            time.sleep(0.12)
        except Exception as e:
            print(f"  [NHL upcoming] {d}: {e}")

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df["date"])
    return df[["home", "away", "date", "game_id"]].reset_index(drop=True)


def build_nhl_training(seasons: list) -> pd.DataFrame:
    """
    seasons: lista de strings ej. ["20232024", "20242025"]
    AVISO: descarga día a día → puede tardar ~1-2 min por temporada.
    """
    frames = []
    for s in seasons:
        print(f"  Fetching NHL season {s} (puede tardar ~1-2 min)...")
        try:
            df = fetch_nhl_finished(s)
            if not df.empty:
                frames.append(df)
                print(f"  NHL {s}: {len(df)} partidos")
            else:
                print(f"  NHL {s}: sin datos")
        except Exception as e:
            print(f"  Error NHL {s}: {e}")
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


if __name__ == "__main__":
    print("=== NHL Upcoming (próx. 7 días) ===")
    up = fetch_nhl_upcoming(days=7)
    print(up.to_string(index=False) if not up.empty else "  Sin partidos programados (offseason/playoffs)")

    print("\n=== NHL muestra (3 días enero 2025) ===")
    rows = []
    for d in ["20250115", "20250116", "20250117"]:
        for ev in _get_scoreboard(d):
            p = _parse_event(ev)
            if p["status"] == "STATUS_FINAL":
                rows.append(p)
        time.sleep(0.15)
    df = pd.DataFrame(rows)
    print(f"Juegos encontrados: {len(df)}")
    if not df.empty:
        print(df[["home", "away", "home_score", "away_score", "date"]].to_string(index=False))
