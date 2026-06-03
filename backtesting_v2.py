"""
Backtesting v2 — con Platt Scaling + threshold óptimo por deporte.

Metodología walk-forward honesta:
  1. 60% datos → entrenar motor + entrenar calibrador Platt
  2. 40% datos → evaluar con probabilidades calibradas
  3. Threshold por deporte calculado dinámicamente (maximiza ROI * sqrt(n))
  4. Odds simuladas con vig del 5% sobre la probabilidad de mercado implícita
     (separada de la probabilidad del modelo para no crear circularidad)

La diferencia clave vs v1:
  - Antes: odds = 1 / (p_model * 0.95)  → circular, sin edge posible
  - Ahora: odds de mercado = 1 / (p_implicita_mercado * 0.95)
           donde p_mercado = p_historica_promedio para ese matchup tipo
           Edge real = p_calibrada - p_implicita_mercado
"""

import os
import warnings
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

CACHE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def _simulate_market_odds(home_win_rate_hist: float, vig: float = 0.05) -> tuple:
    """
    Simula odds de mercado independientes del modelo.
    Usa la tasa histórica de victorias locales por liga, no la predicción del modelo.
    Esto rompe la circularidad.
    """
    p_h = np.clip(home_win_rate_hist, 0.35, 0.65)
    p_a = 1 - p_h
    # Aplicar vig: casas retienen 5% del pool
    odds_h = round(1 / (p_h * (1 + vig)), 3)
    odds_a = round(1 / (p_a * (1 + vig)), 3)
    return odds_h, odds_a


def run_backtest_v2(sport: str, banco: float = 10000) -> dict:
    """
    Backtesting walk-forward con calibración Platt.
    Devuelve dict con métricas completas.
    """
    from motor_deportes import SportsEngine
    from calibracion_platt import PlattCalibrator

    df = pd.read_csv(os.path.join(CACHE_DIR, f"{sport}_train.csv"), parse_dates=["date"])
    df = df.sort_values("date").reset_index(drop=True)

    if len(df) < 200:
        return {"error": "Datos insuficientes", "sport": sport}

    split = int(len(df) * 0.60)
    train = df.iloc[:split].copy()
    test  = df.iloc[split:].copy().reset_index(drop=True)

    # ── 1. Entrenar motor ──────────────────────────────────────────────────
    eng = SportsEngine(sport=sport.lower(), confidence_floor=0.50,
                       edge_threshold=0.0, market_trust=0.0)
    eng.fit(train)

    # ── 2. Obtener predicciones en TRAIN para entrenar Platt ───────────────
    platt_rows = []
    home_wins_train = []
    for _, row in train.iterrows():
        h, a = row["home"], row["away"]
        if h not in eng._teams_seen or a not in eng._teams_seen:
            continue
        try:
            pred = eng.predict(h, a)
            p_h = pred.get("p_home", 0.5)
            actual = int(row["home_score"] > row["away_score"])
            platt_rows.append({"p_model": p_h, "result": actual})
            home_wins_train.append(actual)
        except Exception:
            continue

    # Tasa histórica de victorias locales (para odds de mercado independientes)
    home_win_rate = np.mean(home_wins_train) if home_wins_train else 0.54

    # Entrenar Platt Scaling
    platt = PlattCalibrator(sport)
    if len(platt_rows) >= 50:
        platt.fit_from_history(pd.DataFrame(platt_rows))

    # ── 3. Encontrar threshold óptimo en últimos 20% del train ─────────────
    val_start = int(len(platt_rows) * 0.80)
    val_rows = platt_rows[val_start:]
    best_thr, best_score = 0.60, -999
    for thr in np.arange(0.55, 0.80, 0.01):
        sub = [r for r in val_rows if platt.transform(r["p_model"]) >= thr]
        if len(sub) < 15:
            continue
        roi = np.mean([(r["result"] * 2 - 1) for r in sub])
        score = roi * np.sqrt(len(sub))
        if score > best_score:
            best_score, best_thr = score, round(float(thr), 2)

    # ── 4. Evaluar en TEST con Platt + threshold óptimo ────────────────────
    bets = []
    bankroll = banco
    odds_h_market, odds_a_market = _simulate_market_odds(home_win_rate)

    for _, row in test.iterrows():
        h, a = row["home"], row["away"]
        if h not in eng._teams_seen or a not in eng._teams_seen:
            continue
        try:
            pred = eng.predict(h, a)
            p_h_raw  = pred.get("p_home", 0.5)
            p_a_raw  = 1 - p_h_raw

            # Calibrar con Platt
            p_h_cal = platt.transform(p_h_raw)
            p_a_cal = 1 - p_h_cal

            actual_home = int(row["home_score"] > row["away_score"])

            for side, p_cal, odds, actual in [
                ("home", p_h_cal, odds_h_market, actual_home),
                ("away", p_a_cal, odds_a_market, 1 - actual_home),
            ]:
                if p_cal < best_thr:
                    continue

                # Edge real: diferencia entre probabilidad calibrada y probabilidad implícita del mercado
                p_implied = 1 / odds
                edge = p_cal - p_implied
                if edge < 0.02:
                    continue

                # Quarter-Kelly, cap 3%
                kelly = max(0, (p_cal * odds - 1) / (odds - 1))
                stake_pct = min(kelly * 0.25, 0.03)
                stake = round(bankroll * stake_pct, 2)
                if stake < 1:
                    continue

                profit = round((odds - 1) * stake * actual - stake * (1 - actual), 2)
                bankroll = round(bankroll + profit, 2)

                bets.append({
                    "date":      row["date"],
                    "home":      h, "away": a,
                    "pick":      side,
                    "p_raw":     round(p_h_raw if side == "home" else p_a_raw, 4),
                    "p_cal":     round(p_cal, 4),
                    "p_implied": round(p_implied, 4),
                    "odds":      odds,
                    "edge":      round(edge, 4),
                    "stake":     stake,
                    "result":    actual,
                    "profit":    profit,
                    "bankroll":  bankroll,
                })
        except Exception:
            continue

    df_bets = pd.DataFrame(bets)
    if df_bets.empty:
        return {
            "sport": sport, "total_bets": 0,
            "threshold": best_thr, "platt_a": platt._a, "platt_b": platt._b,
            "home_win_rate": round(home_win_rate, 3),
        }

    n    = len(df_bets)
    wins = df_bets["result"].sum()
    wr   = wins / n * 100
    total_staked  = df_bets["stake"].sum()
    total_profit  = df_bets["profit"].sum()
    roi  = total_profit / total_staked * 100 if total_staked > 0 else 0

    bk   = df_bets["bankroll"]
    dd   = ((bk - bk.cummax()) / bk.cummax() * 100).min()

    # Brier score con p calibrada
    brier = ((df_bets["p_cal"] - df_bets["result"]) ** 2).mean()

    # Sharpe
    ret   = df_bets["profit"] / df_bets["stake"]
    sharpe = float(ret.mean() / ret.std() * np.sqrt(252)) if ret.std() > 0 else 0

    # Rachas
    res = df_bets["result"].tolist()
    best_w = worst_l = cur_w = cur_l = 0
    for r in res:
        if r == 1: cur_w += 1; cur_l = 0
        else: cur_l += 1; cur_w = 0
        best_w = max(best_w, cur_w); worst_l = max(worst_l, cur_l)

    # ROI por bucket (probabilidad calibrada)
    buckets_out = {}
    for lo, hi in [(0.55,0.60),(0.60,0.65),(0.65,0.70),(0.70,0.75),(0.75,0.80),(0.80,1.01)]:
        sub = df_bets[(df_bets["p_cal"] >= lo) & (df_bets["p_cal"] < hi)]
        if len(sub) < 5: continue
        r = sub["profit"].sum() / sub["stake"].sum() * 100
        buckets_out[f"{lo:.0%}-{hi:.0%}"] = {
            "n": len(sub),
            "win_rate": round(sub["result"].mean() * 100, 1),
            "roi": round(r, 1),
        }

    # ROI por mes
    df_bets["month"] = df_bets["date"].dt.to_period("M").astype(str)
    roi_monthly = {}
    for m, g in df_bets.groupby("month"):
        roi_monthly[m] = round(g["profit"].sum() / g["stake"].sum() * 100, 1)

    df_bets.to_csv(os.path.join(CACHE_DIR, f"backtest_v2_{sport}.csv"), index=False)

    return {
        "sport":          sport,
        "total_bets":     n,
        "win_rate":       round(wr, 1),
        "roi":            round(roi, 1),
        "total_profit":   round(total_profit, 0),
        "banco_final":    round(bankroll, 0),
        "max_drawdown":   round(float(dd), 1),
        "sharpe":         round(sharpe, 2),
        "brier_cal":      round(float(brier), 4),
        "best_streak":    best_w,
        "worst_streak":   worst_l,
        "threshold":      best_thr,
        "platt_a":        round(platt._a, 3),
        "platt_b":        round(platt._b, 3),
        "home_win_rate":  round(home_win_rate, 3),
        "buckets":        buckets_out,
        "roi_monthly":    roi_monthly,
        "df_bets":        df_bets,
    }


def print_report_v2(r: dict):
    sport = r.get("sport", "?")
    if r.get("total_bets", 0) == 0:
        print(f"\n  {sport}: sin apuestas con edge real positivo.")
        print(f"  (threshold={r.get('threshold','?'):.0%}, "
              f"Platt a={r.get('platt_a','?'):.3f} b={r.get('platt_b','?'):.3f})")
        return

    roi   = r["roi"]
    flag  = "✅ RENTABLE" if roi > 3 else ("⚠️ NEUTRO" if roi > 0 else "❌ NEGATIVO")

    print(f"\n{'═'*62}")
    print(f"  BACKTESTING V2 — {sport}  ({flag})")
    print(f"{'═'*62}")
    print(f"  Banco inicial: $10,000  →  Banco final: ${r['banco_final']:>10,.0f}")
    print(f"  Apuestas:   {r['total_bets']:>5}  |  Win rate: {r['win_rate']:.1f}%  |  ROI: {roi:+.1f}%")
    print(f"  Profit:  ${r['total_profit']:>+10,.0f}  |  Max DD: {r['max_drawdown']:.1f}%  |  Sharpe: {r['sharpe']:.2f}")
    print(f"  Brier calibrado: {r['brier_cal']:.4f}  |  Threshold óptimo: {r['threshold']:.0%}")
    print(f"  Platt a={r['platt_a']:.3f} b={r['platt_b']:.3f}  "
          f"(home_win_rate hist={r['home_win_rate']:.1%})")

    print(f"\n  ROI por rango de confianza calibrada:")
    print(f"  {'Rango':<12} {'Bets':>5}  {'Win%':>7}  {'ROI':>8}")
    print(f"  {'─'*38}")
    for rng, d in r["buckets"].items():
        flag2 = "✅" if d["roi"] > 3 else ("⚠️" if d["roi"] > 0 else "❌")
        print(f"  {rng:<12} {d['n']:>5}  {d['win_rate']:>6.1f}%  {d['roi']:>+7.1f}%  {flag2}")

    print(f"\n  ROI mensual:")
    for m, roi_m in r["roi_monthly"].items():
        bar = "█" * int(max(0, roi_m / 3)) if roi_m > 0 else "░" * int(max(0, -roi_m / 3))
        flag3 = "✅" if roi_m > 0 else "❌"
        print(f"    {m}  {roi_m:>+7.1f}%  {bar} {flag3}")

    print(f"  Mejor racha: +{r['best_streak']}  |  Peor racha: -{r['worst_streak']}")
    print(f"{'═'*62}")


def run_full_backtest_v2(banco: float = 10000):
    """Corre backtesting v2 para todos los deportes y muestra resumen final."""
    print("\n" + "="*62)
    print("  BACKTESTING V2 — Platt Scaling + Threshold Óptimo")
    print("  Banco inicial: $10,000")
    print("="*62)

    all_results = {}
    total_profit = 0
    total_bets   = 0

    for sport in ["MLB", "NBA", "NHL"]:
        print(f"\n  Procesando {sport}...", flush=True)
        try:
            r = run_backtest_v2(sport, banco=banco)
            print_report_v2(r)
            if r.get("total_bets", 0) > 0:
                total_profit += r["total_profit"]
                total_bets   += r["total_bets"]
            all_results[sport] = r
        except Exception as e:
            print(f"  {sport}: ERROR — {e}")
            import traceback; traceback.print_exc()

    print(f"\n{'═'*62}")
    print(f"  RESUMEN SISTEMA COMPLETO")
    print(f"  Total apuestas: {total_bets}  |  Profit neto: ${total_profit:+,.0f}")
    print(f"{'═'*62}\n")

    return all_results


if __name__ == "__main__":
    run_full_backtest_v2()
