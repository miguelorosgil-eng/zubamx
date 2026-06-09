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
    from mercados_alternativos import evaluate_alt_markets
    _HAS_ALT_MARKETS = True
except ImportError:
    _HAS_ALT_MARKETS = False

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

try:
    from stats_avanzados import enrich_prediction
    _HAS_ADV_STATS = True
except ImportError:
    _HAS_ADV_STATS = False

try:
    from conector_mundial import fetch_wc_upcoming, build_wc_training, FIFA_RANKINGS
    _HAS_MUNDIAL = True
except ImportError:
    _HAS_MUNDIAL = False

try:
    from line_movement import get_line_movement, save_opening_lines, format_movement_summary
    _HAS_LM = True
except ImportError:
    _HAS_LM = False

try:
    from lineup_nba import fetch_nba_lineup_status, get_lineup_adjusted_prob
    _HAS_LINEUP = True
except ImportError:
    _HAS_LINEUP = False

try:
    from motivacion_wc import analyze_group_motivation, adjust_wc_probabilities
    _HAS_MOTIVACION = True
except ImportError:
    _HAS_MOTIVACION = False

try:
    from calibracion import get_calibration_adjustment, print_calibration_report
    _HAS_CALIBRACION = True
except ImportError:
    _HAS_CALIBRACION = False

try:
    from statcast import get_statcast_game_score
    _HAS_STATCAST = True
except ImportError:
    _HAS_STATCAST = False

try:
    from features_mlb_avanzados import enrich_mlb_training, get_game_features
    _HAS_MLB_FEATURES = True
except ImportError:
    _HAS_MLB_FEATURES = False

try:
    from modelo_secuencial import SequenceModel, apply_sequence_adjustment
    _HAS_SEQUENCE = True
except ImportError:
    _HAS_SEQUENCE = False

try:
    from motor_contextual import ContextualEngine
    _HAS_CONTEXTUAL = True
except ImportError:
    _HAS_CONTEXTUAL = False

try:
    from clv_tracker import record_pick, update_closing_lines, print_clv_report, is_positive_ev
    _HAS_CLV = True
except ImportError:
    _HAS_CLV = False

# Modelos secuenciales por deporte (se cargan una vez)
_SEQ_MODELS = {}

try:
    from calibracion_platt import get_calibrator as get_platt
    _HAS_PLATT = True
except ImportError:
    _HAS_PLATT = False

# Cargar calibradores Platt al inicio (una sola vez)
_PLATT = {}
if _HAS_PLATT:
    for _s in ["MLB", "NBA", "NHL"]:
        try:
            _PLATT[_s] = get_platt(_s)
        except Exception:
            pass

try:
    from historical_odds import get_line_movement_signal
    _HAS_HIST_ODDS = True
except ImportError:
    _HAS_HIST_ODDS = False

try:
    from series_model import get_series_adjustment, fetch_nba_series_status, fetch_nhl_series_status
    _HAS_SERIES = True
except ImportError:
    _HAS_SERIES = False

try:
    from backtesting import run_all_backtests, print_backtest_report
    _HAS_BACKTEST = True
except ImportError:
    _HAS_BACKTEST = False

try:
    from alertas import send_daily_picks, send_steam_alert
    _HAS_ALERTAS = True
except ImportError:
    _HAS_ALERTAS = False

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

# El Mundial usa su propio conector y motor dedicado
WC_ACTIVE = True  # activar cuando empiece el torneo (11 jun 2026)


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
        # Si la temporada activa tiene muy pocos partidos, usar solo la completa
        if not df.empty and "season" in df.columns:
            counts = df.groupby("season").size()
            valid = counts[counts >= 500].index.tolist()
            if valid and len(valid) < len(counts):
                df = df[df["season"].isin(valid)].copy()
    elif code == "NBA":
        from conector_nba import build_nba_training
        df = build_nba_training(cfg["seasons"])
    elif code == "NHL":
        from conector_nhl import build_nhl_training
        df = build_nhl_training(cfg["seasons"])
    else:
        return pd.DataFrame()

    if not df.empty:
        # Enriquecer MLB con features avanzados antes de guardar
        if code == "MLB" and _HAS_MLB_FEATURES:
            try:
                df = enrich_mlb_training(df)
            except Exception:
                pass
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
    tomorrow = (datetime.date.fromisoformat(today) + datetime.timedelta(days=1)).isoformat()
    mask = up["date"].astype(str).str.startswith(today) | up["date"].astype(str).str.startswith(tomorrow)
    return up[mask].reset_index(drop=True)


def analizar_deporte(code, today, filtros, banco_info):
    """Procesa un deporte y devuelve sus value bets."""
    print(f"\n{'='*80}\n  {code} — {today}\n{'='*80}")

    df = _load_training(code)
    if df.empty:
        print("  Sin datos de entrenamiento disponibles."); return []

    # Usar ContextualEngine si disponible (sub-modelos por contexto)
    if _HAS_CONTEXTUAL:
        try:
            eng = ContextualEngine(sport=SPORT_CONFIG[code]["sport"],
                                   edge_threshold=filtros["edge_threshold"],
                                   confidence_floor=filtros["confidence_floor"],
                                   market_trust=filtros["market_trust"])
            eng.fit(df)
        except Exception:
            eng = SportsEngine(sport=SPORT_CONFIG[code]["sport"],
                               edge_threshold=filtros["edge_threshold"],
                               confidence_floor=filtros["confidence_floor"],
                               market_trust=filtros["market_trust"])
            eng.fit(df)
    else:
        eng = SportsEngine(sport=SPORT_CONFIG[code]["sport"],
                           edge_threshold=filtros["edge_threshold"],
                           confidence_floor=filtros["confidence_floor"],
                           market_trust=filtros["market_trust"])
        eng.fit(df)

    # Modelo secuencial (momentum, rachas, H2H) — se entrena una vez por deporte
    if _HAS_SEQUENCE and code not in _SEQ_MODELS:
        try:
            seq = SequenceModel(window=10, decay=0.85)
            seq.fit(df)
            _SEQ_MODELS[code] = seq
        except Exception:
            pass

    upcoming = _fetch_upcoming_today(code, today)
    if upcoming.empty:
        print("  Sin juegos hoy."); return []
    print(f"  {len(upcoming)} juego(s) hoy.")

    ml = fetch_odds(code, region="us")
    mk = fetch_market_odds(code, region="us")

    # Guardar opening lines y calcular movimiento sharp
    if _HAS_LM:
        try:
            save_opening_lines(code, ml, today)
            _line_moves = {(m["home"], m["away"]): m
                          for m in get_line_movement(code, ml, today)}
        except Exception:
            _line_moves = {}
    else:
        _line_moves = {}

    # Series playoffs NBA/NHL — contexto Best-of-7
    _series_status = {}
    if _HAS_SERIES:
        try:
            if code == "NBA":
                _series_status = fetch_nba_series_status()
            elif code == "NHL":
                _series_status = fetch_nhl_series_status()
        except Exception:
            pass

    # Lineup NBA confirmado
    _lineup_status = {}
    if code == "NBA" and _HAS_LINEUP:
        try:
            _lineup_status = fetch_nba_lineup_status(today)
        except Exception:
            pass

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

        # Movimiento de línea sharp + señal histórica
        lm = _line_moves.get((r.home, r.away))
        if lm and lm.get("sharp_side"):
            print(f"     {format_movement_summary(lm)}")
        if _HAS_HIST_ODDS:
            try:
                hist_signal = get_line_movement_signal(SPORT_CONFIG[code]["sport"], r.home, r.away)
                if hist_signal and hist_signal.get("sharp_win_rate", 0.5) > 0.55:
                    print(f"     [HistOdds] Sharp side win rate histórico: {hist_signal['sharp_win_rate']:.0%}")
            except Exception:
                pass

        # Contexto de series playoffs (NBA/NHL)
        if _HAS_SERIES and _series_status:
            try:
                adj_h, adj_a, series_summary = get_series_adjustment(r.home, r.away, _series_status)
                if series_summary:
                    print(f"     [Series] {series_summary}")
            except Exception:
                adj_h, adj_a = 1.0, 1.0
        else:
            adj_h, adj_a = 1.0, 1.0

        # Lineup NBA — ajustar probabilidades por bajas
        lineup_warnings = []
        if code == "NBA" and _lineup_status:
            try:
                p_h_raw = eng.predict(r.home, r.away).get("p_home", 0.5)
                p_a_raw = 1 - p_h_raw
                p_h_adj, p_a_adj, lineup_warnings = get_lineup_adjusted_prob(
                    r.home, r.away, p_h_raw, p_a_raw, _lineup_status)
                for w in lineup_warnings:
                    print(f"     {w}")
            except Exception:
                pass

        # Moneyline
        e_ml = _find(r.home, r.away, ml, "ML")
        if e_ml:
            pred = eng.predict(r.home, r.away,
                               market_odds={"home": e_ml["odds"]["home"],
                                            "away": e_ml["odds"]["away"]})
            # Aplicar calibración Platt (corrige sobreconfianza)
            if code in _PLATT and _PLATT[code]._fitted:
                platt = _PLATT[code]
                p_h_raw = pred.get("p_home", 0.5)
                p_h_cal = platt.transform(p_h_raw)
                pred["p_home"] = p_h_cal
                pred["p_away"] = 1 - p_h_cal
                if "value_bets" in pred:
                    for vb in pred["value_bets"]:
                        vb["model_p"] = p_h_cal if "home" in vb.get("label","").lower() else 1-p_h_cal
                        vb["edge"] = vb["model_p"] - (1 / vb["odds_offered"])

            # Ajuste secuencial (momentum, rachas, H2H reciente)
            seq_model = _SEQ_MODELS.get(code)
            if seq_model:
                try:
                    seq_adj = seq_model.predict_adjustment(r.home, r.away, today)
                    pred = apply_sequence_adjustment(pred, seq_adj)
                    for w in seq_adj.get("warnings", []):
                        print(f"     [Seq] {w}")
                    streak_h = seq_adj.get("home_streak", 0)
                    streak_a = seq_adj.get("away_streak", 0)
                    if abs(streak_h) >= 4 or abs(streak_a) >= 4:
                        sh = f"+{streak_h}" if streak_h > 0 else str(streak_h)
                        sa = f"+{streak_a}" if streak_a > 0 else str(streak_a)
                        print(f"     [Racha] {r.home} {sh} | {r.away} {sa}")
                except Exception:
                    pass

            # Verificar +EV vs Pinnacle si disponible
            if _HAS_CLV and e_ml:
                try:
                    ev_ok, edge_pct, rec = is_positive_ev(
                        pred.get("p_home", 0.5), e_ml["odds"]["home"])
                    if ev_ok:
                        print(f"     [CLV] +EV detectado vs Pinnacle: {edge_pct:+.1f}%  {rec}")
                except Exception:
                    pass
            # Enriquecer con stats avanzados (PDO, Net Rating, bullpen ERA)
            if _HAS_ADV_STATS:
                try:
                    season = SPORT_CONFIG[code]["seasons"][-1]
                    pred = enrich_prediction(SPORT_CONFIG[code]["sport"],
                                            r.home, r.away, pred, season)
                    for w in pred.get("adv_warnings", []):
                        print(f"     {w}")
                except Exception:
                    pass
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

            # Mercados alternativos (F5, run line, primera mitad, puck line, BTTS, etc.)
            if _HAS_ALT_MARKETS:
                try:
                    for b in evaluate_alt_markets(code, eng, r.home, r.away, e_mk, filtros):
                        match_bets.append((b["market"], b["label"], b["odds_offered"],
                                           b["model_p"], b["edge"], b["kelly_frac"]))
                except Exception:
                    pass

        # Statcast — enriquecer totales MLB con xFIP / hard-hit (guardamos sc para NRFI)
        statcast_info = ""
        _sc_cache = {}
        if code == "MLB" and _HAS_STATCAST and nr:
            try:
                _sc_cache = get_statcast_game_score(
                    nr.get("home_sp"), nr.get("away_sp"),
                    r.home, r.away,
                    season=int(today[:4]),
                    home_sp_id=nr.get("home_sp_id"),
                    away_sp_id=nr.get("away_sp_id"),
                )
                if _sc_cache.get("total_adj", 0) != 0:
                    statcast_info = (f"Statcast adj {_sc_cache['total_adj']:+.1f} runs "
                                     f"(nrfi_boost={_sc_cache.get('nrfi_boost',0):+.2f})")
            except Exception:
                pass

        # NRFI — calcula probabilidad, edge vs cuota de mercado típica y entra al portfolio
        nrfi_bets = []
        if code == "MLB" and nr and era_home_sp and era_away_sp:
            p_nrfi, p_yrfi = prob_nrfi(era_home_sp, era_away_sp)
            if p_nrfi is not None:
                # Boost de statcast reutilizando el resultado ya calculado
                nrfi_boost = _sc_cache.get("nrfi_boost", 0.0)
                p_nrfi = min(0.97, p_nrfi + nrfi_boost * 0.02)

                # Cuota de mercado típica para NRFI: casas ofrecen ~1.80-1.90 (≈52-55%)
                # Usamos 1.85 como referencia conservadora
                nrfi_market_odds = 1.85
                nrfi_implied = 1.0 / nrfi_market_odds
                nrfi_edge = p_nrfi - nrfi_implied

                sp_line = (f"SP {nr.get('home_sp','?')} {era_home_sp:.2f} ERA / "
                           f"{nr.get('away_sp','?')} {era_away_sp:.2f} ERA")

                if p_nrfi >= filtros["nrfi_floor"] and nrfi_edge >= filtros["edge_min"]:
                    kelly_nrfi = max(0.0, (p_nrfi * nrfi_market_odds - 1) / (nrfi_market_odds - 1)) * 0.25
                    label_nrfi = f"NRFI {r.home[:8]}/{r.away[:8]}"
                    nrfi_bets.append(("NRFI", label_nrfi, nrfi_market_odds, p_nrfi, nrfi_edge, kelly_nrfi))
                else:
                    # Mostrar informativo aunque no pase el filtro
                    flag = "⚠️ " if p_nrfi >= 0.52 else ""
                    print(f"  {flag}[NRFI info] {r.home} vs {r.away}  p={p_nrfi:.0%}  edge {nrfi_edge:.1%}  ({sp_line})")

        if match_bets or nrfi_bets:
            mh, ma = eng.expected_scores(r.home, r.away, era_home_sp, era_away_sp)
            inj_h = injury_summary(r.home, injuries) if _HAS_INJURIES else ""
            inj_a = injury_summary(r.away, injuries) if _HAS_INJURIES else ""
            print(f"  {r.home} vs {r.away}  (μ {mh:.1f}-{ma:.1f}, total {mh+ma:.1f})")
            if weather_info:
                print(f"     [Weather] {weather_info}")
            if statcast_info:
                print(f"     [Statcast] {statcast_info}")
            if inj_h:
                print(f"     {inj_h}")
            if inj_a:
                print(f"     {inj_a}")
            for mkt, lbl, od, p, ed, k in match_bets + nrfi_bets:
                print(f"     [{mkt:>7}] {lbl:<26} @{od:.2f}  p={p:.0%}  edge {ed:.1%}  kelly {k:.1%}")
                value_bets.append({
                    "label": f"{code} {r.home[:10]} {mkt}:{lbl[:14]}",
                    "sport": code, "home": r.home, "away": r.away,
                    "pick_team": lbl, "pick_side": mkt,
                    "market": mkt, "model_p": p, "odds_offered": od,
                    "edge": ed, "kelly_frac": k,
                })

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

        # Mercados alternativos de fútbol (BTTS, doble oportunidad, primera mitad, totales alt.)
        if _HAS_ALT_MARKETS and e_mk:
            try:
                _pred_soc = eng.predict(r.home, r.away)
                for b in evaluate_alt_markets(
                        code, eng, r.home, r.away, e_mk, filtros,
                        p_home=_pred_soc.get("p_home"),
                        p_draw=_pred_soc.get("p_draw"),
                        p_away=_pred_soc.get("p_away")):
                    match_bets.append((b["market"], b["label"], b["odds_offered"],
                                       b["model_p"], b["edge"], b["kelly_frac"]))
            except Exception:
                pass

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


def _load_wc_training(refrescar=False):
    cache_file = os.path.join(CACHE_DIR, "WC_train.csv")
    if os.path.exists(cache_file) and not refrescar:
        age_h = (datetime.datetime.now().timestamp() - os.path.getmtime(cache_file)) / 3600
        if age_h < 48:
            return pd.read_csv(cache_file, parse_dates=["date"])
        print("  ♻️  Caché WC expirado — reentrenando con datos frescos...")
    if not _HAS_MUNDIAL:
        return pd.DataFrame()
    df = build_wc_training()
    if not df.empty:
        df.to_csv(cache_file, index=False)
    return df


def analizar_mundial(today, filtros):
    """Análisis dedicado al Mundial FIFA 2026 con motor de fútbol."""
    print(f"\n{'='*80}\n  🌍 MUNDIAL FIFA 2026 — {today}\n{'='*80}")

    if not _HAS_MUNDIAL:
        print("  conector_mundial no disponible."); return []

    from motor_futbol_v1 import FootballEngine
    from features_futbol import _get_fifa_rank

    # Partidos del día
    upcoming = fetch_wc_upcoming(days=2)
    if upcoming.empty:
        print("  Sin partidos del Mundial hoy/mañana.")
        return []
    tomorrow = (datetime.date.fromisoformat(today) + datetime.timedelta(days=1)).isoformat()
    mask = (upcoming["date"].astype(str).str.startswith(today) |
            upcoming["date"].astype(str).str.startswith(tomorrow))
    up_hoy = upcoming[mask].reset_index(drop=True)
    if up_hoy.empty:
        print(f"  {len(upcoming)} partidos próximos, pero ninguno hoy/mañana."); return []
    print(f"  {len(up_hoy)} partido(s) del Mundial hoy/mañana.")

    # Entrenar con datos históricos de selecciones
    df = _load_wc_training()
    if df.empty:
        print("  Sin datos históricos de selecciones — usando solo rankings FIFA.");

    value_bets = []
    ml = fetch_odds("WC", region="eu")

    for r in up_hoy.itertuples():
        rank_h = _get_fifa_rank(r.home)
        rank_a = _get_fifa_rank(r.away)
        rank_diff = rank_a - rank_h  # positivo = local mejor rankeado

        # Probabilidad base desde ranking FIFA (modelo Elo-like simple)
        elo_h = 2000 - rank_h * 30
        elo_a = 2000 - rank_a * 30
        p_home_raw = 1 / (1 + 10 ** ((elo_a - elo_h) / 400))
        # Ajuste por ventaja local (en Fase de Grupos no hay local puro → reducir)
        p_home = p_home_raw * 0.95 + 0.05
        p_draw = 0.25  # en fútbol ~25% de empates
        p_home = p_home * (1 - p_draw)
        p_away = (1 - p_draw) * (1 - p_home_raw * 0.95)
        total = p_home + p_draw + p_away
        p_home /= total; p_draw /= total; p_away /= total

        # Si hay motor entrenado, usar sus predicciones
        if not df.empty:
            try:
                eng = FootballEngine(edge_threshold=filtros["edge_threshold"],
                                     confidence_floor=filtros["confidence_floor"],
                                     market_trust=filtros["market_trust"])
                eng.fit(df[["home", "away", "hg", "ag", "date"]], league_code="WC")
                if r.home in eng._teams_seen and r.away in eng._teams_seen:
                    pred_eng = eng.predict(r.home, r.away)
                    p_home = pred_eng["p_home"]
                    p_draw = pred_eng.get("p_draw", p_draw)
                    p_away = pred_eng["p_away"]
            except Exception:
                pass

        e_ml = _find(r.home, r.away, ml)
        match_bets = []
        if e_ml and e_ml["odds"].get("draw"):
            from mercados import evaluate_three_way
            for b in evaluate_three_way(
                    p_home, p_draw, p_away,
                    e_ml["odds"]["home"], e_ml["odds"]["draw"], e_ml["odds"]["away"],
                    r.home, r.away, filtros["market_trust"],
                    filtros["confidence_floor"], filtros["edge_threshold"]):
                match_bets.append(b)

        # Motivación fase de grupos
        if _HAS_MOTIVACION:
            try:
                mot = analyze_group_motivation(r.home, r.away)
                p_home, p_draw, p_away = adjust_wc_probabilities(
                    p_home, p_draw, p_away, mot)
                for w in mot.get("warnings", []):
                    print(f"     {w}")
            except Exception:
                pass

        print(f"  {r.home} (#{rank_h}) vs {r.away} (#{rank_a})")
        print(f"     p={p_home:.0%}/{p_draw:.0%}/{p_away:.0%}  "
              f"(H/D/A)  ranking_diff={rank_diff:+d}")
        for b in match_bets:
            print(f"     [{b['market']:>7}] {b['label']:<26} @{b['odds_offered']:.2f}  "
                  f"p={b['model_p']:.0%}  edge {b['edge']:.1%}")
            value_bets.append({
                "label": f"WC {r.home[:12]} {b['market']}:{b['label'][:12]}",
                "sport": "WC", "home": r.home, "away": r.away,
                "pick_team": b["label"], "pick_side": b["market"],
                "market": b["market"], "model_p": b["model_p"],
                "odds_offered": b["odds_offered"], "edge": b["edge"],
                "kelly_frac": b["kelly_frac"],
            })
        if not match_bets:
            print(f"     Sin value bets (no hay momios disponibles aún o no hay edge)")

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
    p.add_argument("--mundial", action="store_true",
                   help="Incluir análisis del Mundial FIFA 2026")
    p.add_argument("--backtest", action="store_true",
                   help="Ejecutar backtesting histórico y mostrar ROI por bucket")
    p.add_argument("--telegram", action="store_true",
                   help="Enviar picks del día por Telegram")
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
        "edge_min": a.edge,
        "confidence_floor": a.confianza,
        "nrfi_floor": max(0.55, a.confianza - 0.08),  # NRFI mercado más ineficiente → umbral menor
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

    # Mundial FIFA 2026 — siempre activo cuando hay partidos (a partir del 11 jun)
    if a.mundial or WC_ACTIVE:
        try:
            all_value += analizar_mundial(today, filtros)
        except Exception as e:
            print(f"\n  ERROR en Mundial: {e}")

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

        # Aplicar ajuste de calibración histórica si hay suficiente historial
        if _HAS_CALIBRACION:
            try:
                for bet in top:
                    adj = get_calibration_adjustment(bet["model_p"],
                                                     bet.get("sport", ""))
                    if adj != bet["model_p"]:
                        bet["model_p_cal"] = round(adj, 4)
            except Exception:
                pass

        result = compute_portfolio(top, bankroll=a.banco,
                                   target_return=a.target, min_winners=a.min_ganadores)
        print_portfolio_report(result, bankroll=a.banco)

        # Monte Carlo — simulación de escenarios a 30 días
        try:
            from portfolio import monte_carlo_portfolio, print_monte_carlo_report
            mc = monte_carlo_portfolio(top, bankroll=a.banco, n_sims=5000, days=30)
            print_monte_carlo_report(mc, bankroll=a.banco)
        except Exception:
            pass

        # Guardar picks del día en tracker
        if _HAS_TRACKER:
            try:
                stake = a.banco * 0.02
                save_picks(top, today, stake_per_pick=stake)
            except Exception:
                pass

        # Registrar picks en CLV tracker (para medir Closing Line Value)
        if _HAS_CLV:
            try:
                for bet in top:
                    record_pick(
                        sport=bet.get("sport", ""),
                        home=bet.get("home", ""),
                        away=bet.get("away", ""),
                        pick_team=bet.get("pick_team", bet.get("label", "")),
                        pick_side=bet.get("pick_side", ""),
                        odds_taken=bet.get("odds_offered", 0),
                        source_book="market",
                    )
            except Exception:
                pass
    else:
        print("\n  Hoy NINGUNA apuesta pasa el estándar de calidad.")
        print("  La decisión disciplinada es NO apostar. Esto protege la banca.")

    # Calibración del modelo (si hay historial suficiente)
    if _HAS_CALIBRACION:
        try:
            print_calibration_report()
        except Exception:
            pass

    # Historial y ROI acumulado
    if _HAS_TRACKER:
        try:
            print_stats()
        except Exception:
            pass

    # CLV report — actualiza líneas de cierre de ayer y muestra reporte
    if _HAS_CLV:
        try:
            update_closing_lines()   # actualiza ayer automáticamente
            print_clv_report()
        except Exception:
            pass

    # Backtesting histórico completo
    if a.backtest and _HAS_BACKTEST:
        try:
            print(f"\n{'#'*80}")
            print("#  BACKTESTING HISTÓRICO")
            print(f"{'#'*80}")
            results = run_all_backtests()
            for sport_key, bt_result in results.items():
                print_backtest_report(bt_result, sport_key)
        except Exception as e:
            print(f"  (Backtesting no disponible: {e})")

    # Enviar picks por Telegram
    if _HAS_ALERTAS and (a.telegram or os.environ.get("TELEGRAM_AUTO")):
        try:
            send_daily_picks(all_value, today, a.banco)
        except Exception as e:
            print(f"  (Telegram no enviado: {e})")


if __name__ == "__main__":
    main()
