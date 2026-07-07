"""
Features avanzadas para el motor de fútbol.
ELO, forma rolling, H2H, splits casa/fuera, ranking FIFA.
"""
import numpy as np
import pandas as pd
from difflib import SequenceMatcher

ELO_K = 20
ELO_DEFAULT = 1500
ROLLING_N = 5

FIFA_RANKINGS = {
    "Argentina": 1, "France": 2, "England": 3, "Brazil": 4,
    "Belgium": 5, "Portugal": 6, "Netherlands": 7, "Spain": 8,
    "Germany": 9, "Morocco": 10, "Italy": 11, "USA": 11,
    "Croatia": 13, "Colombia": 14, "Japan": 15, "Senegal": 16,
    "Mexico": 17, "Switzerland": 18, "Uruguay": 19, "Denmark": 20,
    "Ecuador": 21, "Australia": 22, "South Korea": 23, "Canada": 24,
    "Poland": 25, "Serbia": 26, "Iran": 27, "Cameroon": 28,
    "Ghana": 29, "Saudi Arabia": 30, "Qatar": 31, "Tunisia": 32,
}


def _sim(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _get_fifa_rank(name: str) -> int:
    best, best_s = 50, 0
    for k, v in FIFA_RANKINGS.items():
        s = _sim(name, k)
        if s > best_s:
            best_s, best = s, v
    return best if best_s > 0.55 else 50


def build_soccer_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    df: home, away, hg, ag, date (opcionalmente: league)
    Retorna DataFrame con features walk-forward + targets.
    """
    df = df.copy().sort_values("date").reset_index(drop=True)

    elos: dict = {}
    last_date: dict = {}
    home_wins: dict = {}   # {team: [1/0]} solo como local
    away_wins: dict = {}   # {team: [1/0]} solo como visitante
    form: dict = {}        # últimos 5 pts (W=3 D=1 L=0)
    gf_hist: dict = {}
    ga_hist: dict = {}
    h2h: dict = {}         # {(team_a, team_b): [(result_a, date)]}

    records = []
    for _, row in df.iterrows():
        h, a = row["home"], row["away"]
        hg, ag = int(row["hg"]), int(row["ag"])
        d = pd.Timestamp(row["date"])

        elo_h = elos.get(h, ELO_DEFAULT)
        elo_a = elos.get(a, ELO_DEFAULT)

        # Forma rolling (puntos últimos 5)
        form_h = np.mean(form.get(h, [])[-ROLLING_N:]) / 3 if form.get(h) else 0.5
        form_a = np.mean(form.get(a, [])[-ROLLING_N:]) / 3 if form.get(a) else 0.5

        # GF/GA rolling
        gf_h = np.mean(gf_hist.get(h, [])[-ROLLING_N:]) if gf_hist.get(h) else 1.3
        ga_h = np.mean(ga_hist.get(h, [])[-ROLLING_N:]) if ga_hist.get(h) else 1.3
        gf_a = np.mean(gf_hist.get(a, [])[-ROLLING_N:]) if gf_hist.get(a) else 1.3
        ga_a = np.mean(ga_hist.get(a, [])[-ROLLING_N:]) if ga_hist.get(a) else 1.3

        # Home/away splits
        hw_rate = np.mean(home_wins.get(h, [])[-20:]) if home_wins.get(h) else 0.45
        aw_rate = np.mean(away_wins.get(a, [])[-20:]) if away_wins.get(a) else 0.30

        # H2H últimos 3 encuentros
        key = tuple(sorted([h, a]))
        h2h_hist = h2h.get(key, [])[-3:]
        if h2h_hist:
            h_pts = sum(3 if r[0] == h and r[1] > 0 else (1 if r[1] == 0 else 0) for r in h2h_hist)
            h2h_adv = h_pts / (len(h2h_hist) * 3)
        else:
            h2h_adv = 0.5

        # FIFA ranking (selecciones nacionales)
        rank_h = _get_fifa_rank(h)
        rank_a = _get_fifa_rank(a)
        rank_diff = rank_a - rank_h  # positivo = local mejor rankeado

        # Rest days
        rest_h = min(int((d - last_date[h]).days), 14) if h in last_date else 7
        rest_a = min(int((d - last_date[a]).days), 14) if a in last_date else 7

        # Targets
        if hg > ag:
            home_win, draw, away_win = 1, 0, 0
        elif hg == ag:
            home_win, draw, away_win = 0, 1, 0
        else:
            home_win, draw, away_win = 0, 0, 1

        records.append({
            "elo_diff": elo_h - elo_a,
            "elo_home": elo_h, "elo_away": elo_a,
            "form_home": form_h, "form_away": form_a, "form_diff": form_h - form_a,
            "gf_home": gf_h, "ga_home": ga_h,
            "gf_away": gf_a, "ga_away": ga_a,
            "attack_diff": gf_h - ga_a,
            "defense_diff": ga_h - gf_a,
            "home_win_rate": hw_rate, "away_win_rate": aw_rate,
            "h2h_adv": h2h_adv,
            "rank_diff": rank_diff,
            "rest_home": rest_h, "rest_away": rest_a,
            "home_win": home_win, "draw": draw, "away_win": away_win,
        })

        # Actualizar estado
        ea = 1 / (1 + 10 ** ((elo_a - elo_h) / 400))
        sa = 1.0 if hg > ag else (0.5 if hg == ag else 0.0)
        elos[h] = elo_h + ELO_K * (sa - ea)
        elos[a] = elo_a + ELO_K * ((1 - sa) - (1 - ea))

        pts_h = 3 if hg > ag else (1 if hg == ag else 0)
        pts_a = 3 if ag > hg else (1 if hg == ag else 0)
        form.setdefault(h, []).append(pts_h)
        form.setdefault(a, []).append(pts_a)
        gf_hist.setdefault(h, []).append(hg)
        ga_hist.setdefault(h, []).append(ag)
        gf_hist.setdefault(a, []).append(ag)
        ga_hist.setdefault(a, []).append(hg)
        home_wins.setdefault(h, []).append(1 if hg > ag else 0)
        away_wins.setdefault(a, []).append(1 if ag > hg else 0)
        h2h.setdefault(key, []).append((h, hg - ag, d))
        last_date[h] = d
        last_date[a] = d

    return pd.DataFrame(records)


def get_live_features(home: str, away: str,
                      elos: dict, forms: dict, gf_hist: dict, ga_hist: dict,
                      home_wins: dict, away_wins: dict, h2h: dict) -> dict:
    """Genera features en tiempo real para predict() del motor de fútbol."""
    elo_h = elos.get(home, ELO_DEFAULT)
    elo_a = elos.get(away, ELO_DEFAULT)
    form_h = np.mean(forms.get(home, [])[-ROLLING_N:]) / 3 if forms.get(home) else 0.5
    form_a = np.mean(forms.get(away, [])[-ROLLING_N:]) / 3 if forms.get(away) else 0.5
    gf_h = np.mean(gf_hist.get(home, [])[-ROLLING_N:]) if gf_hist.get(home) else 1.3
    ga_h = np.mean(ga_hist.get(home, [])[-ROLLING_N:]) if ga_hist.get(home) else 1.3
    gf_a = np.mean(gf_hist.get(away, [])[-ROLLING_N:]) if gf_hist.get(away) else 1.3
    ga_a = np.mean(ga_hist.get(away, [])[-ROLLING_N:]) if ga_hist.get(away) else 1.3
    hw_rate = np.mean(home_wins.get(home, [])[-20:]) if home_wins.get(home) else 0.45
    aw_rate = np.mean(away_wins.get(away, [])[-20:]) if away_wins.get(away) else 0.30
    key = tuple(sorted([home, away]))
    h2h_hist = h2h.get(key, [])[-3:]
    if h2h_hist:
        pts = sum(3 if r[0] == home and r[1] > 0 else (1 if r[1] == 0 else 0) for r in h2h_hist)
        h2h_adv = pts / (len(h2h_hist) * 3)
    else:
        h2h_adv = 0.5
    return {
        "elo_diff": elo_h - elo_a, "elo_home": elo_h, "elo_away": elo_a,
        "form_home": form_h, "form_away": form_a, "form_diff": form_h - form_a,
        "gf_home": gf_h, "ga_home": ga_h, "gf_away": gf_a, "ga_away": ga_a,
        "attack_diff": gf_h - ga_a, "defense_diff": ga_h - gf_a,
        "home_win_rate": hw_rate, "away_win_rate": aw_rate,
        "h2h_adv": h2h_adv,
        "rank_diff": _get_fifa_rank(away) - _get_fifa_rank(home),
        "rest_home": 7, "rest_away": 7,
    }


if __name__ == "__main__":
    print("=== Test features_futbol ===")
    df = pd.DataFrame([
        {"home": "Spain", "away": "Germany", "hg": 2, "ag": 1, "date": "2024-06-01"},
        {"home": "France", "away": "England", "hg": 1, "ag": 1, "date": "2024-06-02"},
        {"home": "Argentina", "away": "Brazil", "hg": 3, "ag": 0, "date": "2024-06-03"},
    ])
    feat = build_soccer_features(df)
    print(feat[["elo_diff", "form_diff", "rank_diff", "home_win"]].to_string())
