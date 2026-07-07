"""
Piloto diario automatizado — 1er inning MLB.

Hace TODO solo:
  1. Trae los juegos de hoy + pitchers + ERA.
  2. Aplica las reglas validadas (maxERA>=5.5 -> YRFI; <=4.0 -> NRFI; medio -> nada).
  3. Escanea las casas para leer la tendencia del mercado.
  4. Resuelve los picks pendientes (busca el resultado real de la 1ª entrada).
  5. Actualiza seguimiento_picks.csv y reporta el desempeño acumulado.

Uso: python piloto_diario.py [YYYY-MM-DD]
"""
import sys
import csv
import os
import json
import urllib.request
import datetime as dt

from escaner_primera_entrada import clasificar_partido

REG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "seguimiento_picks.csv")
COLS = ["fecha", "deporte", "mercado", "partido", "pick", "pitcher_info",
        "resultado_1i", "acierto", "notas"]


def _get(u):
    with urllib.request.urlopen(u, timeout=20) as r:
        return json.load(r)


_era_cache = {}
def _era(pid, season):
    if not pid:
        return None
    if pid in _era_cache:
        return _era_cache[pid]
    try:
        u = (f"https://statsapi.mlb.com/api/v1/people/{pid}/stats?"
             f"stats=season&group=pitching&season={season}")
        sp = _get(u)["stats"][0]["splits"]
        v = float(sp[0]["stat"]["era"]) if sp else None
    except Exception:
        v = None
    _era_cache[pid] = v
    return v


def primera_entrada_resultado(date_str):
    """{(away,home): 'YRFI'|'NRFI'|None} según carreras reales en la 1ª entrada."""
    out = {}
    try:
        u = (f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
             f"&hydrate=linescore")
        for d in _get(u).get("dates", []):
            for g in d.get("games", []):
                h = g["teams"]["home"]["team"]["name"]
                a = g["teams"]["away"]["team"]["name"]
                innings = g.get("linescore", {}).get("innings", [])
                if not innings:
                    out[(a, h)] = None
                    continue
                f = innings[0]
                r1 = (f.get("home", {}).get("runs", 0) or 0) + \
                     (f.get("away", {}).get("runs", 0) or 0)
                out[(a, h)] = "YRFI" if r1 > 0 else "NRFI"
    except Exception:
        pass
    return out


def picks_de_hoy(date_str):
    """Aplica las reglas validadas y devuelve solo los partidos apostables."""
    season = int(date_str[:4])
    u = (f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&date={date_str}"
         f"&hydrate=probablePitcher")
    sched = _get(u)
    picks = []
    for d in sched.get("dates", []):
        for g in d.get("games", []):
            h = g["teams"]["home"]["team"]["name"]
            a = g["teams"]["away"]["team"]["name"]
            hp = g["teams"]["home"].get("probablePitcher", {}) or {}
            ap = g["teams"]["away"].get("probablePitcher", {}) or {}
            eh = _era(hp.get("id"), season)
            ea = _era(ap.get("id"), season)
            lado, prob = clasificar_partido(eh, ea)
            if lado is None:
                continue
            picks.append({
                "partido": f"{a} @ {h}", "away": a, "home": h,
                "pick": lado, "prob": prob,
                "pitcher_info": f"{ap.get('fullName','?')} {ea} / {hp.get('fullName','?')} {eh} "
                                f"(maxERA {max(ea, eh):.1f})",
            })
    return picks


def _leer_registro():
    if not os.path.exists(REG):
        return []
    with open(REG, newline="") as f:
        return list(csv.DictReader(f))


def _guardar_registro(rows):
    with open(REG, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        w.writerows(rows)


def resolver_pendientes():
    """Busca resultados de la 1ª entrada para los picks 'pendiente'."""
    rows = _leer_registro()
    por_fecha = {}
    cambios = 0
    for r in rows:
        if r.get("acierto", "").lower() in ("pendiente", ""):
            por_fecha.setdefault(r["fecha"], None)
    for fecha in por_fecha:
        por_fecha[fecha] = primera_entrada_resultado(fecha)
    for r in rows:
        if r.get("acierto", "").lower() not in ("pendiente", ""):
            continue
        # localizar el partido
        try:
            a, h = [s.strip() for s in r["partido"].split("@")]
        except ValueError:
            continue
        real = (por_fecha.get(r["fecha"]) or {}).get((a, h))
        if real:
            pick_lado = "YRFI" if "YRFI" in r["pick"] else "NRFI"
            r["resultado_1i"] = real
            r["acierto"] = "GANO" if real == pick_lado else "PERDIO"
            cambios += 1
    if cambios:
        _guardar_registro(rows)
    return cambios


def reporte_desempeno():
    rows = [r for r in _leer_registro() if r.get("acierto") in ("GANO", "PERDIO")]
    if not rows:
        print("  Sin picks resueltos todavía."); return
    w = sum(1 for r in rows if r["acierto"] == "GANO")
    l = len(rows) - w
    print(f"  Desempeño acumulado: {w}W-{l}L ({w/len(rows)*100:.0f}% acierto) en {len(rows)} picks")


if __name__ == "__main__":
    fecha = sys.argv[1] if len(sys.argv) > 1 else dt.date.today().isoformat()
    print(f"=== PILOTO DIARIO 1er INNING — {fecha} ===\n")
    print("Resolviendo picks pendientes...")
    n = resolver_pendientes()
    print(f"  {n} pick(s) resuelto(s).")
    reporte_desempeno()
    print(f"\nPicks apostables para {fecha} (reglas validadas):")
    picks = picks_de_hoy(fecha)
    if not picks:
        print("  Ninguno en zona extrema hoy (o sin pitchers confirmados).")
    for p in picks:
        print(f"  • {p['partido']} → {p['pick']} (p={p['prob']:.0%}) | {p['pitcher_info']}")
    print("\n  Recuerda: revisar momio >=1.70 en Caliente antes de entrar.")
