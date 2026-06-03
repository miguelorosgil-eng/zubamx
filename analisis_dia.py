"""
ANÁLISIS DEL DÍA — runner unificado multi-deporte, multi-mercado.

Corre MLB + NBA + NHL, evalúa TODOS los mercados (moneyline, O/U, spread,
team totals, BTTS, NRFI), aplica el filtro estricto (confianza + shrinkage +
gate de divergencia) y arma un portafolio de cobertura con el banco indicado.

Uso:
    python analisis_dia.py --deportes MLB NBA NHL --banco 1000
    python analisis_dia.py --deportes MLB --banco 1000 --refrescar   # ignora caché
"""
import os
import argparse
import datetime
from difflib import SequenceMatcher

import pandas as pd

from conector_odds import fetch_odds, fetch_market_odds
from motor_deportes import SportsEngine
from mercados import evaluate_markets, prob_nrfi, evaluate_two_way, evaluate_three_way
from portfolio import compute_portfolio, print_portfolio_report

try:
    from injuries import get_injuries, injury_summary
    _HAS_INJURIES = True
except ImportError:
    _HAS_INJURIES = False

try:
    from weather import get_weather_adjustment
    _HAS_WEATHER = True
except ImportError:
    _HAS_WEATHER = False

try:
    from tracker import save_picks, print_stats, update_results
    _HAS_TRACKER = True
except ImportError:
    _HAS_TRACKER = False

try:
    from props_mlb import get_today_pitcher_props, print_pitcher_props
    _HAS_PROPS = True
except ImportError:
    _HAS_PROPS = False

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Config por deporte: cómo entrenar y traer fixtures
SPORT_CONFIG = {
    "MLB": {"sport": "mlb", "seasons": [2024, 2025]},
    "NBA": {"sport": "nba", "seasons": ["2024-25"]},
    "NHL": {"sport": "nhl", "seasons": ["20242025"]},
}

# Ligas de fútbol importantes (códigos Football-Data). Usan Dixon-Coles.
SOCCER_LEAGUES = {
    "PL":  {"seasons": [2024, 2025], "name": "Premier League"},
    "PD":  {"seasons": [2024, 2025], "name": "La Liga"},
    "SA":  {"seasons": [2024, 2025], "name": "Serie A"},
    "BL1": {"seasons": [2024, 2025], "name": "Bundesliga"},
    "FL1": {"seasons": [2024, 2025], "name": "Ligue 1"},
    "CL":  {"seasons": [2024, 2025], "name": "Champions League"},
    "WC":  {"seasons": [2024],       "name": "Mundial 2026"},
}


def _sim(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


_DEBUG = False


def _find(home, away, events, label=""):
    best, bscore = None, 0
    for e in events:
        s = (_sim(home, e["home"]) + _sim(away, e["away"])) / 2
        if s > bscore:
            best, bscore = e, s
    if _DEBUG:
        tag = f"[{label}]" if label else ""
        if best and bscore > 0.5:
            print(f"    {tag} match {bscore:.2f}: '{home}' → '{best['home']}' | '{away}' → '{best['away']}'")
        else:
            print(f"    {tag} NO MATCH (best {bscore:.2f}) for '{home}' vs '{away}'")
    return best if bscore > 0.5 else None


def _load_training(code, refrescar=False):
    """Carga datos de entrenamiento con caché en disco.
    Auto-reentrenamiento: refresca si el caché tiene >24h (diario automático).
    """
    cfg = SPORT_CONFIG[code]
    cache_file = os.path.join(CACHE_DIR, f"{code}_train.csv")
    if os.path.exists(cache_file) and not refrescar:
        age_h = (datetime.datetime.now().timestamp() - os.path.getmtime(cache_file)) / 3600
        if age_h < 24:  # caché válido 24h — reentrenamiento diario automático
            return pd.read_csv(cache_file, parse_dates=["date"])
        else:
            print(f"  ♻️  Caché de {code} expirado ({age_h:.0f}h) — reentrenando...")

    if code == "MLB":
        from conector_mlb import build_mlb_training
        df = build_mlb_training(cfg["seasons"])
    elif code == "NBA":
        from conector_nba import build_nba_training
        df = build_nba_training(cfg["seasons"])
    elif code == "NHL":
        from conector_nhl import build_nhl_training
        df = build_nhl_training(cfg["seasons"])
    else:
        return pd.DataFrame()

    if not df.empty:
        df.to_csv(cache_file, index=False)
    return df


def _fetch_upcoming_today(code, today):
    if code == "MLB":
        from conector_mlb import fetch_mlb_upcoming
        up = fetch_mlb_upcoming()
    elif code == "NBA":
        from conector_nba import fetch_nba_upcoming
        up = fetch_nba_upcoming(days=1)
    elif code == "NHL":
        from conector_nhl import fetch_nhl_upcoming
        up = fetch_nhl_upcoming()
    else:
        return pd.DataFrame()
    if up.empty:
        return up
    return up[up["date"].astype(str).str.startswith(today)].reset_index(drop=True)


def analizar_deporte(code, today, filtros, banco_info):
    """Procesa un deporte y devuelve sus value bets."""
    print(f"\n{'='*80}\n  {code} — {today}\n{'='*80}")

    df = _load_training(code)
    if df.empty:
        print("  Sin datos de entrenamiento disponibles."); return []
    eng = SportsEngine(sport=SPORT_CONFIG[code]["sport"],
                       edge_threshold=filtros["edge_threshold"],
                       confidence_floor=filtros["confidence_floor"],
                       market_trust=filtros["market_trust"])
    eng.fit(df)

    upcoming = _fetch_upcoming_today(code, today)
    if upcoming.empty:
        print("  Sin juegos hoy."); return []
    print(f"  {len(upcoming)} juego(s) hoy.")

    ml = fetch_odds(code, region="us")
    mk = fetch_market_odds(code, region="us")

    nrfi_data = []
    if code == "MLB":
        try:
            from conector_mlb import fetch_probable_pitchers
            nrfi_data = fetch_probable_pitchers(today)
        except Exception as e:
            print(f"  (NRFI no disponible: {e})")

    # Lesiones en tiempo real
    injuries = {}
    if _HAS_INJURIES:
        try:
            injuries = get_injuries(SPORT_CONFIG[code]["sport"], today)
        except Exception:
            pass

    value_bets = []
    rechazados = 0
    for r in upcoming.itertuples():
        if r.home not in eng._teams_seen or r.away not in eng._teams_seen:
            if _DEBUG:
                missing = [t for t in [r.home, r.away] if t not in eng._teams_seen]
                print(f"    SKIP (not in training): {missing}")
            continue
        match_bets = []

        # Buscar pitcher data para este juego
        nr = None
        era_home_sp, era_away_sp = None, None
        if code == "MLB" and nrfi_data:
            nr = _find(r.home, r.away, nrfi_data)
            if nr:
                era_home_sp = nr.get("era_home_sp")
                era_away_sp = nr.get("era_away_sp")

        # Ajuste climático (solo MLB estadios abiertos)
        weather_info = ""
        if code == "MLB" and _HAS_WEATHER:
            try:
                w = get_weather_adjustment(r.home)
                if w.get("summary"):
                    weather_info = w["summary"]
                if w.get("rain_risk"):
                    print(f"    ⚠️ RIESGO LLUVIA {r.home} vs {r.away} — partido puede posponerse")
            except Exception:
                pass

        # Moneyline
        e_ml = _find(r.home, r.away, ml, "ML")
        if e_ml:
            pred = eng.predict(r.home, r.away,
                               market_odds={"home": e_ml["odds"]["home"],
                                            "away": e_ml["odds"]["away"]})
            for b in pred.get("value_bets", []):
                match_bets.append(("ML", b["label"], b["odds_offered"], b["model_p"],
                                   b["edge"], b["kelly_frac"]))

        # O/U, Spread, Team totals (vía mercados genéricos)
        e_mk = _find(r.home, r.away, mk, "MK")
        if e_mk:
            lines = {}
            if "totals" in e_mk:
                lines["totals"] = e_mk["totals"]
            if "spread" in e_mk:
                lines["spread"] = e_mk["spread"]
            for b in evaluate_markets(eng, r.home, r.away, lines, filters=filtros):
                match_bets.append((b["market"], b["label"], b["odds_offered"],
                                   b["model_p"], b["edge"], b["kelly_frac"]))
            if "totals" in lines:
                mh, ma = eng.expected_scores(r.home, r.away, era_home_sp, era_away_sp)
                ln = lines["totals"]["line"]
                if abs((mh + ma) - ln) / max(ln, 1e-6) > filtros["max_divergence"]:
                    rechazados += 1

        # NRFI (solo MLB, informativo + value si hubiera odds)
        nrfi_info = ""
        if code == "MLB" and nr and era_home_sp and era_away_sp:
            p_nrfi, p_yrfi = prob_nrfi(era_home_sp, era_away_sp)
            if p_nrfi is not None:
                nrfi_info = (f"NRFI {p_nrfi:.0%} (SP {nr['home_sp']} {era_home_sp:.2f} / "
                             f"{nr['away_sp']} {era_away_sp:.2f})")

        if match_bets or nrfi_info:
            mh, ma = eng.expected_scores(r.home, r.away, era_home_sp, era_away_sp)
            inj_h = injury_summary(r.home, injuries) if _HAS_INJURIES else ""
            inj_a = injury_summary(r.away, injuries) if _HAS_INJURIES else ""
            print(f"  {r.home} vs {r.away}  (μ {mh:.1f}-{ma:.1f}, total {mh+ma:.1f})")
            if weather_info:
                print(f"     [Weather] {weather_info}")
            if inj_h:
                print(f"     {inj_h}")
            if inj_a:
                print(f"     {inj_a}")
            for mkt, lbl, od, p, ed, k in match_bets:
                print(f"     [{mkt:>7}] {lbl:<26} @{od:.2f}  p={p:.0%}  edge {ed:.1%}  kelly {k:.1%}")
                value_bets.append({
                    "label": f"{code} {r.home[:10]} {mkt}:{lbl[:14]}",
                    "sport": code, "home": r.home, "away": r.away,
                    "pick_team": lbl, "pick_side": mkt,
                    "market": mkt, "model_p": p, "odds_offered": od,
                    "edge": ed, "kelly_frac": k,
                })
            if nrfi_info:
                print(f"     [   NRFI] {nrfi_info}")

    if rechazados:
        print(f"  >> {rechazados} mercado(s) de totales rechazados por divergencia "
              f"absurda modelo↔mercado (protección activa).")
    if not value_bets:
        print("  Sin value bets que pasen el filtro estricto hoy.")
    return value_bets


def _load_soccer_training(code, seasons, refrescar=False):
    """Carga histórico de una liga de fútbol con caché en disco."""
    cache_file = os.path.join(CACHE_DIR, f"SOCCER_{code}_train.csv")
    if os.path.exists(cache_file) and not refrescar:
        age_h = (datetime.datetime.now().timestamp() - os.path.getmtime(cache_file)) / 3600
        if age_h < 24:
            return pd.read_csv(cache_file, parse_dates=["date"])
    from conector_fd import build_training_set
    df = build_training_set(code, seasons)
    if not df.empty:
        df.to_csv(cache_file, index=False)
    return df


def analizar_futbol(code, today, filtros):
    """Procesa una liga de fútbol (1X2 + O/U + BTTS + spread + team totals)."""
    cfg = SOCCER_LEAGUES[code]
    print(f"\n{'='*80}\n  ⚽ {cfg['name']} ({code}) — {today}\n{'='*80}")

    from conector_fd import fetch_upcoming
    from motor_futbol_v1 import FootballEngine

    df = _load_soccer_training(code, cfg["seasons"])
    if df.empty:
        print("  Sin datos de entrenamiento."); return []
    # normalizar columnas al esquema del motor de fútbol
    eng = FootballEngine(edge_threshold=filtros["edge_threshold"],
                         confidence_floor=filtros["confidence_floor"],
                         market_trust=filtros["market_trust"])
    eng.fit(df[["home", "away", "hg", "ag", "date"]], league_code=code)

    upcoming = fetch_upcoming(code)
    if upcoming.empty:
        print("  Sin partidos programados (posible temporada terminada)."); return []
    up_hoy = upcoming[upcoming["date"].astype(str).str.startswith(today)].reset_index(drop=True)
    if up_hoy.empty:
        print(f"  {len(upcoming)} partidos próximos, pero ninguno HOY."); return []
    print(f"  {len(up_hoy)} partido(s) hoy.")

    ml = fetch_odds(code, region="eu")          # 1X2 (con empate)
    mk = fetch_market_odds(code, region="eu")   # totals + spreads (hándicap)

    value_bets, rechazados = [], 0
    for r in up_hoy.itertuples():
        if r.home not in eng._teams_seen or r.away not in eng._teams_seen:
            continue
        mh, ma = eng.expected_scores(r.home, r.away)
        match_bets = []

        # 1X2 moneyline
        e_ml = _find(r.home, r.away, ml)
        if e_ml and e_ml["odds"].get("draw"):
            pred = eng.predict(r.home, r.away)
            for b in evaluate_three_way(
                    pred["p_home"], pred["p_draw"], pred["p_away"],
                    e_ml["odds"]["home"], e_ml["odds"]["draw"], e_ml["odds"]["away"],
                    r.home, r.away, filtros["market_trust"],
                    filtros["confidence_floor"], filtros["edge_threshold"]):
                match_bets.append((b["market"], b["label"], b["odds_offered"],
                                   b["model_p"], b["edge"], b["kelly_frac"]))

        # O/U, spread, BTTS, team totals
        e_mk = _find(r.home, r.away, mk)
        lines = {}
        if e_mk:
            if "totals" in e_mk:
                lines["totals"] = e_mk["totals"]
            if "spread" in e_mk:
                lines["spread"] = e_mk["spread"]
        for b in evaluate_markets(eng, r.home, r.away, lines, filters=filtros):
            match_bets.append((b["market"], b["label"], b["odds_offered"],
                               b["model_p"], b["edge"], b["kelly_frac"]))
        if "totals" in lines:
            ln = lines["totals"]["line"]
            if abs((mh + ma) - ln) / max(ln, 1e-6) > filtros["max_divergence"]:
                rechazados += 1

        if match_bets:
            print(f"  {r.home} vs {r.away}  (xG {mh:.1f}-{ma:.1f})")
            for mkt, lbl, od, p, ed, k in match_bets:
                print(f"     [{mkt:>7}] {lbl:<26} @{od:.2f}  p={p:.0%}  edge {ed:.1%}  kelly {k:.1%}")
                value_bets.append({
                    "label": f"{code} {r.home[:10]} {mkt}:{lbl[:14]}",
                    "market": mkt, "model_p": p, "odds_offered": od,
                    "edge": ed, "kelly_frac": k,
                })
    if rechazados:
        print(f"  >> {rechazados} totales rechazados por divergencia (protección activa).")
    if not value_bets:
        print("  Sin value bets que pasen el filtro estricto hoy.")
    return value_bets


def main():
    p = argparse.ArgumentParser(description="Análisis del día multi-deporte")
    p.add_argument("--deportes", nargs="*", default=["MLB", "NBA", "NHL"])
    p.add_argument("--futbol", nargs="*", default=["PL", "PD", "SA", "BL1", "FL1", "CL"],
                   help="Ligas de fútbol a revisar (códigos Football-Data)")
    p.add_argument("--banco", type=float, default=1000)
    p.add_argument("--min-ganadores", type=int, default=1)
    p.add_argument("--target", type=float, default=1.0)
    p.add_argument("--confianza", type=float, default=0.65)
    p.add_argument("--market-trust", type=float, default=0.5)
    p.add_argument("--edge", type=float, default=0.02)
    p.add_argument("--max-div", type=float, default=0.20)
    p.add_argument("--refrescar", action="store_true")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--actualizar", action="store_true",
                   help="Actualizar resultados de ayer y mostrar ROI acumulado")
    p.add_argument("--props", action="store_true",
                   help="Mostrar props de strikeouts para pitchers de hoy (MLB)")
    a = p.parse_args()

    global _DEBUG
    _DEBUG = a.debug

    today = datetime.date.today().isoformat()

    # Actualizar resultados pendientes y mostrar historial si se pide
    if _HAS_TRACKER:
        try:
            update_results()  # actualiza ayer automáticamente
        except Exception:
            pass
        if a.actualizar:
            print_stats()
            return

    filtros = {
        "edge_threshold": a.edge,
        "confidence_floor": a.confianza,
        "market_trust": a.market_trust,
        "anchor_weight": 0.5,
        "max_divergence": a.max_div,
    }

    deportes_str = ", ".join(a.deportes + (a.futbol or []))
    print(f"\n{'#'*80}")
    print(f"#  ANÁLISIS DEL DÍA — {today}  |  Banco: ${a.banco:,.0f}  |  {deportes_str}")
    print(f"{'#'*80}")

    all_value = []
    for code in a.deportes:
        if code not in SPORT_CONFIG:
            print(f"\n  Deporte desconocido: {code}"); continue
        try:
            all_value += analizar_deporte(code, today, filtros, a.banco)
        except Exception as e:
            print(f"\n  ERROR en {code}: {e}")

    for code in (a.futbol or []):
        if code not in SOCCER_LEAGUES:
            print(f"\n  Liga de fútbol desconocida: {code}"); continue
        try:
            all_value += analizar_futbol(code, today, filtros)
        except Exception as e:
            print(f"\n  ERROR en fútbol {code}: {e}")

    # Props de strikeouts MLB
    if a.props and _HAS_PROPS and "MLB" in a.deportes:
        try:
            from conector_mlb import fetch_probable_pitchers
            pitchers = fetch_probable_pitchers(today)
            if pitchers:
                props = get_today_pitcher_props(pitchers, season=int(today[:4]))
                print_pitcher_props(props)
        except Exception as e:
            print(f"  (Props MLB no disponibles: {e})")

    print(f"\n{'#'*80}")
    print(f"#  PORTAFOLIO DEL DÍA — ${a.banco:,.0f}")
    print(f"{'#'*80}")
    if all_value:
        top = sorted(all_value, key=lambda x: -x["edge"])[:10]
        result = compute_portfolio(top, bankroll=a.banco,
                                   target_return=a.target, min_winners=a.min_ganadores)
        print_portfolio_report(result, bankroll=a.banco)

        # Guardar picks del día en tracker
        if _HAS_TRACKER:
            try:
                stake = a.banco * 0.02  # 2% del banco por pick por defecto
                save_picks(top, today, stake_per_pick=stake)
            except Exception:
                pass
    else:
        print("\n  Hoy NINGUNA apuesta pasa el estándar de calidad.")
        print("  La decisión disciplinada es NO apostar. Esto protege la banca.")

    # Mostrar estadísticas históricas al final
    if _HAS_TRACKER:
        try:
            print_stats()
        except Exception:
            pass


if __name__ == "__main__":
    main()
