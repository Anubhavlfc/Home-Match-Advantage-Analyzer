"""Pre-match team features: rest days, recent form and Elo strength.

All features are computed on a long table with one row per team per match,
sorted by date, and use only matches strictly before the current one
(``shift(1)`` before every rolling window; Elo is read before it is updated).
Matches from every competition in the dataset count, including the warm-up
seasons, so a 2016/17 opening-day feature already has history behind it.

Rest days are approximate: domestic cups, the Europa League and other
competitions are not in the dataset, so a club that played one of those in
between appears more rested than it was.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

FORM_WINDOW = 5
REST_CAP_DAYS = 14


def long_format(df: pd.DataFrame) -> pd.DataFrame:
    """One row per team per match, with the team's own perspective."""
    common = ["match_id", "date", "season", "competition", "neutral_venue"]
    home = df[common].assign(
        team_id=df["home_team_id"], is_home=1, gf=df["home_goals"], ga=df["away_goals"], pts=df["home_points"]
    )
    away = df[common].assign(
        team_id=df["away_team_id"], is_home=0, gf=df["away_goals"], ga=df["home_goals"], pts=df["away_points"]
    )
    long = pd.concat([home, away], ignore_index=True)
    long["gf"] = long["gf"].astype(float)
    long["ga"] = long["ga"].astype(float)
    long["pts"] = long["pts"].astype(float)
    long["win"] = (long["pts"] == 3).astype(float)
    long["gd"] = long["gf"] - long["ga"]
    return long.sort_values(["team_id", "date", "match_id"]).reset_index(drop=True)


def add_rest_days(long: pd.DataFrame) -> pd.DataFrame:
    long = long.copy()
    prev_date = long.groupby("team_id")["date"].shift(1)
    prev_season = long.groupby("team_id")["season"].shift(1)
    rest = (long["date"] - prev_date).dt.days.astype(float)
    # First match of a team's season follows the off-season: not comparable.
    rest[prev_season != long["season"]] = np.nan
    long["rest_days"] = rest
    return long


def add_form(long: pd.DataFrame) -> pd.DataFrame:
    """Last-5 form from matches before kick-off (any venue, plus venue-specific)."""
    long = long.copy()
    g = long.groupby("team_id")
    for col, out in (("pts", "last5_points"), ("win", "last5_win_pct"), ("gd", "last5_goal_difference"),
                     ("gf", "last5_goals_scored"), ("ga", "last5_goals_conceded")):
        prior = g[col].shift(1)
        long[out] = prior.groupby(long["team_id"]).rolling(FORM_WINDOW, min_periods=FORM_WINDOW).sum().reset_index(level=0, drop=True)
    long["last5_win_pct"] = long["last5_win_pct"] / FORM_WINDOW
    long["matches_before"] = g.cumcount()

    # Venue-specific form: last 5 genuine home (or away) matches, excluding
    # neutral venues, computed within that subset and shifted the same way.
    for flag, out in ((1, "last5_home_points"), (0, "last5_away_points")):
        sub = long[(long["is_home"] == flag) & (long["neutral_venue"] == 0)]
        prior = sub.groupby("team_id")["pts"].shift(1)
        long[out] = (
            prior.groupby(sub["team_id"]).rolling(FORM_WINDOW, min_periods=FORM_WINDOW).sum().reset_index(level=0, drop=True)
        )
    return long


# ---------------------------------------------------------------------------
# Elo
# ---------------------------------------------------------------------------
ELO_K = 20.0
ELO_INIT = 1500.0


def _goal_multiplier(gd: int) -> float:
    gd = abs(gd)
    return 1.0 if gd <= 1 else 1.5 if gd == 2 else (11.0 + gd) / 8.0


def run_elo(df: pd.DataFrame, home_adv: float) -> pd.DataFrame:
    """Pre-match Elo ratings for every match, in date order.

    ``home_adv`` is added to the home side's rating in the expected score only
    when the venue is not neutral; the stored ratings never include it.
    A club entering a domestic league for the first time (promotion) starts at
    the mean rating of that league's three lowest-rated clubs at that moment;
    any other newcomer starts at 1500.
    """
    d = df.sort_values(["date", "match_id"])
    hid, aid = d["home_team_id"].to_numpy(), d["away_team_id"].to_numpy()
    comps = d["competition"].to_numpy()
    neutral = d["neutral_venue"].to_numpy() == 1
    gd = (d["home_goals"].astype(int) - d["away_goals"].astype(int)).to_numpy()
    ratings: dict[str, float] = {}
    league_members: dict[str, set] = {}
    pre_h = np.empty(len(d))
    pre_a = np.empty(len(d))
    for i in range(len(d)):
        comp = comps[i]
        for team in (hid[i], aid[i]):
            if team not in ratings:
                members = [ratings[t] for t in league_members.get(comp, ())]
                if comp != "UCL" and len(members) >= 10:
                    ratings[team] = float(np.mean(sorted(members)[:3]))
                else:
                    ratings[team] = ELO_INIT
            if comp != "UCL":
                league_members.setdefault(comp, set()).add(team)
        rh, ra = ratings[hid[i]], ratings[aid[i]]
        pre_h[i], pre_a[i] = rh, ra
        h = 0.0 if neutral[i] else home_adv
        exp_h = 1.0 / (1.0 + 10 ** ((ra - (rh + h)) / 400.0))
        score_h = 1.0 if gd[i] > 0 else 0.5 if gd[i] == 0 else 0.0
        delta = ELO_K * _goal_multiplier(int(gd[i])) * (score_h - exp_h)
        ratings[hid[i]] = rh + delta
        ratings[aid[i]] = ra - delta
    return pd.DataFrame({"home_elo": pre_h, "away_elo": pre_a}, index=d.index).loc[df.index]


def fit_home_advantage(df: pd.DataFrame, grid=range(0, 151, 10)) -> float:
    """Choose the Elo home-advantage term that best predicts results (Brier).

    Fitted on the warm-up seasons only, so the analysis seasons never inform
    a parameter used to build their own features.
    """
    best, best_score = None, np.inf
    hw = (df["home_goals"] > df["away_goals"]).astype(float).values
    aw = (df["home_goals"] < df["away_goals"]).astype(float).values
    for h in grid:
        elo = run_elo(df, float(h))
        hh = np.where(df["neutral_venue"] == 1, 0.0, h)
        exp = 1.0 / (1.0 + 10 ** ((elo["away_elo"].values - (elo["home_elo"].values + hh)) / 400.0))
        score = np.mean((exp - (hw + 0.5 * (1 - hw - aw))) ** 2)
        if score < best_score:
            best, best_score = float(h), score
    return best


def attach_team_features(df: pd.DataFrame, long: pd.DataFrame) -> pd.DataFrame:
    """Join per-team pre-match features back onto the match table."""
    feats = ["rest_days", "last5_points", "last5_win_pct", "last5_goal_difference", "last5_goals_scored",
             "last5_goals_conceded", "last5_home_points", "last5_away_points", "matches_before"]
    out = df.copy()
    for side, flag in (("home", 1), ("away", 0)):
        part = long[long["is_home"] == flag].set_index("match_id")[feats]
        part = part.add_prefix(f"{side}_")
        out = out.join(part, on="match_id")
    out = out.rename(columns={"home_last5_points": "home_form", "away_last5_points": "away_form"})
    # Keep only the venue-specific form that applies to each side.
    out = out.drop(columns=["home_last5_away_points", "away_last5_home_points"])
    out["rest_difference"] = out["home_rest_days"] - out["away_rest_days"]
    out["rest_difference_capped"] = out["home_rest_days"].clip(upper=REST_CAP_DAYS) - out["away_rest_days"].clip(
        upper=REST_CAP_DAYS
    )
    return out
