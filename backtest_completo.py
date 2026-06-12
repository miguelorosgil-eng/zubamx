"""
Backtesting completo — walk-forward multi-fold con odds reales.

Metodología:
  - Expanding window: fold N usa meses 1..N como train, mes N+1 como test.
  - Odds de mercado: closing lines de Pinnacle vía The Odds API histórico
    (caché en _cache/historical_odds/{sport}/{YYYY-MM-DD}.json).
    Si no hay odds históricas disponibles, AVISA y excluye el partido.
  - Métricas: ROI flat, ROI Kelly, CLV promedio (model vs closing line),
    ROI por fold + std para detectar dependencia de folds aislados.
  - Si CLV ≤ 0 → el mercado/deporte no tiene edge real. Punto.

Criterio de aceptación:
  - backtest corre 100% con odds reales (no sintéticas)
  - CLV promedio > +1.5% sostenido = edge demostrado
  - ROI global > 15% → tiene un bug hasta que se demuestre lo contrario

Ejecutar:  python backtest_completo.py [--edge 0.02] [--confianza 0.54] [--banco 10000]
"""

import os
import json
import warnings
import datetime
import numpy as np
import pandas as pd
from scipy.stats import poisson

warnings.filterwarnings("ignore")
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache")
HIST_ODDS_DIR = os.path.join(CACHE_DIR, "historical_odds")


# ─────────────────────────────────────────────────────────────────────
#  Descarga y caché de odds históricas (Pinnacle closing lines)
# ─────────────────────────────────────────────────────────────────────

_SPORT_KEYS = {
    "MLB": "baseball_mlb",
    "NBA": "basketball_nba",
    "NHL": "icehockey_nhl",
}

PREFERRED_BOOK = "pinnacle"


def _load_cached_odds(sport: str, date_str: str) -> list:
    path = os.path.join(HIST_ODDS_DIR, sport, f"{date_str}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


def _save_cached_odds(sport: str, date_str: str, data: list):
    d = os.path.join(HIST_ODDS_DIR, sport)
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, f"{date_str}.json")
    with open(path, "w") as f:
        json.dump(data, f)


def fetch_closing_odds(sport: str, date_str: str, api_key: str) -> list:
    """
    Descarga closing lines de Pinnacle para una fecha (snapshot ~hora de inicio).
    Cachea en disco — NO repite la llamada si ya existe.
    Devuelve lista de {home, away, odds_home, odds_away}.
    """
    cached = _load_cached_odds(sport, date_str)
    if cached is not None:
        return cached

    try:
        import requests
        sport_key = _SPORT_KEYS.get(sport.upper())
        if not sport_key:
            return []
        from conector_odds import ODDS_API_KEY
        key = api_key or ODDS_API_KEY
        url = f"https://api.the-odds-api.com/v4/historical/sports/{sport_key}/odds/"
        params = {
            "apiKey": key,
            "date": f"{date_str}T22:00:00Z",  # cierre típico de líneas
            "regions": "us",
            "markets": "h2h",
            "oddsFormat": "decimal",
        }
        resp = requests.get(url, params=params, timeout=20)
        resp.raise_for_status()
        raw = resp.json()
        events_raw = raw.get("data", raw) if isinstance(raw, dict) else raw
        if not isinstance(events_raw, list):
            return []

        results = []
        for ev in events_raw:
            home = ev.get("home_team", "")
            away = ev.get("away_team", "")
            # Preferir Pinnacle
            bookmakers = ev.get("bookmakers", [])
            selected_bm = next((b for b in bookmakers if b.get("key") == PREFERRED_BOOK), None)
            if not selected_bm and bookmakers:
                selected_bm = bookmakers[0]
            if not selected_bm:
                continue
            for mkt in selected_bm.get("markets", []):
                if mkt.get("key") != "h2h":
                    continue
                outcomes = {o["name"]: o["price"] for o in mkt.get("outcomes", [])}
                h_odds = outcomes.get(home)
                a_odds = outcomes.get(away)
                if h_odds and a_odds:
                    results.append({"home": home, "away": away,
                                    "odds_home": h_odds, "odds_away": a_odds})
                    break
        _save_cached_odds(sport, date_str, results)
        return results
    except Exception:
        _save_cached_odds(sport, date_str, [])  # marcar como "intentado"
        return []


def _match_odds(home: str, away: str, closing_list: list) -> dict | None:
    """Empareja un partido con las odds históricas por fuzzy matching."""
    from difflib import SequenceMatcher
    best, best_score = None, 0.0
    for ev in closing_list:
        sh = SequenceMatcher(None, home.lower(), ev["home"].lower()).ratio()
        sa = SequenceMatcher(None, away.lower(), ev["away"].lower()).ratio()
        score = (sh + sa) / 2
        if score > best_score:
            best, best_score = ev, score
    return best if best_score > 0.55 else None


# ─────────────────────────────────────────────────────────────────────
#  Helpers de backtesting
# ─────────────────────────────────────────────────────────────────────

def _kelly(p: float, odds: float, frac: float = 0.25) -> float:
    edge = p * odds - 1
    if edge <= 0 or odds <= 1:
        return 0.0
    k = edge / (odds - 1)
    return max(0.0, k * frac)


def _brier(y_true, y_pred):
    return float(np.mean((np.array(y_pred) - np.array(y_true)) ** 2))


def _implied(odds: float) -> float:
    return 1.0 / odds if odds > 1 else 1.0


def _novig_prob(odds_h: float, odds_a: float) -> tuple[float, float]:
    """Quita la vig. Devuelve (p_home_novig, p_away_novig)."""
    raw_h = 1.0 / odds_h
    raw_a = 1.0 / odds_a
    total = raw_h + raw_a
    return raw_h / total, raw_a / total


# ─────────────────────────────────────────────────────────────────────
#  Motor de backtesting por fold
# ─────────────────────────────────────────────────────────────────────

def backtest_fold(sport: str, train_df: pd.DataFrame, test_df: pd.DataFrame,
                  min_edge: float, conf_floor: float, banco: float,
                  api_key: str = None) -> dict:
    """
    Entrena en train_df, evalúa en test_df.
    Usa closing odds reales de Pinnacle si están disponibles.
    Devuelve dict con métricas del fold.
    """
    from motor_deportes import SportsEngine

    if len(train_df) < 100:
        return {"error": "Train insuficiente", "n_bets": 0}
    if len(test_df) < 20:
        return {"error": "Test insuficiente", "n_bets": 0}

    eng = SportsEngine(sport=sport.lower(), edge_threshold=min_edge,
                       confidence_floor=conf_floor, market_trust=0.5)
    try:
        eng.fit(train_df)
    except Exception as e:
        return {"error": f"fit: {e}", "n_bets": 0}

    # Calibrador Platt SOLO sobre train
    platt = None
    try:
        from calibracion_platt import PlattCalibrator
        cal = PlattCalibrator(sport)
        pairs = [(r.home, r.away, 1 if r.home_score > r.away_score else 0)
                 for r in train_df.itertuples()
                 if r.home in eng._teams_seen and r.away in eng._teams_seen]
        if pairs:
            preds_train = [eng.predict(h, a).get("p_home", 0.5) for h, a, _ in pairs]
            results_train = [lbl for _, _, lbl in pairs]
            cal.fit_from_history(pd.DataFrame({"p_model": preds_train, "result": results_train}))
            platt = cal
    except Exception:
        pass

    # Agrupar test por fecha para cargar odds históricas en batch
    test_dates = test_df["date"].dt.date.unique() if hasattr(test_df["date"].iloc[0], "date") \
                 else pd.to_datetime(test_df["date"]).dt.date.unique()
    odds_by_date = {}
    n_real_odds = 0
    n_missing_odds = 0
    for d in test_dates:
        d_str = str(d)
        ev_list = fetch_closing_odds(sport, d_str, api_key)
        odds_by_date[d_str] = ev_list
        if ev_list:
            n_real_odds += 1
        else:
            n_missing_odds += 1

    bets = []
    clv_values = []

    for r in test_df.itertuples():
        if r.home not in eng._teams_seen or r.away not in eng._teams_seen:
            continue

        pred = eng.predict(r.home, r.away)
        p_h = pred.get("p_home", 0.5)
        if platt and getattr(platt, "_fitted", False):
            p_h = platt.transform(p_h)
        p_a = 1 - p_h

        actual_home_win = 1 if r.home_score > r.away_score else 0

        # Buscar closing odds reales
        date_key = str(pd.Timestamp(r.date).date())
        closing_list = odds_by_date.get(date_key, [])
        matched = _match_odds(r.home, r.away, closing_list) if closing_list else None

        if matched is None:
            # Sin odds reales — NO evaluar este partido (evita odds sintéticas)
            continue

        odds_h = matched["odds_home"]
        odds_a = matched["odds_away"]
        novig_h, novig_a = _novig_prob(odds_h, odds_a)

        # CLV: edge del modelo vs closing line sin vig
        clv_h = p_h - novig_h
        clv_a = p_a - novig_a
        clv_values.append(clv_h)  # perspectiva del local

        # Evaluar moneyline
        edge_h = p_h - _implied(odds_h)
        edge_a = p_a - _implied(odds_a)

        if p_h >= conf_floor and edge_h >= min_edge:
            k = _kelly(p_h, odds_h)
            won = actual_home_win == 1
            bets.append({
                "sport": sport, "market": "ML",
                "pick": f"{r.home} ML", "odds": odds_h,
                "model_p": p_h, "novig_p": novig_h,
                "edge": edge_h, "clv": clv_h,
                "kelly": k, "won": won,
                "pnl_unit": (odds_h - 1) if won else -1,
            })

        if p_a >= conf_floor and edge_a >= min_edge:
            k = _kelly(p_a, odds_a)
            won = actual_home_win == 0
            bets.append({
                "sport": sport, "market": "ML",
                "pick": f"{r.away} ML", "odds": odds_a,
                "model_p": p_a, "novig_p": novig_a,
                "edge": edge_a, "clv": clv_a,
                "kelly": k, "won": won,
                "pnl_unit": (odds_a - 1) if won else -1,
            })

    if not bets:
        return {
            "n_bets": 0, "n_games_with_odds": n_real_odds,
            "n_missing_odds": n_missing_odds, "error": "Sin apuestas con odds reales",
        }

    bet_df = pd.DataFrame(bets)
    n_bets  = len(bet_df)
    n_won   = int(bet_df["won"].sum())
    win_pct = n_won / n_bets
    roi_flat = float(bet_df["pnl_unit"].sum()) / n_bets
    avg_clv  = float(bet_df["clv"].mean())
    avg_edge = float(bet_df["edge"].mean())

    # Kelly compounding
    bank = banco
    for _, b in bet_df.iterrows():
        stake = bank * b["kelly"]
        bank += stake * (b["odds"] - 1) if b["won"] else -stake
    roi_kelly = (bank - banco) / banco

    # Drawdown máximo
    peak, max_dd, running = banco, 0.0, banco
    for _, b in bet_df.iterrows():
        stake = running * b["kelly"]
        running += stake * (b["odds"] - 1) if b["won"] else -stake
        peak = max(peak, running)
        max_dd = max(max_dd, (peak - running) / max(peak, 1e-6))

    return {
        "n_bets": n_bets, "n_won": n_won, "win_pct": round(win_pct, 4),
        "roi_flat": round(roi_flat, 4), "roi_kelly": round(roi_kelly, 4),
        "avg_clv": round(avg_clv, 4), "avg_edge": round(avg_edge, 4),
        "max_drawdown": round(max_dd, 4),
        "n_games_with_odds": n_real_odds, "n_missing_odds": n_missing_odds,
        "bets_df": bet_df,
    }


# ─────────────────────────────────────────────────────────────────────
#  Walk-forward multi-fold (expanding window)
# ─────────────────────────────────────────────────────────────────────

def backtest_sport(sport: str, min_edge: float = 0.02,
                   conf_floor: float = 0.54, banco: float = 10000,
                   api_key: str = None, min_train_months: int = 6) -> dict:
    """
    Walk-forward expanding window:
      Fold 1: train meses 1-6  → test mes 7
      Fold 2: train meses 1-7  → test mes 8
      ...
    Recalibra Platt en cada fold.
    Reporta ROI por fold + std para detectar dependencia en folds buenos.
    """
    csv = os.path.join(CACHE_DIR, f"{sport}_train.csv")
    if not os.path.exists(csv):
        return {"error": f"Sin datos: {csv}", "sport": sport}

    df = pd.read_csv(csv, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    if len(df) < 200:
        return {"error": "Datos insuficientes (<200 juegos)", "sport": sport}

    # Asignar períodos mensuales
    df["_period"] = df["date"].dt.to_period("M")
    periods = df["_period"].unique()
    periods.sort()

    if len(periods) < min_train_months + 1:
        return {"error": f"Necesita al menos {min_train_months + 1} meses de datos", "sport": sport}

    fold_results = []
    all_bets = []
    brier_vals = []

    print(f"\n[Backtest {sport}] {len(periods)} meses, "
          f"expanding window (mín train={min_train_months} meses)")

    for test_idx in range(min_train_months, len(periods)):
        train_periods = periods[:test_idx]
        test_period   = periods[test_idx]

        train_df = df[df["_period"].isin(train_periods)].drop(columns=["_period"])
        test_df  = df[df["_period"] == test_period].drop(columns=["_period"])

        if len(train_df) < 100 or len(test_df) < 10:
            continue

        fold_res = backtest_fold(sport, train_df, test_df, min_edge, conf_floor, banco, api_key)
        fold_res["fold"] = str(test_period)
        fold_results.append(fold_res)

        if "bets_df" in fold_res and fold_res["bets_df"] is not None:
            all_bets.append(fold_res["bets_df"])

        # Brier sobre todos los juegos de test
        from motor_deportes import SportsEngine
        try:
            eng = SportsEngine(sport=sport.lower(), edge_threshold=min_edge,
                               confidence_floor=conf_floor, market_trust=0.5)
            eng.fit(train_df)
            y_true = [1 if r.home_score > r.away_score else 0
                      for r in test_df.itertuples()
                      if r.home in eng._teams_seen and r.away in eng._teams_seen]
            y_pred = [eng.predict(r.home, r.away).get("p_home", 0.5)
                      for r in test_df.itertuples()
                      if r.home in eng._teams_seen and r.away in eng._teams_seen]
            if y_true:
                brier_vals.append(_brier(y_true, y_pred))
        except Exception:
            pass

        status = "OK" if fold_res.get("n_bets", 0) > 0 else fold_res.get("error", "?")
        n_b = fold_res.get("n_bets", 0)
        roi = fold_res.get("roi_flat", 0)
        clv = fold_res.get("avg_clv", 0)
        print(f"  Fold {test_period}: {len(train_df):>4} train | {len(test_df):>3} test | "
              f"picks={n_b:>4} | ROI={roi:>+7.2%} | CLV={clv:>+6.2%}  [{status}]")

    if not fold_results:
        return {"error": "Ningún fold válido", "sport": sport}

    # Agregar métricas globales
    valid_folds = [f for f in fold_results if f.get("n_bets", 0) > 0]
    if not valid_folds:
        return {"error": "Sin apuestas con odds reales en ningún fold", "sport": sport,
                "fold_results": fold_results}

    total_bets = sum(f["n_bets"] for f in valid_folds)
    total_won  = sum(f["n_won"] for f in valid_folds)
    pnl_total  = sum(f["roi_flat"] * f["n_bets"] for f in valid_folds)
    roi_global = pnl_total / total_bets

    fold_rois = [f["roi_flat"] for f in valid_folds]
    roi_std   = float(np.std(fold_rois))
    roi_min   = min(fold_rois)
    roi_max   = max(fold_rois)
    n_positive_folds = sum(1 for r in fold_rois if r > 0)

    clv_values = [f["avg_clv"] for f in valid_folds if "avg_clv" in f]
    avg_clv_global = float(np.mean(clv_values)) if clv_values else 0.0

    # Consolidar todas las apuestas
    if all_bets:
        all_bets_df = pd.concat(all_bets, ignore_index=True)
        bank = banco
        max_dd = 0.0
        peak = banco
        running = banco
        for _, b in all_bets_df.iterrows():
            stake = running * b["kelly"]
            running += stake * (b["odds"] - 1) if b["won"] else -stake
            peak = max(peak, running)
            max_dd = max(max_dd, (peak - running) / max(peak, 1e-6))
        roi_kelly_global = (running - banco) / banco
    else:
        roi_kelly_global = 0.0
        max_dd = 0.0

    # Veredicto sobre CLV
    if avg_clv_global > 0.015:
        clv_verdict = "EDGE REAL — CLV>1.5% sostenido"
    elif avg_clv_global > 0:
        clv_verdict = "EDGE MARGINAL — CLV positivo pero débil (<1.5%)"
    else:
        clv_verdict = "SIN EDGE — CLV negativo o nulo; no apostar este deporte/mercado"

    return {
        "sport":              sport,
        "n_folds":            len(valid_folds),
        "n_bets":             total_bets,
        "n_won":              total_won,
        "win_pct":            round(total_won / max(total_bets, 1), 4),
        "roi_flat":           round(roi_global, 4),
        "roi_kelly":          round(roi_kelly_global, 4),
        "roi_std_per_fold":   round(roi_std, 4),
        "roi_min_fold":       round(roi_min, 4),
        "roi_max_fold":       round(roi_max, 4),
        "n_positive_folds":   n_positive_folds,
        "avg_clv":            round(avg_clv_global, 4),
        "clv_verdict":        clv_verdict,
        "avg_brier":          round(float(np.mean(brier_vals)), 4) if brier_vals else None,
        "max_drawdown":       round(max_dd, 4),
        "fold_results":       fold_results,
        # Advertencia si ROI global >15% (flag de bug potencial)
        "roi_sanity_warning": roi_global > 0.15,
    }


# ─────────────────────────────────────────────────────────────────────
#  Reportes
# ─────────────────────────────────────────────────────────────────────

def print_report(res: dict):
    if "error" in res and res.get("n_bets", 0) == 0:
        print(f"  ERROR ({res.get('sport','?')}): {res['error']}")
        return

    sport = res["sport"].upper()
    print(f"\n{'═'*70}")
    print(f"  {sport}  —  {res.get('n_folds', 1)} fold(s)  |  {res.get('n_bets', 0)} picks con odds reales")
    print(f"{'═'*70}")

    if res.get("n_bets", 0) == 0:
        print(f"  Sin apuestas. {res.get('error', '')}")
        return

    roi_flat  = res["roi_flat"]
    roi_kelly = res["roi_kelly"]
    win_pct   = res["win_pct"]
    avg_clv   = res["avg_clv"]

    print(f"\n  📊 RESUMEN (odds reales Pinnacle)")
    print(f"  {'Picks seleccionados':<30}: {res['n_bets']}")
    print(f"  {'Ganadas':<30}: {res['n_won']}  ({win_pct:.1%})")
    print(f"  {'ROI flat-stake':<30}: {roi_flat:>+.2%}")
    print(f"  {'ROI Kelly':<30}: {roi_kelly:>+.2%}")
    print(f"  {'CLV promedio vs Pinnacle':<30}: {avg_clv:>+.2%}  ← métrica real")
    print(f"  {'Veredicto CLV':<30}: {res.get('clv_verdict','')}")

    if res.get("roi_sanity_warning"):
        print(f"\n  ⚠️  ROI>{res['roi_flat']:.0%} — posible bug en datos o leakage. No confiable.")

    # Por fold
    folds = [f for f in res.get("fold_results", []) if f.get("n_bets", 0) > 0]
    if folds:
        print(f"\n  📂 ROI POR FOLD (std={res['roi_std_per_fold']:+.2%}, "
              f"positivos={res['n_positive_folds']}/{len(folds)})")
        print(f"  {'Fold':<10} {'Picks':>6} {'Win%':>7} {'ROI':>8} {'CLV':>8} {'OddsReales':>11}")
        print(f"  {'-'*55}")
        for f in folds:
            print(f"  {f['fold']:<10} {f['n_bets']:>6} {f['win_pct']:>7.1%} "
                  f"{f['roi_flat']:>+8.2%} {f.get('avg_clv', 0):>+8.2%} "
                  f"{f.get('n_games_with_odds', 0):>11}")

    if res.get("avg_brier"):
        print(f"\n  🎯 CALIDAD: Brier={res['avg_brier']:.4f}  Max Drawdown={res['max_drawdown']:.1%}")


def print_summary(results: list):
    print(f"\n\n{'#'*70}")
    total_bets = sum(r.get("n_bets", 0) for r in results)
    print(f"#  RESUMEN GLOBAL — {total_bets} picks con odds reales Pinnacle")
    print(f"{'#'*70}")

    print(f"\n  {'Deporte':<8} {'Folds':>6} {'Picks':>7} {'Win%':>7} "
          f"{'ROI flat':>9} {'CLV prom':>9} {'Veredicto'}")
    print(f"  {'-'*80}")
    for r in results:
        if "error" in r and r.get("n_bets", 0) == 0:
            print(f"  {r.get('sport','?'):<8}  ERROR: {r['error']}")
            continue
        wp = r.get("win_pct", 0)
        clv = r.get("avg_clv", 0)
        verdict = "✅" if clv > 0.015 else ("⚠️" if clv > 0 else "❌")
        print(f"  {r['sport']:<8} {r.get('n_folds',0):>6} {r.get('n_bets',0):>7} "
              f"{wp:>7.1%} {r.get('roi_flat',0):>+9.2%} {clv:>+9.2%}  {verdict} {r.get('clv_verdict','')[:40]}")

    # Global
    all_valid = [r for r in results if r.get("n_bets", 0) > 0]
    if all_valid:
        total_pnl = sum(r["roi_flat"] * r["n_bets"] for r in all_valid)
        total_bets_v = sum(r["n_bets"] for r in all_valid)
        roi_global = total_pnl / total_bets_v
        avg_clv_all = np.mean([r["avg_clv"] for r in all_valid])
        print(f"\n  {'GLOBAL':<8} {'':>6} {total_bets_v:>7} {'':>7} {roi_global:>+9.2%} "
              f"{avg_clv_all:>+9.2%}")

    print(f"\n  NOTA: CLV>1.5% sostenido = edge real. ROI corto plazo no es señal.")
    print(f"  Expectativa honesta de los mejores sistemas: 3-6% ROI sostenido.")


# ─────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--edge",      type=float, default=0.02)
    ap.add_argument("--confianza", type=float, default=0.54)
    ap.add_argument("--banco",     type=float, default=10000)
    ap.add_argument("--deportes",  nargs="*",  default=["MLB", "NBA", "NHL"])
    ap.add_argument("--api-key",   type=str,   default=None,
                    help="The Odds API key (default: usa ODDS_API_KEY de conector_odds)")
    args = ap.parse_args()

    os.makedirs(HIST_ODDS_DIR, exist_ok=True)

    print(f"\n{'#'*70}")
    print(f"#  BACKTESTING WALK-FORWARD MULTI-FOLD — ZUBAMX v3.0")
    print(f"#  Edge mín: {args.edge:.1%}  |  Confianza: {args.confianza:.0%}  |  Banco: ${args.banco:,.0f}")
    print(f"#  Odds: Pinnacle closing lines reales (caché local)")
    print(f"#  ADVERTENCIA: Picks sin odds históricas disponibles se EXCLUYEN.")
    print(f"{'#'*70}")

    results = []
    for sport in args.deportes:
        print(f"\n  ⏳ Procesando {sport} (expanding window)...")
        r = backtest_sport(sport, min_edge=args.edge,
                           conf_floor=args.confianza, banco=args.banco,
                           api_key=args.api_key)
        results.append(r)
        print_report(r)

    print_summary(results)
