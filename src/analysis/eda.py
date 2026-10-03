"""Phase 4 exploratory analysis: summary tables for research questions A to F.

Every table is computed from ``data/processed/matches_gold.csv`` and written to
``reports/tables/``. The numbers here are descriptive: 95% intervals show the
sampling uncertainty of each figure, and formal tests and regressions follow in
Phase 5.

Two measures of home advantage are reported side by side
(``docs/methodology.md``):

* raw rates (home win %, points, goals, goal difference) and, for full league
  seasons only, the points share ``home points / (home + away points)``;
* the **strength-adjusted home excess**: the home side's actual score
  (win 1, draw 0.5, loss 0) minus the score Elo expects from the pre-match
  ratings alone, with no home term. Two equally rated teams are expected to
  score 0.5, so a mean excess of 0.10 means home teams took 10 percentage
  points more of the available result than their strength alone predicts.
  It stays fair in unbalanced samples (the Champions League, crowd subsets,
  individual clubs).

Matches at neutral venues are excluded from every home-advantage figure.

Run with ``python -m src.analysis.eda``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config import REPO_ROOT, repo_path

Z = 1.959964
COMPETITIONS = ["EPL", "LALIGA", "UCL"]
COMP_LABELS = {"EPL": "Premier League", "LALIGA": "La Liga", "UCL": "Champions League"}
CROWD_ORDER = ["normal", "restricted", "behind_closed_doors"]
CROWD_LABELS = {"normal": "Normal crowd", "restricted": "Restricted crowd", "behind_closed_doors": "Behind closed doors"}
# Match statistics available for EPL and La Liga only (none for the UCL).
STAT_PAIRS = ["shots", "shots_on_target", "corners", "fouls", "yellow_cards", "red_cards"]
TEAM_MIN_HOME = 90  # roughly five full league seasons of home games


# ---------------------------------------------------------------------------
# Loading and per-match helpers
# ---------------------------------------------------------------------------
def load_gold() -> pd.DataFrame:
    g = pd.read_csv(repo_path("processed") / "matches_gold.csv", parse_dates=["date"], low_memory=False)
    g["home_score"] = g["result"].map({"H": 1.0, "D": 0.5, "A": 0.0})
    g["elo_expected"] = 1.0 / (1.0 + 10 ** (-g["strength_difference"] / 400.0))
    g["home_excess"] = g["home_score"] - g["elo_expected"]
    g["goal_difference"] = g["home_goals"] - g["away_goals"]
    for s in STAT_PAIRS:
        g[f"{s}_diff"] = g[f"home_{s}"] - g[f"away_{s}"]
    return g


def genuine_home(g: pd.DataFrame) -> pd.DataFrame:
    return g[g["neutral_venue"] == 0]


def wilson(k: float, n: float) -> tuple[float, float]:
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    denom = 1 + Z**2 / n
    centre = (p + Z**2 / (2 * n)) / denom
    half = Z * np.sqrt(p * (1 - p) / n + Z**2 / (4 * n**2)) / denom
    return centre - half, centre + half


def mean_ci(x: pd.Series) -> tuple[float, float, float]:
    x = x.dropna()
    if len(x) < 2:
        return (x.mean() if len(x) else np.nan, np.nan, np.nan)
    m, se = x.mean(), x.std(ddof=1) / np.sqrt(len(x))
    return m, m - Z * se, m + Z * se


def summarise(g: pd.DataFrame) -> pd.Series:
    """Core home-advantage metrics for one group of matches."""
    n = len(g)
    out = {"matches": n}
    for code, name in (("H", "home_win"), ("D", "draw"), ("A", "away_win")):
        k = int((g["result"] == code).sum())
        lo, hi = wilson(k, n)
        out[f"{name}_pct"] = 100 * k / n if n else np.nan
        out[f"{name}_pct_lo"], out[f"{name}_pct_hi"] = 100 * lo, 100 * hi
    out["home_goals_pm"] = g["home_goals"].mean()
    out["away_goals_pm"] = g["away_goals"].mean()
    out["home_points_pm"] = g["home_points"].mean()
    out["away_points_pm"] = g["away_points"].mean()
    m, lo, hi = mean_ci(g["goal_difference"])
    out["goal_diff_pm"], out["goal_diff_pm_lo"], out["goal_diff_pm_hi"] = m, lo, hi
    out["points_share"] = g["home_points"].sum() / (g["home_points"].sum() + g["away_points"].sum())
    m, lo, hi = mean_ci(g["home_excess"])
    out["home_excess"], out["home_excess_lo"], out["home_excess_hi"] = m, lo, hi
    out["mean_strength_difference"] = g["strength_difference"].mean()
    return pd.Series(out)


def _group(g: pd.DataFrame, by: list[str]) -> pd.DataFrame:
    return g.groupby(by, observed=True).apply(summarise, include_groups=False).reset_index()


# ---------------------------------------------------------------------------
# Question tables
# ---------------------------------------------------------------------------
def q_a_overall(g: pd.DataFrame) -> pd.DataFrame:
    """A. Does home advantage exist? One row per competition."""
    t = _group(genuine_home(g), ["competition"])
    t.loc[t["competition"] == "UCL", "points_share"] = np.nan  # unbalanced schedule
    return t


def q_a_home_away(g: pd.DataFrame) -> pd.DataFrame:
    """A. Home vs away per-match means for goals, points and match statistics."""
    rows = []
    for comp, d in genuine_home(g).groupby("competition"):
        for metric in ["goals", "points"] + STAT_PAIRS:
            h, a = d[f"home_{metric}"], d[f"away_{metric}"]
            if h.notna().sum() == 0:
                continue
            m, lo, hi = mean_ci(h - a)
            rows.append({"competition": comp, "metric": metric, "matches": int((h.notna() & a.notna()).sum()),
                         "home_pm": h.mean(), "away_pm": a.mean(), "diff_pm": m, "diff_lo": lo, "diff_hi": hi})
    return pd.DataFrame(rows)


def q_b_trend(g: pd.DataFrame) -> pd.DataFrame:
    """B. Season-by-season home advantage per competition."""
    t = _group(genuine_home(g), ["competition", "season"])
    t.loc[t["competition"] == "UCL", "points_share"] = np.nan
    return t


def q_c_crowd(g: pd.DataFrame) -> pd.DataFrame:
    """C. Home advantage by crowd status, all competitions and per competition."""
    d = genuine_home(g)
    d = d[d["crowd_status"].isin(CROWD_ORDER)]
    overall = _group(d, ["crowd_status"]).assign(competition="ALL")
    per = _group(d, ["competition", "crowd_status"])
    t = pd.concat([overall, per], ignore_index=True)
    t["crowd_status"] = pd.Categorical(t["crowd_status"], CROWD_ORDER, ordered=True)
    return t.sort_values(["competition", "crowd_status"]).reset_index(drop=True)


def q_c_window(g: pd.DataFrame) -> pd.DataFrame:
    """C. Same comparison restricted to the domestic 2019/20 to 2021/22 window.

    Comparing like with like in time: the same leagues and largely the same
    clubs, so a decade-long drift cannot masquerade as a crowd effect.
    """
    d = genuine_home(g)
    d = d[d["competition"].isin(["EPL", "LALIGA"]) & d["season"].isin(["2019/20", "2020/21", "2021/22"])]
    d = d[d["crowd_status"].isin(CROWD_ORDER)]
    t = _group(d, ["crowd_status"])
    t["crowd_status"] = pd.Categorical(t["crowd_status"], CROWD_ORDER, ordered=True)
    return t.sort_values("crowd_status").reset_index(drop=True)


def stat_diffs_by_crowd(g: pd.DataFrame, stats: list[str]) -> pd.DataFrame:
    """Per-match home minus away for match statistics, by crowd status (domestic)."""
    d = genuine_home(g)
    d = d[d["competition"].isin(["EPL", "LALIGA"]) & d["crowd_status"].isin(CROWD_ORDER)]
    rows = []
    for (comp, crowd), x in pd.concat([d.assign(competition="ALL"), d]).groupby(["competition", "crowd_status"]):
        for s in stats:
            m, lo, hi = mean_ci(x[f"{s}_diff"])
            rows.append({"competition": comp, "crowd_status": crowd, "metric": s,
                         "matches": int(x[f"{s}_diff"].notna().sum()),
                         "home_pm": x[f"home_{s}"].mean(), "away_pm": x[f"away_{s}"].mean(),
                         "diff_pm": m, "diff_lo": lo, "diff_hi": hi})
    t = pd.DataFrame(rows)
    t["crowd_status"] = pd.Categorical(t["crowd_status"], CROWD_ORDER, ordered=True)
    return t.sort_values(["competition", "metric", "crowd_status"]).reset_index(drop=True)


def q_c_performance(g: pd.DataFrame) -> pd.DataFrame:
    """C. Underlying performance (shots, shots on target, corners) by crowd."""
    return stat_diffs_by_crowd(g, ["shots", "shots_on_target", "corners"])


def q_d_referee(g: pd.DataFrame) -> pd.DataFrame:
    """D. Referee-related outcomes (fouls, yellow and red cards) by crowd.

    These are differences in outcomes, not a measure of referee bias: fouls
    and cards also follow from how each team plays.
    """
    return stat_diffs_by_crowd(g, ["fouls", "yellow_cards", "red_cards"])


def team_home_advantage(g: pd.DataFrame, min_home: int = TEAM_MIN_HOME) -> pd.DataFrame:
    """E. Club-level home advantage in domestic league matches with normal crowds.

    ``raw_ppm_gap`` is home minus away points per match. ``adj_gap`` is the
    club's mean home excess minus its mean away excess (each from its own
    perspective, against Elo with no home term), which removes differences in
    opponent strength between its home and away fixtures.
    """
    d = g[g["competition"].isin(["EPL", "LALIGA"]) & (g["crowd_status"] == "normal") & (g["neutral_venue"] == 0)]
    home = d.assign(team=d["home_team"], team_id=d["home_team_id"], pts=d["home_points"], excess=d["home_excess"], venue="home")
    away = d.assign(team=d["away_team"], team_id=d["away_team_id"], pts=d["away_points"], excess=-d["home_excess"], venue="away")
    long = pd.concat([home, away])
    rows = []
    for (tid, comp), x in long.groupby(["team_id", "competition"]):
        h, a = x[x["venue"] == "home"], x[x["venue"] == "away"]
        if len(h) < min_home or len(a) < min_home:
            continue
        gap = h["excess"].mean() - a["excess"].mean()
        se = np.sqrt(h["excess"].var(ddof=1) / len(h) + a["excess"].var(ddof=1) / len(a))
        rows.append({"team_id": tid, "team": x["team"].iloc[0], "competition": comp,
                     "home_matches": len(h), "away_matches": len(a), "seasons": x["season"].nunique(),
                     "home_ppm": h["pts"].mean(), "away_ppm": a["pts"].mean(),
                     "raw_ppm_gap": h["pts"].mean() - a["pts"].mean(),
                     "home_excess": h["excess"].mean(), "away_excess": a["excess"].mean(),
                     "adj_gap": gap, "adj_gap_lo": gap - Z * se, "adj_gap_hi": gap + Z * se})
    return pd.DataFrame(rows).sort_values("adj_gap", ascending=False).reset_index(drop=True)


def q_f_competition(g: pd.DataFrame) -> pd.DataFrame:
    """F. Standardised comparison, including UCL format and stage."""
    d = genuine_home(g).copy()
    d["segment"] = d["competition"].map(COMP_LABELS)
    ucl = d[d["competition"] == "UCL"].copy()
    ucl["segment"] = np.where(
        ucl["knockout_match"] == 1, "UCL knockout",
        np.where(ucl["ucl_format"] == "league_phase", "UCL league phase", "UCL group stage"),
    )
    t = pd.concat([_group(d, ["segment"]), _group(ucl, ["segment"])], ignore_index=True)
    order = ["Premier League", "La Liga", "Champions League", "UCL group stage", "UCL league phase", "UCL knockout"]
    t["segment"] = pd.Categorical(t["segment"], order, ordered=True)
    return t.sort_values("segment").reset_index(drop=True)


def travel_bins(g: pd.DataFrame) -> pd.DataFrame:
    """Supplementary: home excess by away-team travel distance (normal crowds)."""
    d = genuine_home(g)
    d = d[d["crowd_status"] == "normal"].copy()
    edges = [0, 100, 250, 500, 1000, 2000, 7000]
    labels = ["<100", "100-250", "250-500", "500-1,000", "1,000-2,000", "2,000+"]
    d["travel_band"] = pd.cut(d["travel_distance_km"], edges, labels=labels, right=False)
    d["scope"] = np.where(d["competition"] == "UCL", "UCL", "Domestic")
    return _group(d, ["scope", "travel_band"])


def rest_bins(g: pd.DataFrame) -> pd.DataFrame:
    """Supplementary: home excess by rest difference (home minus away days)."""
    d = genuine_home(g).dropna(subset=["rest_difference_capped"]).copy()
    edges = [-15, -3, -1, 1, 3, 15]
    labels = ["away 3+ more", "away 1-2 more", "level", "home 1-2 more", "home 3+ more"]
    d["rest_band"] = pd.cut(d["rest_difference_capped"], edges, labels=labels, right=False)
    return _group(d, ["rest_band"])


TABLES = {
    "a_overall": q_a_overall,
    "a_home_away": q_a_home_away,
    "b_trend": q_b_trend,
    "c_crowd": q_c_crowd,
    "c_crowd_window": q_c_window,
    "c_performance": q_c_performance,
    "d_referee": q_d_referee,
    "e_teams": team_home_advantage,
    "f_competition": q_f_competition,
    "g_travel": travel_bins,
    "g_rest": rest_bins,
}


def build_tables(g: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    g = load_gold() if g is None else g
    return {name: fn(g) for name, fn in TABLES.items()}


def main() -> None:
    from src.visualization import plots

    g = load_gold()
    tables = build_tables(g)
    out = REPO_ROOT / "reports" / "tables"
    out.mkdir(parents=True, exist_ok=True)
    for name, t in tables.items():
        t.round(4).to_csv(out / f"eda_{name}.csv", index=False)
    figs = plots.make_eda_figures(tables)
    for f in figs:
        print("wrote", f)


if __name__ == "__main__":
    main()
