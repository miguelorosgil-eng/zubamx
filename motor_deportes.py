"""
Motor genérico para deportes sin empate: MLB, NBA, NHL.
Predice HOME/AWAY con ELO + rolling stats + LogisticRegression calibrada.
"""
import warnings
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import brier_score_loss, log_loss

warnings.filterwarnings("ignore")

ELO_K = 20
ELO_DEFAULT = 1500
ROLLING_N = 10
HOME_ADVANTAGE = 0.05  # boost a probabilidad home antes de calibración


def _expected_elo(ra: float, rb: float) -> float:
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400))


def _update_elo(ra: float, rb: float, home_win: bool, k: float = ELO_K):
    ea = _expected_elo(ra, rb)
    sa = 1.0 if home_win else 0.0
    new_ra = ra + k * (sa - ea)
    new_rb = rb + k * ((1 - sa) - (1 - ea))
    return new_ra, new_rb


def _build_features(df: pd.DataFrame, include_run_diff: bool = False) -> pd.DataFrame:
    """
    Genera features fila a fila (walk-forward, sin data leakage).
    df debe tener: home, away, home_score, away_score, date
    """
    df = df.copy().sort_values("date").reset_index(drop=True)

    elos: dict[str, float] = {}
    win_history: dict[str, list] = {}
    score_diff_history: dict[str, list] = {}

    records = []
    for _, row in df.iterrows():
        h, a = row["home"], row["away"]
        home_score, away_score = row["home_score"], row["away_score"]
        home_win = int(home_score > away_score)

        elo_h = elos.get(h, ELO_DEFAULT)
        elo_a = elos.get(a, ELO_DEFAULT)
        elo_diff = elo_h - elo_a

        wh = win_history.get(h, [])
        wa = win_history.get(a, [])
        rwr_h = np.mean(wh[-ROLLING_N:]) if wh else 0.5
        rwr_a = np.mean(wa[-ROLLING_N:]) if wa else 0.5

        feat = {
            "elo_diff": elo_diff,
            "elo_home": elo_h,
            "elo_away": elo_a,
            "rolling_wr_home": rwr_h,
            "rolling_wr_away": rwr_a,
            "rolling_wr_diff": rwr_h - rwr_a,
            "home_win": home_win,
        }

        if include_run_diff:
            sd_h = score_diff_history.get(h, [])
            sd_a = score_diff_history.get(a, [])
            rd_h = np.mean(sd_h[-ROLLING_N:]) if sd_h else 0.0
            rd_a = np.mean(sd_a[-ROLLING_N:]) if sd_a else 0.0
            feat["run_diff_home"] = rd_h
            feat["run_diff_away"] = rd_a
            feat["run_diff_delta"] = rd_h - rd_a

        records.append(feat)

        # Actualizar estado post-partido
        new_elo_h, new_elo_a = _update_elo(elo_h, elo_a, bool(home_win))
        elos[h] = new_elo_h
        elos[a] = new_elo_a
        win_history.setdefault(h, []).append(home_win)
        win_history.setdefault(a, []).append(1 - home_win)
        diff = home_score - away_score
        score_diff_history.setdefault(h, []).append(diff)
        score_diff_history.setdefault(a, []).append(-diff)

    return pd.DataFrame(records)


class SportsEngine:
    """
    Motor de predicción para deportes sin empate.

    fit(df)            → entrena modelo
    predict(home, away, market_odds) → dict de probabilidades y value bets
    walk_forward_validate(df) → métricas de validación
    """

    def __init__(self, sport: str = "generic",
                 edge_threshold: float = 0.02,
                 confidence_floor: float = 0.65,
                 market_trust: float = 0.5):
        """
        edge_threshold:   edge mínimo (prob_final - precio) para recomendar.
        confidence_floor: prob. final mínima para apostar a un equipo (p. ej. 0.65).
                          Solo apostamos a equipos que de verdad creemos ganadores.
        market_trust:     λ ∈ [0,1]. Cuánto peso damos al mercado al mezclar.
                          0.5 = mitad modelo, mitad mercado (mercado como prior fuerte).
                          Mata edges absurdos de underdogs donde el modelo delira.
        """
        self.sport = sport
        self.include_run_diff = sport.lower() == "mlb"
        self.edge_threshold = edge_threshold
        self.confidence_floor = confidence_floor
        self.market_trust = market_trust
        self.model: Pipeline | None = None
        self.feature_cols: list[str] = []
        self.elos: dict[str, float] = {}
        self.win_history: dict[str, list] = {}
        self.score_diff_history: dict[str, list] = {}
        self._trained_df: pd.DataFrame | None = None

    def _feature_cols_from(self, df_feat: pd.DataFrame) -> list[str]:
        return [c for c in df_feat.columns if c != "home_win"]

    def fit(self, df: pd.DataFrame) -> "SportsEngine":
        """df: home, away, home_score, away_score, date"""
        if len(df) < 50:
            raise ValueError("Se necesitan al menos 50 partidos para entrenar.")
        df = df.sort_values("date").reset_index(drop=True)
        self._trained_df = df.copy()

        feat_df = _build_features(df, include_run_diff=self.include_run_diff)
        self.feature_cols = self._feature_cols_from(feat_df)
        X = feat_df[self.feature_cols].values
        y = feat_df["home_win"].values

        base_lr = LogisticRegression(max_iter=1000, C=1.0)
        calibrated = CalibratedClassifierCV(base_lr, cv=5, method="isotonic")
        self.model = Pipeline([
            ("scaler", StandardScaler()),
            ("clf", calibrated),
        ])
        self.model.fit(X, y)

        # Construir estado ELO final para predicciones live
        self.elos = {}
        self.win_history = {}
        self.score_diff_history = {}
        for _, row in df.iterrows():
            h, a = row["home"], row["away"]
            elo_h = self.elos.get(h, ELO_DEFAULT)
            elo_a = self.elos.get(a, ELO_DEFAULT)
            home_win = row["home_score"] > row["away_score"]
            new_h, new_a = _update_elo(elo_h, elo_a, home_win)
            self.elos[h] = new_h
            self.elos[a] = new_a
            self.win_history.setdefault(h, []).append(int(home_win))
            self.win_history.setdefault(a, []).append(int(not home_win))
            diff = row["home_score"] - row["away_score"]
            self.score_diff_history.setdefault(h, []).append(diff)
            self.score_diff_history.setdefault(a, []).append(-diff)

        # ── Modelo de anotación esperada (para mercados O/U, spread, BTTS) ──
        self.scored_history = {}
        self.allowed_history = {}
        for _, row in df.iterrows():
            h, a = row["home"], row["away"]
            hs, as_ = row["home_score"], row["away_score"]
            self.scored_history.setdefault(h, []).append(hs)
            self.allowed_history.setdefault(h, []).append(as_)
            self.scored_history.setdefault(a, []).append(as_)
            self.allowed_history.setdefault(a, []).append(hs)

        self.league_home_avg = float(df["home_score"].mean())
        self.league_away_avg = float(df["away_score"].mean())
        self.league_avg = (self.league_home_avg + self.league_away_avg) / 2.0
        # Desviaciones históricas para mercados de distribución Normal (NBA)
        totals = (df["home_score"] + df["away_score"]).astype(float)
        margins = (df["home_score"] - df["away_score"]).astype(float)
        self.sigma_total = float(totals.std())
        self.sigma_margin = float(margins.std())
        self.sigma_team = float(pd.concat([df["home_score"], df["away_score"]]).astype(float).std())

        self._teams_seen = set(df["home"]) | set(df["away"])
        print(f"[SportsEngine:{self.sport}] Entrenado con {len(df)} partidos. "
              f"Anotación liga μ≈{self.league_avg:.2f}/equipo.")
        return self

    def expected_scores(self, home: str, away: str):
        """
        Anotación esperada (μ) de cada equipo, modelo multiplicativo tipo Pythagorean:
          μ_local  = prom_local_liga · (ataque_local/μ_liga) · (defensa_visita/μ_liga)
        Devuelve (mu_home, mu_away). Útil para O/U, spread, BTTS, team totals.
        """
        def off(team):
            h = self.scored_history.get(team, [])
            return float(np.mean(h[-30:])) if h else self.league_avg
        def deff(team):
            h = self.allowed_history.get(team, [])
            return float(np.mean(h[-30:])) if h else self.league_avg

        la = max(self.league_avg, 1e-6)
        # Exponente <1 amortigua la sobre-amplificación (regresión a la media)
        damp = 0.85
        mu_home = self.league_home_avg * (off(home) / la) ** damp * (deff(away) / la) ** damp
        mu_away = self.league_away_avg * (off(away) / la) ** damp * (deff(home) / la) ** damp
        # clamp a rangos razonables
        return max(mu_home, 0.05), max(mu_away, 0.05)

    def _build_live_features(self, home: str, away: str) -> np.ndarray:
        elo_h = self.elos.get(home, ELO_DEFAULT)
        elo_a = self.elos.get(away, ELO_DEFAULT)
        wh = self.win_history.get(home, [])
        wa = self.win_history.get(away, [])
        rwr_h = np.mean(wh[-ROLLING_N:]) if wh else 0.5
        rwr_a = np.mean(wa[-ROLLING_N:]) if wa else 0.5

        feat = [
            elo_h - elo_a,
            elo_h,
            elo_a,
            rwr_h,
            rwr_a,
            rwr_h - rwr_a,
        ]

        if self.include_run_diff:
            sd_h = self.score_diff_history.get(home, [])
            sd_a = self.score_diff_history.get(away, [])
            rd_h = np.mean(sd_h[-ROLLING_N:]) if sd_h else 0.0
            rd_a = np.mean(sd_a[-ROLLING_N:]) if sd_a else 0.0
            feat += [rd_h, rd_a, rd_h - rd_a]

        return np.array(feat).reshape(1, -1)

    def predict(self, home: str, away: str, market_odds: dict = None) -> dict:
        """
        market_odds: {"home": float, "away": float}  (cuotas decimales europeas)
        Retorna dict con p_home, p_away, value_bets.
        """
        if self.model is None:
            raise RuntimeError("Modelo no entrenado. Llama fit() primero.")

        X = self._build_live_features(home, away)
        p_home_raw = float(self.model.predict_proba(X)[0][1])
        # Añadir home advantage boost y renormalizar
        p_home = min(0.98, p_home_raw + HOME_ADVANTAGE)
        p_away = 1.0 - p_home

        result = {
            "home": home,
            "away": away,
            "p_home": round(p_home, 4),
            "p_away": round(p_away, 4),
            "fair_odds_home": round(1 / p_home, 3),
            "fair_odds_away": round(1 / p_away, 3),
            "value_bets": [],
        }

        if market_odds:
            o_home = market_odds.get("home")
            o_away = market_odds.get("away")
            if o_home and o_away:
                # 1) Quitar la vig: probabilidad real del mercado (sin margen)
                raw_h, raw_a = 1.0 / o_home, 1.0 / o_away
                total = raw_h + raw_a
                novig_h, novig_a = raw_h / total, raw_a / total

                # 2) Shrinkage: mezclar modelo con mercado (mercado = prior fuerte)
                lam = self.market_trust
                blend_h = (1 - lam) * p_home + lam * novig_h
                blend_a = (1 - lam) * p_away + lam * novig_a

                result["blended_p_home"] = round(blend_h, 4)
                result["blended_p_away"] = round(blend_a, 4)
                result["novig_p_home"] = round(novig_h, 4)
                result["novig_p_away"] = round(novig_a, 4)

                for side, blended_p, odds in [("home", blend_h, o_home),
                                              ("away", blend_a, o_away)]:
                    implied_vig = 1.0 / odds            # precio que pagas (con vig)
                    edge = blended_p - implied_vig       # valor real sobre el precio
                    kelly = edge / (odds - 1) if odds > 1 else 0.0

                    # FILTRO COMBINADO: confianza alta Y edge positivo
                    passes_confidence = blended_p >= self.confidence_floor
                    passes_edge = edge >= self.edge_threshold
                    if passes_confidence and passes_edge:
                        result["value_bets"].append({
                            "market": side,
                            "model_p": round(blended_p, 4),     # prob ajustada (la que usamos)
                            "model_p_raw": round(p_home if side == "home" else p_away, 4),
                            "implied_p": round(implied_vig, 4),
                            "odds_offered": odds,
                            "edge": round(edge, 4),
                            "kelly_frac": round(max(0, kelly), 4),
                            "label": f"{home if side == 'home' else away} gana",
                        })

        return result

    def walk_forward_validate(self, df: pd.DataFrame, min_train: int = 200) -> dict:
        """
        Validación walk-forward: entrena en primeras min_train filas,
        evalúa en el resto de forma incremental.
        """
        df = df.sort_values("date").reset_index(drop=True)
        if len(df) < min_train + 50:
            raise ValueError(f"Necesitas al menos {min_train + 50} partidos para validar.")

        feat_df = _build_features(df, include_run_diff=self.include_run_diff)
        fcols = self._feature_cols_from(feat_df)
        X = feat_df[fcols].values
        y = feat_df["home_win"].values

        probs = np.full(len(y), np.nan)
        preds = np.full(len(y), np.nan)

        for i in range(min_train, len(y)):
            X_tr, y_tr = X[:i], y[:i]
            base_lr = LogisticRegression(max_iter=500, C=1.0)
            cal = CalibratedClassifierCV(base_lr, cv=3, method="sigmoid")
            pipe = Pipeline([("sc", StandardScaler()), ("clf", cal)])
            try:
                pipe.fit(X_tr, y_tr)
                probs[i] = pipe.predict_proba(X[i:i+1])[0][1]
                preds[i] = int(probs[i] > 0.5)
            except Exception:
                pass

        mask = ~np.isnan(probs)
        y_val = y[mask]
        p_val = probs[mask]
        pred_val = preds[mask]

        acc = float(np.mean(pred_val == y_val))
        brier = float(brier_score_loss(y_val, p_val))
        ll = float(log_loss(y_val, np.column_stack([1 - p_val, p_val])))

        print(f"[Walk-Forward {self.sport}] N={mask.sum()} | Accuracy={acc:.3f} | Brier={brier:.4f} | LogLoss={ll:.4f}")
        return {"accuracy": acc, "brier": brier, "log_loss": ll, "n_eval": int(mask.sum())}


if __name__ == "__main__":
    # Demo con datos sintéticos
    rng = np.random.default_rng(42)
    n = 500
    teams = [f"Team{i}" for i in range(20)]
    records = []
    for i in range(n):
        h, a = rng.choice(teams, 2, replace=False)
        hs = int(rng.poisson(5))
        as_ = int(rng.poisson(4))
        records.append({"home": h, "away": a, "home_score": hs, "away_score": as_,
                         "date": pd.Timestamp("2023-01-01") + pd.Timedelta(days=int(i))})

    df_demo = pd.DataFrame(records)
    engine = SportsEngine(sport="nhl")
    engine.fit(df_demo)
    result = engine.predict("Team0", "Team1", market_odds={"home": 1.9, "away": 2.1})
    print(result)
    engine.walk_forward_validate(df_demo, min_train=200)
