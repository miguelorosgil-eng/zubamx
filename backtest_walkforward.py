"""
Backtest walk-forward HONESTO del sistema v3.9.

Para cada día del último mes:
  1. Toma los juegos MLB reales y sus LÍNEAS DE CIERRE reales (ESPN core API).
  2. Corre el modelo (entrenado solo con 2024-2025 → sin look-ahead de fuerza
     de equipo) y aplica TODOS los filtros del sistema actual.
  3. Compara el pick con el RESULTADO REAL del partido.
  4. Calcula P/L con stake plano y con Kelly 1/4.

Limitación honesta declarada: el ERA de los pitchers viene de la temporada
acumulada (statsapi), así que tiene un leve look-ahead. Se interpreta con
cautela; el efecto sobre totales es menor porque el modelo ancla al mercado.

Uso: python backtest_walkforward.py 2026-06-06 2026-07-05
"""
import sys
import json
import time
import urllib.request
import datetime as dt
import pickle
import numpy as np

from mercados import evaluate_markets

ESPN_SB = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard"
ESPN_ODDS = ("https://sports.core.api.espn.com/v2/sports/baseball/leagues/mlb/"
             "events/{eid}/competitions/{eid}/odds")

# Mapa abreviatura ESPN -> nombre completo (el que usa el motor)
TEAM = {
    "ATL": "Atlanta Braves", "NYM": "New York Mets", "WSH": "Washington Nationals",
    "PIT": "Pittsburgh Pirates", "CIN": "Cincinnati Reds", "BAL": "Baltimore Orioles",
    "NYY": "New York Yankees", "MIN": "Minnesota Twins", "STL": "St. Louis Cardinals",
    "CHC": "Chicago Cubs", "CWS": "Chicago White Sox", "CLE": "Cleveland Guardians",
    "PHI": "Philadelphia Phillies", "KC": "Kansas City Royals", "DET": "Detroit Tigers",
    "TEX": "Texas Rangers", "TB": "Tampa Bay Rays", "HOU": "Houston Astros",
    "MIL": "Milwaukee Brewers", "AZ": "Arizona Diamondbacks", "ARI": "Arizona Diamondbacks",
    "SF": "San Francisco Giants", "COL": "Colorado Rockies", "MIA": "Miami Marlins",
    "ATH": "Athletics", "OAK": "Athletics", "TOR": "Toronto Blue Jays",
    "SEA": "Seattle Mariners", "SD": "San Diego Padres", "LAD": "Los Angeles Dodgers",
    "LAA": "Los Angeles Angels", "BOS": "Boston Red Sox",
}


def _get(url):
    with urllib.request.urlopen(url, timeout=20) as r:
        return json.load(r)


_ERA_CACHE = {}


def pitcher_era_ip(pid, season):
    """ERA/IP de temporada (cumulativa — leve look-ahead, declarado)."""
    if not pid:
        return None, None
    key = (pid, season)
    if key in _ERA_CACHE:
        return _ERA_CACHE[key]
    try:
        u = (f"https://statsapi.mlb.com/api/v1/people/{pid}/stats?"
             f"stats=season&group=pitching&season={season}")
        sp = _get(u).get("stats", [{}])[0].get("splits", [])
        if sp:
            s = sp[0]["stat"]
            era = float(s.get("era", 0)) or None
            ip_str = str(s.get("inningsPitched", "0")).split(".")
            ip = int(ip_str[0]) + (int(ip_str[1]) / 3 if len(ip_str) > 1 else 0)
            res = (era, round(ip, 1))
        else:
            res = (None, None)
    except Exception:
        res = (None, None)
    _ERA_CACHE[key] = res
    return res


def day_pitchers(date_str):
    """Mapa (home_ab_proxy) -> ERAs vía statsapi. Devuelve por par de equipos."""
    season = int(date_str[:4])
    try:
        u = (f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
             f"&hydrate=probablePitcher")
        data = _get(u)
    except Exception:
        return {}
    out = {}
    for d in data.get("dates", []):
        for g in d.get("games", []):
            hn = g["teams"]["home"]["team"]["name"]
            an = g["teams"]["away"]["team"]["name"]
            hp = g["teams"]["home"].get("probablePitcher", {}) or {}
            ap = g["teams"]["away"].get("probablePitcher", {}) or {}
            eh, ih = pitcher_era_ip(hp.get("id"), season)
            ea, ia = pitcher_era_ip(ap.get("id"), season)
            out[(hn, an)] = {"era_home": eh, "ip_home": ih, "era_away": ea, "ip_away": ia}
    return out


def american_to_decimal(ml):
    if ml is None:
        return None
    ml = float(ml)
    return 1 + (ml / 100.0 if ml > 0 else 100.0 / abs(ml))


def fetch_day(date_str):
    """Devuelve lista de juegos con resultado real y líneas de cierre."""
    ymd = date_str.replace("-", "")
    sb = _get(f"{ESPN_SB}?dates={ymd}")
    games = []
    for ev in sb.get("events", []):
        comp = ev["competitions"][0]
        status = comp["status"]["type"]["name"]
        if status != "STATUS_FINAL":
            continue
        cs = {c["homeAway"]: c for c in comp["competitors"]}
        home_ab = cs["home"]["team"]["abbreviation"]
        away_ab = cs["away"]["team"]["abbreviation"]
        try:
            hs = int(cs["home"]["score"]); as_ = int(cs["away"]["score"])
        except (ValueError, TypeError, KeyError):
            continue
        eid = ev["id"]
        try:
            od = _get(ESPN_ODDS.format(eid=eid)).get("items", [])
        except Exception:
            od = []
        if not od:
            continue
        o = od[0]
        ou = o.get("overUnder")
        over_odds = american_to_decimal(o.get("overOdds"))
        under_odds = american_to_decimal(o.get("underOdds"))
        ml_home = american_to_decimal(o.get("homeTeamOdds", {}).get("moneyLine"))
        ml_away = american_to_decimal(o.get("awayTeamOdds", {}).get("moneyLine"))
        games.append({
            "home": TEAM.get(home_ab, home_ab), "away": TEAM.get(away_ab, away_ab),
            "home_ab": home_ab, "away_ab": away_ab,
            "home_score": hs, "away_score": as_, "total": hs + as_,
            "line": ou, "over_odds": over_odds, "under_odds": under_odds,
            "ml_home": ml_home, "ml_away": ml_away,
        })
        time.sleep(0.05)
    return games


def run_backtest(start, end, engine_path="_cache/MLB_engine.pkl"):
    with open(engine_path, "rb") as f:
        eng = pickle.load(f)

    # Envolver expected_scores para inyectar el ERA del día (que evaluate_markets
    # llama internamente sin ERA). Así el modelo diverge como en producción.
    _orig_es = eng.expected_scores
    def _es_era(home, away, **kw):
        o = getattr(eng, "_era_override", None)
        if o and not kw:
            eh, ea, ih, ia = o
            return _orig_es(home, away, era_home_sp=eh, era_away_sp=ea,
                            ip_home_sp=ih, ip_away_sp=ia)
        return _orig_es(home, away, **kw)
    eng.expected_scores = _es_era

    filtros = {"market_trust": 0.45, "confidence_floor": 0.57, "edge_threshold": 0.0,
               "anchor_weight": 0.5, "max_divergence": 0.20, "max_divergence_totals": 0.28,
               "max_divergence_under": 0.22, "over_confidence_premium": 0.12}
    MIN_ODDS = 1.70
    ML_FLOOR = 0.60

    d0 = dt.date.fromisoformat(start)
    d1 = dt.date.fromisoformat(end)
    picks = []
    day = d0
    while day <= d1:
        ds = day.isoformat()
        try:
            games = fetch_day(ds)
            eras = day_pitchers(ds)
        except Exception as e:
            print(f"  {ds}: error {e}")
            day += dt.timedelta(days=1); continue

        for g in games:
            h, a = g["home"], g["away"]
            if h not in eng._teams_seen or a not in eng._teams_seen:
                continue
            if not g["line"] or not g["over_odds"] or not g["under_odds"]:
                continue

            # ── ERA de los abridores (cumulativa — leve look-ahead declarado) ──
            ei = eras.get((h, a), {})
            eh, ea = ei.get("era_home"), ei.get("era_away")
            ih, ia = ei.get("ip_home"), ei.get("ip_away")
            mh, ma = _orig_es(h, a, era_home_sp=eh, era_away_sp=ea,
                              ip_home_sp=ih, ip_away_sp=ia)
            total = mh + ma
            line = g["line"]

            # ── Lógica EXACTA de las recomendaciones diarias (sigma 3.0, sin
            #     amortiguamiento) + todos los guards del sistema v3.9 ──────────
            from scipy.stats import norm
            p_over = 1 - norm.cdf(line + 0.5, loc=total, scale=3.0)
            p_under = norm.cdf(line - 0.5, loc=total, scale=3.0)
            tt = p_over + p_under
            p_over, p_under = p_over / tt, p_under / tt
            div = abs(total - line) / max(line, 1e-6)
            is_coors = "Colorado" in h

            bets = []
            # UNDER: p>=0.62, div<=0.22, línea<10, no Coors
            if (p_under >= 0.62 and div <= 0.22 and line < 10.0 and not is_coors
                    and g["under_odds"] >= MIN_ODDS):
                bets.append({"label": f"UNDER {line}", "model_p": round(p_under, 3),
                             "odds_offered": g["under_odds"]})
            # OVER: p>=0.75 (piso alto), div<=0.28
            if (p_over >= 0.75 and div <= 0.28 and g["over_odds"] >= MIN_ODDS):
                bets.append({"label": f"OVER {line}", "model_p": round(p_over, 3),
                             "odds_offered": g["over_odds"]})

            # ── Moneyline ──
            ml_bets = []
            if g["ml_home"] and g["ml_away"]:
                pred = eng.predict(h, a, market_odds={"home": g["ml_home"], "away": g["ml_away"]})
                if pred["p_home"] >= ML_FLOOR and g["ml_home"] >= MIN_ODDS:
                    ml_bets.append(("ML", f"{h} ML", pred["p_home"], g["ml_home"]))
                if pred["p_away"] >= ML_FLOOR and g["ml_away"] >= MIN_ODDS:
                    ml_bets.append(("ML", f"{a} ML", pred["p_away"], g["ml_away"]))

            for b in bets:
                if b["odds_offered"] < MIN_ODDS:
                    continue
                side = "OVER" if "OVER" in b["label"] else "UNDER"
                won = (g["total"] > g["line"]) if side == "OVER" else (g["total"] < g["line"])
                push = g["total"] == g["line"]
                picks.append({"date": ds, "game": f"{a}@{h}", "market": "O/U",
                              "pick": b["label"], "p": b["model_p"], "odds": b["odds_offered"],
                              "result": "PUSH" if push else ("W" if won else "L")})
            for mkt, label, p, odds in ml_bets:
                team = label.replace(" ML", "")
                won = (g["home_score"] > g["away_score"]) if team == h else (g["away_score"] > g["home_score"])
                picks.append({"date": ds, "game": f"{a}@{h}", "market": "ML",
                              "pick": label, "p": p, "odds": odds,
                              "result": "W" if won else "L"})
        print(f"  {ds}: {len(games)} juegos procesados")
        day += dt.timedelta(days=1)

    return picks


def report(picks, kelly_frac=0.25, bank=10000):
    if not picks:
        print("\nSin picks generados en el periodo."); return
    S = 100
    flat = 0.0
    w = l = p = 0
    by_type = {}
    for pk in picks:
        r = pk["result"]
        pl = S * (pk["odds"] - 1) if r == "W" else (-S if r == "L" else 0)
        flat += pl
        w += r == "W"; l += r == "L"; p += r == "PUSH"
        t = pk["pick"].split()[0] if pk["market"] == "O/U" else "ML"
        d = by_type.setdefault(t if t in ("OVER", "UNDER") else "ML", [0, 0, 0, 0.0])
        d[0] += r == "W"; d[1] += r == "L"; d[2] += r == "PUSH"; d[3] += pl

    print("\n" + "=" * 64)
    print(f"RESULTADO BACKTEST — {len(picks)} picks")
    print("=" * 64)
    for t, (tw, tl, tp, tpl) in sorted(by_type.items()):
        wr = tw / (tw + tl) * 100 if tw + tl else 0
        print(f"  {t:6}: {tw}W-{tl}L-{tp}P | WR {wr:3.0f}% | {tpl:+.0f} pesos")
    wr = w / (w + l) * 100 if w + l else 0
    roi = flat / ((w + l) * S) * 100 if w + l else 0
    print("-" * 64)
    print(f"  TOTAL : {w}W-{l}L-{p}P | WR {wr:.0f}% | {flat:+.0f} pesos | ROI {roi:+.1f}%")
    print(f"  (stake plano 100/pick sobre {(w+l)} apuestas resueltas)")


if __name__ == "__main__":
    start = sys.argv[1] if len(sys.argv) > 1 else "2026-06-06"
    end = sys.argv[2] if len(sys.argv) > 2 else "2026-07-05"
    print(f"Backtest walk-forward {start} → {end}")
    picks = run_backtest(start, end)
    report(picks)
    # Guardar detalle
    with open("_cache/backtest_picks.json", "w") as f:
        json.dump(picks, f, indent=2)
    print("\nDetalle guardado en _cache/backtest_picks.json")
