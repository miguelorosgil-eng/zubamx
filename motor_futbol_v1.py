"""
MOTOR PREDICTIVO DE FÚTBOL v1
Ensemble: Dixon-Coles (probabilidades por goles) + XGBoost (clasificador
con features ELO/form/fatiga) → meta-blend calibrado.

Detección de EDGE: compara probabilidad del modelo vs implied probability
del mercado. Solo recomienda apuestas con divergencia > umbral.

Validación: walk-forward temporal (sin leakage), métrica RPS.
"""

import numpy as np
import pandas as pd
from xgboost import XGBClassifier
from sklearn.calibration import CalibratedClassifierCV
from dixon_coles import DixonColes
from features import FeatureBuilder
from fifa_seeds import get_elo_seeds

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

    def fit(self, df, league_code=None):
        """df: home, away, hg, ag, date.
        league_code: si es torneo internacional activa seeds FIFA."""
        use_seeds = league_code in INTL_CODES if league_code else False
        elo_seeds = get_elo_seeds() if use_seeds else None

        if use_seeds:
            print("  🌍 Seeds FIFA activadas para selecciones nacionales.")
            self.dc.set_fifa_seeds(elo_seeds)

        # 1) Dixon-Coles sobre todo el histórico
        self.dc.fit(df[['home', 'away', 'hg', 'ag', 'date']])

        # 2) Features + XGBoost
        feat_df, *state = self.fb.build(df, elo_seeds=elo_seeds)
        self._state = state
        X = feat_df[self.fb.FEATURE_COLS]
        y = feat_df['result']

        n_samples = len(X)
        # Con pocos partidos reducimos complejidad y usamos cv más pequeño
        if n_samples < 100:
            base = XGBClassifier(
                n_estimators=100, max_depth=3, learning_rate=0.05,
                subsample=0.9, colsample_bytree=0.9,
                objective='multi:softprob', num_class=3,
                eval_metric='mlogloss', n_jobs=-1
            )
            cv = min(3, n_samples // 10)
        else:
            base = XGBClassifier(
                n_estimators=300, max_depth=4, learning_rate=0.03,
                subsample=0.8, colsample_bytree=0.8,
                objective='multi:softprob', num_class=3,
                eval_metric='mlogloss', n_jobs=-1
            )
            cv = 3
        # calibración isotónica → probabilidades confiables
        self.xgb = CalibratedClassifierCV(base, method='isotonic', cv=cv)
        self.xgb.fit(X, y)
        self._teams_seen = set(df['home']) | set(df['away'])
        self._elo_seeds = elo_seeds  # guardamos para predict de equipos nuevos
        return self

    def _blend(self, dc_p, xgb_p):
        return self.dc_weight * dc_p + (1 - self.dc_weight) * xgb_p

    def predict(self, home, away, market_odds=None):
        """Predice un partido. market_odds=[home,draw,away] decimales (opc)."""
        dc = self.dc.predict_proba(home, away)
        dc_p = np.array([dc['p_home'], dc['p_draw'], dc['p_away']])

        # features actuales desde el estado entrenado
        elo, form, gf, ga, last_match, h2h = self._state

        # Para equipos sin historial de partidos usamos seed FIFA como ELO
        seeds = self._elo_seeds or {}
        elo_h = elo.get(home) if home in elo.ratings else seeds.get(home, 1500)
        elo_a = elo.get(away) if away in elo.ratings else seeds.get(away, 1500)

        feat = pd.DataFrame([{
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
        }])[self.fb.FEATURE_COLS]
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
