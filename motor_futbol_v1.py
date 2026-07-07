"""
MOTOR PREDICTIVO DE FÚTBOL v1
Ensemble: Dixon-Coles (probabilidades por goles) + XGBoost (clasificador
con features ELO/form/fatiga) → meta-blend calibrado.

Detección de EDGE: compara probabilidad del modelo vs implied probability
del mercado. Solo recomienda apuestas con divergencia > umbral.

Validación: walk-forward temporal (sin leakage), métrica RPS.

v1.1 — Mundial 2026:
  - Soporte para features avanzadas de features_futbol.py (ELO K=20,
    rolling form normalizado, goal diff, H2H, FIFA ranking diff)
  - Método predict_group_stage() con contexto de fase de grupos
  - XGBoostClassifier multi-clase como alternativa/ensemble si disponible
"""

import numpy as np
import pandas as pd
from collections import defaultdict

# XGBoost: opcional pero preferido
try:
    from xgboost import XGBClassifier
    _HAS_XGB = True
except ImportError:
    _HAS_XGB = False

from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from dixon_coles import DixonColes
from features import FeatureBuilder
from fifa_seeds import get_elo_seeds

# Features avanzadas para torneos de selecciones (opcional)
try:
    from features_futbol import (
        build_soccer_features,
        get_live_features,
        FIFA_RANKINGS as _FF_FIFA_RANKINGS,
    )
    _HAS_FEATURES_FUTBOL = True
    # Columnas que produce build_soccer_features (sin targets)
    _ADV_FEAT_COLS = [
        "elo_diff", "elo_home", "elo_away",
        "form_home", "form_away", "form_diff",
        "gf_home", "ga_home", "gf_away", "ga_away",
        "attack_diff", "defense_diff",
        "home_win_rate", "away_win_rate",
        "h2h_adv", "rank_diff",
        "rest_home", "rest_away",
    ]
except ImportError:
    _HAS_FEATURES_FUTBOL = False
    _FF_FIFA_RANKINGS = {}
    _ADV_FEAT_COLS = []

# Rankings FIFA: preferir conector_mundial, fallback a features_futbol
try:
    from conector_mundial import FIFA_RANKINGS as _FIFA_RANKINGS_DICT
except ImportError:
    _FIFA_RANKINGS_DICT = _FF_FIFA_RANKINGS

# Competiciones internacionales donde se usan seeds FIFA
INTL_CODES = {"WC", "EC", "CA", "WCQ", "UCL"}


# ---------- Métricas ----------
def ranked_probability_score(probs, outcome):
    """RPS — la métrica correcta para predicción de 3 resultados.
    probs: [p_home, p_draw, p_away]; outcome: 0=home,1=draw,2=away.
    Menor = mejor. Benchmark mercado ~0.19-0.21."""
    cum_p = np.cumsum(probs)
    actual = np.zeros(3); actual[outcome] = 1
    cum_a = np.cumsum(actual)
    return np.sum((cum_p - cum_a) ** 2) / (len(probs) - 1)


def implied_proba(odds):
    """Convierte cuotas decimales a probabilidad sin vig (normalizada)."""
    raw = np.array([1 / o for o in odds])
    return raw / raw.sum()


# ---------- Motor ----------
class FootballEngine:
    sport = "soccer"

    def __init__(self, dc_weight=0.45, edge_threshold=0.04,
                 confidence_floor=0.65, market_trust=0.5):
        """
        dc_weight: peso de Dixon-Coles en el blend (resto = XGBoost).
        edge_threshold: divergencia mínima vs mercado para recomendar.
        confidence_floor / market_trust: mismos filtros que el motor de deportes,
            usados por los mercados O/U, BTTS, spread, team totals.
        """
        self.dc = DixonColes()
        self.xgb = None
        self.fb = FeatureBuilder()
        self.dc_weight = dc_weight
        self.edge_threshold = edge_threshold
        self.confidence_floor = confidence_floor
        self.market_trust = market_trust
        self._state = None  # estado de features para predecir futuros

    def expected_scores(self, home, away):
        """Goles esperados (xG) de cada equipo según Dixon-Coles.
        Es el μ que consumen los mercados O/U, BTTS, spread y team totals."""
        dc = self.dc.predict_proba(home, away)
        return float(dc["xg_home"]), float(dc["xg_away"])

    def fit(self, df, league_code=None, use_advanced_features=None):
        """df: home, away, hg, ag, date.
        league_code: si es torneo internacional activa seeds FIFA.
        use_advanced_features: True/False/None (None = auto-detecta: True si
            es torneo internacional Y features_futbol está disponible).
        """
        use_seeds = league_code in INTL_CODES if league_code else False
        elo_seeds = get_elo_seeds() if use_seeds else None

        if use_seeds:
            print("  Seeds FIFA activadas para selecciones nacionales.")
            self.dc.set_fifa_seeds(elo_seeds)

        # Auto-detectar si usar features avanzadas
        if use_advanced_features is None:
            use_advanced_features = (use_seeds and _HAS_FEATURES_FUTBOL)

        self._use_advanced = use_advanced_features
        self._league_code  = league_code

        # 1) Dixon-Coles sobre todo el histórico
        self.dc.fit(df[['home', 'away', 'hg', 'ag', 'date']])

        # 2) Features
        if use_advanced_features and _HAS_FEATURES_FUTBOL:
            print("  Usando features_futbol.py (features avanzadas de selecciones).")
            feat_df = build_soccer_features(df)
            self._feat_cols = _ADV_FEAT_COLS
            # Reconstruir los dicts de estado (elo, form, etc.) para predict()
            self._adv_state = self._rebuild_adv_state(df)
            self._adv_feat_df = None  # no necesitamos el DF de training para pred
            X = feat_df[self._feat_cols].fillna(0)
            y = (feat_df['home_win'] * 0 + feat_df['draw'] * 1 + feat_df['away_win'] * 2).astype(int)
        else:
            feat_df, *state = self.fb.build(df, elo_seeds=elo_seeds)
            self._state = state
            self._feat_cols = self.fb.FEATURE_COLS
            self._adv_feat_df = None
            self._fifa_rankings = None
            X = feat_df[self._feat_cols]
            y = feat_df['result']

        n_samples = len(X)
        cv = min(3, max(2, n_samples // 15))

        # 3) Clasificador principal: XGBoost si disponible, RF si no
        if _HAS_XGB:
            if n_samples < 100:
                base_clf = XGBClassifier(
                    n_estimators=100, max_depth=3, learning_rate=0.05,
                    subsample=0.9, colsample_bytree=0.9,
                    objective='multi:softprob', num_class=3,
                    eval_metric='mlogloss', n_jobs=-1,
                    verbosity=0,
                )
            else:
                base_clf = XGBClassifier(
                    n_estimators=300, max_depth=4, learning_rate=0.03,
                    subsample=0.8, colsample_bytree=0.8,
                    objective='multi:softprob', num_class=3,
                    eval_metric='mlogloss', n_jobs=-1,
                    verbosity=0,
                )
        else:
            # Fallback: Random Forest
            base_clf = RandomForestClassifier(
                n_estimators=200, max_depth=6, n_jobs=-1, random_state=42
            )

        # Calibración isotónica → probabilidades bien calibradas
        self.xgb = CalibratedClassifierCV(base_clf, method='isotonic', cv=cv)
        self.xgb.fit(X, y)
        self._teams_seen = set(df['home']) | set(df['away'])
        self._elo_seeds = elo_seeds  # guardamos para predict de equipos nuevos
        return self

    def _rebuild_adv_state(self, df):
        """Reproduce el mismo loop de estado que build_soccer_features() para
        obtener los dicts finales (elos, forms, gf_hist, ga_hist, home_wins,
        away_wins, h2h) que necesita get_live_features() en predict()."""
        from features_futbol import ELO_K, ELO_DEFAULT, ROLLING_N
        df = df.copy().sort_values("date").reset_index(drop=True)
        elos = {}
        forms = {}
        gf_hist = {}
        ga_hist = {}
        home_wins = {}
        away_wins = {}
        h2h = {}
        for _, row in df.iterrows():
            h, a = row["home"], row["away"]
            hg, ag = int(row["hg"]), int(row["ag"])
            elo_h = elos.get(h, ELO_DEFAULT)
            elo_a = elos.get(a, ELO_DEFAULT)
            ea = 1 / (1 + 10 ** ((elo_a - elo_h) / 400))
            sa = 1.0 if hg > ag else (0.5 if hg == ag else 0.0)
            elos[h] = elo_h + ELO_K * (sa - ea)
            elos[a] = elo_a + ELO_K * ((1 - sa) - (1 - ea))
            pts_h = 3 if hg > ag else (1 if hg == ag else 0)
            pts_a = 3 if ag > hg else (1 if hg == ag else 0)
            forms.setdefault(h, []).append(pts_h)
            forms.setdefault(a, []).append(pts_a)
            gf_hist.setdefault(h, []).append(hg)
            ga_hist.setdefault(h, []).append(ag)
            gf_hist.setdefault(a, []).append(ag)
            ga_hist.setdefault(a, []).append(hg)
            home_wins.setdefault(h, []).append(1 if hg > ag else 0)
            away_wins.setdefault(a, []).append(1 if ag > hg else 0)
            key = tuple(sorted([h, a]))
            d = pd.Timestamp(row["date"])
            h2h.setdefault(key, []).append((h, hg - ag, d))
        return elos, forms, gf_hist, ga_hist, home_wins, away_wins, h2h

    def _blend(self, dc_p, xgb_p):
        return self.dc_weight * dc_p + (1 - self.dc_weight) * xgb_p

    def _build_pred_feat(self, home, away):
        """Construye el vector de features para un partido futuro usando
        el estado actual del modelo (sea avanzado o básico)."""
        seeds = self._elo_seeds or {}

        if self._use_advanced and _HAS_FEATURES_FUTBOL and hasattr(self, '_adv_state'):
            elos, forms, gf_h, ga_h, hw, aw, h2h = self._adv_state
            feat_dict = get_live_features(home, away, elos, forms, gf_h, ga_h, hw, aw, h2h)

        else:
            # Features básicas del FeatureBuilder
            elo, form, gf, ga, last_match, h2h = self._state
            elo_h = elo.get(home) if home in elo.ratings else seeds.get(home, 1500)
            elo_a = elo.get(away) if away in elo.ratings else seeds.get(away, 1500)
            feat_dict = {
                'elo_home': elo_h, 'elo_away': elo_a,
                'elo_diff': elo_h - elo_a,
                'form_home': np.mean(form[home]) if form[home] else 0.5,
                'form_away': np.mean(form[away]) if form[away] else 0.5,
                'gf_home': np.mean(gf[home]) if gf[home] else 1.2,
                'ga_home': np.mean(ga[home]) if ga[home] else 1.2,
                'gf_away': np.mean(gf[away]) if gf[away] else 1.2,
                'ga_away': np.mean(ga[away]) if ga[away] else 1.2,
                'rest_home': 7, 'rest_away': 7,
                'h2h_home': np.mean(h2h[(home, away)]) if h2h[(home, away)] else 0.5,
            }

        return pd.DataFrame([feat_dict])[self._feat_cols].fillna(0)

    def predict(self, home, away, market_odds=None):
        """Predice un partido. market_odds=[home,draw,away] decimales (opc)."""
        dc = self.dc.predict_proba(home, away)
        dc_p = np.array([dc['p_home'], dc['p_draw'], dc['p_away']])

        feat = self._build_pred_feat(home, away)
        xgb_p = self.xgb.predict_proba(feat)[0]

        blend = self._blend(dc_p, xgb_p)
        # Normalizar: clamp negativos a 0 y renormalizar a suma=1
        blend = np.maximum(blend, 0)
        blend = blend / blend.sum()
        out = {
            'home': home, 'away': away,
            'p_home': round(blend[0], 4),
            'p_draw': round(blend[1], 4),
            'p_away': round(blend[2], 4),
            'p_over25': round(dc['p_over25'], 4),
            'p_btts': round(dc['p_btts'], 4),
            'xg_home': round(dc['xg_home'], 2),
            'xg_away': round(dc['xg_away'], 2),
        }

        # --- detección de edge ---
        if market_odds is not None:
            mkt = implied_proba(market_odds)
            edges = blend - mkt
            labels = ['HOME', 'DRAW', 'AWAY']
            value_bets = []
            for i, lab in enumerate(labels):
                if edges[i] > self.edge_threshold:
                    fair_odds = 1 / blend[i]
                    value_bets.append({
                        'market': lab,
                        'model_p': round(blend[i], 4),
                        'market_p': round(mkt[i], 4),
                        'edge': round(edges[i], 4),
                        'odds_offered': market_odds[i],
                        'fair_odds': round(fair_odds, 2),
                        # Kelly fraccional (1/4) para sizing conservador
                        'kelly_frac': round(0.25 * max(
                            (market_odds[i] * blend[i] - 1) / (market_odds[i] - 1), 0
                        ), 4)
                    })
            out['value_bets'] = value_bets
        return out

    def predict_group_stage(self, home, away, market_odds=None):
        """
        Predice un partido de fase de grupos del Mundial 2026.

        Diferencias respecto a predict():
          - Usa rankings FIFA como señal primaria de calidad del equipo cuando
            no hay historial ELO suficiente (equipos con pocos partidos en data).
          - Ajusta el blend: mayor peso a Dixon-Coles si ambos equipos son nuevos
            en el dataset (sin historial confiable de form/ELO).
          - Devuelve también 'context' con info de la fase de grupos.

        Parámetros
        ----------
        home, away : nombres de equipo (deben coincidir con FIFA_RANKINGS o data entrenada)
        market_odds : [home_odds, draw_odds, away_odds] decimales (opcional)
        """
        teams_seen = self._teams_seen if hasattr(self, '_teams_seen') else set()
        home_seen = home in teams_seen
        away_seen = away in teams_seen

        # Si ninguno tiene historial, aumentar peso de Dixon-Coles (más robusto con seeds)
        dc_w = self.dc_weight
        if not home_seen and not away_seen:
            dc_w = 0.65  # más peso a DC cuando no hay form/ELO real
        elif not home_seen or not away_seen:
            dc_w = 0.55

        # Obtener predicción base
        original_dc_weight = self.dc_weight
        self.dc_weight = dc_w
        out = self.predict(home, away, market_odds=market_odds)
        self.dc_weight = original_dc_weight  # restaurar

        # Añadir contexto de grupo
        fifa = _FIFA_RANKINGS_DICT or {}
        out['context'] = {
            'stage': 'GROUP_STAGE',
            'home_in_training': home_seen,
            'away_in_training': away_seen,
            'dc_weight_used': dc_w,
            'fifa_rank_home': fifa.get(home, 'N/A'),
            'fifa_rank_away': fifa.get(away, 'N/A'),
            'fifa_rank_diff': (
                fifa.get(home, 50) - fifa.get(away, 50)
                if home in fifa and away in fifa else 'N/A'
            ),
        }
        return out

    # ---------- Validación temporal ----------
    def walk_forward_validate(self, df, train_frac=0.7, league_code=None):
        """Backtest honesto: entrena con pasado, evalúa en futuro."""
        df = df.sort_values('date').reset_index(drop=True)
        split = int(len(df) * train_frac)
        train, test = df.iloc[:split], df.iloc[split:]

        self.fit(train, league_code=league_code)
        rps_model, rps_naive = [], []
        for r in test.itertuples():
            if r.home not in self._teams_seen or r.away not in self._teams_seen:
                continue
            pred = self.predict(r.home, r.away)
            probs = [pred['p_home'], pred['p_draw'], pred['p_away']]
            outcome = 0 if r.hg > r.ag else (1 if r.hg == r.ag else 2)
            rps_model.append(ranked_probability_score(probs, outcome))
            rps_naive.append(ranked_probability_score([0.4, 0.27, 0.33], outcome))

        return {
            'n_test': len(rps_model),
            'rps_model': round(np.mean(rps_model), 4),
            'rps_naive_baseline': round(np.mean(rps_naive), 4),
            'mejora_vs_naive_%': round(
                100 * (1 - np.mean(rps_model) / np.mean(rps_naive)), 2)
        }


if __name__ == '__main__':
    # ---- DEMO con data sintética (sustituir por API real) ----
    rng = np.random.default_rng(42)
    teams = [f'T{i}' for i in range(12)]
    strength = {t: rng.normal(0, 0.4) for t in teams}
    dates = pd.date_range('2023-08-01', periods=400, freq='D')
    rows = []
    for d in dates:
        h, a = rng.choice(teams, 2, replace=False)
        lx = np.exp(0.2 + strength[h] - strength[a] + 0.25)
        my = np.exp(0.2 + strength[a] - strength[h])
        rows.append({'home': h, 'away': a, 'hg': rng.poisson(lx),
                     'ag': rng.poisson(my), 'date': d})
    demo = pd.DataFrame(rows)

    eng = FootballEngine()
    print("=== VALIDACIÓN WALK-FORWARD ===")
    print(eng.walk_forward_validate(demo))
    print("\n=== PREDICCIÓN EJEMPLO (con odds de mercado) ===")
    eng.fit(demo)
    res = eng.predict('T0', 'T1', market_odds=[2.10, 3.40, 3.60])
    for k, v in res.items():
        print(f"{k}: {v}")
