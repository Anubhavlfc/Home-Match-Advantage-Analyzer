"""Phase 6 logistic regression models.

Model A: pre-match home-win model
    Predicts ``home_win`` (1 = home win, 0 = draw or away win) from
    information available before kick-off only. Uses a time-based split:
    train on 2016/17 to 2022/23, choose the regularisation strength on
    2023/24, then refit on train + validation and score 2024/25 to 2025/26
    once. The test seasons are not touched before that final step.

Model A3: three-way pre-match model
    Same features, split and protocol as Model A, but predicts home win,
    draw or away win (multinomial logistic regression), so a draw is no
    longer lumped in with an away win. Scored with the ranked probability
    score, which respects the order away < draw < home.

Rest check: Model A refitted on 2020/21 to 2024/25 domestic matches, the
    only seasons where rest days can count cup and Europa fixtures, once with
    the dataset-only rest measure and once with the full one.

Model B: explanatory home-advantage model
    Relates the result to in-match statistics (shots, corners, fouls, cards)
    in EPL and La Liga. Those happen during the match, so this model
    describes mechanisms. It is never used for prediction and never mixed
    into Model A.

Run with ``python -m src.models.logistic_model``.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import statsmodels.api as sm
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, brier_score_loss, confusion_matrix, f1_score, log_loss,
                             precision_score, recall_score, roc_auc_score)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from statsmodels.stats.outliers_influence import variance_inflation_factor

from src.analysis import eda
from src.config import REPO_ROOT

OUT = REPO_ROOT / "reports" / "tables"
TRAIN = ["2016/17", "2017/18", "2018/19", "2019/20", "2020/21", "2021/22", "2022/23"]
VALID = ["2023/24"]
TEST = ["2024/25", "2025/26"]

# Model A features: all known before kick-off.
NUMERIC = ["strength_difference", "home_form", "away_form", "home_rest_days", "away_rest_days",
           "log_travel_km"]
CATEGORICAL = ["crowd_status", "competition"]
BINARY = ["neutral_venue", "knockout_match"]
CROWD_LEVELS = ["normal", "restricted", "behind_closed_doors", "unknown"]
COMP_LEVELS = ["EPL", "LALIGA", "UCL"]
C_GRID = [0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0]


def load() -> pd.DataFrame:
    g = eda.load_gold()
    g["home_win"] = (g["result"] == "H").astype(int)
    g["log_travel_km"] = np.log1p(g["travel_distance_km"])
    for c in BINARY:
        g[c] = g[c].astype(float)
    return g


def split(g: pd.DataFrame) -> dict[str, pd.DataFrame]:
    parts = {"train": g[g["season"].isin(TRAIN)], "valid": g[g["season"].isin(VALID)], "test": g[g["season"].isin(TEST)]}
    assert sum(len(p) for p in parts.values()) == len(g), "split must cover every match exactly once"
    return parts


def make_pipeline(C: float, numeric_cols: list[str] | None = None) -> Pipeline:
    # Missing rest days (first match of a season) and form (fewer than 5 prior
    # matches) are imputed with the training median AND flagged with an
    # indicator column, so the model sees that the value was absent.
    numeric = Pipeline([("impute", SimpleImputer(strategy="median", add_indicator=True)), ("scale", StandardScaler())])
    pre = ColumnTransformer([
        ("num", numeric, numeric_cols or NUMERIC),
        # Reference levels: normal crowd and the Premier League.
        ("cat", OneHotEncoder(categories=[CROWD_LEVELS, COMP_LEVELS], drop="first", handle_unknown="ignore",
                              sparse_output=False), CATEGORICAL),
        ("bin", "passthrough", BINARY),
    ])
    return Pipeline([("pre", pre), ("clf", LogisticRegression(C=C, max_iter=2000))])


def metrics(y: np.ndarray, p: np.ndarray, threshold: float = 0.5) -> dict:
    yhat = (p >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, yhat, labels=[0, 1]).ravel()
    return {
        "n": int(len(y)), "home_win_rate": float(y.mean()), "threshold": threshold,
        "accuracy": accuracy_score(y, yhat), "precision": precision_score(y, yhat, zero_division=0),
        "recall": recall_score(y, yhat), "f1": f1_score(y, yhat), "roc_auc": roc_auc_score(y, p),
        "log_loss": log_loss(y, p), "brier": brier_score_loss(y, p),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
    }


def feature_names(pipe: Pipeline) -> list[str]:
    return [n.split("__", 1)[1] for n in pipe.named_steps["pre"].get_feature_names_out()]


def model_a(g: pd.DataFrame) -> dict:
    parts = split(g)
    tr, va, te = parts["train"], parts["valid"], parts["test"]
    X = NUMERIC + CATEGORICAL + BINARY

    # 1. Tune C on the validation season only.
    tuning = []
    for C in C_GRID:
        pipe = make_pipeline(C).fit(tr[X], tr["home_win"])
        p = pipe.predict_proba(va[X])[:, 1]
        tuning.append({"C": C, "valid_log_loss": log_loss(va["home_win"], p), "valid_auc": roc_auc_score(va["home_win"], p)})
    tuning = pd.DataFrame(tuning)
    best_C = float(tuning.loc[tuning["valid_log_loss"].idxmin(), "C"])

    # Decision threshold chosen on validation (maximise F1), kept alongside 0.5.
    pipe_tv = make_pipeline(best_C).fit(tr[X], tr["home_win"])
    p_va = pipe_tv.predict_proba(va[X])[:, 1]
    grid = np.round(np.arange(0.30, 0.61, 0.01), 2)
    f1s = [f1_score(va["home_win"], (p_va >= t).astype(int)) for t in grid]
    best_t = float(grid[int(np.argmax(f1s))])

    # Baselines, evaluated with the same protocol.
    base_rate = tr["home_win"].mean()
    elo_only = Pipeline([("scale", StandardScaler()), ("clf", LogisticRegression(max_iter=1000))])

    # 2. Final fit on train + validation, scored once on the untouched test seasons.
    trv = pd.concat([tr, va])
    final = make_pipeline(best_C).fit(trv[X], trv["home_win"])
    p_te = final.predict_proba(te[X])[:, 1]
    elo_only.fit(trv[["strength_difference"]], trv["home_win"])
    p_elo = elo_only.predict_proba(te[["strength_difference"]])[:, 1]
    p_base = np.full(len(te), trv["home_win"].mean())

    rows = []
    for name, p, t in (("Model A (threshold 0.5)", p_te, 0.5),
                       (f"Model A (validation-tuned threshold {best_t:.2f})", p_te, best_t),
                       ("Elo difference only", p_elo, 0.5),
                       ("Base rate (always the training home-win rate)", p_base, 0.5)):
        rows.append({"model": name, **metrics(te["home_win"].to_numpy(), p, t)})
    test_metrics = pd.DataFrame(rows)

    # Validation metrics for the record (model fitted on train only).
    valid_metrics = pd.DataFrame([{"model": "Model A (train only)", **metrics(va["home_win"].to_numpy(), p_va, 0.5)}])

    # Calibration on test: deciles of predicted probability.
    cal = pd.DataFrame({"p": p_te, "y": te["home_win"].to_numpy()})
    cal["bin"] = pd.qcut(cal["p"], 10, labels=False, duplicates="drop")
    calibration = cal.groupby("bin").agg(mean_predicted=("p", "mean"), observed=("y", "mean"), n=("y", "size")).reset_index()

    # Test predictions by competition (does the model transfer across them?).
    by_comp = []
    for comp, idx in te.groupby("competition").groups.items():
        mask = te.index.isin(idx)
        by_comp.append({"competition": comp, **metrics(te.loc[mask, "home_win"].to_numpy(), p_te[mask], 0.5)})
    by_comp = pd.DataFrame(by_comp)

    sk_coef = pd.DataFrame({"feature": feature_names(final), "coef": final.named_steps["clf"].coef_[0]})
    sk_coef["odds_ratio"] = np.exp(sk_coef["coef"])

    return {
        "tuning": tuning, "best_C": best_C, "best_threshold": best_t, "test_metrics": test_metrics,
        "valid_metrics": valid_metrics, "calibration": calibration, "by_competition": by_comp,
        "sklearn_coefficients": sk_coef, "pipeline": final, "train_base_rate": float(base_rate),
        "test_predictions": pd.DataFrame({"match_id": te["match_id"].to_numpy(), "season": te["season"].to_numpy(),
                                          "competition": te["competition"].to_numpy(), "home_win": te["home_win"].to_numpy(),
                                          "p_model_a": p_te, "p_elo_only": p_elo}),
    }


CLASSES = ["A", "D", "H"]  # ordered away < draw < home


def rps(y: np.ndarray, P: np.ndarray) -> float:
    """Mean ranked probability score for ordered outcomes (lower is better)."""
    Y = np.zeros_like(P)
    Y[np.arange(len(y)), y] = 1.0
    cum = np.cumsum(P - Y, axis=1)[:, :-1]
    return float(np.mean(np.sum(cum ** 2, axis=1) / (P.shape[1] - 1)))


def metrics3(y: np.ndarray, P: np.ndarray) -> dict:
    Y = np.eye(3)[y]
    pred = P.argmax(axis=1)
    return {"n": int(len(y)), "accuracy": accuracy_score(y, pred), "log_loss": log_loss(y, P, labels=[0, 1, 2]),
            "rps": rps(y, P), "brier": float(np.mean(np.sum((P - Y) ** 2, axis=1))),
            **{f"share_predicted_{c}": float(np.mean(pred == i)) for i, c in enumerate(CLASSES)},
            **{f"mean_p_{c}": float(P[:, i].mean()) for i, c in enumerate(CLASSES)},
            **{f"observed_{c}": float(np.mean(y == i)) for i, c in enumerate(CLASSES)}}


def model_a3(g: pd.DataFrame) -> dict:
    """Three-way (H/D/A) version of Model A, same features and protocol."""
    parts = split(g)
    tr, va, te = parts["train"], parts["valid"], parts["test"]
    X = NUMERIC + CATEGORICAL + BINARY
    enc = {c: i for i, c in enumerate(CLASSES)}
    y = {k: v["result"].map(enc).to_numpy() for k, v in parts.items()}

    tuning = []
    for C in C_GRID:
        P = make_pipeline(C).fit(tr[X], y["train"]).predict_proba(va[X])
        tuning.append({"C": C, "valid_log_loss": log_loss(y["valid"], P, labels=[0, 1, 2]), "valid_rps": rps(y["valid"], P)})
    tuning = pd.DataFrame(tuning)
    best_C = float(tuning.loc[tuning["valid_rps"].idxmin(), "C"])

    trv = pd.concat([tr, va])
    y_trv = np.concatenate([y["train"], y["valid"]])
    final = make_pipeline(best_C).fit(trv[X], y_trv)
    P_te = final.predict_proba(te[X])
    elo = Pipeline([("scale", StandardScaler()), ("clf", LogisticRegression(max_iter=1000))])
    P_elo = elo.fit(trv[["strength_difference"]], y_trv).predict_proba(te[["strength_difference"]])
    P_base = np.tile(np.bincount(y_trv, minlength=3) / len(y_trv), (len(te), 1))
    test_metrics = pd.DataFrame([{"model": name, **metrics3(y["test"], P)} for name, P in (
        ("Model A3 (home / draw / away)", P_te), ("Elo difference only", P_elo),
        ("Base rates (training shares)", P_base))])

    # Calibration per outcome: quintiles of that outcome's predicted probability.
    cal = []
    for i, c in enumerate(CLASSES):
        t = pd.DataFrame({"p": P_te[:, i], "y": (y["test"] == i).astype(float)})
        t["bin"] = pd.qcut(t["p"], 5, labels=False, duplicates="drop")
        agg = t.groupby("bin").agg(mean_predicted=("p", "mean"), observed=("y", "mean"), n=("y", "size")).reset_index()
        cal.append(agg.assign(outcome=c))
    coef = pd.DataFrame(final.named_steps["clf"].coef_.T, columns=[f"coef_{c}" for c in CLASSES])
    coef.insert(0, "feature", feature_names(final))
    return {"a3_tuning": tuning, "a3_best_C": best_C, "a3_test_metrics": test_metrics,
            "a3_calibration": pd.concat(cal, ignore_index=True), "a3_coefficients": coef,
            "a3_test_predictions": pd.DataFrame({"match_id": te["match_id"].to_numpy(), "result": te["result"].to_numpy(),
                                                 **{f"p_{c}": P_te[:, i] for i, c in enumerate(CLASSES)}})}


REST_SEASONS = {"train": ["2020/21", "2021/22", "2022/23"], "valid": ["2023/24"], "test": ["2024/25"]}


def rest_check(g: pd.DataFrame, C: float) -> pd.DataFrame:
    """Does complete rest data improve Model A? Same window, three rest options.

    EPL and La Liga 2020/21-2024/25 only (the seasons where every fixture is
    known). Fitted on 2020/21-2023/24 with Model A's C and scored on 2024/25.
    Matches where either full rest value is missing (first match of a season)
    are dropped, so all three variants use exactly the same rows.
    """
    d = g[g["competition"].isin(["EPL", "LALIGA"])].dropna(subset=["home_rest_days_all", "away_rest_days_all"])
    fit = d[d["season"].isin(REST_SEASONS["train"] + REST_SEASONS["valid"])]
    te = d[d["season"].isin(REST_SEASONS["test"])]
    base = [c for c in NUMERIC if "rest" not in c]
    rows = []
    for name, cols in (("no rest", base),
                       ("rest: league and UCL only", base + ["home_rest_days", "away_rest_days"]),
                       ("rest: all fixtures", base + ["home_rest_days_all", "away_rest_days_all"])):
        X = cols + CATEGORICAL + BINARY
        p = make_pipeline(C, cols).fit(fit[X], fit["home_win"]).predict_proba(te[X])[:, 1]
        rows.append({"variant": name, "n_fit": len(fit), "n_test": len(te), "roc_auc": roc_auc_score(te["home_win"], p),
                     "log_loss": log_loss(te["home_win"], p), "brier": brier_score_loss(te["home_win"], p)})
    return pd.DataFrame(rows)


def model_a_inference(g: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Unpenalised logit on the training seasons for interpretable inference.

    Same features and preprocessing as Model A (fitted on train only),
    standard errors clustered by home club. Coefficients are per standard
    deviation for numeric predictors.
    """
    tr = split(g)["train"]
    pre = make_pipeline(1.0).named_steps["pre"].fit(tr[NUMERIC + CATEGORICAL + BINARY])
    names = [n.split("__", 1)[1] for n in pre.get_feature_names_out()]
    X = pd.DataFrame(pre.transform(tr[NUMERIC + CATEGORICAL + BINARY]), columns=names, index=tr.index)
    X = X.loc[:, X.std() > 0]  # drop constant columns (e.g. an indicator never set in train)
    groups = tr["home_team_id"].astype("category").cat.codes
    res = sm.Logit(tr["home_win"], sm.add_constant(X)).fit(disp=0, cov_type="cluster", cov_kwds={"groups": groups})
    ci = res.conf_int()
    coef = pd.DataFrame({
        "term": res.params.index, "coef": res.params.values, "se": res.bse.values, "z": res.tvalues.values,
        "p_value": res.pvalues.values, "odds_ratio": np.exp(res.params.values),
        "or_ci_lo": np.exp(ci[0].values), "or_ci_hi": np.exp(ci[1].values),
    })
    numeric_cols = [c for c in X.columns if not c.startswith(("crowd_status_", "competition_"))]
    Xn = sm.add_constant(X[numeric_cols])
    vif = pd.DataFrame({"term": numeric_cols,
                        "vif": [variance_inflation_factor(Xn.values, i + 1) for i in range(len(numeric_cols))]})
    return coef, vif


def model_b(g: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Explanatory model: result vs in-match statistics (EPL and La Liga).

    Fitted twice, with and without the match statistics, to see how much of
    the closed-doors change in home-win odds runs through them.
    """
    d = eda.genuine_home(g)
    d = d[d["competition"].isin(["EPL", "LALIGA"]) & (d["crowd_status"] != "unknown")].copy()
    d["home_win"] = (d["result"] == "H").astype(int)
    stats_cols = ["shots_on_target_diff", "shots_diff", "corners_diff", "fouls_diff", "yellow_cards_diff", "red_cards_diff"]
    d = d.dropna(subset=stats_cols)
    X = pd.DataFrame(index=d.index)
    sd = {}
    for c in ["strength_difference"] + stats_cols:
        sd[c] = d[c].std(ddof=0)
        X[f"z_{c}"] = (d[c] - d[c].mean()) / sd[c]
    X["behind_closed_doors"] = (d["crowd_status"] == "behind_closed_doors").astype(float)
    X["restricted"] = (d["crowd_status"] == "restricted").astype(float)
    X["la_liga"] = (d["competition"] == "LALIGA").astype(float)
    groups = d["home_team_id"].astype("category").cat.codes
    rows = []
    fits = {}
    for name, cols in (("without match statistics", ["z_strength_difference", "behind_closed_doors", "restricted", "la_liga"]),
                       ("with match statistics", list(X.columns))):
        res = sm.Logit(d["home_win"], sm.add_constant(X[cols])).fit(disp=0, cov_type="cluster", cov_kwds={"groups": groups})
        fits[name] = res
        ci = res.conf_int()
        for term in res.params.index:
            rows.append({"specification": name, "term": term, "coef": res.params[term], "p_value": res.pvalues[term],
                         "odds_ratio": np.exp(res.params[term]), "or_ci_lo": np.exp(ci.loc[term, 0]),
                         "or_ci_hi": np.exp(ci.loc[term, 1]), "n": int(res.nobs), "pseudo_r2": res.prsquared,
                         "sd_of_raw_variable": sd.get(term[2:], np.nan) if term.startswith("z_") else np.nan})
    coef = pd.DataFrame(rows)
    b0 = fits["without match statistics"].params["behind_closed_doors"]
    b1 = fits["with match statistics"].params["behind_closed_doors"]
    summary = pd.DataFrame([{
        "bcd_log_odds_without_stats": b0, "bcd_log_odds_with_stats": b1,
        "share_of_bcd_effect_accounted_for": 1 - b1 / b0 if b0 != 0 else np.nan,
        "pseudo_r2_without": fits["without match statistics"].prsquared,
        "pseudo_r2_with": fits["with match statistics"].prsquared,
        "n": int(fits["with match statistics"].nobs),
    }])
    return coef, summary


def run() -> dict:
    g = load()
    a = model_a(g)
    a3 = model_a3(g)
    rest = rest_check(g, a["best_C"])
    inf_coef, vif = model_a_inference(g)
    b_coef, b_summary = model_b(g)
    return {**a, **a3, "rest_check": rest, "inference_coefficients": inf_coef, "vif": vif, "model_b_coefficients": b_coef,
            "model_b_summary": b_summary}


def main() -> None:
    from src.visualization import plots

    out = run()
    OUT.mkdir(parents=True, exist_ok=True)
    for key in ("test_predictions", "tuning", "test_metrics", "valid_metrics", "calibration", "by_competition", "sklearn_coefficients",
                "inference_coefficients", "vif", "model_b_coefficients", "model_b_summary",
                "a3_tuning", "a3_test_metrics", "a3_calibration", "a3_coefficients", "a3_test_predictions", "rest_check"):
        out[key].to_csv(OUT / f"ml_model_{key}.csv", index=False, float_format="%.6g")
    (OUT / "ml_model_a_choices.json").write_text(json.dumps(
        {"best_C": out["best_C"], "best_threshold": out["best_threshold"], "train_seasons": TRAIN,
         "valid_seasons": VALID, "test_seasons": TEST, "train_base_rate": out["train_base_rate"],
         "a3_best_C": out["a3_best_C"]}, indent=2) + "\n")
    for f in plots.make_model_figures(out):
        print("wrote", f)
    with pd.option_context("display.width", 200):
        print(out["tuning"].round(4))
        print(out["test_metrics"].round(4).to_string())
        print(out["by_competition"].round(4).to_string())
        print(out["inference_coefficients"].round(4).to_string())
        print(out["vif"].round(2))
        print(out["model_b_summary"].round(4).to_string())
        print(out["a3_tuning"].round(4))
        print(out["a3_test_metrics"].round(4).T.to_string())
        print(out["a3_calibration"].round(3).to_string())
        print(out["rest_check"].round(4).to_string())


if __name__ == "__main__":
    main()
