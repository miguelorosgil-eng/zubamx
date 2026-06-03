"""
Injuries en tiempo real para MLB, NHL y NBA.
MLB: MLB Stats API (gratis)
NHL/NBA: ESPN API (gratis)
Se usa para filtrar partidos con jugadores clave lesionados.
"""
import requests
import pandas as pd
from datetime import date

# Posiciones "clave" por deporte — si están en IL, afecta significativamente
MLB_KEY_POSITIONS = {"SP", "P"}   # Starting pitcher es el más crítico
NBA_KEY_POSITIONS = {"PG", "SG", "SF", "PF", "C"}
NHL_KEY_POSITIONS = {"G", "C", "LW", "RW", "D"}


def fetch_mlb_injuries(target_date=None):
    """
    Devuelve dict {team_name: [lista de lesionados]} con jugadores en IL.
    Fuente: MLB Stats API /injuries endpoint.
    """
    d = target_date or date.today().isoformat()
    url = "https://statsapi.mlb.com/api/v1/injuries"
    try:
        r = requests.get(url, params={"sportId": 1, "date": d}, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return {}

    out = {}
    for item in data.get("injuries", []):
        team = item.get("team", {}).get("name", "")
        player = item.get("person", {}).get("fullName", "")
        position = item.get("person", {}).get("primaryPosition", {}).get("abbreviation", "")
        status = item.get("status", "")
        if team:
            out.setdefault(team, []).append({
                "player": player,
                "position": position,
                "status": status,
            })
    return out


def fetch_nhl_injuries():
    """
    Lesionados NHL desde ESPN injury report.
    """
    url = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/injuries"
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return {}

    out = {}
    for item in data.get("injuries", []):
        team = item.get("team", {}).get("displayName", "")
        for inj in item.get("injuries", []):
            player = inj.get("athlete", {}).get("displayName", "")
            status = inj.get("status", "")
            pos = inj.get("athlete", {}).get("position", {}).get("abbreviation", "")
            if team:
                out.setdefault(team, []).append({
                    "player": player, "position": pos, "status": status
                })
    return out


def fetch_nba_injuries():
    """
    Lesionados NBA desde ESPN injury report.
    """
    url = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/injuries"
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
    except Exception:
        return {}

    out = {}
    for item in data.get("injuries", []):
        team = item.get("team", {}).get("displayName", "")
        for inj in item.get("injuries", []):
            player = inj.get("athlete", {}).get("displayName", "")
            status = inj.get("status", "")
            pos = inj.get("athlete", {}).get("position", {}).get("abbreviation", "")
            if team:
                out.setdefault(team, []).append({
                    "player": player, "position": pos, "status": status
                })
    return out


def get_injuries(sport: str, target_date=None) -> dict:
    """Dispatcher por deporte. Devuelve {team: [lesionados]}."""
    sport = sport.lower()
    if sport == "mlb":
        return fetch_mlb_injuries(target_date)
    elif sport == "nhl":
        return fetch_nhl_injuries()
    elif sport == "nba":
        return fetch_nba_injuries()
    return {}


def injury_summary(team: str, injuries: dict) -> str:
    """Devuelve string resumido de lesionados de un equipo."""
    inj = injuries.get(team, [])
    if not inj:
        return ""
    names = [f"{i['player']} ({i['position']})" for i in inj[:3]]
    suffix = f" +{len(inj)-3} más" if len(inj) > 3 else ""
    return f"🚑 IL: {', '.join(names)}{suffix}"


def has_pitcher_injured(home_team: str, away_team: str, injuries: dict, pitchers: list) -> bool:
    """True si el pitcher probable de algún equipo está en la IL."""
    if not pitchers:
        return False
    injured_names = set()
    for team in [home_team, away_team]:
        for inj in injuries.get(team, []):
            injured_names.add(inj["player"].lower())
    for p in pitchers:
        if p and p.lower() in injured_names:
            return True
    return False


if __name__ == "__main__":
    print("=== MLB Injuries ===")
    inj = fetch_mlb_injuries()
    for team, players in list(inj.items())[:5]:
        print(f"  {team}: {[p['player'] for p in players]}")
