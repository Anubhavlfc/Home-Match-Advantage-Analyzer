"""Phase 6 K-Means team segmentation.

One row per club and league (EPL or La Liga): league matches with normal
crowds over the ten seasons, for clubs with enough home and away games for
stable rates. The features describe home performance and the home-away gap.
Raw home win rates mostly track club quality, so the strength-adjusted
home-advantage index (Phase 4/5) is included as well.

The number of clusters is chosen from the data, not in advance. Each k from
2 to 8 is scored with the elbow (inertia) and the silhouette score, and
stability across random starts is measured with the adjusted Rand index.
Clusters are named only after inspecting their centroids.

Run with ``python -m src.models.clustering``.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import adjusted_rand_score, silhouette_score
from sklearn.preprocessing import StandardScaler

from src.analysis import eda
from src.config import REPO_ROOT

OUT = REPO_ROOT / "reports" / "tables"
MIN_MATCHES = 57  # three full league seasons of home (and away) games
K_RANGE = range(2, 9)
SEED = 0

# Main specification: the feature list from the project brief (attendance_pct
# is unavailable). Sensitivity specification: only the home-away gap measures,
# so overall club quality cannot drive the split.
FEATURES = [
    "home_win_pct", "home_points_per_game", "home_goal_difference_per_game", "home_goals_per_game",
    "home_goals_conceded_per_game", "home_vs_away_win_difference", "home_vs_away_points_difference",
    "home_vs_away_goal_difference", "home_advantage_index",
]
GAP_FEATURES = ["home_vs_away_win_difference", "home_vs_away_points_difference", "home_vs_away_goal_difference",
                "home_advantage_index"]


def team_features(g: pd.DataFrame | None = None, min_matches: int = MIN_MATCHES) -> pd.DataFrame:
    g = eda.load_gold() if g is None else g
    d = g[g["competition"].isin(["EPL", "LALIGA"]) & (g["crowd_status"] == "normal") & (g["neutral_venue"] == 0)]
    home = pd.DataFrame({"team_id": d["home_team_id"], "team": d["home_team"], "competition": d["competition"],
                         "season": d["season"], "venue": "home", "win": (d["result"] == "H").astype(float),
                         "pts": d["home_points"], "gf": d["home_goals"], "ga": d["away_goals"],
                         "excess": d["home_excess"], "strength": d["home_strength"]})
    away = pd.DataFrame({"team_id": d["away_team_id"], "team": d["away_team"], "competition": d["competition"],
                         "season": d["season"], "venue": "away", "win": (d["result"] == "A").astype(float),
                         "pts": d["away_points"], "gf": d["away_goals"], "ga": d["home_goals"],
                         "excess": -d["home_excess"], "strength": d["away_strength"]})
    long = pd.concat([home, away])
    rows = []
    for (tid, comp), x in long.groupby(["team_id", "competition"]):
        h, a = x[x["venue"] == "home"], x[x["venue"] == "away"]
        if len(h) < min_matches or len(a) < min_matches:
            continue
        rows.append({
            "team_id": tid, "team": x["team"].iloc[0], "competition": comp, "seasons": x["season"].nunique(),
            "home_matches": len(h), "away_matches": len(a),
            "home_win_pct": 100 * h["win"].mean(), "home_points_per_game": h["pts"].mean(),
            "home_goal_difference_per_game": (h["gf"] - h["ga"]).mean(), "home_goals_per_game": h["gf"].mean(),
            "home_goals_conceded_per_game": h["ga"].mean(),
            "home_vs_away_win_difference": 100 * (h["win"].mean() - a["win"].mean()),
            "home_vs_away_points_difference": h["pts"].mean() - a["pts"].mean(),
            "home_vs_away_goal_difference": (h["gf"] - h["ga"]).mean() - (a["gf"] - a["ga"]).mean(),
            "home_advantage_index": h["excess"].mean() - a["excess"].mean(),
            # Not a clustering feature: used afterwards to describe the clusters.
            "mean_elo": x["strength"].mean(),
        })
    return pd.DataFrame(rows).reset_index(drop=True)


def choose_k(Xs: np.ndarray) -> pd.DataFrame:
    rows = []
    for k in K_RANGE:
        km = KMeans(n_clusters=k, n_init=50, random_state=SEED).fit(Xs)
        labels = [KMeans(n_clusters=k, n_init=1, random_state=s).fit_predict(Xs) for s in range(20)]
        ari = np.mean([adjusted_rand_score(labels[i], labels[j]) for i in range(20) for j in range(i + 1, 20)])
        rows.append({"k": k, "inertia": km.inertia_, "silhouette": silhouette_score(Xs, km.labels_),
                     "stability_ari": ari, "smallest_cluster": int(np.bincount(km.labels_).min())})
    return pd.DataFrame(rows)


def pick_k(scores: pd.DataFrame) -> int:
    """Highest silhouette among stable solutions (mean ARI >= 0.8) whose
    smallest cluster has at least 5 clubs; ties go to the smaller k."""
    ok = scores[(scores["stability_ari"] >= 0.8) & (scores["smallest_cluster"] >= 5)]
    ok = ok if len(ok) else scores
    best = ok["silhouette"].max()
    return int(ok[ok["silhouette"] >= best - 1e-9]["k"].min())


def cluster(teams: pd.DataFrame, features: list[str]) -> dict:
    teams = teams.copy()
    scaler = StandardScaler().fit(teams[features])
    Xs = scaler.transform(teams[features])
    scores = choose_k(Xs)
    k = pick_k(scores)
    km = KMeans(n_clusters=k, n_init=50, random_state=SEED).fit(Xs)
    # Order cluster ids by mean home-advantage index so labels are stable.
    order = pd.Series(km.cluster_centers_[:, features.index("home_advantage_index")]).rank(ascending=False).astype(int) - 1
    teams["cluster"] = order[km.labels_].to_numpy()
    pca = PCA(n_components=2, random_state=SEED).fit(Xs)
    pcs = pca.transform(Xs)
    teams["pc1"], teams["pc2"] = pcs[:, 0], pcs[:, 1]
    cols = list(dict.fromkeys(features + FEATURES + ["mean_elo"]))
    profile = teams.groupby("cluster")[cols].mean()
    profile.insert(0, "clubs", teams.groupby("cluster").size())
    centroids_z = pd.DataFrame(scaler.transform(profile[features]), columns=features, index=profile.index)
    loadings = pd.DataFrame(pca.components_.T, index=features, columns=["pc1", "pc2"])
    return {"teams": teams, "scores": scores, "k": k, "profile": profile.reset_index(),
            "centroids_z": centroids_z.reset_index(), "pca_loadings": loadings.reset_index(names="feature"),
            "pca_explained": pca.explained_variance_ratio_.tolist(), "features": features}


def run(g: pd.DataFrame | None = None) -> dict:
    teams = team_features(g)
    return {"main": cluster(teams, FEATURES), "gap_only": cluster(teams, GAP_FEATURES)}


def main() -> None:
    from src.visualization import plots

    out = run()
    OUT.mkdir(parents=True, exist_ok=True)
    choice = {"min_matches": MIN_MATCHES}
    for spec, res in out.items():
        for key in ("teams", "scores", "profile", "centroids_z", "pca_loadings"):
            res[key].to_csv(OUT / f"ml_clusters_{spec}_{key}.csv", index=False, float_format="%.6g")
        choice[spec] = {"k": res["k"], "features": res["features"], "pca_explained_variance": res["pca_explained"]}
    (OUT / "ml_clusters_choice.json").write_text(json.dumps(choice, indent=2) + "\n")
    for f in plots.make_cluster_figures(out):
        print("wrote", f)
    with pd.option_context("display.width", 220, "display.max_rows", 100):
        for spec, res in out.items():
            print(spec, "k =", res["k"], "PCA explained", np.round(res["pca_explained"], 3))
            print(res["scores"].round(3))
            print(res["profile"].round(3).to_string())
            print(res["teams"].sort_values(["cluster", "home_advantage_index"])[
                ["cluster", "team", "competition", "home_points_per_game", "home_vs_away_points_difference",
                 "home_advantage_index", "mean_elo"]].round(3).to_string())


if __name__ == "__main__":
    main()
