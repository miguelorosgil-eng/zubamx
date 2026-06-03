"""
MAIN — Orquestador del motor predictivo de fútbol v1 (con odds automáticas).
Flujo: data real → entrena → valida → descarga odds → VALUE BETS automáticos.

Ligas de clubes:
    python main.py --ligas PL PD SA BL1 FL1 --seasons 2023 2024
Mundial / torneos internacionales:
    python main.py --ligas WC EC CA --seasons 2026
Combo completo:
    python main.py --ligas WC PL PD SA BL1 FL1 --seasons 2023 2024
"""

import argparse
from conector_fd import build_training_set, fetch_upcoming, LEAGUES, INTL_LEAGUES
from conector_odds import fetch_odds, get_match_odds, ODDS_API_KEY
from motor_futbol_v1 import FootballEngine

# Torneos internacionales necesitan manejo especial (pocas selecciones, menos data)
INTL_CODES = set(INTL_LEAGUES.keys())


def run(ligas, seasons, edge=0.04, dc_weight=0.45, use_odds=True):
    odds_ok = use_odds and len(ODDS_API_KEY) > 20 and "PEGA_TU" not in ODDS_API_KEY
    if use_odds and not odds_ok:
        print("⚠️  ODDS_API_KEY no configurada → corriendo sin detección de edge.\n")

    for code in ligas:
        is_intl = code in INTL_CODES
        # Para torneos internacionales bajamos el dc_weight (más peso a ELO/form
        # porque las selecciones nacionales tienen menos partidos históricos)
        effective_dc_weight = 0.60 if is_intl else dc_weight
        # Umbral de edge algo más estricto en torneos (mercados más eficientes)
        effective_edge = edge + 0.01 if is_intl else edge

        print(f"\n{'='*58}\n  {LEAGUES.get(code, code)} ({code})\n{'='*58}")

        # 1) Histórico + entrenamiento
        print("Descargando histórico...")
        df = build_training_set(code, seasons)
        if df.empty:
            print("  Sin data disponible, saltando competición."); continue

        print(f"Total: {len(df)} partidos")
        if len(df) < 30:
            print(f"  ⚠️  Pocos partidos ({len(df)}) — predicciones menos fiables.")

        eng = FootballEngine(dc_weight=effective_dc_weight, edge_threshold=effective_edge)

        if len(df) >= 50:
            print("\nVALIDACIÓN WALK-FORWARD:")
            print(" ", eng.walk_forward_validate(df, league_code=code))
        else:
            print("  (Validación omitida — datos insuficientes para split)")

        eng.fit(df, league_code=code)

        # 2) Próximos fixtures
        upcoming = fetch_upcoming(code)
        if upcoming.empty:
            print("\n  Sin fixtures programados."); continue

        print(f"\n  {len(upcoming)} partido(s) próximo(s) encontrado(s).")

        # 3) Odds de mercado (opcional)
        odds_events = []
        if odds_ok:
            try:
                odds_events = fetch_odds(code)
                print(f"  Odds descargadas: {len(odds_events)} eventos")
            except Exception as e:
                print(f"\n⚠️  Error odds: {e}")

        # 4) Predicción + value bets
        print(f"\n{'PRÓXIMOS PARTIDOS':<40} | PROB MODELO          | VALUE")
        print("-" * 80)
        all_value = []
        has_seeds = eng._elo_seeds is not None
        from fifa_seeds import FIFA_POINTS
        skipped = 0
        for r in upcoming.itertuples():
            home_known = r.home in eng._teams_seen or (has_seeds and r.home in FIFA_POINTS)
            away_known = r.away in eng._teams_seen or (has_seeds and r.away in FIFA_POINTS)
            if not home_known or not away_known:
                skipped += 1
                continue
            mkt = get_match_odds(r.home, r.away, odds_events) if odds_events else None
            pred = eng.predict(r.home, r.away, market_odds=mkt)

            label = f"{r.home} vs {r.away}"
            probs = (f"H{pred['p_home']:.0%} X{pred['p_draw']:.0%} "
                     f"A{pred['p_away']:.0%} O25:{pred['p_over25']:.0%}")
            vb = pred.get("value_bets", [])
            tag = ""
            if vb:
                best = max(vb, key=lambda x: x["edge"])
                tag = (f"✅ {best['market']} @{best['odds_offered']:.2f} "
                       f"(edge {best['edge']:.0%}, kelly {best['kelly_frac']:.1%})")
                all_value.append((label, best, r.date))
            print(f"{label[:39]:<40} | {probs:<20} | {tag}")

        if skipped:
            print(f"  ({skipped} partido(s) omitidos — equipos sin historial suficiente)")

        # 5) Resumen de value bets
        if all_value:
            print(f"\n{'★ VALUE BETS RECOMENDADAS ★':^80}")
            print(f"  {'Partido':<38} {'Mercado':<6} {'Cuota':>6} {'Modelo':>7} "
                  f"{'Mkt':>7} {'Edge':>6} {'Kelly¼':>7}")
            print("  " + "-" * 76)
            for lab, b, date in sorted(all_value, key=lambda x: -x[1]["edge"]):
                print(f"  {lab[:38]:<38} {b['market']:<6} "
                      f"{b['odds_offered']:>6.2f} {b['model_p']:>6.1%} "
                      f"{b['market_p']:>6.1%} {b['edge']:>5.1%} "
                      f"{b['kelly_frac']:>6.1%}  [{date}]")
        else:
            print("\n  (Sin value bets detectados con el umbral actual)")


if __name__ == "__main__":
    p = argparse.ArgumentParser(
        description="Motor predictivo de fútbol — ligas + Mundial 2026"
    )
    p.add_argument("--ligas", nargs="+", default=["WC", "PL", "PD"],
                   help="Códigos: WC EC CA PL PD SA BL1 FL1 PPL DED CL EL CLI UCL")
    p.add_argument("--seasons", nargs="+", type=int, default=[2023, 2024, 2025],
                   help="Temporadas a incluir en training (año de inicio)")
    p.add_argument("--edge", type=float, default=0.04,
                   help="Edge mínimo para recomendar apuesta (default 0.04 = 4%%)")
    p.add_argument("--dc_weight", type=float, default=0.45,
                   help="Peso Dixon-Coles en el blend (default 0.45)")
    p.add_argument("--no-odds", action="store_true",
                   help="Omitir descarga de odds (ahorra cuota API)")
    a = p.parse_args()
    run(a.ligas, a.seasons, a.edge, a.dc_weight, use_odds=not a.no_odds)
