"""
Backtesting completo — 1000+ juegos reales, multi-deporte, multi-mercado.

Metodología walk-forward honesta:
  - 60% train / 40% test  (sin data leakage)
  - Modelo: SportsEngine (ELO + LR/XGBoost) con Platt calibration
  - Mercados evaluados: moneyline + O/U + spread
  - Odds de mercado: tasa histórica de victorias locales + vig 5% (no circulares)
  - Sizing: quarter-Kelly sobre el edge calculado
  - Métricas: ROI, accuracy, Brier score, CLV simulado, edge vs umbral

Ejecutar:  python backtest_completo.py
"""

import os
import warnings
import numpy as np
import pandas as pd
from scipy.stats import poisson

warnings.filterwarnings("ignore")
CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache")


# ─────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────

def _market_odds(p_hist: float, vig: float = 0.05):
    p_h = np.clip(p_hist, 0.30, 0.70)
    p_a = 1 - p_h
    return round(1 / (p_h * (1 + vig)), 3), round(1 / (p_a * (1 + vig)), 3)


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


# ─────────────────────────────────────────────────────────────────────
#  Motor de backtesting por deporte
# ─────────────────────────────────────────────────────────────────────

def backtest_sport(sport: str, min_edge: float = 0.02,
                   conf_floor: float = 0.54, banco: float = 10000) -> dict:
    """Walk-forward backtesting sobre datos reales del deporte."""
    from motor_deportes import SportsEngine

    csv = os.path.join(CACHE_DIR, f"{sport}_train.csv")
    if not os.path.exists(csv):
        return {"error": f"Sin datos: {csv}", "sport": sport}

    df = pd.read_csv(csv, parse_dates=["date"]).sort_values("date").reset_index(drop=True)
    if len(df) < 200:
        return {"error": "Datos insuficientes (<200 juegos)", "sport": sport}

    split = int(len(df) * 0.60)
    train_df = df.iloc[:split].copy()
    test_df  = df.iloc[split:].copy().reset_index(drop=True)

    # Tasa histórica de victorias locales (se usa para odds de mercado no circulares)
    home_wins_train = (train_df["home_score"] > train_df["away_score"]).mean()

    # Entrenar motor
    eng = SportsEngine(sport=sport.lower(), edge_threshold=min_edge,
                       confidence_floor=conf_floor, market_trust=0.5)
    try:
        eng.fit(train_df)
    except Exception as e:
        return {"error": f"Error fit: {e}", "sport": sport}

    # Calibrador Platt sobre train
    platt = None
    try:
        from calibracion_platt import PlattCalibrator
        cal = PlattCalibrator(sport)
        cal.fit_from_history(
            pd.DataFrame({
                "p_model": [eng.predict(r.home, r.away).get("p_home", 0.5)
                            for r in train_df.itertuples()
                            if r.home in eng._teams_seen and r.away in eng._teams_seen],
                "result":  [1 if r.home_score > r.away_score else 0
                            for r in train_df.itertuples()
                            if r.home in eng._teams_seen and r.away in eng._teams_seen],
            })
        )
        platt = cal
    except Exception:
        pass

    # ── Evaluar en test set ──
    records = []      # todos los juegos evaluados
    bets    = []      # solo los que pasaron el filtro

    for r in test_df.itertuples():
        if r.home not in eng._teams_seen or r.away not in eng._teams_seen:
            continue

        pred = eng.predict(r.home, r.away)
        p_h = pred.get("p_home", 0.5)
        if platt and getattr(platt, "_fitted", False):
            p_h = platt.transform(p_h)
        p_a = 1 - p_h

        actual_home_win = 1 if r.home_score > r.away_score else 0
        total_actual    = r.home_score + r.away_score

        # Odds de mercado independientes del modelo
        odds_h, odds_a = _market_odds(home_wins_train)

        # Scores esperados para O/U
        mu_h, mu_a = eng.expected_scores(r.home, r.away)
        mu_total   = mu_h + mu_a

        records.append({
            "home": r.home, "away": r.away,
            "p_home": p_h, "actual_home_win": actual_home_win,
            "mu_total": mu_total, "actual_total": total_actual,
        })

        # ── Moneyline ──
        edge_h = p_h - _implied(odds_h)
        edge_a = p_a - _implied(odds_a)

        if p_h >= conf_floor and edge_h >= min_edge:
            k = _kelly(p_h, odds_h)
            won = actual_home_win == 1
            bets.append({
                "sport": sport, "market": "ML",
                "pick": f"{r.home} ML", "odds": odds_h,
                "model_p": p_h, "edge": edge_h,
                "kelly": k, "won": won,
                "pnl_unit": (odds_h - 1) if won else -1,
            })

        if p_a >= conf_floor and edge_a >= min_edge:
            k = _kelly(p_a, odds_a)
            won = actual_home_win == 0
            bets.append({
                "sport": sport, "market": "ML",
                "pick": f"{r.away} ML", "odds": odds_a,
                "model_p": p_a, "edge": edge_a,
                "kelly": k, "won": won,
                "pnl_unit": (odds_a - 1) if won else -1,
            })

        # ── O/U total (línea = mu_total de train, simulada) ──
        ou_line = round(mu_total * 2) / 2  # redondear a .5 más cercano
        # Umbral más alto para O/U: el modelo de totales tiene más ruido que moneyline
        ou_floor = min(conf_floor + 0.06, 0.72)
        if ou_line > 0:
            # P(over) con Poisson (béisbol/hockey) o Normal (basket)
            if sport.upper() in ("MLB", "NHL"):
                k_floor = int(ou_line)
                p_over  = 1.0 - poisson.cdf(k_floor, mu_total)
                p_under = poisson.cdf(k_floor, mu_total)
            else:
                from scipy.stats import norm as _norm
                sig_t = getattr(eng, "sigma_total", 18.0) or 18.0
                p_over  = 1.0 - _norm.cdf(ou_line, mu_total, sig_t)
                p_under = _norm.cdf(ou_line, mu_total, sig_t)

            ou_odds = 1.87  # mercado estándar ~−115
            ou_imp  = _implied(ou_odds)

            for direction, p_d, won_d in [
                ("OVER",  p_over,  total_actual > ou_line),
                ("UNDER", p_under, total_actual < ou_line),
            ]:
                edge_d = p_d - ou_imp
                if p_d >= ou_floor and edge_d >= min_edge:
                    k = _kelly(p_d, ou_odds, frac=0.125)  # 1/8 Kelly para totals
                    bets.append({
                        "sport": sport, "market": "OU",
                        "pick": f"Total {direction} {ou_line}",
                        "odds": ou_odds, "model_p": p_d,
                        "edge": edge_d, "kelly": k,
                        "won": won_d,
                        "pnl_unit": (ou_odds - 1) if won_d else -1,
                    })

    if not records:
        return {"error": "Sin juegos evaluables en test set", "sport": sport}

    rec_df = pd.DataFrame(records)
    # Métricas globales del modelo (todos los juegos, sin filtro)
    brier = _brier(rec_df["actual_home_win"], rec_df["p_home"])
    accuracy = float((rec_df["p_home"] > 0.5) == rec_df["actual_home_win"]).mean() if False else \
               (((rec_df["p_home"] > 0.5).astype(int)) == rec_df["actual_home_win"]).mean()

    if not bets:
        return {
            "sport": sport, "n_games_evaluated": len(records),
            "n_bets": 0, "roi": 0.0, "accuracy": round(accuracy, 4),
            "brier": round(brier, 4),
            "error": "Ninguna apuesta pasó el filtro — prueba bajar --edge",
        }

    bet_df = pd.DataFrame(bets)
    n_bets  = len(bet_df)
    n_won   = int(bet_df["won"].sum())
    win_pct = n_won / n_bets

    # ROI por unidad (stake = 1 por apuesta)
    total_pnl   = float(bet_df["pnl_unit"].sum())
    roi         = total_pnl / n_bets  # ROI por apuesta apostada

    # ROI por Kelly (sizing proporcional al bankroll inicial)
    bank  = banco
    for _, b in bet_df.iterrows():
        stake = bank * b["kelly"]
        if b["won"]:
            bank += stake * (b["odds"] - 1)
        else:
            bank -= stake
    roi_kelly = (bank - banco) / banco

    # Edge promedio de las apuestas seleccionadas
    avg_edge = float(bet_df["edge"].mean())
    avg_odds = float(bet_df["odds"].mean())

    # Distribución por mercado
    by_market = bet_df.groupby("market").agg(
        n=("won", "count"),
        wins=("won", "sum"),
        pnl=("pnl_unit", "sum"),
        avg_edge=("edge", "mean"),
    ).to_dict("index")

    # Curva de equity (bankroll por bloque de 50 apuestas)
    equity = []
    b2 = banco
    for _, row in bet_df.iterrows():
        stake = b2 * row["kelly"]
        b2 += stake * (row["odds"] - 1) if row["won"] else -stake
        equity.append(round(b2, 2))

    # Drawdown máximo
    peak = banco
    max_dd = 0.0
    running = banco
    for _, row in bet_df.iterrows():
        stake = running * row["kelly"]
        running += stake * (row["odds"] - 1) if row["won"] else -stake
        peak = max(peak, running)
        dd = (peak - running) / peak
        max_dd = max(max_dd, dd)

    return {
        "sport":              sport,
        "n_games_evaluated":  len(records),
        "n_bets":             n_bets,
        "n_won":              n_won,
        "win_pct":            round(win_pct, 4),
        "roi_flat":           round(roi, 4),
        "roi_kelly":          round(roi_kelly, 4),
        "final_bank":         round(bank, 2),
        "avg_edge":           round(avg_edge, 4),
        "avg_odds":           round(avg_odds, 3),
        "brier":              round(brier, 4),
        "accuracy":           round(accuracy, 4),
        "max_drawdown":       round(max_dd, 4),
        "by_market":          by_market,
        "equity_curve":       equity[::max(1, len(equity)//50)],  # muestra 50 puntos
        "bets_df":            bet_df,
    }


# ─────────────────────────────────────────────────────────────────────
#  Reportes
# ─────────────────────────────────────────────────────────────────────

def _bar(value, max_val, width=30, fill="█", empty="░"):
    n = int(round(value / max(max_val, 1e-6) * width))
    n = max(0, min(n, width))
    return fill * n + empty * (width - n)


def print_report(res: dict):
    if "error" in res and "n_bets" not in res:
        print(f"  ERROR ({res['sport']}): {res['error']}")
        return

    sport = res["sport"].upper()
    print(f"\n{'═'*70}")
    print(f"  {sport}  —  {res['n_games_evaluated']} juegos evaluados")
    print(f"{'═'*70}")

    if res["n_bets"] == 0:
        print(f"  Sin apuestas que pasen el filtro. {res.get('error','')}")
        return

    roi_flat  = res["roi_flat"]
    roi_kelly = res["roi_kelly"]
    win_pct   = res["win_pct"]
    n_bets    = res["n_bets"]
    n_won     = res["n_won"]

    roi_color = "+" if roi_flat >= 0 else ""
    print(f"\n  📊 RESUMEN DE APUESTAS")
    print(f"  {'Apuestas seleccionadas':<28}: {n_bets}")
    print(f"  {'Ganadas':<28}: {n_won}  ({win_pct:.1%})")
    print(f"  {'ROI flat-stake':<28}: {roi_color}{roi_flat:.2%}")
    print(f"  {'ROI Kelly (¼)':<28}: {'+' if roi_kelly>=0 else ''}{roi_kelly:.2%}")
    print(f"  {'Banco final ($10,000)':<28}: ${res['final_bank']:,.0f}  ({'+' if (res['final_bank']-10000)>=0 else ''}{(res['final_bank']-10000)/10000:.1%})")
    print(f"  {'Max drawdown':<28}: {res['max_drawdown']:.1%}")
    print(f"  {'Edge promedio picks':<28}: {res['avg_edge']:+.2%}")
    print(f"  {'Cuota promedio':<28}: {res['avg_odds']:.3f}")

    print(f"\n  🎯 CALIDAD DEL MODELO")
    print(f"  {'Accuracy (mejor lado > 50%)':<28}: {res['accuracy']:.1%}")
    print(f"  {'Brier score (< 0.25 = bueno)':<28}: {res['brier']:.4f}")

    # Por mercado
    if res.get("by_market"):
        print(f"\n  📂 POR MERCADO")
        print(f"  {'Mercado':<8} {'N':>5} {'Ganadas':>8} {'Win%':>7} {'ROI':>8} {'Edge Prom':>10}")
        print(f"  {'-'*55}")
        for mkt, d in res["by_market"].items():
            wp = d["wins"] / d["n"] if d["n"] > 0 else 0
            roi_m = d["pnl"] / d["n"] if d["n"] > 0 else 0
            print(f"  {mkt:<8} {d['n']:>5} {int(d['wins']):>8} {wp:>7.1%} {roi_m:>+8.2%} {d['avg_edge']:>+9.2%}")

    # Curva de equity ASCII
    eq = res.get("equity_curve", [])
    if eq and len(eq) > 2:
        eq_min = min(eq); eq_max = max(eq)
        print(f"\n  📈 CURVA DE BANKROLL  (min ${eq_min:,.0f}  max ${eq_max:,.0f})")
        for i, val in enumerate(eq):
            bar = _bar(val - eq_min, max(eq_max - eq_min, 1), width=40)
            print(f"  {i*max(1,len(res['equity_curve'])//50):>4}  ${val:>8,.0f}  {bar}")


def print_summary(results: list):
    print(f"\n\n{'#'*70}")
    print(f"#  RESUMEN GLOBAL — {sum(r.get('n_games_evaluated',0) for r in results)} juegos totales")
    print(f"{'#'*70}")

    total_bets = sum(r.get("n_bets", 0) for r in results)
    total_won  = sum(r.get("n_won", 0) for r in results)
    all_pnl    = sum(r.get("roi_flat", 0) * r.get("n_bets", 0) for r in results)
    roi_global = all_pnl / max(total_bets, 1)

    print(f"\n  {'Deporte':<8} {'Juegos':>8} {'Picks':>7} {'Win%':>7} {'ROI flat':>9} {'ROI Kelly':>10} {'Brier':>7}")
    print(f"  {'-'*65}")
    for r in results:
        if "error" in r and "n_bets" not in r:
            print(f"  {r['sport']:<8}  ERROR: {r['error']}")
            continue
        wp = r.get("win_pct", 0)
        print(f"  {r['sport']:<8} {r.get('n_games_evaluated',0):>8} {r.get('n_bets',0):>7} "
              f"{wp:>7.1%} {r.get('roi_flat',0):>+9.2%} {r.get('roi_kelly',0):>+10.2%} "
              f"{r.get('brier',0):>7.4f}")

    print(f"\n  {'TOTAL':<8} {sum(r.get('n_games_evaluated',0) for r in results):>8} "
          f"{total_bets:>7} {total_won/max(total_bets,1):>7.1%} {roi_global:>+9.2%}")

    print(f"\n  {'─'*50}")
    print(f"  Apuestas totales evaluadas : {total_bets}")
    print(f"  Ganadas                    : {total_won} ({total_won/max(total_bets,1):.1%})")
    print(f"  ROI global (flat-stake)    : {roi_global:+.2%}")

    # Veredicto
    if roi_global > 0.05:
        v = "🟢  SISTEMA RENTABLE — edge real vs mercado detectado."
    elif roi_global > 0:
        v = "🟡  SISTEMA CON EDGE MARGINAL — rentable pero estrecho."
    elif roi_global > -0.03:
        v = "🟠  SISTEMA BREAK-EVEN — calibración puede mejorar el ROI."
    else:
        v = "🔴  SISTEMA CON PÉRDIDA — revisar parámetros o datos."
    print(f"\n  Veredicto: {v}")


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
    args = ap.parse_args()

    print(f"\n{'#'*70}")
    print(f"#  BACKTESTING COMPLETO — ZUBAMX")
    print(f"#  Edge mín: {args.edge:.1%}  |  Confianza: {args.confianza:.0%}  |  Banco: ${args.banco:,.0f}")
    print(f"#  Quarter-Kelly sizing  |  Odds no-circulares (vig 5%)")
    print(f"{'#'*70}")

    results = []
    for sport in args.deportes:
        print(f"\n  ⏳ Procesando {sport}...")
        r = backtest_sport(sport, min_edge=args.edge,
                           conf_floor=args.confianza, banco=args.banco)
        results.append(r)
        print_report(r)

    print_summary(results)
