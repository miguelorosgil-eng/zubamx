"""
Configuración por deporte — umbrales, mercados habilitados, Kelly fracción.

P0.4: MLB moneyline full-game apagado (ROI -2.09% en backtest).
      Solo se reactiva si backtest honesto muestra ROI>0 y CLV>0 en ≥2 folds.

Estructura:
  SPORT_CONFIG[sport] = {
      "enabled_markets": lista de mercados permitidos (None = todos),
      "cf_floor":        piso de confianza mínimo para este deporte,
      "edge_min":        edge mínimo,
      "market_trust":    peso del mercado en el shrinkage (0=modelo puro, 1=mercado puro),
      "kelly_fraction":  fracción de Kelly (0.25=quarter, 0.125=1/8, 0.10=1/10),
      "max_picks_per_game": máximo de picks del mismo partido en el portfolio (default 1),
      "clv_kill_threshold": CLV rolling umbral bajo el cual se desactiva el mercado (-0.01),
      "clv_min_picks":      picks mínimos para activar el kill switch (50),
  }
"""

SPORT_CONFIG = {
    "MLB": {
        # ML full-game desactivado — solo F5, NRFI y props K
        "enabled_markets": ["F5_ML", "F5_OU", "NRFI", "PROP-K", "RL"],
        "cf_floor": 0.66,
        # Piso ML béisbol subido a 0.60 (lección 2026-07-02: Phillies ML @58.3%
        # perdió 6-1). A 58% con la comisión de la casa el edge es diminuto y la
        # varianza del béisbol enorme — 58% no se distingue de 50% juego a juego.
        "ml_floor": 0.60,
        # Premium OVER = 0.12 → piso OVER efectivo 0.75 (reevaluación completa).
        # Los OVER de MLB rendían 3W-5L (-232). El modelo SUB-proyecta runs, así
        # que solo hay que confiar en un OVER de altísima convicción (>=75%),
        # cuando el modelo lo grita a pesar de su sesgo a la baja. Subir el piso
        # de 0.68 a 0.75 convierte esa categoría de -232 a +87 en el histórico.
        # ROI histórico total: +40% -> +74%.
        "over_confidence_premium": 0.12,
        "edge_min": 0.035,
        "market_trust": 0.70,
        "kelly_fraction": 0.25,
        "max_picks_per_game": 1,
        "clv_kill_threshold": -0.01,
        "clv_min_picks": 50,
    },
    "WNBA": {
        "enabled_markets": None,
        "cf_floor": 0.62,
        "ml_floor": 0.60,
        "over_confidence_premium": 0.12,
        "edge_min": 0.02,
        "market_trust": 0.45,
        "kelly_fraction": 0.25,
        "max_picks_per_game": 1,
        "clv_kill_threshold": -0.01,
        "clv_min_picks": 50,
    },
    "NBA": {
        "enabled_markets": None,   # todos habilitados
        "cf_floor": 0.62,
        "edge_min": 0.02,
        "market_trust": 0.45,
        "kelly_fraction": 0.25,
        "max_picks_per_game": 1,
        "clv_kill_threshold": -0.01,
        "clv_min_picks": 50,
    },
    "NHL": {
        "enabled_markets": None,
        "cf_floor": 0.64,
        "edge_min": 0.025,
        "market_trust": 0.55,
        "kelly_fraction": 0.25,
        "max_picks_per_game": 1,
        "clv_kill_threshold": -0.01,
        "clv_min_picks": 50,
    },
    "SOCCER": {
        "enabled_markets": None,
        "cf_floor": 0.62,
        "edge_min": 0.025,
        "market_trust": 0.50,
        "kelly_fraction": 0.25,
        "max_picks_per_game": 1,
        "clv_kill_threshold": -0.01,
        "clv_min_picks": 50,
    },
    # Mundial FIFA 2026 — modo ultra-conservador (mercado muy eficiente)
    "WC": {
        "enabled_markets": ["MOTIVATION", "1X2"],
        "cf_floor": 0.64,
        "edge_min": 0.03,
        "market_trust": 0.70,
        "kelly_fraction": 0.10,   # 1/10-Kelly
        "max_picks_per_game": 1,
        "clv_kill_threshold": -0.01,
        "clv_min_picks": 20,      # menos picks → kill switch más rápido
    },
}


def get_sport_config(sport_code: str) -> dict:
    """Devuelve la config del deporte, con fallback a defaults conservadores."""
    defaults = {
        "enabled_markets": None,
        "cf_floor": 0.65,
        "edge_min": 0.03,
        "market_trust": 0.50,
        "kelly_fraction": 0.25,
        "max_picks_per_game": 1,
        "clv_kill_threshold": -0.01,
        "clv_min_picks": 50,
    }
    sc = sport_code.upper()
    # Soccer leagues (PL, PD, etc.) usan config SOCCER
    if sc not in SPORT_CONFIG:
        sc = "SOCCER"
    cfg = defaults.copy()
    cfg.update(SPORT_CONFIG.get(sc, {}))
    return cfg


def is_market_enabled(sport_code: str, market_key: str) -> bool:
    """True si el mercado está habilitado para este deporte."""
    cfg = get_sport_config(sport_code)
    enabled = cfg.get("enabled_markets")
    if enabled is None:
        return True
    return market_key.upper() in [m.upper() for m in enabled]
