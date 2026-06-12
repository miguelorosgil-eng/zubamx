"""
P3.3 — Logging estructurado de decisiones.

Por cada pick evaluado (aceptado o rechazado), loggea JSON:
{fecha, partido, mercado, p_raw, p_calibrada, p_novig_mercado, p_blended,
 edge, filtro_que_rechazo, stake, odds_tomadas}

Sin esto no se puede diagnosticar por qué el sistema pierde cuando pierde.

Uso:
    from decision_log import log_decision, print_decision_summary
    log_decision(...)
"""

import os
import json
import datetime
from typing import Optional

_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_cache", "decision_logs")


def _log_path(date_str: str = None) -> str:
    if date_str is None:
        date_str = datetime.date.today().isoformat()
    os.makedirs(_LOG_DIR, exist_ok=True)
    return os.path.join(_LOG_DIR, f"decisions_{date_str}.jsonl")


def log_decision(
    fecha: str,
    partido: str,
    mercado: str,
    home: str,
    away: str,
    p_raw: float,
    p_calibrada: float,
    p_novig_mercado: float,
    p_blended: float,
    edge: float,
    odds_tomadas: float,
    stake: float = 0.0,
    aceptado: bool = True,
    filtro_que_rechazo: Optional[str] = None,
    sport: str = "",
    extra: dict = None,
):
    """
    Registra la decisión de apostar o rechazar en un archivo JSONL.
    Un registro por pick evaluado.
    """
    record = {
        "ts":                datetime.datetime.now().isoformat(),
        "fecha":             fecha,
        "partido":           partido,
        "sport":             sport,
        "home":              home,
        "away":              away,
        "mercado":           mercado,
        "p_raw":             round(p_raw, 4),
        "p_calibrada":       round(p_calibrada, 4),
        "p_novig_mercado":   round(p_novig_mercado, 4),
        "p_blended":         round(p_blended, 4),
        "edge":              round(edge, 4),
        "odds_tomadas":      round(odds_tomadas, 4),
        "stake":             round(stake, 2),
        "aceptado":          aceptado,
        "filtro_que_rechazo": filtro_que_rechazo or "",
    }
    if extra:
        record.update(extra)

    path = _log_path(fecha)
    with open(path, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_decisions(date_str: str = None) -> list:
    """Lee las decisiones del día."""
    path = _log_path(date_str)
    if not os.path.exists(path):
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def print_decision_summary(date_str: str = None, only_rejected: bool = False):
    """Imprime resumen de decisiones del día."""
    records = read_decisions(date_str)
    if not records:
        print(f"[DecisionLog] Sin decisiones registradas para {date_str or 'hoy'}.")
        return

    aceptados  = [r for r in records if r.get("aceptado")]
    rechazados = [r for r in records if not r.get("aceptado")]
    shown = rechazados if only_rejected else records

    print(f"\n{'═'*72}")
    print(f"  DECISION LOG — {date_str or datetime.date.today().isoformat()}")
    print(f"  Total: {len(records)}  |  Aceptados: {len(aceptados)}  |  Rechazados: {len(rechazados)}")
    print(f"{'═'*72}")
    print(f"  {'Partido':<22} {'Mkt':>5} {'p_raw':>7} {'p_cal':>7} {'p_mkt':>7} "
          f"{'edge':>7} {'stake':>8}  {'status'}")
    print(f"  {'-'*72}")

    for r in shown[-50:]:  # últimos 50
        status = "✅" if r["aceptado"] else f"❌ {r['filtro_que_rechazo'][:20]}"
        partido = f"{r['home'][:10]} vs {r['away'][:10]}"
        print(f"  {partido:<22} {r['mercado']:>5} {r['p_raw']:>7.1%} "
              f"{r['p_calibrada']:>7.1%} {r['p_novig_mercado']:>7.1%} "
              f"{r['edge']:>+7.2%} ${r['stake']:>7.2f}  {status}")

    # Distribución de filtros de rechazo
    if rechazados:
        filtros: dict = {}
        for r in rechazados:
            f = r.get("filtro_que_rechazo", "desconocido") or "desconocido"
            filtros[f] = filtros.get(f, 0) + 1
        print(f"\n  Razones de rechazo:")
        for f, cnt in sorted(filtros.items(), key=lambda x: -x[1]):
            print(f"    {f:<35}: {cnt}")
    print(f"{'═'*72}\n")


def get_rejection_analysis(date_str: str = None) -> dict:
    """Análisis de cuántos picks rechazó cada filtro (para tuning)."""
    records = read_decisions(date_str)
    rechazados = [r for r in records if not r.get("aceptado")]
    if not rechazados:
        return {}
    filtros: dict = {}
    for r in rechazados:
        f = r.get("filtro_que_rechazo", "desconocido") or "desconocido"
        filtros[f] = filtros.get(f, 0) + 1
    return dict(sorted(filtros.items(), key=lambda x: -x[1]))
