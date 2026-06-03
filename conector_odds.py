"""
Conector The Odds API → cuotas de mercado (decimal, 1X2).
Se usa para alimentar market_odds al motor y detectar value bets automático.

Free tier: 500 req/mes. Cada llamada = 1 región x 1 market = 1 crédito.
"""

import requests
from difflib import SequenceMatcher

ODDS_API_KEY = "0e72a2907fb18699be347a6507f018b3"
ODDS_BASE = "https://api.the-odds-api.com/v4"

# mapeo liga Football-Data → sport_key de The Odds API
SPORT_KEYS = {
    # Béisbol
    "MLB": "baseball_mlb",
    # Baloncesto
    "NBA": "basketball_nba",
    # Hockey
    "NHL": "icehockey_nhl",
    # Ligas de fútbol (clubes)
    "PL":  "soccer_epl",
    "PD":  "soccer_spain_la_liga",
    "SA":  "soccer_italy_serie_a",
    "BL1": "soccer_germany_bundesliga",
    "FL1": "soccer_france_ligue_one",
    "PPL": "soccer_portugal_primeira_liga",
    "DED": "soccer_netherlands_eredivisie",
    "BSA": "soccer_brazil_campeonato",
    "CL":  "soccer_uefa_champs_league",
    "EL":  "soccer_uefa_europa_league",
    "CLI": "soccer_conmebol_copa_libertadores",
    # Competiciones internacionales
    "WC":  "soccer_fifa_world_cup",
    "EC":  "soccer_uefa_european_championship",
    "CA":  "soccer_conmebol_copa_america",
    "UCL": "soccer_uefa_nations_league",
}

PREFERRED_BOOK = "pinnacle"


def fetch_odds(league_code, region="eu"):
    """Devuelve lista de eventos con odds 1X2 decimales."""
    sport = SPORT_KEYS.get(league_code)
    if not sport:
        return []
    url = f"{ODDS_BASE}/sports/{sport}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": region,
        "markets": "h2h",
        "oddsFormat": "decimal",
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()

    events = []
    for ev in r.json():
        home, away = ev["home_team"], ev["away_team"]
        book = _pick_book(ev["bookmakers"])
        if not book:
            continue
        odds = _extract_h2h(book, home, away)
        if odds:
            events.append({
                "home": home, "away": away,
                "commence": ev["commence_time"][:10],
                "odds": odds, "book": book["title"],
            })
    return events


def _main_line_pair(outcomes, name_a, name_b):
    """
    De una lista de outcomes (que puede traer líneas alternativas), devuelve el
    par (A, B) de la LÍNEA PRINCIPAL: misma 'point' para ambos lados y precios
    lo más balanceados posible (~1.90/1.90). Descarta alternativas desbalanceadas.
    """
    by_point = {}
    for o in outcomes:
        pt = o.get("point")
        if pt is None:
            continue
        by_point.setdefault(pt, {})[o["name"]] = o
    best, best_balance = None, 1e9
    for pt, sides in by_point.items():
        a, b = sides.get(name_a), sides.get(name_b)
        if not a or not b:
            continue
        # |1/odds_a - 1/odds_b| → mínimo = línea más balanceada = línea principal
        balance = abs(1.0 / a["price"] - 1.0 / b["price"])
        if balance < best_balance:
            best, best_balance = (a, b), balance
    return best


def fetch_market_odds(league_code, region="us"):
    """
    Descarga cuotas de totals (O/U) y spreads (hándicap) para todos los eventos.
    Devuelve lista: [{home, away, commence, totals:{...}, spread:{...}, book}].
    Cuesta 1 crédito por mercado solicitado (2 mercados = 2 créditos por liga).
    """
    sport = SPORT_KEYS.get(league_code)
    if not sport:
        return []
    url = f"{ODDS_BASE}/sports/{sport}/odds"
    params = {
        "apiKey": ODDS_API_KEY,
        "regions": region,
        "markets": "totals,spreads",
        "oddsFormat": "decimal",
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()

    events = []
    for ev in r.json():
        home, away = ev["home_team"], ev["away_team"]
        book = _pick_book(ev["bookmakers"])
        if not book:
            continue
        entry = {"home": home, "away": away,
                 "commence": ev["commence_time"][:10], "book": book["title"]}
        for m in book.get("markets", []):
            if m["key"] == "totals":
                pair = _main_line_pair(m["outcomes"], "Over", "Under")
                if pair:
                    over, under = pair
                    entry["totals"] = {
                        "line": over["point"],
                        "over_odds": over["price"],
                        "under_odds": under["price"],
                    }
            elif m["key"] == "spreads":
                pair = _main_line_pair(m["outcomes"], home, away)
                if pair:
                    oh, oa = pair
                    entry["spread"] = {
                        "line": oh["point"],       # hándicap del LOCAL
                        "home_odds": oh["price"],
                        "away_odds": oa["price"],
                    }
        if "totals" in entry or "spread" in entry:
            events.append(entry)
    return events


def fetch_opening_odds(league_code, region="eu", date_str=None):
    """
    Igual que fetch_odds pero garantiza que la primera corrida del día
    guarda las odds como opening lines en caché.

    Si ya hay caché de apertura, lo carga en lugar de consumir un crédito API.
    Esto asegura que la opening line se preserva para tracking de line movement.
    """
    import json
    import os
    from datetime import date as _date

    if date_str is None:
        date_str = str(_date.today())

    cache_dir = "_cache"
    os.makedirs(cache_dir, exist_ok=True)
    cache_path = os.path.join(cache_dir, f"opening_lines_{league_code}_{date_str}.json")

    # Si ya hay opening lines guardadas, devolvemos los eventos del caché
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            data = json.load(f)
        events = []
        for key, ev in data.items():
            events.append({
                "home": ev["home"],
                "away": ev["away"],
                "commence": date_str,
                "odds": ev["odds"],
                "book": "cached_opening",
            })
        return events

    # Primera corrida del día: obtener odds de la API y guardar como opening
    events = fetch_odds(league_code, region)

    if events:
        from line_movement import save_opening_lines
        save_opening_lines(league_code, events, date_str)

    return events


def fetch_odds_multi(league_codes, region="eu"):
    """Descarga odds para varias ligas de golpe, ahorrando créditos."""
    all_events = {}
    for code in league_codes:
        sport = SPORT_KEYS.get(code)
        if not sport:
            continue
        try:
            evs = fetch_odds(code, region)
            all_events[code] = evs
        except Exception as e:
            print(f"  ⚠️  Odds {code}: {e}")
            all_events[code] = []
    return all_events


def _pick_book(bookmakers):
    for b in bookmakers:
        if b["key"] == PREFERRED_BOOK:
            return b
    return bookmakers[0] if bookmakers else None


def _extract_h2h(book, home, away):
    for m in book["markets"]:
        if m["key"] != "h2h":
            continue
        d = {o["name"]: o["price"] for o in m["outcomes"]}
        # Fútbol (con empate)
        if home in d and away in d and "Draw" in d:
            return {"home": d[home], "draw": d["Draw"], "away": d[away]}
        # Deportes sin empate (MLB, NBA, NHL) — buscar por fuzzy si el nombre no coincide exacto
        if home in d and away in d:
            return {"home": d[home], "draw": None, "away": d[away]}
        # Fallback: tomar las dos primeras cuotas no-Draw
        teams = [k for k in d if k != "Draw"]
        if len(teams) == 2:
            # Emparejar por similitud
            scores_h = [(k, SequenceMatcher(None, _norm(home), _norm(k)).ratio()) for k in teams]
            scores_a = [(k, SequenceMatcher(None, _norm(away), _norm(k)).ratio()) for k in teams]
            best_h = max(scores_h, key=lambda x: x[1])
            best_a = max(scores_a, key=lambda x: x[1])
            if best_h[1] > 0.45 and best_a[1] > 0.45 and best_h[0] != best_a[0]:
                return {"home": d[best_h[0]], "draw": None, "away": d[best_a[0]]}
    return None


# ---------- Matching de nombres entre APIs ----------
# NHL: city+nickname combos that differ between sources
_NHL_ALIASES = {
    "canadiens": "montreal canadiens",
    "habs": "montreal canadiens",
    "hurricanes": "carolina hurricanes",
    "canes": "carolina hurricanes",
    "maple leafs": "toronto maple leafs",
    "leafs": "toronto maple leafs",
    "blue jackets": "columbus blue jackets",
    "golden knights": "vegas golden knights",
    "knights": "vegas golden knights",
    "kraken": "seattle kraken",
    "wild": "minnesota wild",
    "avalanche": "colorado avalanche",
    "avs": "colorado avalanche",
    "lightning": "tampa bay lightning",
    "bolts": "tampa bay lightning",
    "panthers": "florida panthers",
    "bruins": "boston bruins",
    "rangers": "new york rangers",
    "islanders": "new york islanders",
    "devils": "new jersey devils",
    "flyers": "philadelphia flyers",
    "capitals": "washington capitals",
    "penguins": "pittsburgh penguins",
    "sabres": "buffalo sabres",
    "senators": "ottawa senators",
    "canadians": "montreal canadiens",   # occasional typo in feeds
}


def _norm(name):
    n = name.lower()
    # NHL alias lookup first (nickname-only to canonical)
    if n in _NHL_ALIASES:
        return _NHL_ALIASES[n]
    for suf in [" fc", " cf", " afc", " ac", " sc", " bc",
                " 1909", " calcio", " club", " de futbol",
                " football club", " soccer club"]:
        n = n.replace(suf, "")
    return n.strip()


def _similar(a, b):
    return SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def match_team(fd_name, odds_names, threshold=0.6):
    best, score = None, 0.0
    for on in odds_names:
        s = _similar(fd_name, on)
        if s > score:
            best, score = on, s
    return best if score >= threshold else None


def get_match_odds(fd_home, fd_away, odds_events):
    odds_teams = set()
    for e in odds_events:
        odds_teams.add(e["home"]); odds_teams.add(e["away"])

    oh = match_team(fd_home, odds_teams)
    oa = match_team(fd_away, odds_teams)
    if not oh or not oa:
        return None
    for e in odds_events:
        if e["home"] == oh and e["away"] == oa:
            odds = e["odds"]
            if odds.get("draw") is not None:
                return [odds["home"], odds["draw"], odds["away"]]
            return [odds["home"], odds["away"]]  # sin empate (MLB/NBA/NHL)
    return None
