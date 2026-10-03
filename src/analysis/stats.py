"""Phase 5 statistical analysis: hypothesis tests and strength-controlled models.

Every test is recorded in one registry (``reports/tables/stats_tests.csv``)
with its hypothesis, method, sample, test statistic, p-value, estimate,
95% confidence interval and effect size. Holm's correction is applied across
the family of pre-specified primary tests. Model coefficient tables are
written alongside it.

Conventions:

* Unit of analysis is the match, from the home side's point of view.
  Neutral-venue matches are excluded throughout.
* Crowd comparisons use ``crowd_status``; matches with ``unknown`` status
  are dropped from those analyses.
* Team strength enters as ``sd100`` = pre-match Elo difference / 100.
  The intercept of a model with ``sd100`` is therefore the home effect
  between two equally rated teams.
* Standard errors are clustered by home club, because a club's home matches
  are not independent of each other.

Run with ``python -m src.analysis.stats``.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats as st
from statsmodels.miscmodels.ordinal_model import OrderedModel
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.outliers_influence import variance_inflation_factor
from statsmodels.stats.proportion import proportions_ztest

from src.analysis import eda
from src.config import REPO_ROOT

Z = st.norm.ppf(0.975)
OUT = REPO_ROOT / "reports" / "tables"


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
def prepare(g: pd.DataFrame | None = None) -> pd.DataFrame:
    g = eda.load_gold() if g is None else g
    d = eda.genuine_home(g).copy()
    d["sd100"] = d["strength_difference"] / 100.0
    d["home_win"] = (d["result"] == "H").astype(int)
    d["result_ord"] = pd.Categorical(d["result"].map({"A": "away", "D": "draw", "H": "home"}),
                                     ["away", "draw", "home"], ordered=True)
    d["crowd"] = pd.Categorical(d["crowd_status"], ["normal", "restricted", "behind_closed_doors", "unknown"])
    d["competition"] = pd.Categorical(d["competition"], ["EPL", "LALIGA", "UCL"])
    seasons = sorted(d["season"].unique())
    d["season_index"] = d["season"].map({s: i for i, s in enumerate(seasons)})
    d["log_travel"] = np.log1p(d["travel_distance_km"])
    return d


def known_crowd(d: pd.DataFrame) -> pd.DataFrame:
    x = d[d["crowd_status"] != "unknown"].copy()
    x["crowd"] = x["crowd"].cat.remove_unused_categories()
    return x


def normal_vs_bcd(d: pd.DataFrame) -> pd.DataFrame:
    x = d[d["crowd_status"].isin(["normal", "behind_closed_doors"])].copy()
    x["crowd"] = x["crowd"].cat.remove_unused_categories()
    return x


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
class Registry:
    def __init__(self) -> None:
        self.rows: list[dict] = []

    def add(self, test_id, question, hypothesis, method, sample, n, statistic_name, statistic, p_value,
            estimate, ci_lo, ci_hi, effect_name="", effect=np.nan, primary=False, note=""):
        self.rows.append(dict(
            test_id=test_id, question=question, hypothesis=hypothesis, method=method, sample=sample, n=int(n),
            statistic_name=statistic_name, statistic=statistic, p_value=p_value, estimate=estimate,
            ci_lo=ci_lo, ci_hi=ci_hi, effect_size_name=effect_name, effect_size=effect, primary=primary, note=note,
        ))

    def frame(self) -> pd.DataFrame:
        t = pd.DataFrame(self.rows)
        t["p_holm"] = np.nan
        prim = t["primary"]
        if prim.any():
            t.loc[prim, "p_holm"] = multipletests(t.loc[prim, "p_value"], method="holm")[1]
        return t


def cohens_h(p1: float, p2: float) -> float:
    return 2 * np.arcsin(np.sqrt(p1)) - 2 * np.arcsin(np.sqrt(p2))


def cramers_v(table: np.ndarray) -> float:
    chi2 = st.chi2_contingency(table, correction=False)[0]
    n = table.sum()
    return float(np.sqrt(chi2 / (n * (min(table.shape) - 1))))


def _cluster_fit(formula: str, data: pd.DataFrame, kind: str = "ols"):
    model = smf.ols if kind == "ols" else smf.logit
    m = model(formula, data=data)
    groups = data.loc[m.data.row_labels, "home_team_id"].astype("category").cat.codes
    kw = {"disp": 0} if kind == "logit" else {}
    return m.fit(cov_type="cluster", cov_kwds={"groups": groups}, **kw)


def _coef_table(res, model_name: str) -> pd.DataFrame:
    ci = res.conf_int()
    t = pd.DataFrame({"model": model_name, "term": res.params.index, "coef": res.params.values,
                      "se": res.bse.values, "z_or_t": res.tvalues.values, "p_value": res.pvalues.values,
                      "ci_lo": ci[0].values, "ci_hi": ci[1].values, "n": int(res.nobs)})
    if model_name.startswith("logit") or model_name.startswith("ordered"):
        t["odds_ratio"] = np.exp(t["coef"])
        t["or_ci_lo"] = np.exp(t["ci_lo"])
        t["or_ci_hi"] = np.exp(t["ci_hi"])
    return t


def _lincom(res, weights: dict[str, float]) -> tuple[float, float, float, float]:
    """Estimate, CI and p-value of a linear combination of coefficients."""
    names = list(res.params.index)
    w = np.zeros(len(names))
    for k, v in weights.items():
        w[names.index(k)] = v
    est = float(w @ res.params.values)
    se = float(np.sqrt(w @ res.cov_params().values @ w))
    p = float(2 * st.norm.sf(abs(est / se)))
    return est, est - Z * se, est + Z * se, p


# ---------------------------------------------------------------------------
# Q1 / A: does home advantage exist?
# ---------------------------------------------------------------------------
def test_existence(d: pd.DataFrame, reg: Registry) -> None:
    for comp, x in d.groupby("competition", observed=True):
        decisive = x[x["result"] != "D"]
        k, n = int((decisive["result"] == "H").sum()), len(decisive)
        b = st.binomtest(k, n, 0.5)
        ci = b.proportion_ci(method="wilson")
        reg.add(f"A1_{comp}", "Q1", f"{comp}: among decisive matches, home wins = away wins",
                "exact binomial test", "decisive matches, genuine home", n, "home share of wins", k / n, b.pvalue,
                k / n, ci.low, ci.high, "Cohen's h vs 0.5", cohens_h(k / n, 0.5))
        t = st.ttest_1samp(x["home_excess"], 0.0)
        m, lo, hi = eda.mean_ci(x["home_excess"])
        reg.add(f"A2_{comp}", "Q1", f"{comp}: mean strength-adjusted home excess = 0",
                "one-sample t-test", "genuine home", len(x), "t", t.statistic, t.pvalue, m, lo, hi,
                "Cohen's d", m / x["home_excess"].std(ddof=1), primary=True)


# ---------------------------------------------------------------------------
# Q3 / C: crowds
# ---------------------------------------------------------------------------
def test_crowd_proportions(d: pd.DataFrame, reg: Registry) -> None:
    nb = normal_vs_bcd(d)
    window = nb[nb["competition"].isin(["EPL", "LALIGA"]) & nb["season"].isin(["2019/20", "2020/21", "2021/22"])]
    samples = [("all", nb, True)] + [(c, x, False) for c, x in nb.groupby("competition", observed=True)]
    samples.append(("domestic 2019/20-2021/22", window, False))
    for label, x, primary in samples:
        a = x[x["crowd_status"] == "normal"]["home_win"]
        b = x[x["crowd_status"] == "behind_closed_doors"]["home_win"]
        stat, p = proportions_ztest([a.sum(), b.sum()], [len(a), len(b)])
        p1, p2 = a.mean(), b.mean()
        diff = p1 - p2
        se = np.sqrt(p1 * (1 - p1) / len(a) + p2 * (1 - p2) / len(b))
        reg.add(f"C1_{label}", "Q3", f"{label}: home-win rate equal with normal crowds and behind closed doors",
                "two-proportion z-test", label, len(x), "z", stat, p, diff, diff - Z * se, diff + Z * se,
                "Cohen's h", cohens_h(p1, p2), primary=primary,
                note=f"normal {p1:.3f} (n={len(a)}), closed doors {p2:.3f} (n={len(b)})")
        t = st.ttest_ind(x[x["crowd_status"] == "normal"]["home_excess"],
                         x[x["crowd_status"] == "behind_closed_doors"]["home_excess"], equal_var=False)
        e1 = x[x["crowd_status"] == "normal"]["home_excess"]
        e2 = x[x["crowd_status"] == "behind_closed_doors"]["home_excess"]
        dm = e1.mean() - e2.mean()
        se = np.sqrt(e1.var(ddof=1) / len(e1) + e2.var(ddof=1) / len(e2))
        pooled = np.sqrt(((len(e1) - 1) * e1.var() + (len(e2) - 1) * e2.var()) / (len(e1) + len(e2) - 2))
        reg.add(f"C2_{label}", "Q3", f"{label}: home excess equal with normal crowds and behind closed doors",
                "Welch t-test", label, len(x), "t", t.statistic, t.pvalue, dm, dm - Z * se, dm + Z * se,
                "Cohen's d", dm / pooled)


def test_crowd_chisq(d: pd.DataFrame, reg: Registry) -> None:
    k = known_crowd(d)
    for label, x in [("all", k)] + [(c, y) for c, y in k.groupby("competition", observed=True)]:
        tab = pd.crosstab(x["crowd_status"], x["result"]).reindex(columns=["H", "D", "A"]).values
        chi2, p, dof, _ = st.chi2_contingency(tab, correction=False)
        reg.add(f"C3_{label}", "Q3", f"{label}: result (H/D/A) independent of crowd status (3 levels)",
                "chi-square test of independence", label, tab.sum(), f"chi2 (df={dof})", chi2, p,
                np.nan, np.nan, np.nan, "Cramér's V", cramers_v(tab), primary=(label == "all"))


def crowd_models(d: pd.DataFrame, reg: Registry) -> list[pd.DataFrame]:
    k = known_crowd(d)
    tables = []
    rhs = "sd100 + C(crowd, Treatment('normal')) + C(competition)"
    bcd = "C(crowd, Treatment('normal'))[T.behind_closed_doors]"
    rst = "C(crowd, Treatment('normal'))[T.restricted]"

    ols = _cluster_fit(f"goal_difference ~ {rhs}", k)
    tables.append(_coef_table(ols, "ols_goal_difference"))
    for term, lab, prim in ((bcd, "behind closed doors", True), (rst, "restricted", False)):
        lo, hi = ols.conf_int().loc[term]
        reg.add(f"M1_{lab.replace(' ', '_')}", "Q3",
                f"Home goal-difference advantage unchanged {lab}, controlling for strength and competition",
                "OLS, club-clustered SE", "genuine home, known crowd", ols.nobs, "z", ols.tvalues[term],
                ols.pvalues[term], ols.params[term], lo, hi, "goals per match", ols.params[term], primary=prim)

    logit = _cluster_fit(f"home_win ~ {rhs}", k, "logit")
    tables.append(_coef_table(logit, "logit_home_win"))
    lo, hi = logit.conf_int().loc[bcd]
    reg.add("M2_behind_closed_doors", "Q3", "Odds of a home win unchanged behind closed doors (controls as M1)",
            "logistic regression, club-clustered SE", "genuine home, known crowd", logit.nobs, "z",
            logit.tvalues[bcd], logit.pvalues[bcd], np.exp(logit.params[bcd]), np.exp(lo), np.exp(hi),
            "odds ratio", np.exp(logit.params[bcd]))

    x = k.copy()
    x["crowd_bcd"] = (x["crowd_status"] == "behind_closed_doors").astype(float)
    x["crowd_restricted"] = (x["crowd_status"] == "restricted").astype(float)
    x["comp_laliga"] = (x["competition"] == "LALIGA").astype(float)
    x["comp_ucl"] = (x["competition"] == "UCL").astype(float)
    exog = x[["sd100", "crowd_bcd", "crowd_restricted", "comp_laliga", "comp_ucl"]]
    om = OrderedModel(x["result_ord"], exog, distr="logit").fit(method="bfgs", disp=False)
    tables.append(_coef_table(om, "ordered_logit_result"))
    lo, hi = om.conf_int().loc["crowd_bcd"]
    reg.add("M3_behind_closed_doors", "Q3", "Ordered result (A<D<H) unchanged behind closed doors (controls as M1)",
            "ordered logit (proportional odds), model SE", "genuine home, known crowd", om.nobs, "z",
            om.tvalues["crowd_bcd"], om.pvalues["crowd_bcd"], np.exp(om.params["crowd_bcd"]), np.exp(lo), np.exp(hi),
            "cumulative odds ratio", np.exp(om.params["crowd_bcd"]))

    # Robustness: domestic leagues 2019/20-2021/22 with season fixed effects, so
    # the closed-doors effect is identified within seasons, not across the decade.
    w = k[k["competition"].isin(["EPL", "LALIGA"]) & k["season"].isin(["2019/20", "2020/21", "2021/22"])].copy()
    w["competition"] = w["competition"].cat.remove_unused_categories()
    rob = _cluster_fit(f"goal_difference ~ {rhs} + C(season)", w)
    tables.append(_coef_table(rob, "ols_goal_difference_window_season_fe"))
    lo, hi = rob.conf_int().loc[bcd]
    reg.add("M1r_window_season_fe", "Q3",
            "Robustness: closed-doors effect on goal difference within 2019/20-2021/22 domestic seasons",
            "OLS with season fixed effects, club-clustered SE", "EPL + La Liga 2019/20-2021/22", rob.nobs, "z",
            rob.tvalues[bcd], rob.pvalues[bcd], rob.params[bcd], lo, hi, "goals per match", rob.params[bcd])
    return tables


# ---------------------------------------------------------------------------
# Q6: does the crowd effect differ by competition?
# ---------------------------------------------------------------------------
def interaction_model(d: pd.DataFrame, reg: Registry) -> tuple[pd.DataFrame, pd.DataFrame]:
    x = normal_vs_bcd(d)
    res = _cluster_fit("goal_difference ~ sd100 + C(competition) * C(crowd, Treatment('normal'))", x)
    coef = _coef_table(res, "ols_goal_difference_interaction")
    b = "C(crowd, Treatment('normal'))[T.behind_closed_doors]"
    inter = [n for n in res.params.index if ":" in n]
    wald = res.wald_test(" = 0, ".join(inter) + " = 0", scalar=True)
    reg.add("M4_interaction", "Q6", "The closed-doors change in home advantage is the same in all three competitions",
            "joint Wald test of competition x crowd interactions (OLS, club-clustered SE)",
            "genuine home, normal or closed doors", res.nobs, f"chi2 (df={len(inter)})", float(wald.statistic),
            float(wald.pvalue), np.nan, np.nan, np.nan, primary=True)

    rows = []
    comp_term = {"EPL": None, "LALIGA": "C(competition)[T.LALIGA]", "UCL": "C(competition)[T.UCL]"}
    for comp, ct in comp_term.items():
        base = {"Intercept": 1.0}
        if ct:
            base[ct] = 1.0
        normal = _lincom(res, base)
        drop_w = {b: 1.0}
        if ct:
            drop_w[f"{ct}:{b}"] = 1.0
        closed = _lincom(res, {**base, **drop_w})
        drop = _lincom(res, drop_w)
        n_n = int(((x["competition"] == comp) & (x["crowd_status"] == "normal")).sum())
        n_b = int(((x["competition"] == comp) & (x["crowd_status"] == "behind_closed_doors")).sum())
        rows.append({"competition": comp, "normal_effect": normal[0], "normal_lo": normal[1], "normal_hi": normal[2],
                     "closed_effect": closed[0], "closed_lo": closed[1], "closed_hi": closed[2],
                     "change": drop[0], "change_lo": drop[1], "change_hi": drop[2], "change_p": drop[3],
                     "n_normal": n_n, "n_closed": n_b})
        reg.add(f"M4_change_{comp}", "Q6", f"{comp}: home goal-difference advantage unchanged behind closed doors",
                "linear combination from interaction model", comp, n_n + n_b, "z", drop[0] / ((drop[2] - drop[1]) / (2 * Z)),
                drop[3], drop[0], drop[1], drop[2], "goals per match", drop[0])
    for a, bb in (("EPL", "LALIGA"), ("EPL", "UCL"), ("LALIGA", "UCL")):
        w = {}
        if comp_term[a]:
            w[f"{comp_term[a]}:{b}"] = 1.0
        if comp_term[bb]:
            w[f"{comp_term[bb]}:{b}"] = w.get(f"{comp_term[bb]}:{b}", 0) - 1.0
        est, lo, hi, p = _lincom(res, w)
        reg.add(f"M4_diff_{a}_{bb}", "Q6", f"Closed-doors change equal in {a} and {bb}",
                "linear combination from interaction model", f"{a} vs {bb}", res.nobs, "z", est / ((hi - lo) / (2 * Z)),
                p, est, lo, hi, "goals per match", est)
    return coef, pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Q4 / Q5: match statistics and referee-related outcomes
# ---------------------------------------------------------------------------
def outcome_models(d: pd.DataFrame, reg: Registry) -> pd.DataFrame:
    k = known_crowd(d)
    k = k[k["competition"].isin(["EPL", "LALIGA"])].copy()
    k["competition"] = k["competition"].cat.remove_unused_categories()
    term = "C(crowd, Treatment('normal'))[T.behind_closed_doors]"
    tables = []
    spec = [("shots", "Q4", False), ("shots_on_target", "Q4", True), ("corners", "Q4", False),
            ("fouls", "Q5", True), ("yellow_cards", "Q5", True), ("red_cards", "Q5", False)]
    for stat, q, prim in spec:
        res = _cluster_fit(f"{stat}_diff ~ sd100 + C(crowd, Treatment('normal')) + C(competition)", k)
        tables.append(_coef_table(res, f"ols_{stat}_diff"))
        lo, hi = res.conf_int().loc[term]
        normal_level = _lincom(res, {"Intercept": 1.0})
        reg.add(f"{'M5' if q == 'Q4' else 'M6'}_{stat}", q,
                f"Home-minus-away {stat.replace('_', ' ')} unchanged behind closed doors, controlling for strength",
                "OLS, club-clustered SE", "EPL + La Liga, known crowd", res.nobs, "z", res.tvalues[term],
                res.pvalues[term], res.params[term], lo, hi, "per match", res.params[term], primary=prim,
                note=f"normal-crowd home-minus-away at equal strength: {normal_level[0]:+.3f}")
    return pd.concat(tables, ignore_index=True)


# ---------------------------------------------------------------------------
# Q8 / Q9 / Q12: travel, rest and other pre-match factors
# ---------------------------------------------------------------------------
def factor_model(d: pd.DataFrame, reg: Registry) -> tuple[pd.DataFrame, pd.DataFrame]:
    k = known_crowd(d).dropna(subset=["rest_difference_capped", "form_difference"]).copy()
    z = {}
    for col, name in (("sd100", "z_strength"), ("log_travel", "z_log_travel"),
                      ("rest_difference_capped", "z_rest"), ("form_difference", "z_form")):
        k[name] = (k[col] - k[col].mean()) / k[col].std(ddof=0)
        z[name] = k[col].std(ddof=0)
    rhs = "z_strength + z_log_travel + z_rest + z_form + C(crowd, Treatment('normal')) + C(competition)"
    logit = _cluster_fit(f"home_win ~ {rhs}", k, "logit")
    ols = _cluster_fit(f"goal_difference ~ {rhs}", k)
    coef = pd.concat([_coef_table(logit, "logit_home_win_factors"), _coef_table(ols, "ols_goal_difference_factors")])
    for term, q, label in (("z_log_travel", "Q8", "away travel distance (log km)"),
                           ("z_rest", "Q9", "rest difference (home minus away, capped)"),
                           ("z_form", "Q12", "form difference (last-5 points)")):
        lo, hi = logit.conf_int().loc[term]
        reg.add(f"M7_{term}", q, f"Odds of a home win unrelated to {label}, given strength, crowd and competition",
                "logistic regression, standardised predictors, club-clustered SE", "genuine home, known crowd, rest known",
                logit.nobs, "z", logit.tvalues[term], logit.pvalues[term], np.exp(logit.params[term]), np.exp(lo),
                np.exp(hi), "odds ratio per 1 SD", np.exp(logit.params[term]), primary=(q in ("Q8", "Q9")),
                note=f"1 SD = {z[term]:.2f} {'log-km' if 'travel' in term else 'days' if 'rest' in term else 'points'}")
    # Multicollinearity check on the numeric predictors.
    X = sm.add_constant(k[["z_strength", "z_log_travel", "z_rest", "z_form"]])
    vif = pd.DataFrame({"term": X.columns[1:], "vif": [variance_inflation_factor(X.values, i) for i in range(1, X.shape[1])]})
    return coef, vif


def travel_within_scope(d: pd.DataFrame, reg: Registry) -> None:
    """Travel effect separately for domestic and UCL matches (normal crowds)."""
    k = d[d["crowd_status"] == "normal"].copy()
    for scope, x in (("domestic", k[k["competition"] != "UCL"]), ("UCL", k[k["competition"] == "UCL"])):
        x = x.copy()
        x["competition"] = x["competition"].cat.remove_unused_categories()
        f = "goal_difference ~ sd100 + log_travel" + (" + C(competition)" if scope == "domestic" else "")
        res = _cluster_fit(f, x)
        lo, hi = res.conf_int().loc["log_travel"]
        reg.add(f"M7b_travel_{scope}", "Q8", f"{scope}: home goal difference unrelated to away travel (log km)",
                "OLS, club-clustered SE", f"{scope}, normal crowds", res.nobs, "z", res.tvalues["log_travel"],
                res.pvalues["log_travel"], res.params["log_travel"], lo, hi, "goals per log-km", res.params["log_travel"],
                note="coefficient x 0.69 = change for a doubling of distance")


# ---------------------------------------------------------------------------
# Q2: trend over the decade
# ---------------------------------------------------------------------------
def trend_model(d: pd.DataFrame, reg: Registry) -> pd.DataFrame:
    x = d[d["crowd_status"] == "normal"]
    res = _cluster_fit("home_excess ~ season_index + C(competition)", x)
    lo, hi = res.conf_int().loc["season_index"]
    reg.add("M8_trend", "Q2", "No linear trend in strength-adjusted home excess across seasons (normal crowds)",
            "OLS, club-clustered SE", "genuine home, normal crowds", res.nobs, "z", res.tvalues["season_index"],
            res.pvalues["season_index"], res.params["season_index"], lo, hi, "home excess per season",
            res.params["season_index"], primary=True)
    out = [_coef_table(res, "ols_home_excess_trend")]
    for comp, y in x.groupby("competition", observed=True):
        r = _cluster_fit("home_excess ~ season_index", y)
        lo, hi = r.conf_int().loc["season_index"]
        reg.add(f"M8_trend_{comp}", "Q2", f"{comp}: no linear trend in home excess (normal crowds)",
                "OLS, club-clustered SE", comp, r.nobs, "z", r.tvalues["season_index"], r.pvalues["season_index"],
                r.params["season_index"], lo, hi, "home excess per season", r.params["season_index"])
    return pd.concat(out)


# ---------------------------------------------------------------------------
# Q7: club-level home advantage with shrinkage
# ---------------------------------------------------------------------------
def club_shrinkage(g: pd.DataFrame, reg: Registry) -> pd.DataFrame:
    """Random-effects (DerSimonian-Laird) shrinkage of club home-advantage gaps.

    Each club's raw gap is pulled toward the across-club mean in proportion
    to how noisy it is, so a short, lucky run cannot top the ranking.
    """
    t = eda.team_home_advantage(g).copy()
    se = (t["adj_gap_hi"] - t["adj_gap_lo"]) / (2 * Z)
    w = 1 / se**2
    mu_fe = np.sum(w * t["adj_gap"]) / w.sum()
    q = float(np.sum(w * (t["adj_gap"] - mu_fe) ** 2))
    df = len(t) - 1
    tau2 = max(0.0, (q - df) / (w.sum() - np.sum(w**2) / w.sum()))
    w_re = 1 / (se**2 + tau2)
    mu = float(np.sum(w_re * t["adj_gap"]) / w_re.sum())
    mu_se = float(np.sqrt(1 / w_re.sum()))
    shrink = tau2 / (tau2 + se**2)
    t["se"] = se
    t["shrinkage_weight"] = shrink
    t["shrunk_gap"] = mu + shrink * (t["adj_gap"] - mu)
    post_sd = np.sqrt(shrink * se**2)
    t["shrunk_lo"] = t["shrunk_gap"] - Z * post_sd
    t["shrunk_hi"] = t["shrunk_gap"] + Z * post_sd
    t["differs_from_mean"] = (t["shrunk_lo"] > mu) | (t["shrunk_hi"] < mu)
    reg.add("E1_heterogeneity", "Q7", "All clubs share the same home-advantage gap",
            "Cochran's Q (random-effects meta-analysis)", "clubs with >= 90 home and away league matches, normal crowds",
            len(t), f"Q (df={df})", q, float(st.chi2.sf(q, df)), mu, mu - Z * mu_se, mu + Z * mu_se,
            "I-squared", max(0.0, (q - df) / q) if q > 0 else 0.0, primary=True,
            note=f"tau = {np.sqrt(tau2):.3f}; {int(t['differs_from_mean'].sum())} clubs' shrunk 95% interval excludes the mean")
    return t.sort_values("shrunk_gap", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
def run(g: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    g = eda.load_gold() if g is None else g
    d = prepare(g)
    reg = Registry()
    test_existence(d, reg)
    test_crowd_proportions(d, reg)
    test_crowd_chisq(d, reg)
    coefs = crowd_models(d, reg)
    inter_coef, inter_effects = interaction_model(d, reg)
    coefs.append(inter_coef)
    coefs.append(outcome_models(d, reg))
    factor_coef, vif = factor_model(d, reg)
    coefs.append(factor_coef)
    travel_within_scope(d, reg)
    coefs.append(trend_model(d, reg))
    clubs = club_shrinkage(g, reg)
    return {
        "tests": reg.frame(),
        "coefficients": pd.concat(coefs, ignore_index=True),
        "interaction_effects": inter_effects,
        "vif": vif,
        "clubs_shrunk": clubs,
    }


def main() -> None:
    from src.visualization import plots

    out = run()
    OUT.mkdir(parents=True, exist_ok=True)
    for name, t in out.items():
        t.to_csv(OUT / f"stats_{name}.csv", index=False, float_format="%.6g")
    for f in plots.make_stats_figures(out):
        print("wrote", f)
    tests = out["tests"]
    cols = ["test_id", "n", "statistic", "p_value", "p_holm", "estimate", "ci_lo", "ci_hi", "effect_size"]
    with pd.option_context("display.width", 200, "display.max_rows", 200):
        print(tests[cols].round(4).to_string())


if __name__ == "__main__":
    main()
