"""
Líneas históricas de odds para entrenar el modelo con movimiento de línea.
Fuente: The Odds API historical endpoint (gratis hasta 500 eventos).
"""

import os
from datetime import datetime, timedelta

import pandas as pd
import requests

from conector_odds import ODDS_API_KEY

ODDS_HISTORICAL_BASE = "https://api.the-odds-api.com/v4/historical/sports"
CACHE_DIR = "_cache"


def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def fetch_historical_odds(sport_key: str, date_str: str,
                          api_key: str) -> list:
    """
    Descarga odds históricas de una fecha específica.
    URL: https://api.the-odds-api.com/v4/historical/sports/{sport_key}/odds/
    params: apiKey, date (ISO8601: 2025-10-15T12:00:00Z), regions=us, markets=h2h
    Devuelve lista de eventos con {home, away, odds_open, odds_close} o [] si falla.
    """
    try:
        url = f"{ODDS_HISTORICAL_BASE}/{sport_key}/odds/"
        params = {
            "apiKey": api_key,
            "date": date_str,
            "regions": "us",
            "markets": "h2h",
            "oddsFormat": "decimal",
        }
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        events = data.get("data", data) if isinstance(data, dict) else data
        if not isinstance(events, list):
            return []

        results = []
        for event in events:
            home = event.get("home_team", "")
            away = event.get("away_team", "")
            bookmakers = event.get("bookmakers", [])

            home_price = None
            away_price = None

            for bm in bookmakers:
                for market in bm.get("markets", []):
                    if market.get("key") != "h2h":
                        continue
                    for outcome in market.get("outcomes", []):
                        if outcome.get("name") == home:
                            home_price = outcome.get("price")
                        elif outcome.get("name") == away:
                            away_price = outcome.get("price")
                    if home_price and away_price:
                        break
                if home_price and away_price:
                    break

            if home and away:
                results.append({
                    "home": home,
                    "away": away,
                    "odds_open": home_price,
                    "odds_close": home_price,  # histórico solo tiene un snapshot
                    "away_odds_open": away_price,
                    "away_odds_close": away_price,
                    "date": date_str,
                })

        return results
    except Exception:
        return []


def build_odds_history(sport_key: str, start_date: str, end_date: str,
                       api_key: str, sample_days: int = 30) -> pd.DataFrame:
    """
    Construye historial de odds para un rango de fechas.
    Muestrea cada sample_days días (para no agotar créditos).
    Devuelve DataFrame con columnas: date, home, away, open_home, open_away,
    close_home, close_away, move_home, move_away, sharp_side.
    Guarda en _cache/odds_history_{sport_key}.csv
    """
    _ensure_cache_dir()
    cache_path = os.path.join(CACHE_DIR, f"odds_history_{sport_key}.csv")

    if os.path.exists(cache_path):
        return pd.read_csv(cache_path)

    try:
        start_dt = datetime.fromisoformat(start_date)
        end_dt = datetime.fromisoformat(end_date)
    except ValueError:
        return pd.DataFrame()

    all_events = []
    current = start_dt
    while current <= end_dt:
        date_str = current.strftime("%Y-%m-%dT12:00:00Z")
        events = fetch_historical_odds(sport_key, date_str, api_key)
        all_events.extend(events)
        current += timedelta(days=sample_days)

    if not all_events:
        return pd.DataFrame(columns=[
            "date", "home", "away", "open_home", "open_away",
            "close_home", "close_away", "move_home", "move_away", "sharp_side"
        ])

    rows = []
    for ev in all_events:
        open_home = ev.get("odds_open") or 2.0
        open_away = ev.get("away_odds_open") or 2.0
        close_home = ev.get("odds_close") or open_home
        close_away = ev.get("away_odds_close") or open_away

        move_home = close_home - open_home
        move_away = close_away - open_away

        # sharp side: si la línea bajó (cuota más baja = favorito reforzado),
        # se considera que el dinero sharp está en ese lado
        if move_home < move_away:
            sharp_side = ev.get("home", "")
        elif move_away < move_home:
            sharp_side = ev.get("away", "")
        else:
            sharp_side = ""

        rows.append({
            "date": ev.get("date", ""),
            "home": ev.get("home", ""),
            "away": ev.get("away", ""),
            "open_home": open_home,
            "open_away": open_away,
            "close_home": close_home,
            "close_away": close_away,
            "move_home": round(move_home, 4),
            "move_away": round(move_away, 4),
            "sharp_side": sharp_side,
        })

    df = pd.DataFrame(rows)
    df.to_csv(cache_path, index=False)
    return df


def get_line_movement_signal(home: str, away: str,
                              odds_history_df: pd.DataFrame) -> dict:
    """
    Dado el historial, calcula la señal histórica de movimiento de línea:
    - % de veces que el equipo local ganó cuando la línea bajó (más caro)
    - % de veces que ganó el sharp side histórico
    Devuelve {home_win_when_line_drops: float, sharp_win_rate: float}
    """
    defaults = {"home_win_when_line_drops": 0.5, "sharp_win_rate": 0.52}

    try:
        if odds_history_df.empty:
            return defaults

        required_cols = {"home", "away", "move_home", "sharp_side"}
        if not required_cols.issubset(odds_history_df.columns):
            return defaults

        # filtrar partidos con alguno de estos equipos
        mask = (
            odds_history_df["home"].str.contains(home, case=False, na=False) |
            odds_history_df["away"].str.contains(away, case=False, na=False) |
            odds_history_df["home"].str.contains(away, case=False, na=False) |
            odds_history_df["away"].str.contains(home, case=False, na=False)
        )
        df_filtered = odds_history_df[mask].copy()

        if df_filtered.empty:
            # usar todo el historial como base estadística
            df_filtered = odds_history_df.copy()

        # % de veces que la línea del local bajó (cuota disminuyó = favorito)
        line_drop_mask = df_filtered["move_home"] < 0
        n_line_drops = line_drop_mask.sum()

        if "result_home" in df_filtered.columns and n_line_drops > 0:
            home_wins_when_drop = df_filtered[line_drop_mask]["result_home"].mean()
        else:
            # sin resultado conocido, usar prior basado en cuántas veces bajó
            home_win_when_line_drops = 0.55 if n_line_drops > len(df_filtered) * 0.4 else 0.5
            home_wins_when_drop = home_win_when_line_drops

        # sharp win rate
        if "result_home" in df_filtered.columns and "sharp_side" in df_filtered.columns:
            sharp_df = df_filtered[df_filtered["sharp_side"] != ""]
            if not sharp_df.empty:
                sharp_wins = (
                    (sharp_df["sharp_side"] == sharp_df["home"]) & (sharp_df["result_home"] == 1) |
                    (sharp_df["sharp_side"] == sharp_df["away"]) & (sharp_df["result_home"] == 0)
                )
                sharp_win_rate = float(sharp_wins.mean())
            else:
                sharp_win_rate = 0.52
        else:
            sharp_win_rate = 0.52

        return {
            "home_win_when_line_drops": round(float(home_wins_when_drop), 4),
            "sharp_win_rate": round(sharp_win_rate, 4),
        }
    except Exception:
        return defaults
