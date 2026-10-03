"""Small aggregate tables for the Streamlit dashboard (Phase 7).

The gold match table is not committed (it is rebuilt by the pipeline), so the
dashboard reads only the committed tables in ``reports/tables`` plus the
aggregates written here to ``dashboard/data``. That lets the dashboard run
straight after a clone.

``team_seasons.csv`` has one row per club, competition, season, venue and
crowd status, with match counts and sums, so the dashboard can aggregate any
way without the match-level file. Neutral-venue matches are excluded: the
side listed first there had no home ground.

Run with ``python -m src.visualization.dashboard_data``.
"""
from __future__ import annotations

import pandas as pd

from src.analysis import eda
from src.config import REPO_ROOT

OUT = REPO_ROOT / "dashboard" / "data"


def team_seasons(g: pd.DataFrame) -> pd.DataFrame:
    d = eda.genuine_home(g)
    common = ["competition", "season", "crowd_status"]
    home = d[common].assign(team_id=d["home_team_id"], team=d["home_team"], venue="home",
                            win=(d["result"] == "H"), draw=(d["result"] == "D"), points=d["home_points"],
                            goals_for=d["home_goals"], goals_against=d["away_goals"], excess=d["home_excess"])
    away = d[common].assign(team_id=d["away_team_id"], team=d["away_team"], venue="away",
                            win=(d["result"] == "A"), draw=(d["result"] == "D"), points=d["away_points"],
                            goals_for=d["away_goals"], goals_against=d["home_goals"], excess=-d["home_excess"])
    long = pd.concat([home, away], ignore_index=True)
    out = (long.groupby(["team_id", "team", "competition", "season", "venue", "crowd_status"], observed=True)
           .agg(matches=("win", "size"), wins=("win", "sum"), draws=("draw", "sum"), points=("points", "sum"),
                goals_for=("goals_for", "sum"), goals_against=("goals_against", "sum"), excess_sum=("excess", "sum"))
           .reset_index())
    for c in ("wins", "draws", "points", "goals_for", "goals_against"):
        out[c] = out[c].astype(int)
    return out.sort_values(["team", "competition", "season", "venue", "crowd_status"]).reset_index(drop=True)


def main() -> None:
    g = eda.load_gold()
    OUT.mkdir(parents=True, exist_ok=True)
    t = team_seasons(g)
    assert t["matches"].sum() == 2 * int((g["neutral_venue"] == 0).sum()), "every genuine-home match counted twice"
    t.to_csv(OUT / "team_seasons.csv", index=False, float_format="%.6g")
    print(f"wrote {OUT / 'team_seasons.csv'} ({len(t):,} rows)")


if __name__ == "__main__":
    main()
