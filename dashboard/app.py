"""Home-Field Advantage Analyzer: interactive dashboard (Phase 7).

Reads only committed outputs (``reports/tables`` and ``dashboard/data``), so it
runs straight after a clone:

    streamlit run dashboard/app.py

Every number on the page comes from those tables. Rebuild them with the
pipeline commands in the README; nothing here is typed in by hand except the
cluster names, which were chosen after inspecting the centroids.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.models.clustering import CLUSTER_NAMES  # noqa: E402

TABLES = ROOT / "reports" / "tables"
DATA = ROOT / "dashboard" / "data"

# Palette shared with the static report figures (src/visualization/plots.py).
SURFACE, INK, INK_2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"
COMP_COLORS = {"EPL": "#2a78d6", "LALIGA": "#eb6834", "UCL": "#1baf7a"}
COMP_LABELS = {"EPL": "Premier League", "LALIGA": "La Liga", "UCL": "Champions League", "ALL": "All competitions"}
CROWD_COLORS = {"normal": "#184f95", "restricted": "#3987e5", "behind_closed_doors": "#86b6ef"}
CROWD_LABELS = {"normal": "Normal crowd", "restricted": "Restricted crowd", "behind_closed_doors": "Behind closed doors"}
RESULT_COLORS = {"H": "#2a78d6", "D": "#bdbcb6", "A": "#e34948"}
CLUSTER_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]
COVID_SEASONS = ("2019/20", "2020/21")

SECTIONS = ["Overview", "Home advantage over time", "The COVID experiment", "Competition comparison",
            "Team explorer", "Travel and rest", "Team clusters", "Statistical models"]

st.set_page_config(page_title="Home-Field Advantage Analyzer", page_icon="⚽", layout="wide")
st.markdown(
    """
    <style>
      .block-container {padding-top: 2rem; max-width: 1200px;}
      [data-testid="stMetricValue"] {font-size: 1.9rem;}
      .note {color: #52514e; font-size: 0.92rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
@st.cache_data
def table(name: str) -> pd.DataFrame:
    return pd.read_csv(TABLES / f"{name}.csv")


@st.cache_data
def team_seasons() -> pd.DataFrame:
    return pd.read_csv(DATA / "team_seasons.csv")


@st.cache_data
def choice(name: str) -> dict:
    return json.loads((TABLES / f"{name}.json").read_text())


def test_row(test_id: str) -> pd.Series:
    t = table("stats_tests")
    return t.loc[t["test_id"] == test_id].iloc[0]


def fmt_p(p: float) -> str:
    return "< 0.001" if p < 0.001 else f"{p:.3f}"


# ---------------------------------------------------------------------------
# Plotly styling
# ---------------------------------------------------------------------------
def style(fig: go.Figure, title: str, height: int = 420, xtitle: str = "", ytitle: str = "") -> go.Figure:
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left", font=dict(size=17, color=INK)),
        height=height, paper_bgcolor=SURFACE, plot_bgcolor=SURFACE,
        font=dict(family="Inter, Helvetica, Arial, sans-serif", size=13, color=INK_2),
        margin=dict(l=10, r=10, t=60, b=10), hovermode="closest",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1, title=None),
        hoverlabel=dict(bgcolor="white", font_color=INK, bordercolor=AXIS),
    )
    fig.update_xaxes(title=xtitle, showgrid=False, linecolor=AXIS, ticks="outside", tickcolor=AXIS, zeroline=False)
    fig.update_yaxes(title=ytitle, gridcolor=GRID, linecolor=AXIS, zeroline=False)
    return fig


def zero_line(fig: go.Figure, axis: str = "x", value: float = 0.0) -> None:
    (fig.add_vline if axis == "x" else fig.add_hline)(value, line_color=MUTED, line_width=1, line_dash="dot")


def dot_ci(fig, x, y, lo, hi, color, name, horizontal=True, text=None, showlegend=True, hover=None):
    err = dict(type="data", symmetric=False, array=np.asarray(hi) - np.asarray(x if horizontal else y),
               arrayminus=np.asarray(x if horizontal else y) - np.asarray(lo), color=color, thickness=2, width=0)
    kw = {"error_x": err} if horizontal else {"error_y": err}
    fig.add_trace(go.Scatter(x=x, y=y, mode="markers", name=name, showlegend=showlegend, text=text,
                             marker=dict(size=11, color=color, line=dict(color=SURFACE, width=2)),
                             hovertemplate=hover, **kw))


def log_ticks(fig: go.Figure, values=(0.25, 0.5, 0.75, 1, 1.5, 2, 3, 5)) -> None:
    fig.update_xaxes(type="log", tickvals=list(values), ticktext=[f"{v:g}" for v in values])


def caption(text: str) -> None:
    st.markdown(f"<p class='note'>{text}</p>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------
def overview() -> None:
    st.title("How much is playing at home worth?")
    st.markdown(
        "Ten completed seasons (2016/17 to 2025/26) of the **Premier League, La Liga and the Champions League**. "
        "Every comparison controls for team strength with pre-match Elo ratings, and the COVID-19 period, when "
        "stadiums were empty, is used as a natural experiment."
    )
    inter = table("stats_interaction_effects").set_index("competition")
    m1, m1r, e1 = test_row("M1_behind_closed_doors"), test_row("M1r_window_season_fe"), test_row("E1_heterogeneity")
    crowd = table("eda_c_crowd")
    crowd = crowd[crowd["competition"] == "ALL"].set_index("crowd_status")
    metrics = table("ml_model_test_metrics").set_index("model")
    auc_a = metrics.loc["Model A (threshold 0.5)", "roc_auc"]
    auc_elo = metrics.loc["Elo difference only", "roc_auc"]
    overall = table("eda_a_overall")

    c = st.columns(4)
    c[0].metric("Home edge, equal teams (EPL)", f"+{inter.loc['EPL', 'normal_effect']:.2f} goals",
                help="Home goal difference per match between two equally rated teams with normal crowds (OLS, "
                     "club-clustered standard errors).")
    c[1].metric("Change behind closed doors", f"{m1['estimate']:+.2f} goals",
                help=f"95% CI {m1['ci_lo']:.2f} to {m1['ci_hi']:.2f}; Holm-adjusted p = {fmt_p(m1['p_holm'])}.")
    c[2].metric("Home-win rate, normal vs empty", f"{crowd.loc['normal', 'home_win_pct']:.1f}% → "
                f"{crowd.loc['behind_closed_doors', 'home_win_pct']:.1f}%",
                help="Raw rates, all competitions, neutral venues excluded.")
    c[3].metric("Pre-match model ROC-AUC", f"{auc_a:.3f}", f"{auc_a - auc_elo:+.3f} vs Elo alone",
                delta_color="off", help="Scored once on the untouched test seasons 2024/25 and 2025/26.")

    st.subheader("Key findings")
    st.markdown(
        f"""
1. **Home advantage is real in every competition.** Between equally rated teams with normal crowds, the home
   side is worth +{inter.loc['EPL', 'normal_effect']:.2f} goals per match in the Premier League,
   +{inter.loc['LALIGA', 'normal_effect']:.2f} in La Liga and +{inter.loc['UCL', 'normal_effect']:.2f} in the
   Champions League. It has **not trended up or down** over the decade.
2. **Empty stadiums cut it by about two-thirds.** With strength held equal, the home goal-difference edge fell
   by {abs(m1['estimate']):.2f} goals per match behind closed doors (95% CI {m1['ci_lo']:.2f} to
   {m1['ci_hi']:.2f}). With season fixed effects the estimate keeps its direction ({m1r['estimate']:+.2f}) but
   its interval crosses zero, so a season-level explanation cannot be ruled out.
3. **Home sides created less without crowds,** and the away side's extra yellow cards disappeared. These are
   differences in referee-related outcomes; they do not by themselves prove referee bias.
4. **No competition and no club stands apart.** The closed-doors drop does not differ significantly between
   competitions, and club differences in home advantage are not significant (Cochran's Q p =
   {e1['p_value']:.2f}).
5. **Before kick-off, team strength is almost everything.** The full pre-match model barely beats Elo alone
   (ROC-AUC {auc_a:.3f} vs {auc_elo:.3f}); form, rest and travel add little or nothing.
        """
    )
    st.subheader("The data")
    rows = overall.assign(Competition=overall["competition"].map(COMP_LABELS))
    st.dataframe(
        rows[["Competition", "matches", "home_win_pct", "draw_pct", "away_win_pct", "home_points_pm", "away_points_pm"]]
        .rename(columns={"matches": "Matches (genuine home)", "home_win_pct": "Home win %", "draw_pct": "Draw %",
                         "away_win_pct": "Away win %", "home_points_pm": "Home points per match",
                         "away_points_pm": "Away points per match"})
        .round(2), hide_index=True, use_container_width=True)
    caption("Matches at neutral venues (finals and relocated COVID-era ties) are excluded from home-advantage "
            "measures because neither side was at home. Attendance figures were not available from any free, "
            "stable source, so crowd conditions come from a cited table of COVID-era restrictions.")


def over_time() -> None:
    st.header("Has home advantage changed over the decade?")
    t = table("eda_b_trend")
    options = {
        "Strength-adjusted home excess": ("home_excess", "home_excess_lo", "home_excess_hi",
                                          "Home result minus Elo expectation (0 = no home advantage)"),
        "Home win %": ("home_win_pct", "home_win_pct_lo", "home_win_pct_hi", "Home win %"),
        "Home goal difference per match": ("goal_diff_pm", "goal_diff_pm_lo", "goal_diff_pm_hi", "Goals per match"),
        "Home share of points (domestic)": ("points_share", None, None, "Share of points won by the home side"),
    }
    c1, c2 = st.columns([2, 3])
    label = c1.selectbox("Measure", list(options))
    comps = c2.multiselect("Competitions", list(COMP_COLORS), default=list(COMP_COLORS), format_func=COMP_LABELS.get)
    col, lo, hi, ytitle = options[label]
    bands = st.checkbox("Show 95% confidence intervals", value=len(comps) == 1)
    fig = go.Figure()
    seasons = sorted(t["season"].unique())
    fig.add_vrect(x0=seasons.index(COVID_SEASONS[0]) - 0.5, x1=seasons.index(COVID_SEASONS[1]) + 0.5,
                  fillcolor="#f0efec", line_width=0, layer="below", annotation_text="COVID restrictions",
                  annotation_position="top left", annotation_font_color=MUTED)
    for comp in comps:
        d = t[t["competition"] == comp].sort_values("season")
        if d[col].isna().all():
            continue
        if lo and bands:
            fig.add_trace(go.Scatter(x=list(d["season"]) + list(d["season"][::-1]),
                                     y=list(d[hi]) + list(d[lo][::-1]), fill="toself", fillcolor=COMP_COLORS[comp],
                                     opacity=0.12, line=dict(width=0), hoverinfo="skip", showlegend=False))
        fig.add_trace(go.Scatter(x=d["season"], y=d[col], mode="lines+markers", name=COMP_LABELS[comp],
                                 line=dict(color=COMP_COLORS[comp], width=2.5),
                                 marker=dict(size=8, line=dict(color=SURFACE, width=2)),
                                 customdata=d[["matches"]],
                                 hovertemplate="%{x}<br>%{y:.3f}<br>%{customdata[0]:.0f} matches<extra>"
                                               + COMP_LABELS[comp] + "</extra>"))
    if col == "home_excess":
        zero_line(fig, "y")
    fig.update_xaxes(categoryorder="array", categoryarray=seasons)
    st.plotly_chart(style(fig, label + " by season", 460, ytitle=ytitle), use_container_width=True)
    trend = test_row("M8_trend")
    caption(f"Shaded bands are 95% confidence intervals. Using normal-crowd matches only, there is no trend: a regression of home "
            f"excess on season gives {trend['estimate']:+.4f} per season (95% CI {trend['ci_lo']:+.4f} to "
            f"{trend['ci_hi']:+.4f}, Holm p = {fmt_p(trend['p_holm'])}). The dip falls in the empty-stadium seasons.")


def covid() -> None:
    st.header("What happened when the crowds disappeared?")
    st.markdown("Crowd status is assigned per match from published restrictions: normal, restricted (limited "
                "supporters) or behind closed doors.")
    crowd = table("eda_c_crowd")
    comp = st.radio("Competition", ["ALL", "EPL", "LALIGA", "UCL"], horizontal=True, format_func=COMP_LABELS.get)
    d = crowd[(crowd["competition"] == comp) & crowd["crowd_status"].isin(CROWD_COLORS)]
    c1, c2 = st.columns(2)
    for col, lo, hi, title, box, unit in (
            ("home_win_pct", "home_win_pct_lo", "home_win_pct_hi", "Home-win rate", c1, "%"),
            ("home_excess", "home_excess_lo", "home_excess_hi", "Strength-adjusted home excess", c2, "")):
        fig = go.Figure()
        for _, r in d.iterrows():
            dot_ci(fig, [r[col]], [CROWD_LABELS[r["crowd_status"]]], [r[lo]], [r[hi]], CROWD_COLORS[r["crowd_status"]],
                   CROWD_LABELS[r["crowd_status"]], showlegend=False,
                   hover=f"%{{x:.2f}}{unit}<br>{int(r['matches']):,} matches<extra></extra>")
        if col == "home_excess":
            zero_line(fig, "x")
        fig.update_yaxes(categoryorder="array", categoryarray=[CROWD_LABELS[k] for k in reversed(list(CROWD_COLORS))])
        box.plotly_chart(style(fig, title, 300, xtitle=title + (" (%)" if unit else "")), use_container_width=True)
    caption("Dots are estimates, lines 95% confidence intervals. Restricted-crowd matches are few, so their "
            "intervals are wide.")

    st.subheader("With strength held equal")
    rows = []
    for tid, label, unit in (("M1_behind_closed_doors", "Home goal difference (OLS)", "goals per match"),
                             ("M2_behind_closed_doors", "Odds of a home win (logit)", "odds ratio"),
                             ("M3_behind_closed_doors", "Ordered result A < D < H (ordered logit)", "odds ratio"),
                             ("M1r_window_season_fe", "Robustness: season fixed effects, 2019/20 to 2021/22",
                              "goals per match")):
        r = test_row(tid)
        rows.append({"Model": label, "Closed-doors effect": f"{r['estimate']:+.3f} {unit}" if unit != "odds ratio"
                     else f"OR {r['estimate']:.2f}", "95% CI": f"{r['ci_lo']:.2f} to {r['ci_hi']:.2f}",
                     "p": fmt_p(r["p_value"]), "Holm p": "" if pd.isna(r["p_holm"]) else fmt_p(r["p_holm"])})
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
    caption("All models control for the pre-match Elo difference and competition, with standard errors clustered "
            "by home club. The season fixed-effects check keeps the direction but cannot separate empty stadiums "
            "from other features of 2020/21 (fixture congestion, five substitutes, no travelling fans).")

    st.subheader("Did home teams play differently, and did referee-related outcomes change?")
    perf, ref = table("eda_c_performance"), table("eda_d_referee")
    both = pd.concat([perf, ref])
    both = both[(both["competition"] == ("ALL" if comp in ("ALL", "UCL") else comp))
                & both["crowd_status"].isin(CROWD_COLORS)]
    labels = {"shots": "Shots", "shots_on_target": "Shots on target", "corners": "Corners", "fouls": "Fouls",
              "yellow_cards": "Yellow cards", "red_cards": "Red cards"}
    both = both[both["metric"].isin(labels)]
    fig = go.Figure()
    for status in CROWD_COLORS:
        x = both[both["crowd_status"] == status].set_index("metric").reindex(list(labels))
        dot_ci(fig, x["diff_pm"], [labels[m] for m in x.index], x["diff_lo"], x["diff_hi"], CROWD_COLORS[status],
               CROWD_LABELS[status], text=x["matches"],
               hover="%{y}: %{x:+.2f} per match<br>%{text:,.0f} matches<extra>" + CROWD_LABELS[status] + "</extra>")
    zero_line(fig, "x")
    fig.update_layout(scattermode="group")
    fig.update_yaxes(categoryorder="array", categoryarray=list(reversed(list(labels.values()))))
    st.plotly_chart(style(fig, "Home minus away, per match", 460, xtitle="Home minus away per match"),
                    use_container_width=True)
    yel, foul = test_row("M6_yellow_cards"), test_row("M6_fouls")
    caption(f"Premier League and La Liga only{' (the Champions League source has no match statistics)' if comp == 'UCL' else ''}. "
            f"Strength-controlled tests: the home shots-on-target edge shrank behind closed doors, and the away "
            f"side's extra yellow cards disappeared ({yel['estimate']:+.2f} per match, Holm p = "
            f"{fmt_p(yel['p_holm'])}). The foul change does not survive correction (Holm p = {fmt_p(foul['p_holm'])}). "
            "These are differences in referee-related outcomes: teams also played differently without crowds, so "
            "they do not prove referee bias.")


def competitions() -> None:
    st.header("Which competition depends most on home advantage?")
    e = table("stats_interaction_effects")
    fig = go.Figure()
    for status, col, lo, hi in (("normal", "normal_effect", "normal_lo", "normal_hi"),
                                ("behind_closed_doors", "closed_effect", "closed_lo", "closed_hi")):
        dot_ci(fig, e[col], e["competition"].map(COMP_LABELS), e[lo], e[hi], CROWD_COLORS[status], CROWD_LABELS[status],
               hover="%{y}: %{x:+.2f} goals<extra>" + CROWD_LABELS[status] + "</extra>")
    zero_line(fig, "x")
    fig.update_layout(scattermode="group")
    fig.update_yaxes(categoryorder="array", categoryarray=["Champions League", "La Liga", "Premier League"])
    st.plotly_chart(style(fig, "Home goal-difference edge between equal teams", 360,
                          xtitle="Home goals per match above an equally rated opponent"), use_container_width=True)
    m4 = test_row("M4_interaction")
    caption(f"From one regression with a competition × crowd interaction (Elo-controlled, club-clustered errors). "
            f"The drop is significant in the Premier League and La Liga, but the three drops are not significantly "
            f"different (joint test p = {m4['p_value']:.2f}). The Champions League has only "
            f"{int(e.loc[e['competition'] == 'UCL', 'n_closed'].iloc[0])} closed-doors home matches.")
    f = table("eda_f_competition")
    st.dataframe(f[["segment", "matches", "home_win_pct", "draw_pct", "away_win_pct", "goal_diff_pm", "home_excess"]]
                 .rename(columns={"segment": "Competition", "matches": "Matches", "home_win_pct": "Home win %",
                                  "draw_pct": "Draw %", "away_win_pct": "Away win %",
                                  "goal_diff_pm": "Home goal difference per match",
                                  "home_excess": "Strength-adjusted home excess"}).round(3),
                 hide_index=True, use_container_width=True)


def team_explorer() -> None:
    st.header("Team explorer")
    ts = team_seasons()
    clubs = (ts[ts["competition"].isin(["EPL", "LALIGA"])].groupby(["team_id", "team"])["matches"].sum()
             .reset_index().sort_values("team"))
    default = int(np.flatnonzero(clubs["team_id"] == "arsenal")[0]) if (clubs["team_id"] == "arsenal").any() else 0
    c1, c2 = st.columns([2, 3])
    team = c1.selectbox("Club", clubs["team_id"], index=default,
                        format_func=dict(zip(clubs["team_id"], clubs["team"])).get)
    d = ts[ts["team_id"] == team]
    comps = [c for c in ("EPL", "LALIGA", "UCL") if c in set(d["competition"])]
    comp = c2.radio("Competition", comps, horizontal=True, format_func=COMP_LABELS.get)
    d = d[d["competition"] == comp]

    def agg(x: pd.DataFrame) -> pd.Series:
        n = x["matches"].sum()
        return pd.Series({"matches": n, "ppm": x["points"].sum() / n, "win_pct": 100 * x["wins"].sum() / n,
                          "gd_pm": (x["goals_for"].sum() - x["goals_against"].sum()) / n, "excess": x["excess_sum"].sum() / n})

    by = d.groupby("venue").apply(agg, include_groups=False)
    c = st.columns(4)
    if {"home", "away"} <= set(by.index):
        c[0].metric("Home points per match", f"{by.loc['home', 'ppm']:.2f}", help=f"{int(by.loc['home', 'matches'])} matches")
        c[1].metric("Away points per match", f"{by.loc['away', 'ppm']:.2f}", help=f"{int(by.loc['away', 'matches'])} matches")
        c[2].metric("Strength-adjusted gap", f"{by.loc['home', 'excess'] - by.loc['away', 'excess']:+.3f}",
                    help="Home excess minus away excess: results relative to Elo expectation.")
    shrunk = table("stats_clubs_shrunk")
    s = shrunk[(shrunk["team_id"] == team) & (shrunk["competition"] == comp)]
    if len(s):
        r = s.iloc[0]
        c[3].metric("After shrinkage (Phase 5)", f"{r['shrunk_gap']:+.3f}",
                    help=f"95% CI {r['shrunk_lo']:+.3f} to {r['shrunk_hi']:+.3f}. Pulled toward the mean of all clubs "
                         "in proportion to its noise.")

    seasons = d.groupby(["season", "venue"]).apply(agg, include_groups=False).reset_index()
    fig = go.Figure()
    for venue, color in (("home", COMP_COLORS["EPL"]), ("away", RESULT_COLORS["A"])):
        x = seasons[seasons["venue"] == venue]
        fig.add_trace(go.Scatter(x=x["season"], y=x["ppm"], mode="lines+markers", name=venue.title(),
                                 line=dict(color=color, width=2.5), marker=dict(size=8, line=dict(color=SURFACE, width=2)),
                                 customdata=x[["matches", "win_pct"]],
                                 hovertemplate="%{x}<br>%{y:.2f} points per match<br>%{customdata[1]:.0f}% wins, "
                                               "%{customdata[0]:.0f} matches<extra>" + venue.title() + "</extra>"))
    st.plotly_chart(style(fig, "Points per match, home and away, by season", 380, ytitle="Points per match"),
                    use_container_width=True)

    crowd = d.groupby(["crowd_status", "venue"]).apply(agg, include_groups=False).reset_index()
    crowd = crowd.pivot(index="crowd_status", columns="venue", values=["matches", "ppm"])
    crowd.columns = [f"{a}_{b}" for a, b in crowd.columns]
    crowd = crowd.reindex([k for k in CROWD_LABELS if k in crowd.index])
    crowd = crowd[[c for c in ("matches_home", "ppm_home", "matches_away", "ppm_away") if c in crowd.columns]]
    crowd.index = [CROWD_LABELS[k] for k in crowd.index]
    st.dataframe(crowd.rename(columns={"matches_home": "Home matches", "matches_away": "Away matches",
                                       "ppm_home": "Home points per match", "ppm_away": "Away points per match"})
                 .round(2), use_container_width=True)
    caption("Raw points reflect club quality as well as venue. The strength-adjusted gap compares results with what "
            "Elo ratings expected, home and away.")

    if comp in ("EPL", "LALIGA") and len(shrunk):
        st.subheader("Every club with at least 90 home and 90 away league matches")
        x = shrunk.sort_values("shrunk_gap")
        colors = [COMP_COLORS["EPL"] if t == team else AXIS for t in x["team_id"]]
        fig = go.Figure(go.Scatter(
            x=x["shrunk_gap"], y=x["team"], mode="markers",
            marker=dict(size=10, color=colors, line=dict(color=SURFACE, width=2)),
            error_x=dict(type="data", symmetric=False, array=x["shrunk_hi"] - x["shrunk_gap"],
                         arrayminus=x["shrunk_gap"] - x["shrunk_lo"], color=AXIS, thickness=1.5, width=0),
            customdata=x[["adj_gap"]], hovertemplate="%{y}<br>shrunk %{x:+.3f} (raw %{customdata[0]:+.3f})<extra></extra>"))
        mean = test_row("E1_heterogeneity")["estimate"]
        zero_line(fig, "x", mean)
        st.plotly_chart(style(fig, "Strength-adjusted home-away gap after shrinkage", 820,
                              xtitle="Home excess minus away excess (dotted line = average club)"),
                        use_container_width=True)
        caption("No club's interval excludes the average, so ten seasons are not enough to name genuine "
                "'fortress' clubs with confidence.")


def travel_rest() -> None:
    st.header("Do travel and rest matter?")
    tr = table("eda_g_travel")
    fig = go.Figure()
    for scope, color in (("Domestic", COMP_COLORS["EPL"]), ("UCL", COMP_COLORS["UCL"])):
        x = tr[tr["scope"] == scope]
        dot_ci(fig, x["travel_band"], x["home_excess"], x["home_excess_lo"], x["home_excess_hi"], color,
               "Domestic leagues" if scope == "Domestic" else "Champions League", horizontal=False, text=x["matches"],
               hover="%{x} km: %{y:+.3f}<br>%{text:,.0f} matches<extra></extra>")
    zero_line(fig, "y")
    fig.update_layout(scattermode="group")
    st.plotly_chart(style(fig, "Home excess by away-team travel distance", 380, xtitle="Away travel (km)",
                          ytitle="Strength-adjusted home excess"), use_container_width=True)
    trv, dom = test_row("M7_z_log_travel"), test_row("M7b_travel_domestic")
    caption(f"Longer domestic trips go with slightly better home results (+{dom['estimate'] * 0.69:.3f} goals per "
            f"doubling of distance), but the pooled test does not survive the multiple-testing correction "
            f"(OR {trv['estimate']:.2f} per SD, Holm p = {fmt_p(trv['p_holm'])}). There is no effect in the "
            "Champions League.")

    rest = table("eda_g_rest")
    fig = go.Figure()
    dot_ci(fig, rest["rest_band"], rest["home_excess"], rest["home_excess_lo"], rest["home_excess_hi"],
           COMP_COLORS["EPL"], "Home excess", horizontal=False, text=rest["matches"], showlegend=False,
           hover="%{x}: %{y:+.3f}<br>%{text:,.0f} matches<extra></extra>")
    zero_line(fig, "y")
    st.plotly_chart(style(fig, "Home excess by rest difference", 360, xtitle="Which side had more rest",
                          ytitle="Strength-adjusted home excess"), use_container_width=True)
    r_main, r_all = test_row("M7_z_rest"), test_row("M7c_z_rest_all")
    check = table("ml_model_rest_check")
    caption(f"Rest shows no association with home wins once strength is controlled (OR {r_main['estimate']:.2f} per "
            f"SD, Holm p = {fmt_p(r_main['p_holm'])}). The main rest measure misses cup and Europa League games, so "
            f"it was rebuilt with every fixture for 2020/21 to 2024/25: the answer is the same (OR "
            f"{r_all['estimate']:.2f}, p = {fmt_p(r_all['p_value'])}), and complete rest does not improve the "
            f"pre-match model (test ROC-AUC {check['roc_auc'].min():.3f} to {check['roc_auc'].max():.3f} across "
            "with and without rest).")


def clusters() -> None:
    st.header("Do clubs fall into home-advantage types?")
    spec = st.radio("Features", ["main", "gap_only"], horizontal=True,
                    format_func={"main": "All nine features", "gap_only": "Home-away gap features only"}.get)
    teams, scores, profile = (table(f"ml_clusters_{spec}_{k}") for k in ("teams", "scores", "profile"))
    info = choice("ml_clusters_choice")[spec]
    names = CLUSTER_NAMES[spec]
    c1, c2 = st.columns([3, 2])
    fig = go.Figure()
    for k in sorted(teams["cluster"].unique()):
        x = teams[teams["cluster"] == k]
        fig.add_trace(go.Scatter(
            x=x["pc1"], y=x["pc2"], mode="markers", name=f"{names[k]} ({len(x)})",
            marker=dict(size=11, color=CLUSTER_COLORS[k], line=dict(color=SURFACE, width=2)),
            customdata=np.c_[x["team"], x["competition"].map(COMP_LABELS), x["home_points_per_game"],
                             x["home_vs_away_points_difference"], x["mean_elo"]],
            hovertemplate="<b>%{customdata[0]}</b> (%{customdata[1]})<br>home points %{customdata[2]:.2f}<br>"
                          "home-away gap %{customdata[3]:+.2f}<br>mean Elo %{customdata[4]:.0f}<extra></extra>"))
    ev = info["pca_explained_variance"]
    c1.plotly_chart(style(fig, "Clubs on the first two principal components", 460,
                          xtitle=f"PC1 ({ev[0]:.0%} of variance)", ytitle=f"PC2 ({ev[1]:.0%})"),
                    use_container_width=True)
    fig = go.Figure(go.Scatter(x=scores["k"], y=scores["silhouette"], mode="lines+markers", name="Silhouette",
                               line=dict(color=INK_2, width=2), marker=dict(size=8),
                               customdata=scores[["stability_ari"]],
                               hovertemplate="k = %{x}<br>silhouette %{y:.3f}<br>stability (ARI) "
                                             "%{customdata[0]:.2f}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[info["k"]], y=scores.loc[scores["k"] == info["k"], "silhouette"], mode="markers",
                             marker=dict(size=18, color="rgba(0,0,0,0)", line=dict(color=COMP_COLORS["EPL"], width=2)),
                             name="Chosen k", hoverinfo="skip"))
    c2.plotly_chart(style(fig, "Choosing k: silhouette score", 460, xtitle="Number of clusters (k)",
                          ytitle="Silhouette"), use_container_width=True)
    show = profile.assign(Cluster=[names[k] for k in profile["cluster"]])
    st.dataframe(show[["Cluster", "clubs", "home_points_per_game", "home_vs_away_points_difference",
                       "home_advantage_index", "mean_elo"]]
                 .rename(columns={"clubs": "Clubs", "home_points_per_game": "Home points per game",
                                  "home_vs_away_points_difference": "Home-away points gap",
                                  "home_advantage_index": "Home-advantage index", "mean_elo": "Mean Elo"}).round(2),
                 hide_index=True, use_container_width=True)
    caption("K-Means on standardised club features (EPL and La Liga, normal crowds, at least 57 home and 57 away "
            "matches). k was chosen by silhouette and stability across random starts, and clusters were named only "
            "after inspecting their averages. With all nine features the split mostly follows club quality; with "
            "gap features only, the two groups are halves of one continuum. Club differences in home advantage "
            "are not statistically significant, so these are descriptions, not proven club types.")


def models() -> None:
    st.header("Which factors explain a home win?")
    coef = table("ml_model_inference_coefficients")
    labels = {"strength_difference": "Elo difference (+1 SD)", "home_form": "Home form (+1 SD)",
              "away_form": "Away form (+1 SD)", "home_rest_days": "Home rest days (+1 SD)",
              "away_rest_days": "Away rest days (+1 SD)", "log_travel_km": "Away travel, log km (+1 SD)",
              "crowd_status_restricted": "Restricted crowd (vs normal)",
              "crowd_status_behind_closed_doors": "Behind closed doors (vs normal)",
              "competition_LALIGA": "La Liga (vs Premier League)", "competition_UCL": "Champions League (vs Premier League)",
              "neutral_venue": "Neutral venue", "knockout_match": "UCL knockout match"}
    x = coef[coef["term"].isin(labels)].copy()
    x["label"] = x["term"].map(labels)
    x = x.set_index("term").loc[[k for k in labels if k in set(x["term"])]].iloc[::-1]
    sig = x["p_value"] < 0.05
    fig = go.Figure()
    for flag, color, name in ((True, COMP_COLORS["EPL"], "p < 0.05"), (False, AXIS, "not significant")):
        y = x[sig == flag]
        dot_ci(fig, y["odds_ratio"], y["label"], y["or_ci_lo"], y["or_ci_hi"], color, name,
               text=y["p_value"], hover="%{y}<br>OR %{x:.2f}<br>p = %{text:.3f}<extra></extra>")
    zero_line(fig, "x", 1.0)
    log_ticks(fig, (0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3))
    fig.update_yaxes(categoryorder="array", categoryarray=list(x["label"]))
    st.plotly_chart(style(fig, "Odds ratios for a home win (Model A, interpretable fit)", 480,
                          xtitle="Odds ratio, log scale (1 = no association)"), use_container_width=True)
    caption("Unpenalised logistic regression on the training seasons (2016/17 to 2022/23) with standard errors "
            "clustered by home club. Numeric predictors are standardised, so their odds ratios are per standard "
            "deviation. These are associations, not causal effects.")

    st.subheader("How well does it predict? (test seasons 2024/25 and 2025/26, scored once)")
    m = table("ml_model_test_metrics")
    st.dataframe(m[["model", "accuracy", "precision", "recall", "f1", "roc_auc", "log_loss", "brier"]]
                 .rename(columns={"model": "Model", "accuracy": "Accuracy", "precision": "Precision", "recall": "Recall",
                                  "f1": "F1", "roc_auc": "ROC-AUC", "log_loss": "Log loss", "brier": "Brier"}).round(3),
                 hide_index=True, use_container_width=True)
    c1, c2 = st.columns(2)
    cal = table("ml_model_calibration")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", line=dict(color=AXIS, dash="dot"), hoverinfo="skip",
                             showlegend=False))
    fig.add_trace(go.Scatter(x=cal["mean_predicted"], y=cal["observed"], mode="lines+markers", name="Model A",
                             line=dict(color=COMP_COLORS["EPL"], width=2.5), marker=dict(size=8),
                             customdata=cal[["n"]],
                             hovertemplate="predicted %{x:.2f}<br>observed %{y:.2f}<br>%{customdata[0]} matches"
                                           "<extra></extra>"))
    fig.update_xaxes(range=[0, 1])
    fig.update_yaxes(range=[0, 1])
    c1.plotly_chart(style(fig, "Calibration: predicted vs observed home-win rate", 400,
                          xtitle="Predicted probability (decile mean)", ytitle="Observed home-win rate"),
                    use_container_width=True)
    a3 = table("ml_model_a3_calibration")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 0.8], y=[0, 0.8], mode="lines", line=dict(color=AXIS, dash="dot"),
                             hoverinfo="skip", showlegend=False))
    for o, name in (("H", "Home win"), ("D", "Draw"), ("A", "Away win")):
        y = a3[a3["outcome"] == o]
        fig.add_trace(go.Scatter(x=y["mean_predicted"], y=y["observed"], mode="lines+markers", name=name,
                                 line=dict(color=RESULT_COLORS[o], width=2.5),
                                 marker=dict(size=8, line=dict(color=INK_2 if o == "D" else SURFACE, width=1)),
                                 hovertemplate="predicted %{x:.2f}<br>observed %{y:.2f}<extra>" + name + "</extra>"))
    c2.plotly_chart(style(fig, "Three-way model: home, draw, away", 400, xtitle="Predicted probability (quintile mean)",
                          ytitle="Observed share"), use_container_width=True)
    a3m = table("ml_model_a3_test_metrics").set_index("model")
    caption(f"Model A barely beats Elo alone: team strength carries nearly all the pre-match signal. The three-way "
            f"model (accuracy {a3m.iloc[0]['accuracy']:.3f}, ranked probability score {a3m.iloc[0]['rps']:.3f}) gives "
            f"honest probabilities for all three results, but a draw is almost never the single most likely one.")

    st.subheader("What happens on the pitch? (Model B, explanatory only)")
    b = table("ml_model_model_b_coefficients")
    b = b[(b["specification"] == "with match statistics") & (b["term"] != "const")].copy()
    blabels = {"z_strength_difference": "Elo difference", "z_shots_on_target_diff": "Shots on target",
               "z_shots_diff": "Shots", "z_corners_diff": "Corners", "z_fouls_diff": "Fouls",
               "z_yellow_cards_diff": "Yellow cards", "z_red_cards_diff": "Red cards",
               "behind_closed_doors": "Behind closed doors", "restricted": "Restricted crowd", "la_liga": "La Liga"}
    b["label"] = b["term"].map(blabels)
    b = b.dropna(subset=["label"]).sort_values("odds_ratio")
    fig = go.Figure()
    dot_ci(fig, b["odds_ratio"], b["label"], b["or_ci_lo"], b["or_ci_hi"], INK_2, "Odds ratio", showlegend=False,
           text=b["p_value"], hover="%{y}<br>OR %{x:.2f}<br>p = %{text:.3g}<extra></extra>")
    zero_line(fig, "x", 1.0)
    log_ticks(fig, (0.4, 0.5, 0.75, 1, 1.5, 2, 3, 5))
    st.plotly_chart(style(fig, "Home-win odds ratios with in-match statistics (home minus away, per SD)", 420,
                          xtitle="Odds ratio, log scale"), use_container_width=True)
    s = table("ml_model_model_b_summary").iloc[0]
    caption(f"Uses statistics recorded during the match, so it describes mechanisms and is never used for "
            f"prediction. Adding them does not explain away the closed-doors effect (OR "
            f"{np.exp(s['bcd_log_odds_without_stats']):.2f} without, {np.exp(s['bcd_log_odds_with_stats']):.2f} with). "
            "More total shots and corners for a given number on target go with lower odds because teams that are "
            "losing chase the game, not because shooting hurts.")


PAGES = dict(zip(SECTIONS, [overview, over_time, covid, competitions, team_explorer, travel_rest, clusters, models]))

with st.sidebar:
    st.markdown("### Home-Field Advantage Analyzer")
    page = st.radio("Section", SECTIONS, label_visibility="collapsed")
    st.markdown("---")
    st.caption("Premier League, La Liga and Champions League, 2016/17 to 2025/26. Results are associations from "
               "observational data. Source code and full reports are in the repository.")

PAGES[page]()
