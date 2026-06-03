"""
Conector Football-Data.org → formato del motor.
Descarga partidos finalizados (con marcador) y próximos fixtures.
Free tier: 10 req/min, ligas top europeas + competiciones internacionales.
"""

import time
import requests
import pandas as pd

API_KEY = "79f918e5365b4047899f7a70b619ed44"
BASE = "https://api.football-data.org/v4"
HEADERS = {"X-Auth-Token": API_KEY}

# Ligas de clubes (free tier)
CLUB_LEAGUES = {
    "PL":  "Premier League (Inglaterra)",
    "PD":  "La Liga (España)",
    "SA":  "Serie A (Italia)",
    "BL1": "Bundesliga (Alemania)",
    "FL1": "Ligue 1 (Francia)",
    "PPL": "Primeira Liga (Portugal)",
    "DED": "Eredivisie (Holanda)",
    "BSA": "Brasileirao Serie A",
    "CL":  "UEFA Champions League",
    "EL":  "UEFA Europa League",
    "CLI": "Copa Libertadores",
}

# Competiciones nacionales / mundiales
INTL_LEAGUES = {
    "WC":  "Mundial FIFA 2026",
    "EC":  "Eurocopa (UEFA Euro)",
    "CA":  "Copa América",
    "WCQ": "Clasificatorio Mundial (UEFA)",
    "UCL": "UEFA Nations League",
}

LEAGUES = {**CLUB_LEAGUES, **INTL_LEAGUES}

# Competiciones donde el free tier da histórico sin temporada explícita
# Para el Mundial no hay histórico libre → entrenamos con Euro 2024 + Nations League
WC_TRAINING_SOURCES = ["EC"]   # competiciones de selecciones con data disponible

ALWAYS_CURRENT = {"WC", "EC", "CA", "WCQ", "UCL"}


def _get(url, params=None, retry=1):
    last_err = None
    for attempt in range(retry + 1):
        try:
            r = requests.get(url, headers=HEADERS, params=params, timeout=30)
            if r.status_code == 429:
                wait = 12 if attempt == 0 else 20
                print(f"    ⏳ Rate limit — esperando {wait}s...")
                time.sleep(wait)
                continue
            r.raise_for_status()
            return r.json()
        except requests.exceptions.SSLError as e:
            # SSL intermitente en este entorno → 1 reintento corto y seguir
            last_err = e
            time.sleep(1)
            continue
    if last_err:
        raise last_err
    r.raise_for_status()


def fetch_finished(league_code, season=None):
    """Partidos FINALIZADOS (con goles) de una competición/temporada.
    season: año de inicio, ej. 2024 = temporada 2024/25. None = actual."""
    params = {"status": "FINISHED"}
    if season and league_code not in ALWAYS_CURRENT:
        params["season"] = season
    data = _get(f"{BASE}/competitions/{league_code}/matches", params)
    rows = []
    for m in data.get("matches", []):
        ft = m["score"]["fullTime"]
        if ft["home"] is None:
            continue
        rows.append({
            "home": m["homeTeam"]["name"],
            "away": m["awayTeam"]["name"],
            "hg":   ft["home"],
            "ag":   ft["away"],
            "date": m["utcDate"][:10],
            "league": league_code,
            "stage": m.get("stage", "REGULAR_SEASON"),
        })
    return pd.DataFrame(rows)


def fetch_upcoming(league_code):
    """Próximos fixtures (SCHEDULED o TIMED) — para predecir."""
    rows = []
    for status in ("SCHEDULED", "TIMED"):
        try:
            data = _get(f"{BASE}/competitions/{league_code}/matches",
                        {"status": status})
            for m in data.get("matches", []):
                rows.append({
                    "home":  m["homeTeam"]["name"],
                    "away":  m["awayTeam"]["name"],
                    "date":  m["utcDate"][:10],
                    "league": league_code,
                    "stage": m.get("stage", "REGULAR_SEASON"),
                })
        except Exception:
            pass
    return pd.DataFrame(rows).drop_duplicates(subset=["home", "away", "date"])


def build_training_set(league_code, seasons):
    """Concatena varias temporadas (o solo la actual para torneos) para entrenar.
    Para el Mundial usa EC (Euro) como proxy de selecciones nacionales."""
    frames = []

    # WC no tiene histórico libre → usamos Euro 2024 como training de selecciones
    if league_code == "WC":
        print("  ℹ️  WC histórico no disponible en free tier.")
        print("     Entrenando con datos de selecciones de: EC (Euro 2024) ...")
        for src in WC_TRAINING_SOURCES:
            try:
                df = fetch_finished(src)
                if not df.empty:
                    df["league"] = src
                    frames.append(df)
                    print(f"  {src}: {len(df)} partidos de selecciones")
                time.sleep(6.5)
            except Exception as e:
                print(f"  {src}: ERROR {e}")
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    if league_code in ALWAYS_CURRENT:
        try:
            df = fetch_finished(league_code)
            if not df.empty:
                frames.append(df)
                print(f"  {league_code} (actual): {len(df)} partidos")
        except Exception as e:
            print(f"  {league_code}: ERROR {e}")
        time.sleep(6.5)
    else:
        for s in seasons:
            try:
                df = fetch_finished(league_code, season=s)
                frames.append(df)
                print(f"  {league_code} {s}: {len(df)} partidos")
                time.sleep(6.5)
            except Exception as e:
                print(f"  {league_code} {s}: ERROR {e}")

    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


if __name__ == "__main__":
    print("Test conexión Football-Data.org...")
    df = fetch_finished("PL")
    print(f"Premier League temporada actual: {len(df)} partidos finalizados")
    print(df.tail(3).to_string(index=False))
