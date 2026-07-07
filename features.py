"""
Feature Engineering — Capa de variables predictivas.
Genera las features que más impactan accuracy según SHAP analysis:
ELO dinámico, form rolling, fatiga, head-to-head.
"""

import numpy as np
import pandas as pd
from collections import defaultdict, deque


class EloRating:
    """ELO adaptado a fútbol con margen de victoria y ventaja local."""

    def __init__(self, k=20, home_adv=65, base=1500):
        self.k = k
        self.home_adv = home_adv
        self.base = base
        self.ratings = defaultdict(lambda: base)
        self.history = []

    def _expected(self, ra, rb):
        return 1 / (1 + 10 ** ((rb - ra) / 400))

    def _mov_multiplier(self, goal_diff, elo_diff):
        # margen de victoria amplifica el ajuste (FiveThirtyEight method)
        return np.log(abs(goal_diff) + 1) * (2.2 / (elo_diff * 0.001 + 2.2))

    def update(self, home, away, hg, ag):
        ra = self.ratings[home] + self.home_adv
        rb = self.ratings[away]
        exp_home = self._expected(ra, rb)

        if hg > ag:
            res = 1.0
        elif hg < ag:
            res = 0.0
        else:
            res = 0.5

        gd = hg - ag
        elo_diff = (ra - rb) if res == 1 else (rb - ra)
        mult = self._mov_multiplier(gd, elo_diff) if gd != 0 else 1.0

        delta = self.k * mult * (res - exp_home)
        self.ratings[home] += delta
        self.ratings[away] -= delta

    def get(self, team, default=None):
        return self.ratings.get(team, default if default is not None else self.base)


class FeatureBuilder:
    """Construye el vector de features por partido (pre-match, sin leakage)."""

    def __init__(self, form_window=5):
        self.form_window = form_window

    def build(self, df, elo_seeds=None):
        """df: home, away, hg, ag, date (orden cronológico).
        elo_seeds: dict {team: elo_value} para inicializar con FIFA ranking.
        Devuelve df con features calculadas SOLO con info previa al partido."""
        df = df.copy()
        df['date'] = pd.to_datetime(df['date'])
        df = df.sort_values('date').reset_index(drop=True)

        elo = EloRating()
        if elo_seeds:
            for team, val in elo_seeds.items():
                elo.ratings[team] = val
        last_match = {}                      # fecha último partido (fatiga)
        form = defaultdict(lambda: deque(maxlen=self.form_window))
        gf = defaultdict(lambda: deque(maxlen=self.form_window))  # goles favor
        ga = defaultdict(lambda: deque(maxlen=self.form_window))  # goles contra
        h2h = defaultdict(lambda: deque(maxlen=5))

        rows = []
        for r in df.itertuples():
            h, a = r.home, r.away

            # --- features ANTES de conocer el resultado ---
            feat = {
                'elo_home': elo.get(h),
                'elo_away': elo.get(a),
                'elo_diff': elo.get(h) - elo.get(a),
                'form_home': np.mean(form[h]) if form[h] else 0.5,
                'form_away': np.mean(form[a]) if form[a] else 0.5,
                'gf_home': np.mean(gf[h]) if gf[h] else 1.2,
                'ga_home': np.mean(ga[h]) if ga[h] else 1.2,
                'gf_away': np.mean(gf[a]) if gf[a] else 1.2,
                'ga_away': np.mean(ga[a]) if ga[a] else 1.2,
                'rest_home': (r.date - last_match.get(h, r.date)).days if h in last_match else 7,
                'rest_away': (r.date - last_match.get(a, r.date)).days if a in last_match else 7,
                'h2h_home': np.mean(h2h[(h, a)]) if h2h[(h, a)] else 0.5,
            }
            feat['result'] = 0 if r.hg > r.ag else (1 if r.hg == r.ag else 2)
            rows.append(feat)

            # --- AHORA sí actualizamos estado con el resultado ---
            elo.update(h, a, r.hg, r.ag)
            res_h = 1.0 if r.hg > r.ag else (0.5 if r.hg == r.ag else 0.0)
            form[h].append(res_h)
            form[a].append(1 - res_h)
            gf[h].append(r.hg); ga[h].append(r.ag)
            gf[a].append(r.ag); ga[a].append(r.hg)
            h2h[(h, a)].append(res_h)
            last_match[h] = r.date
            last_match[a] = r.date

        feat_df = pd.DataFrame(rows)
        return pd.concat([df.reset_index(drop=True), feat_df], axis=1), elo, form, gf, ga, last_match, h2h

    FEATURE_COLS = [
        'elo_home', 'elo_away', 'elo_diff', 'form_home', 'form_away',
        'gf_home', 'ga_home', 'gf_away', 'ga_away',
        'rest_home', 'rest_away', 'h2h_home'
    ]
