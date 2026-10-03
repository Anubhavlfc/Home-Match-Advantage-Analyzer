"""Static figures for the EDA report (``reports/figures/``).

One figure per question. Colours follow fixed roles so a reader learns them
once: competitions use three categorical hues, crowd conditions use one blue
ramp from dark (full crowd) to light (empty), and results use a blue/grey/red
diverging set (home win / draw / away win). Every series is also labelled
directly, so nothing depends on colour alone.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from src.config import REPO_ROOT  # noqa: E402

FIG_DIR = REPO_ROOT / "reports" / "figures"

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

COMP_COLORS = {"EPL": "#2a78d6", "LALIGA": "#eb6834", "UCL": "#1baf7a"}
COMP_LABELS = {"EPL": "Premier League", "LALIGA": "La Liga", "UCL": "Champions League", "ALL": "All competitions"}
CROWD_COLORS = {"normal": "#184f95", "restricted": "#3987e5", "behind_closed_doors": "#86b6ef"}
CROWD_LABELS = {"normal": "Normal crowd", "restricted": "Restricted", "behind_closed_doors": "Behind closed doors"}
RESULT_COLORS = {"H": "#2a78d6", "D": "#bdbcb6", "A": "#e34948"}
COVID_SHADE = "#f0efec"
METRIC_LABELS = {
    "goals": "Goals", "points": "Points", "shots": "Shots", "shots_on_target": "Shots on target",
    "corners": "Corners", "fouls": "Fouls", "yellow_cards": "Yellow cards", "red_cards": "Red cards",
}

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "sans-serif", "font.size": 10, "text.color": INK,
    "axes.edgecolor": AXIS, "axes.labelcolor": INK_2, "axes.titlesize": 11, "axes.titleweight": "bold",
    "axes.titlecolor": INK, "axes.titlelocation": "left", "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK_2, "ytick.labelcolor": INK_2,
    "legend.frameon": False, "legend.fontsize": 9, "lines.linewidth": 2,
})


def _save(fig, name: str) -> Path:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    path = FIG_DIR / f"{name}.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def _title(fig, title: str, subtitle: str) -> None:
    h = fig.get_figheight()
    base = fig.subplotpars.top + 0.38 / h  # clears panel titles above the axes
    fig.text(0.01, base + 0.3 / h, title, ha="left", va="bottom", fontsize=13, fontweight="bold", color=INK)
    fig.text(0.01, base, subtitle, ha="left", va="bottom", fontsize=9.5, color=INK_2)


def _dot_ci(ax, y, x, lo, hi, color, size=60, label=None):
    ax.hlines(y, lo, hi, color=color, linewidth=2, alpha=0.6, zorder=2)
    ax.scatter(x, y, s=size, color=color, edgecolor=SURFACE, linewidth=2, zorder=3, label=label)


def _zero_line(ax, axis="x", value=0.0):
    (ax.axvline if axis == "x" else ax.axhline)(value, color=AXIS, linewidth=1.2, zorder=1)


# ---------------------------------------------------------------------------
# A. Does home advantage exist?
# ---------------------------------------------------------------------------
def fig_a_results(t: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(8.5, 3.2))
    comps = ["EPL", "LALIGA", "UCL"][::-1]
    for i, comp in enumerate(comps):
        r = t[t["competition"] == comp].iloc[0]
        left = 0.0
        for code, col, name in (("H", "home_win_pct", "Home win"), ("D", "draw_pct", "Draw"), ("A", "away_win_pct", "Away win")):
            w = r[col]
            ax.barh(i, w - 0.3, left=left + 0.15, height=0.62, color=RESULT_COLORS[code],
                    label=name if i == 0 else None)
            ax.text(left + w / 2, i, f"{w:.1f}%", ha="center", va="center", fontsize=9.5,
                    color="#ffffff" if code != "D" else INK, fontweight="bold")
            left += w
        ax.text(101, i, f"n = {int(r['matches']):,}", va="center", fontsize=8.5, color=MUTED)
    ax.set_yticks(range(len(comps)), [COMP_LABELS[c] for c in comps])
    ax.set_xlim(0, 112)
    ax.set_xticks([0, 25, 50, 75, 100], ["0%", "25%", "50%", "75%", "100%"])
    ax.grid(axis="y", visible=False)
    ax.legend(ncol=3, loc="upper left", bbox_to_anchor=(0, -0.12))
    _title(fig, "Home teams win more often than away teams in all three competitions",
           "Share of results, 2016/17 to 2025/26. Neutral-venue matches excluded.")
    return _save(fig, "eda_a_results")


def fig_a_home_away(t: pd.DataFrame) -> Path:
    metrics = ["points", "goals", "shots", "shots_on_target", "corners"]
    fig, axes = plt.subplots(1, len(metrics), figsize=(13, 3.0), sharey=True)
    comps = ["EPL", "LALIGA", "UCL"]
    for ax, m in zip(axes, metrics):
        for i, comp in enumerate(comps):
            r = t[(t["competition"] == comp) & (t["metric"] == m)]
            if r.empty:
                ax.text(0.5, i, "no data", va="center", ha="center", fontsize=8.5, color=MUTED,
                        transform=ax.get_yaxis_transform())
                continue
            r = r.iloc[0]
            _dot_ci(ax, i, r["diff_pm"], r["diff_lo"], r["diff_hi"], COMP_COLORS[comp])
            ax.text(r["diff_hi"], i + 0.28, f"+{r['diff_pm']:.2f}", ha="right", fontsize=8.5, color=INK_2)
        _zero_line(ax)
        ax.set_title(METRIC_LABELS[m], fontsize=10)
        ax.set_ylim(-0.6, 2.6)
        lim = max(abs(np.nanmin(t.loc[t.metric == m, "diff_lo"])), abs(np.nanmax(t.loc[t.metric == m, "diff_hi"])))
        ax.set_xlim(-0.15 * lim, lim * 1.15)
        ax.grid(axis="y", visible=False)
    axes[0].set_yticks(range(3), [COMP_LABELS[c] for c in comps])
    axes[0].invert_yaxis()
    _title(fig, "Home teams out-score, out-shoot and out-point their visitors",
           "Home minus away, per match, with 95% intervals. The UCL source has no match statistics.")
    return _save(fig, "eda_a_home_away")


# ---------------------------------------------------------------------------
# B. Has home advantage changed over time?
# ---------------------------------------------------------------------------
def _shade_covid(ax, seasons):
    i0, i1 = seasons.index("2019/20"), seasons.index("2020/21")
    ax.axvspan(i0 - 0.45, i1 + 0.45, color=COVID_SHADE, zorder=0)


def fig_b_trend(t: pd.DataFrame) -> Path:
    seasons = sorted(t["season"].unique())
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.2))
    panels = [("home_win_pct", "Home win %", "{:.0f}%"), ("home_excess", "Strength-adjusted home excess", "{:+.2f}")]
    for ax, (col, ttl, fmt) in zip(axes, panels):
        _shade_covid(ax, seasons)
        for comp in ["EPL", "LALIGA", "UCL"]:
            d = t[t["competition"] == comp].set_index("season").reindex(seasons)
            x = np.arange(len(seasons))
            ax.plot(x, d[col], color=COMP_COLORS[comp], marker="o", markersize=6,
                    markeredgecolor=SURFACE, markeredgewidth=1.5, label=COMP_LABELS[comp], zorder=3)
            ax.text(x[-1] + 0.2, d[col].iloc[-1], COMP_LABELS[comp], va="center", fontsize=8.5, color=INK_2)
        ax.set_xticks(range(len(seasons)), [s[2:] for s in seasons], rotation=0, fontsize=8.5)
        ax.set_xlim(-0.5, len(seasons) + 1.6)
        ax.set_title(ttl)
        ax.grid(axis="x", visible=False)
        if col == "home_excess":
            _zero_line(ax, "y")
            ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.2f}"))
        else:
            ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
        ax.text(seasons.index("2019/20") + 0.5, ax.get_ylim()[1], "COVID seasons", ha="center", va="top",
                fontsize=8.5, color=MUTED)
    axes[0].legend(loc="upper left", bbox_to_anchor=(0, -0.1), ncol=3)
    _title(fig, "Home advantage dipped in the empty-stadium season and recovered afterwards",
           "Per season, neutral venues excluded. Home excess = home score (win 1, draw 0.5) minus the "
           "score expected from pre-match Elo with no home term.")
    return _save(fig, "eda_b_trend")


# ---------------------------------------------------------------------------
# C. What happened when crowds disappeared?
# ---------------------------------------------------------------------------
def fig_c_crowd(t: pd.DataFrame, window: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6), sharey=True)
    groups = [("All matches, 2016/17 to 2025/26", t[t["competition"] == "ALL"])]
    groups.append(("EPL and La Liga, 2019/20 to 2021/22 only", window))
    crowds = ["normal", "restricted", "behind_closed_doors"]
    panels = [("home_win_pct", "Home win %", lambda v: f"{v:.1f}%"),
              ("goal_diff_pm", "Home goal difference per match", lambda v: f"{v:+.2f}"),
              ("home_excess", "Strength-adjusted home excess", lambda v: f"{v:+.3f}")]
    for ax, (col, ttl, fmt) in zip(axes, panels):
        for gi, (glabel, d) in enumerate(groups):
            for ci, crowd in enumerate(crowds):
                r = d[d["crowd_status"] == crowd]
                if r.empty:
                    continue
                r = r.iloc[0]
                y = gi * 4 + ci
                lo, hi = (r[f"{col}_lo"], r[f"{col}_hi"])
                _dot_ci(ax, y, r[col], lo, hi, CROWD_COLORS[crowd],
                        label=f"{CROWD_LABELS[crowd]}" if (gi == 0 and col == "home_win_pct") else None)
                ax.text(hi, y, f"  {fmt(r[col])}  (n={int(r['matches']):,})", va="center", fontsize=8, color=INK_2)
        if col != "home_win_pct":
            _zero_line(ax)
        ax.set_title(ttl, fontsize=10)
        ax.grid(axis="y", visible=False)
        x0, x1 = ax.get_xlim()
        ax.set_xlim(x0, x1 + (x1 - x0) * 0.45)
    axes[0].set_yticks([1, 5], [g[0].replace(", ", "\n") for g in groups], fontsize=9)
    axes[0].invert_yaxis()
    axes[0].legend(loc="upper left", bbox_to_anchor=(0, -0.08), ncol=3)
    _title(fig, "Home advantage was smaller in matches behind closed doors",
           "Mean with 95% interval. Neutral venues and matches with unknown crowd status excluded.")
    return _save(fig, "eda_c_crowd")


def fig_c_by_competition(t: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(8.5, 4.2))
    crowds = ["normal", "restricted", "behind_closed_doors"]
    comps = ["EPL", "LALIGA", "UCL"]
    for gi, comp in enumerate(comps):
        for ci, crowd in enumerate(crowds):
            r = t[(t["competition"] == comp) & (t["crowd_status"] == crowd)]
            if r.empty:
                continue
            r = r.iloc[0]
            y = gi * 4 + ci
            _dot_ci(ax, y, r["home_excess"], r["home_excess_lo"], r["home_excess_hi"], CROWD_COLORS[crowd],
                    label=CROWD_LABELS[crowd] if gi == 0 else None)
            ax.text(r["home_excess_hi"], y, f"  {r['home_excess']:+.3f}  (n={int(r['matches']):,})", va="center",
                    fontsize=8, color=INK_2)
    _zero_line(ax)
    ax.set_yticks([1, 5, 9], [COMP_LABELS[c] for c in comps])
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    x0, x1 = ax.get_xlim()
    ax.set_xlim(x0, x1 + (x1 - x0) * 0.3)
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.08), ncol=3)
    _title(fig, "The empty-stadium drop is clearest in the Premier League",
           "Strength-adjusted home excess by crowd condition, with 95% intervals. Small samples have wide intervals.")
    return _save(fig, "eda_c_by_competition")


def _stat_panels(t: pd.DataFrame, metrics: list[str], name: str, title: str, subtitle: str) -> Path:
    d = t[t["competition"] == "ALL"]
    crowds = ["normal", "restricted", "behind_closed_doors"]
    fig, axes = plt.subplots(1, len(metrics), figsize=(4.3 * len(metrics), 2.9), sharey=True)
    for ax, m in zip(axes, metrics):
        for ci, crowd in enumerate(crowds):
            r = d[(d["metric"] == m) & (d["crowd_status"] == crowd)]
            if r.empty:
                continue
            r = r.iloc[0]
            _dot_ci(ax, ci, r["diff_pm"], r["diff_lo"], r["diff_hi"], CROWD_COLORS[crowd],
                    label=CROWD_LABELS[crowd] if m == metrics[0] else None)
            ax.text(r["diff_hi"], ci, f"  {r['diff_pm']:+.2f}", va="center", fontsize=8.5, color=INK_2)
        _zero_line(ax)
        ax.set_title(METRIC_LABELS[m], fontsize=10)
        ax.grid(axis="y", visible=False)
        x0, x1 = ax.get_xlim()
        ax.set_xlim(min(x0, -0.05 * (x1 - x0)), x1 + (x1 - x0) * 0.3)
    axes[0].set_yticks(range(3), [CROWD_LABELS[c] for c in crowds])
    axes[0].invert_yaxis()
    _title(fig, title, subtitle)
    return _save(fig, name)


def fig_c_performance(t: pd.DataFrame) -> Path:
    return _stat_panels(t, ["shots", "shots_on_target", "corners"], "eda_c_performance",
                        "Home teams' edge in shots and corners narrowed without crowds",
                        "Home minus away per match, EPL and La Liga, with 95% intervals.")


def fig_d_referee(t: pd.DataFrame) -> Path:
    return _stat_panels(t, ["fouls", "yellow_cards", "red_cards"], "eda_d_referee",
                        "The away side's extra fouls and yellow cards disappeared in empty stadiums",
                        "Home minus away per match, EPL and La Liga, with 95% intervals. Negative = away side "
                        "committed or received more. Penalties are not available.")


# ---------------------------------------------------------------------------
# E. Which teams have the strongest home advantage?
# ---------------------------------------------------------------------------
def fig_e_teams(t: pd.DataFrame, n: int = 10) -> Path:
    top, bottom = t.head(n), t.tail(n)
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6), sharex=True, gridspec_kw={"wspace": 0.55})
    mean = t["adj_gap"].mean()
    for ax, d, ttl in ((axes[0], top, f"Largest home advantage (top {n})"),
                       (axes[1], bottom.iloc[::-1], f"Smallest home advantage (bottom {n})")):
        for i, r in enumerate(d.itertuples()):
            _dot_ci(ax, i, r.adj_gap, r.adj_gap_lo, r.adj_gap_hi, COMP_COLORS[r.competition], size=50)
        ax.set_yticks(range(len(d)), [f"{r.team} ({int(r.home_matches)})" for r in d.itertuples()], fontsize=9)
        ax.invert_yaxis()
        _zero_line(ax)
        ax.axvline(mean, color=MUTED, linewidth=1, linestyle=(0, (3, 3)))
        ax.set_title(ttl, fontsize=10)
        ax.grid(axis="y", visible=False)
    handles = [plt.Line2D([], [], marker="o", linestyle="", color=COMP_COLORS[c], markersize=7, label=COMP_LABELS[c])
               for c in ["EPL", "LALIGA"]]
    axes[0].legend(handles=handles, loc="upper left", bbox_to_anchor=(0, -0.06), ncol=2)
    _title(fig, "Club home advantage varies, but most intervals overlap the league average",
           f"Home excess minus away excess (Elo-adjusted), league matches with normal crowds, "
           f"clubs with at least {int(t['home_matches'].min())} home games (count in brackets). 95% intervals. "
           f"Dashed line = average of all {len(t)} clubs ({mean:+.2f}).")
    return _save(fig, "eda_e_teams")


# ---------------------------------------------------------------------------
# F. Which competition depends most on home advantage?
# ---------------------------------------------------------------------------
def fig_f_competition(t: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(8.5, 3.6))
    colors = {"Premier League": COMP_COLORS["EPL"], "La Liga": COMP_COLORS["LALIGA"]}
    for i, r in enumerate(t.itertuples()):
        c = colors.get(r.segment, COMP_COLORS["UCL"])
        size = 70 if r.segment in ("Premier League", "La Liga", "Champions League") else 45
        _dot_ci(ax, i, r.home_excess, r.home_excess_lo, r.home_excess_hi, c, size=size)
        ax.text(r.home_excess_hi, i, f"  {r.home_excess:+.3f}  (n={int(r.matches):,})", va="center",
                fontsize=8.5, color=INK_2)
    labels = [s if not s.startswith("UCL ") else "    " + s.replace("UCL ", "").capitalize() for s in t["segment"]]
    ax.set_yticks(range(len(t)), labels)
    ax.invert_yaxis()
    _zero_line(ax)
    ax.grid(axis="y", visible=False)
    x0, x1 = ax.get_xlim()
    ax.set_xlim(min(x0, -0.01), x1 + (x1 - x0) * 0.35)
    _title(fig, "La Liga shows the largest strength-adjusted home advantage",
           "Home excess with 95% intervals, neutral venues excluded. Indented rows split the Champions League.")
    return _save(fig, "eda_f_competition")


# ---------------------------------------------------------------------------
# Supplementary: travel and rest
# ---------------------------------------------------------------------------
def fig_g_travel_rest(travel: pd.DataFrame, rest: pd.DataFrame) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(13, 3.8), sharey=True)
    ax = axes[0]
    scope_color = {"Domestic": MUTED, "UCL": COMP_COLORS["UCL"]}
    bands = list(travel["travel_band"].cat.categories) if hasattr(travel["travel_band"], "cat") else list(
        dict.fromkeys(travel["travel_band"]))
    for k, scope in enumerate(["Domestic", "UCL"]):
        d = travel[(travel["scope"] == scope) & (travel["matches"] >= 30)]
        for r in d.itertuples():
            x = bands.index(r.travel_band) + (k - 0.5) * 0.25
            ax.vlines(x, r.home_excess_lo, r.home_excess_hi, color=scope_color[scope], linewidth=2, alpha=0.6)
            ax.scatter(x, r.home_excess, s=55, color=scope_color[scope], edgecolor=SURFACE, linewidth=2, zorder=3,
                       label=f"{scope} matches" if r.Index == d.index[0] else None)
    ax.set_xticks(range(len(bands)), bands, fontsize=8.5)
    ax.set_xlabel("Away team travel distance (km)")
    ax.set_title("By away-team travel distance (normal crowds)", fontsize=10)
    ax.legend(loc="upper left")
    ax = axes[1]
    for i, r in enumerate(rest.itertuples()):
        ax.vlines(i, r.home_excess_lo, r.home_excess_hi, color=COMP_COLORS["EPL"], linewidth=2, alpha=0.6)
        ax.scatter(i, r.home_excess, s=55, color=COMP_COLORS["EPL"], edgecolor=SURFACE, linewidth=2, zorder=3)
        ax.text(i, r.home_excess_hi, f"n={int(r.matches):,}", ha="center", va="bottom", fontsize=8, color=MUTED)
    ax.set_xticks(range(len(rest)), [str(b) for b in rest["rest_band"]], fontsize=8.5)
    ax.set_xlabel("Rest difference (approximate, capped at 14 days)")
    ax.set_title("By rest difference (all crowds)", fontsize=10)
    for a in axes:
        _zero_line(a, "y")
        a.grid(axis="x", visible=False)
        a.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:+.2f}"))
    _title(fig, "Longer trips and extra home rest go with a slightly larger home excess",
           "Strength-adjusted home excess with 95% intervals; bands under 30 matches omitted. Descriptive only: the domestic distance bands mix leagues (La Liga trips are longer).")
    return _save(fig, "eda_g_travel_rest")


def make_eda_figures(tables: dict[str, pd.DataFrame]) -> list[Path]:
    return [
        fig_a_results(tables["a_overall"]),
        fig_a_home_away(tables["a_home_away"]),
        fig_b_trend(tables["b_trend"]),
        fig_c_crowd(tables["c_crowd"], tables["c_crowd_window"]),
        fig_c_by_competition(tables["c_crowd"]),
        fig_c_performance(tables["c_performance"]),
        fig_d_referee(tables["d_referee"]),
        fig_e_teams(tables["e_teams"]),
        fig_f_competition(tables["f_competition"]),
        fig_g_travel_rest(tables["g_travel"], tables["g_rest"]),
    ]


# ---------------------------------------------------------------------------
# Phase 5: statistical results
# ---------------------------------------------------------------------------
def fig_stats_crowd_by_competition(effects: pd.DataFrame) -> Path:
    fig, ax = plt.subplots(figsize=(8.5, 3.8))
    comps = ["EPL", "LALIGA", "UCL"]
    for gi, comp in enumerate(comps):
        r = effects[effects["competition"] == comp].iloc[0]
        for ci, (key, crowd) in enumerate((("normal", "normal"), ("closed", "behind_closed_doors"))):
            y = gi * 3 + ci
            n = r[f"n_{key}"]
            _dot_ci(ax, y, r[f"{key}_effect"], r[f"{key}_lo"], r[f"{key}_hi"], CROWD_COLORS[crowd],
                    label=CROWD_LABELS[crowd] if gi == 0 else None)
            ax.text(r[f"{key}_hi"], y, f"  {r[f'{key}_effect']:+.2f}  (n={int(n):,})", va="center", fontsize=8,
                    color=INK_2)
        ax.text(ax.get_xlim()[0], gi * 3 + 1.75, "", fontsize=1)
    _zero_line(ax)
    ax.set_yticks([0.5, 3.5, 6.5], [COMP_LABELS[c] for c in comps])
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    x0, x1 = ax.get_xlim()
    ax.set_xlim(x0, x1 + (x1 - x0) * 0.3)
    ax.set_xlabel("Home goal-difference advantage between equally rated teams (goals per match)")
    ax.legend(loc="upper left", bbox_to_anchor=(0, -0.2), ncol=2)
    _title(fig, "Home advantage fell behind closed doors in both leagues",
           "Estimates from one model with club-clustered 95% intervals. The difference between competitions "
           "is not statistically significant (p = 0.66).")
    return _save(fig, "stats_crowd_by_competition")


def fig_stats_factors(coef: pd.DataFrame) -> Path:
    c = coef[coef["model"] == "logit_home_win_factors"].set_index("term")
    rows = [
        ("z_strength", "Strength difference (+1 SD)"),
        ("z_form", "Form difference (+1 SD)"),
        ("z_log_travel", "Away travel, log km (+1 SD)"),
        ("z_rest", "Rest difference (+1 SD)"),
        ("C(crowd, Treatment('normal'))[T.restricted]", "Restricted crowd (vs normal)"),
        ("C(crowd, Treatment('normal'))[T.behind_closed_doors]", "Behind closed doors (vs normal)"),
        ("C(competition)[T.LALIGA]", "La Liga (vs Premier League)"),
        ("C(competition)[T.UCL]", "Champions League (vs Premier League)"),
    ]
    fig, ax = plt.subplots(figsize=(8.5, 4.0))
    for i, (term, label) in enumerate(rows):
        r = c.loc[term]
        color = COMP_COLORS["EPL"] if r["or_ci_lo"] > 1 or r["or_ci_hi"] < 1 else MUTED
        _dot_ci(ax, i, r["odds_ratio"], r["or_ci_lo"], r["or_ci_hi"], color, size=50)
        ax.text(max(r["or_ci_hi"], 1.0), i, f"  {r['odds_ratio']:.2f}", va="center", fontsize=8.5, color=INK_2)
    ax.axvline(1.0, color=AXIS, linewidth=1.2)
    ax.set_xscale("log")
    ax.set_xticks([0.5, 0.75, 1, 1.5, 2], ["0.5", "0.75", "1", "1.5", "2"])
    ax.minorticks_off()
    ax.set_yticks(range(len(rows)), [r[1] for r in rows])
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)
    ax.set_xlabel("Odds ratio for a home win (log scale)")
    _title(fig, "Strength dominates; closed doors cut the odds of a home win by about a fifth",
           "Logistic regression with club-clustered 95% intervals. Blue = interval excludes 1. "
           "Associations, not causal effects.")
    return _save(fig, "stats_factors")


def fig_stats_clubs(clubs: pd.DataFrame) -> Path:
    d = clubs.sort_values("shrunk_gap", ascending=True).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(8.5, 8.5))
    for i, r in enumerate(d.itertuples()):
        ax.plot([r.adj_gap, r.shrunk_gap], [i, i], color=GRID, linewidth=1.5, zorder=1)
        ax.scatter(r.adj_gap, i, s=28, facecolor=SURFACE, edgecolor=MUTED, linewidth=1.5, zorder=2,
                   label="Raw estimate" if i == 0 else None)
        ax.hlines(i, r.shrunk_lo, r.shrunk_hi, color=COMP_COLORS[r.competition], linewidth=2, alpha=0.6, zorder=2)
        ax.scatter(r.shrunk_gap, i, s=40, color=COMP_COLORS[r.competition], edgecolor=SURFACE, linewidth=1.5,
                   zorder=3)
    mu = float(np.average(d["shrunk_gap"]))
    ax.axvline(mu, color=MUTED, linewidth=1, linestyle=(0, (3, 3)))
    ax.set_yticks(range(len(d)), d["team"], fontsize=8.5)
    ax.grid(axis="y", visible=False)
    _zero_line(ax)
    handles = [plt.Line2D([], [], marker="o", linestyle="", markerfacecolor=SURFACE, markeredgecolor=MUTED,
                          label="Raw estimate")]
    handles += [plt.Line2D([], [], marker="o", linestyle="", color=COMP_COLORS[c], label=f"Shrunk estimate, {COMP_LABELS[c]}")
                for c in ["EPL", "LALIGA"]]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(0, -0.07), ncol=3)
    ax.set_xlabel("Home excess minus away excess (Elo-adjusted)")
    ax.set_ylim(-0.8, len(d) - 0.2)
    _title(fig, "After shrinkage, no club's home advantage stands apart",
           "Random-effects estimates with 95% intervals; hollow dots are the raw values. Dashed line = mean.")
    return _save(fig, "stats_clubs")


def make_stats_figures(out: dict[str, pd.DataFrame]) -> list[Path]:
    return [
        fig_stats_crowd_by_competition(out["interaction_effects"]),
        fig_stats_factors(out["coefficients"]),
        fig_stats_clubs(out["clubs_shrunk"]),
    ]


# ---------------------------------------------------------------------------
# Phase 6: models
# ---------------------------------------------------------------------------
def _or_forest(ax, rows, table, term_col="term"):
    t = table.set_index(term_col)
    for i, (term, label) in enumerate(rows):
        r = t.loc[term]
        sig = r["or_ci_lo"] > 1 or r["or_ci_hi"] < 1
        color = COMP_COLORS["EPL"] if sig else MUTED
        _dot_ci(ax, i, r["odds_ratio"], r["or_ci_lo"], r["or_ci_hi"], color, size=50)
        ax.text(max(r["or_ci_hi"], 1.0), i, f"  {r['odds_ratio']:.2f}", va="center", fontsize=8.5, color=INK_2)
    ax.axvline(1.0, color=AXIS, linewidth=1.2)
    ax.set_xscale("log")
    ax.minorticks_off()
    ax.set_yticks(range(len(rows)), [r[1] for r in rows])
    ax.invert_yaxis()
    ax.grid(axis="y", visible=False)


def fig_model_a_effects(coef: pd.DataFrame) -> Path:
    rows = [
        ("strength_difference", "Elo difference (+1 SD)"),
        ("home_form", "Home form, last 5 (+1 SD)"),
        ("away_form", "Away form, last 5 (+1 SD)"),
        ("home_rest_days", "Home rest days (+1 SD)"),
        ("away_rest_days", "Away rest days (+1 SD)"),
        ("log_travel_km", "Away travel, log km (+1 SD)"),
        ("crowd_status_restricted", "Restricted crowd (vs normal)"),
        ("crowd_status_behind_closed_doors", "Behind closed doors (vs normal)"),
        ("competition_LALIGA", "La Liga (vs Premier League)"),
        ("competition_UCL", "Champions League (vs Premier League)"),
        ("knockout_match", "UCL knockout match"),
        ("neutral_venue", "Neutral venue"),
    ]
    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    _or_forest(ax, rows, coef)
    ax.set_xticks([0.25, 0.5, 1, 2, 3], ["0.25", "0.5", "1", "2", "3"])
    ax.set_xlabel("Odds ratio for a home win (log scale)")
    _title(fig, "Model A: before kick-off, team strength is what predicts a home win",
           "Unpenalised logit on the training seasons, club-clustered 95% intervals. Blue = interval excludes 1. "
           "Associations, not causal effects.")
    return _save(fig, "ml_model_a_effects")


def fig_model_a_performance(pred: pd.DataFrame, calibration: pd.DataFrame) -> Path:
    from sklearn.metrics import roc_auc_score, roc_curve

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.6))
    ax = axes[0]
    ax.plot([0, 1], [0, 1], color=AXIS, linewidth=1.2, linestyle=(0, (3, 3)))
    for col, label, color in (("p_model_a", "Model A", COMP_COLORS["EPL"]), ("p_elo_only", "Elo difference only", MUTED)):
        fpr, tpr, _ = roc_curve(pred["home_win"], pred[col])
        auc = roc_auc_score(pred["home_win"], pred[col])
        ax.plot(fpr, tpr, color=color, label=f"{label} (AUC {auc:.3f})")
    ax.set_xlabel("False positive rate")
    ax.set_ylabel("True positive rate")
    ax.set_title("ROC curve, test seasons", fontsize=10)
    ax.legend(loc="lower right")
    ax.set_aspect("equal")
    ax = axes[1]
    ax.plot([0, 1], [0, 1], color=AXIS, linewidth=1.2, linestyle=(0, (3, 3)))
    ax.plot(calibration["mean_predicted"], calibration["observed"], color=COMP_COLORS["EPL"], marker="o",
            markersize=6, markeredgecolor=SURFACE, markeredgewidth=1.5)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.set_xlabel("Predicted home-win probability (decile mean)")
    ax.set_ylabel("Observed home-win rate")
    ax.set_title("Calibration, test seasons", fontsize=10)
    _title(fig, "Model A is well calibrated but adds little over Elo alone",
           f"Scored once on 2024/25 and 2025/26 ({len(pred):,} matches) after tuning on 2023/24.")
    return _save(fig, "ml_model_a_performance")


def fig_model_b(coef: pd.DataFrame) -> Path:
    c = coef[coef["specification"] == "with match statistics"]
    rows = [
        ("z_strength_difference", "Elo difference (+1 SD)"),
        ("z_shots_on_target_diff", "Shots on target, home minus away (+1 SD)"),
        ("z_shots_diff", "Shots, home minus away (+1 SD)"),
        ("z_corners_diff", "Corners, home minus away (+1 SD)"),
        ("z_fouls_diff", "Fouls, home minus away (+1 SD)"),
        ("z_yellow_cards_diff", "Yellow cards, home minus away (+1 SD)"),
        ("z_red_cards_diff", "Red cards, home minus away (+1 SD)"),
        ("behind_closed_doors", "Behind closed doors (vs normal)"),
    ]
    fig, ax = plt.subplots(figsize=(8.5, 4.0))
    _or_forest(ax, rows, c)
    ax.set_xticks([0.5, 1, 2, 5], ["0.5", "1", "2", "5"])
    ax.set_xlabel("Odds ratio for a home win (log scale)")
    _title(fig, "Model B: shots on target explain results; closed doors still matter after them",
           "Explanatory logit, EPL and La Liga, in-match statistics (not usable for prediction). "
           "Club-clustered 95% intervals.")
    return _save(fig, "ml_model_b")


def make_model_figures(out: dict) -> list[Path]:
    return [
        fig_model_a_effects(out["inference_coefficients"]),
        fig_model_a_performance(out["test_predictions"], out["calibration"]),
        fig_model_b(out["model_b_coefficients"]),
    ]


CLUSTER_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]


def fig_cluster_selection(out: dict) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    specs = (("main", "All nine features", INK_2), ("gap_only", "Home-away gap features only", COMP_COLORS["EPL"]))
    for spec, label, color in specs:
        s = out[spec]["scores"]
        axes[0].plot(s["k"], s["inertia"] / s["inertia"].iloc[0], color=color, marker="o", markersize=6,
                     markeredgecolor=SURFACE, markeredgewidth=1.5, label=label)
        axes[1].plot(s["k"], s["silhouette"], color=color, marker="o", markersize=6, markeredgecolor=SURFACE,
                     markeredgewidth=1.5, label=label)
        k = out[spec]["k"]
        axes[1].scatter([k], s.loc[s["k"] == k, "silhouette"], s=160, facecolor="none", edgecolor=color, linewidth=1.5)
    axes[0].set_title("Elbow: inertia relative to k = 2", fontsize=10)
    axes[1].set_title("Silhouette score (ringed = chosen k)", fontsize=10)
    for ax in axes:
        ax.set_xlabel("Number of clusters (k)")
        ax.grid(axis="x", visible=False)
    axes[0].legend(loc="upper right")
    _title(fig, "Both specifications point to two clusters",
           "K-Means on standardised club features, 45 clubs. No clear elbow; silhouette peaks at k = 2.")
    return _save(fig, "ml_cluster_selection")


def fig_cluster_pca(out: dict, names: dict[str, list[str]]) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
    titles = {"main": "All nine features", "gap_only": "Home-away gap features only"}
    for ax, spec in zip(axes, ("main", "gap_only")):
        res = out[spec]
        t = res["teams"]
        for c in sorted(t["cluster"].unique()):
            d = t[t["cluster"] == c]
            ax.scatter(d["pc1"], d["pc2"], s=48, color=CLUSTER_COLORS[c], edgecolor=SURFACE, linewidth=1.5,
                       label=f"{names[spec][c]} ({len(d)})", zorder=3)
        # Label only the clubs at the edges of the projection to keep it legible.
        edge = set(t.nlargest(4, "pc1").index) | set(t.nsmallest(4, "pc1").index) | \
            set(t.nlargest(2, "pc2").index) | set(t.nsmallest(2, "pc2").index)
        for i in edge:
            r = t.loc[i]
            ax.annotate(r["team"], (r["pc1"], r["pc2"]), fontsize=7.5, color=INK_2, xytext=(4, 3),
                        textcoords="offset points")
        ev = res["pca_explained"]
        ax.set_xlabel(f"PC1 ({ev[0]:.0%} of variance)")
        ax.set_ylabel(f"PC2 ({ev[1]:.0%})")
        ax.set_title(titles[spec], fontsize=10)
        ax.legend(loc="upper left", bbox_to_anchor=(0, -0.12), ncol=2)
    _title(fig, "Club clusters split mainly along one axis",
           "PCA projection for display only; clustering ran on all standardised features. League matches with normal crowds.")
    return _save(fig, "ml_cluster_pca")


def make_cluster_figures(out: dict) -> list[Path]:
    names = {"main": ["Strong home sides", "Modest home sides"],
             "gap_only": ["Larger home-away gap", "Smaller home-away gap"]}
    return [fig_cluster_selection(out), fig_cluster_pca(out, names)]
