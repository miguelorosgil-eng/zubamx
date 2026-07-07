"""
Phase 6 — Circuit Breaker.

Protección anti-drawdown:
  - Drawdown ≥ 20% del pico → reducir stakes al 50%
  - Drawdown ≥ 35%          → pausar completamente (0 stakes)
  - Cap por pick            → máximo 2% del bankroll por apuesta

Estado persistido en _cache/circuit_breaker_state.json para
sobrevivir entre sesiones.

Uso:
    from circuit_breaker import CircuitBreaker
    cb = CircuitBreaker(bankroll_inicial=1000)
    stake = cb.apply(raw_stake=50, pick_label="MLB Yankees ML")
"""

import os
import json
import datetime
from typing import Optional

_STATE_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "_cache", "circuit_breaker_state.json"
)

# Umbrales
DD_HALF_STAKES = 0.20   # drawdown 20% → mitad de stakes
DD_PAUSE       = 0.35   # drawdown 35% → pausa total
CAP_PER_PICK   = 0.02   # máximo 2% del bankroll por pick


class CircuitBreaker:
    """
    Controla el sizing de stakes en función del drawdown acumulado.

    Estado:
        bankroll_pico: máximo histórico del bankroll
        bankroll_actual: valor actual
        estado: "normal" | "half" | "paused"
    """

    def __init__(self, bankroll_inicial: float = 1000.0):
        self._initial = bankroll_inicial
        self._state = self._load_state(bankroll_inicial)

    # ── Estado ──────────────────────────────────────────────────────

    def _load_state(self, bankroll_inicial: float) -> dict:
        os.makedirs(os.path.dirname(_STATE_FILE), exist_ok=True)
        if os.path.exists(_STATE_FILE):
            try:
                with open(_STATE_FILE) as f:
                    s = json.load(f)
                # Si no hay pico registrado, inicializar
                if "bankroll_pico" not in s:
                    s["bankroll_pico"] = bankroll_inicial
                return s
            except Exception:
                pass
        return {
            "bankroll_pico":   bankroll_inicial,
            "bankroll_actual": bankroll_inicial,
            "estado":          "normal",
            "ultimo_update":   datetime.date.today().isoformat(),
            "n_activaciones":  0,
        }

    def _save_state(self):
        with open(_STATE_FILE, "w") as f:
            json.dump(self._state, f, indent=2)

    def update_bankroll(self, bankroll_actual: float):
        """Actualiza el bankroll y recalcula el estado del circuit breaker."""
        self._state["bankroll_actual"] = round(bankroll_actual, 2)
        self._state["ultimo_update"]   = datetime.date.today().isoformat()

        # Actualizar pico
        if bankroll_actual > self._state["bankroll_pico"]:
            self._state["bankroll_pico"] = round(bankroll_actual, 2)

        # Calcular drawdown
        dd = self._drawdown()
        prev_estado = self._state["estado"]

        if dd >= DD_PAUSE:
            self._state["estado"] = "paused"
        elif dd >= DD_HALF_STAKES:
            self._state["estado"] = "half"
        else:
            self._state["estado"] = "normal"

        if self._state["estado"] != prev_estado:
            self._state["n_activaciones"] = self._state.get("n_activaciones", 0) + 1
            print(f"  [CircuitBreaker] Estado → {self._state['estado'].upper()}  "
                  f"(drawdown={dd:.1%}, banco=${bankroll_actual:,.0f})")

        self._save_state()

    def _drawdown(self) -> float:
        pico   = self._state.get("bankroll_pico", self._initial)
        actual = self._state.get("bankroll_actual", self._initial)
        if pico <= 0:
            return 0.0
        return max(0.0, (pico - actual) / pico)

    # ── Aplicación al stake ─────────────────────────────────────────

    def apply(self, raw_stake: float, pick_label: str = "") -> float:
        """
        Aplica el circuit breaker al stake crudo.
        Retorna el stake ajustado (puede ser 0 si está pausado).
        """
        estado = self._state.get("estado", "normal")
        bankroll = self._state.get("bankroll_actual", self._initial)

        # Cap absoluto por pick
        cap = bankroll * CAP_PER_PICK
        stake = min(raw_stake, cap)

        # Ajuste por drawdown
        if estado == "paused":
            if pick_label:
                print(f"  [CB] ⛔ PAUSADO — {pick_label} stake→0 (DD≥{DD_PAUSE:.0%})")
            return 0.0
        elif estado == "half":
            stake = stake * 0.50
            if pick_label:
                print(f"  [CB] ⚠️  HALF STAKES — {pick_label} ${raw_stake:.2f}→${stake:.2f} (DD≥{DD_HALF_STAKES:.0%})")

        return round(max(0.0, stake), 2)

    def apply_portfolio(self, stakes: list[dict]) -> list[dict]:
        """
        Aplica el circuit breaker a todos los stakes de un portfolio.
        stakes: lista de dicts con 'chosen_stake' y 'label'.
        Retorna lista modificada.
        """
        adjusted = []
        for s in stakes:
            raw = s.get("chosen_stake", 0.0)
            label = s.get("label", "")
            s = dict(s)
            s["chosen_stake"] = self.apply(raw, label)
            s["cb_estado"]    = self._state.get("estado", "normal")
            adjusted.append(s)
        return adjusted

    # ── Info ────────────────────────────────────────────────────────

    def status(self) -> dict:
        dd = self._drawdown()
        return {
            "estado":          self._state.get("estado", "normal"),
            "bankroll_actual": self._state.get("bankroll_actual"),
            "bankroll_pico":   self._state.get("bankroll_pico"),
            "drawdown":        round(dd, 4),
            "cap_por_pick":    round(self._state.get("bankroll_actual", self._initial) * CAP_PER_PICK, 2),
            "n_activaciones":  self._state.get("n_activaciones", 0),
        }

    def print_status(self):
        s = self.status()
        icon = {"normal": "✅", "half": "⚠️", "paused": "⛔"}.get(s["estado"], "?")
        print(f"\n  [Circuit Breaker] {icon} {s['estado'].upper()}")
        print(f"    Bankroll actual: ${s['bankroll_actual']:,.2f}  |  Pico: ${s['bankroll_pico']:,.2f}")
        print(f"    Drawdown:        {s['drawdown']:.1%}  "
              f"(umbral half={DD_HALF_STAKES:.0%}, pausa={DD_PAUSE:.0%})")
        print(f"    Cap por pick:    ${s['cap_por_pick']:.2f}  ({CAP_PER_PICK:.0%} del banco)")
        print(f"    Activaciones:    {s['n_activaciones']}\n")

    def reset(self, nuevo_bankroll: Optional[float] = None):
        """Reset manual (ej. tras recapitalización)."""
        b = nuevo_bankroll or self._state.get("bankroll_actual", self._initial)
        self._state = {
            "bankroll_pico":   b,
            "bankroll_actual": b,
            "estado":          "normal",
            "ultimo_update":   datetime.date.today().isoformat(),
            "n_activaciones":  0,
        }
        self._save_state()
        print(f"  [CircuitBreaker] Reset. Nuevo banco inicial: ${b:,.2f}")


# ── Singleton para uso en analisis_dia.py ───────────────────────────

_cb_instance: Optional[CircuitBreaker] = None


def get_circuit_breaker(bankroll: float = 1000.0) -> CircuitBreaker:
    """Retorna la instancia singleton del circuit breaker."""
    global _cb_instance
    if _cb_instance is None:
        _cb_instance = CircuitBreaker(bankroll_inicial=bankroll)
    return _cb_instance


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--banco",  type=float, default=None)
    ap.add_argument("--reset",  action="store_true")
    ap.add_argument("--update", type=float, default=None, metavar="BANKROLL_ACTUAL")
    args = ap.parse_args()

    cb = CircuitBreaker(bankroll_inicial=args.banco or 1000.0)

    if args.reset:
        cb.reset(args.banco)
    if args.update is not None:
        cb.update_bankroll(args.update)

    cb.print_status()

    # Demo
    if not args.reset and args.update is None:
        print("  Demo stakes:")
        for raw in [50, 100, 25, 200]:
            adjusted = cb.apply(raw, f"test pick ${raw}")
            print(f"    raw=${raw}  →  adjusted=${adjusted}")
