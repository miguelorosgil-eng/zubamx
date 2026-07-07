"""
RECOMENDADOR DIARIO MAESTRO — revisa TODOS los mercados validados cada día.

Orquesta en una sola corrida:
  1. Béisbol MLB — 1er inning (reglas de ERA validadas, 603 juegos)
  2. Fútbol ligas de clubes — Over/Under 2.5 (validado 3,193 partidos)
     Aplica a las ligas activas (Brasil, MLS, Portugal, escandinavas en verano;
     top-5 europeas desde agosto).
  3. KBO/NPB — reporta estado de acumulación de datos.

Resuelve picks pendientes y reporta desempeño acumulado.

Uso: python recomendador_diario.py [YYYY-MM-DD]
"""
import sys
import time
import datetime as dt
import requests

import piloto_diario as beis
from motor_ligas_clubes import build_team_strength, evaluar_partido

ODDS_KEY = "0e72a2907fb18699be347a6507f018b3"
FD_KEY = "79f918e5365b4047899f7a70b619ed44"

# Ligas de clubes: (sport_key Odds API, código football-data, nombre, temporada actual)
LIGAS_CLUBES = [
    ("soccer_brazil_campeonato", "BSA", "Brasil Série A", 2025),
    ("soccer_usa_mls", None, "MLS", None),            # sin football-data en free tier
    ("soccer_epl", "PL", "Premier League", 2025),
    ("soccer_spain_la_liga", "PD", "La Liga", 2025),
    ("soccer_italy_serie_a", "SA", "Serie A", 2025),
    ("soccer_germany_bundesliga", "BL1", "Bundesliga", 2025),
    ("soccer_france_ligue_one", "FL1", "Ligue 1", 2025),
    ("soccer_portugal_primeira_liga", "PPL", "Primeira Liga", 2025),
]


def _fd_matches(code, season):
    """Partidos finalizados de la temporada (para fuerza de equipo)."""
    try:
        r = requests.get(f"https://api.football-data.org/v4/competitions/{code}/matches",
                         headers={"X-Auth-Token": FD_KEY},
                         params={"status": "FINISHED", "season": season}, timeout=30)
        if r.status_code != 200:
            return []
        out = []
        for m in r.json().get("matches", []):
            ft = m.get("score", {}).get("fullTime", {})
            if ft.get("home") is None:
                continue
            out.append({"home": m["homeTeam"]["name"], "away": m["awayTeam"]["name"],
                        "hg": ft["home"], "ag": ft["away"]})
        return out
    except Exception:
        return []


def _odds_totales(sport_key, date_str):
    """Juegos con línea de totales (O/U) para la fecha."""
    try:
        r = requests.get(f"https://api.the-odds-api.com/v4/sports/{sport_key}/odds",
                         params={"apiKey": ODDS_KEY, "regions": "eu",
                                 "markets": "totals", "oddsFormat": "decimal"}, timeout=20)
        if r.status_code != 200:
            return []
        out = []
        for ev in r.json():
            if ev.get("commence_time", "")[:10] != date_str:
                continue
            over = under = None
            for bk in ev.get("bookmakers", []):
                for mk in bk.get("markets", []):
                    if mk["key"] != "totals":
                        continue
                    for o in mk["outcomes"]:
                        if o.get("point") == 2.5:
                            if o["name"] == "Over":
                                over = o["price"]
                            else:
                                under = o["price"]
                if over and under:
                    break
            out.append({"home": ev["home_team"], "away": ev["away_team"],
                        "over": over, "under": under})
        return out
    except Exception:
        return []


def _match(nombre, equipos):
    """Fuzzy match de nombre de equipo (Odds API vs football-data)."""
    from difflib import SequenceMatcher
    best, score = None, 0
    for e in equipos:
        s = SequenceMatcher(None, nombre.lower(), e.lower()).ratio()
        if s > score:
            best, score = e, s
    return best if score > 0.6 else None


def recomendaciones_futbol(date_str):
    picks = []
    for sport_key, fd_code, nombre, season in LIGAS_CLUBES:
        juegos = _odds_totales(sport_key, date_str)
        if not juegos:
            continue
        if not fd_code:
            print(f"  ⚽ {nombre}: {len(juegos)} juego(s) pero sin datos de fuerza (omitido)")
            continue
        fuerza = build_team_strength(_fd_matches(fd_code, season))
        if not fuerza:
            continue
        equipos = list(fuerza.keys())
        for j in juegos:
            h = _match(j["home"], equipos); a = _match(j["away"], equipos)
            if not h or not a:
                continue
            res = evaluar_partido(fuerza, h, a, j["over"], j["under"])
            if res:
                picks.append({"liga": nombre, "partido": f"{j['away']} @ {j['home']}", **res})
        time.sleep(7)  # rate limit football-data
    return picks


def main(date_str):
    print(f"{'='*64}\n  RECOMENDADOR DIARIO — {date_str}\n{'='*64}\n")

    # 1. Béisbol 1er inning (resolver pendientes + picks de hoy)
    print("⚾ BÉISBOL — 1er inning")
    n = beis.resolver_pendientes()
    if n:
        print(f"  {n} pick(s) pendiente(s) resuelto(s).")
    beis.reporte_desempeno()
    bp = beis.picks_de_hoy(date_str)
    if bp:
        for p in bp:
            print(f"  • {p['partido']} → {p['pick']} (p={p['prob']:.0%}) | {p['pitcher_info']}")
    else:
        print("  Sin picks en zona extrema hoy.")

    # 2. Fútbol ligas de clubes (Over/Under 2.5)
    print("\n⚽ FÚTBOL — ligas de clubes (Over/Under 2.5)")
    fp = recomendaciones_futbol(date_str)
    if fp:
        for p in fp:
            print(f"  • [{p['liga']}] {p['partido']} → {p['pick']} "
                  f"(p={p['prob']:.0%}, proj {p['proj']}) | momio {p['odds']} EV {p['edge']:+.0%}")
    else:
        print("  Sin ligas activas con partidos hoy (top-5 europeas: desde agosto).")

    print("\n🇰🇷🇯🇵 KBO/NPB: acumulando datos (se activan al juntar ≥50 partidos).")
    print("\n  Recuerda: momio ≥1.70 en Caliente, stake plano, verificar alineaciones.")


if __name__ == "__main__":
    fecha = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()
    main(fecha)
