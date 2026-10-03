"""Crowd and COVID-period features.

``crowd_status`` comes from ``data/reference/crowd_restrictions.csv``: dated
rules per competition, venue country and (where rules differed by region) home
club. Every rule that matches a match is applied in ascending ``priority``,
so a more specific rule overrides a general one. During the pandemic window
the default is ``unknown``: a match only gets a definite status when a rule
covers it.

No per-match attendance source is integrated, so this is a documented
approximation of crowd presence, not a count.
"""
from __future__ import annotations

import pandas as pd

from src.config import repo_path

CROWD_STATUSES = ("normal", "restricted", "behind_closed_doors", "unknown")

# Calendar definition of the COVID disruption, used for the coarse indicator.
# The first top-flight suspensions in England and Spain were 13 and 12 March
# 2020; full crowds were back for the start of 2021/22.
COVID_START = pd.Timestamp("2020-03-12")
COVID_END = pd.Timestamp("2021-07-31")


def load_rules() -> pd.DataFrame:
    rules = pd.read_csv(repo_path("reference") / "crowd_restrictions.csv", dtype=str, keep_default_na=False)
    rules["priority"] = rules["priority"].astype(int)
    rules["date_from"] = pd.to_datetime(rules["date_from"])
    rules["date_to"] = pd.to_datetime(rules["date_to"])
    bad = set(rules["crowd_status"]) - set(CROWD_STATUSES)
    if bad:
        raise ValueError(f"Unknown crowd_status values in rules: {bad}")
    return rules.sort_values("priority", kind="stable").reset_index(drop=True)


def assign_crowd_status(df: pd.DataFrame, rules: pd.DataFrame | None = None) -> pd.DataFrame:
    rules = load_rules() if rules is None else rules
    df = df.copy()
    status = pd.Series(pd.NA, index=df.index, dtype="string")
    confidence = pd.Series(pd.NA, index=df.index, dtype="string")
    rule_note = pd.Series(pd.NA, index=df.index, dtype="string")
    for r in rules.itertuples(index=False):
        m = (df["date"] >= r.date_from) & (df["date"] <= r.date_to)
        if r.competition != "*":
            m &= df["competition"] == r.competition
        if r.host_country != "*":
            m &= df["country"] == r.host_country
        if r.home_team_id != "*":
            m &= df["home_team_id"] == r.home_team_id
        status[m] = r.crowd_status
        confidence[m] = r.confidence
        rule_note[m] = r.note
    if status.isna().any():
        raise ValueError(f"{int(status.isna().sum())} matches outside every crowd rule's date range")
    df["crowd_status"] = status
    df["crowd_status_confidence"] = confidence
    df["crowd_rule"] = rule_note
    return df


def assign_covid_period(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    phase = pd.Series("pre_covid", index=df.index, dtype="string")
    phase[df["date"] >= COVID_START] = "covid"
    phase[df["date"] > COVID_END] = "post_covid"
    df["covid_phase"] = phase
    df["covid_period"] = (phase == "covid").astype("Int64")
    return df
