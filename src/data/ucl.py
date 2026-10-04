"""Champions League: parse openfootball ``cl.txt`` files into the silver schema.

Format handled (main tournament only; qualifying rounds are not in the files)::

    ▪ Group A                      (also "Gruppe G", "Group, Matchday 3",
    ▪ League, Matchday 1            "Playoffs, Matchday 2", "Finals, Round of 16")
      Tue Sep 13 2016              (year optional after the first date)
        20:45  Team A (ESP)  v  Team B (GER)   2-1 (1-0)
               Team C (ENG)  v  Team D (ITA)   3-2 a.e.t. (2-1, 0-1)
               Team E (FRA)  v  Team F (POR)   4-2 pen. 1-1 a.e.t. (1-1, 0-0)

Score semantics: ``home_goals``/``away_goals`` are always the 90-minute
score so that knockout matches are comparable with league matches. Extra
time and shoot-outs go to separate columns. Any line the parser does not
understand raises instead of being skipped.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd

from src.data.clean import (
    TeamNameNormalizer,
    apply_venue_exceptions,
    build_match_id,
    derive_result,
    normalize_season,
    result_points,
    season_start_year,
)
from src.schema import DTYPES, SILVER_COLUMNS

_MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
_DATE_RE = re.compile(r"^\s*(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Z][a-z]{2})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$")
_MATCH_RE = re.compile(
    r"^\s*(?:(?P<time>\d{1,2}[:.]\d{2})\s+)?(?P<home>.+?)\s+\((?P<hc>[A-Z]{3})\)\s+v\s+"
    r"(?P<away>.+?)\s+\((?P<ac>[A-Z]{3})\)\s+(?P<score>.+?)\s*$"
)
_SCORE_RE = re.compile(
    r"^(?:(?P<pen>\d+-\d+)\s+pen\.\s+)?(?P<main>\d+-\d+)(?P<aet>\s+a\.e\.t\.)?(?:\s+\((?P<inner>[^)]*)\))?$"
)

_STAGES = {
    "round of 16": ("round_of_16", "knockout"),
    "quarterfinals": ("quarter_final", "knockout"),
    "quarter-finals": ("quarter_final", "knockout"),
    "semifinals": ("semi_final", "knockout"),
    "semi-finals": ("semi_final", "knockout"),
    "final": ("final", "knockout"),
}


def _pair(s: str) -> tuple[int, int]:
    h, a = s.strip().split("-")
    return int(h), int(a)


def parse_score(text: str) -> dict:
    """Split an openfootball score string into 90-min, extra-time and pens."""
    m = _SCORE_RE.match(text.strip())
    if not m:
        raise ValueError(f"Unrecognised score {text!r}")
    inner = [p.strip() for p in (m["inner"] or "").split(",") if p.strip()]
    out = {"ht": None, "ft90": None, "aet": None, "pens": _pair(m["pen"]) if m["pen"] else None}
    if m["aet"]:
        out["aet"] = _pair(m["main"])
        if not inner:
            raise ValueError(f"Extra-time score without 90-minute score: {text!r}")
        out["ft90"] = _pair(inner[0])
        out["ht"] = _pair(inner[1]) if len(inner) > 1 else None
    else:
        if m["pen"]:
            raise ValueError(f"Shoot-out without extra time: {text!r}")
        out["ft90"] = _pair(m["main"])
        out["ht"] = _pair(inner[0]) if inner else None
    return out


def _stage_from_header(header: str, start_year: int) -> tuple[str, str]:
    h = header.strip().lower()
    h = h.split(",", 1)[1].strip() if h.startswith("finals,") else h
    if h.startswith(("group", "gruppe")):
        letter = re.search(r"(?:group|gruppe)\s+([a-h])$", h)
        return (f"group_{letter.group(1)}" if letter else "group"), "group"
    if h.startswith("league"):
        return "league_phase", "league_phase"
    if h.startswith("playoffs"):
        return "knockout_playoff", "knockout_playoff"
    if h in _STAGES:
        return _STAGES[h]
    raise ValueError(f"Unknown stage header {header!r}")


def _match_year(month: int, start_year: int) -> int:
    # The main tournament starts in September at the earliest; anything in
    # January-August belongs to the second calendar year (incl. Aug 2020).
    return start_year if month >= 9 else start_year + 1


def parse_cl_text(text: str, season: str) -> pd.DataFrame:
    season = normalize_season(season)
    start = season_start_year(season)
    rows, unparsed = [], []
    stage = stage_type = None
    current_date: date | None = None
    current_time = None
    for lineno, line in enumerate(text.splitlines(), 1):
        if not line.strip() or line.lstrip().startswith(("#", "=")):
            continue
        if line.lstrip().startswith("▪"):
            stage, stage_type = _stage_from_header(line.lstrip()[1:], start)
            current_date, current_time = None, None
            continue
        dm = _DATE_RE.match(line)
        if dm:
            month = _MONTHS[dm.group(2)]
            year = _match_year(month, start)
            if dm.group(4) and int(dm.group(4)) != year:
                raise ValueError(f"line {lineno}: explicit year {dm.group(4)} contradicts season {season}")
            current_date = date(year, month, int(dm.group(3)))
            current_time = None
            continue
        mm = _MATCH_RE.match(line)
        if mm:
            if current_date is None or stage is None:
                raise ValueError(f"line {lineno}: match before any date/stage header")
            if mm["time"]:
                current_time = mm["time"].replace(".", ":")
            sc = parse_score(mm["score"])
            rows.append(
                {
                    "date": pd.Timestamp(current_date),
                    "kickoff_time": current_time,
                    "stage": stage,
                    "stage_type": stage_type,
                    "home_raw": mm["home"].strip(),
                    "away_raw": mm["away"].strip(),
                    "home_goals": sc["ft90"][0],
                    "away_goals": sc["ft90"][1],
                    "home_goals_ht": sc["ht"][0] if sc["ht"] else pd.NA,
                    "away_goals_ht": sc["ht"][1] if sc["ht"] else pd.NA,
                    "home_goals_aet": sc["aet"][0] if sc["aet"] else pd.NA,
                    "away_goals_aet": sc["aet"][1] if sc["aet"] else pd.NA,
                    "home_shootout": sc["pens"][0] if sc["pens"] else pd.NA,
                    "away_shootout": sc["pens"][1] if sc["pens"] else pd.NA,
                }
            )
            continue
        unparsed.append(f"{lineno}: {line.strip()}")
    if unparsed:
        raise ValueError("Unparsed lines in cl.txt:\n  " + "\n  ".join(unparsed[:10]))
    return pd.DataFrame(rows)


def assign_legs(df: pd.DataFrame) -> pd.DataFrame:
    """Mark two-legged ties and number the legs by date.

    Two-legged: knockout play-offs, round of 16, quarter- and semi-finals.
    Single matches: the final, and the 2019/20 quarter-finals onward (Lisbon).
    """
    df = df.copy()
    single = (df["stage"] == "final") | (
        (df["season"] == "2019/20") & df["stage"].isin(["quarter_final", "semi_final"])
    )
    ko = df["stage_type"].isin(["knockout", "knockout_playoff"])
    df["knockout_match"] = ko.astype(int)
    df["two_legged_tie"] = (ko & ~single).astype(int)
    df["leg"] = pd.Series(pd.NA, index=df.index, dtype="Int64")
    tie = df["home_team_id"].where(df["home_team_id"] < df["away_team_id"], df["away_team_id"]) + "|" + df[
        "away_team_id"
    ].where(df["home_team_id"] < df["away_team_id"], df["home_team_id"])
    df["tie_id"] = pd.Series(pd.NA, index=df.index, dtype="string")
    two = df["two_legged_tie"] == 1
    df.loc[two, "tie_id"] = df.loc[two, "stage"] + ":" + tie[two]
    for _, idx in df[two].sort_values("date").groupby("tie_id").groups.items():
        for leg, i in enumerate(df.loc[idx].sort_values("date").index, 1):
            df.loc[i, "leg"] = leg
    return df


def clean_openfootball_cl(path: Path, season: str, teams: TeamNameNormalizer) -> pd.DataFrame:
    season = normalize_season(season)
    parsed = parse_cl_text(Path(path).read_text(encoding="utf-8"), season)
    out = pd.DataFrame(index=parsed.index)
    for c in SILVER_COLUMNS:
        out[c] = pd.Series(pd.NA, index=parsed.index, dtype=DTYPES[c] if DTYPES[c] != "datetime64[ns]" else "object")
    out["date"] = parsed["date"]
    out["kickoff_time"] = parsed["kickoff_time"].astype("string")
    out["season"] = season
    out["season_start_year"] = season_start_year(season)
    out["competition"] = "UCL"
    out["competition_type"] = "continental_cup"
    out["stage"] = parsed["stage"].astype("string")
    out["stage_type"] = parsed["stage_type"].astype("string")
    out["ucl_format"] = "league_phase" if season_start_year(season) >= 2024 else "group_stage"
    out["home_team"] = teams.canonical(parsed["home_raw"])
    out["away_team"] = teams.canonical(parsed["away_raw"])
    out["home_team_id"] = teams.team_id(parsed["home_raw"])
    out["away_team_id"] = teams.team_id(parsed["away_raw"])
    for c in ("home_goals", "away_goals", "home_goals_ht", "away_goals_ht",
              "home_goals_aet", "away_goals_aet", "home_shootout", "away_shootout"):
        out[c] = pd.to_numeric(parsed[c]).astype("Int64")
    # The source omits the half-time score for 0-0 draws; it can only be 0-0.
    goalless = (out["home_goals"] == 0) & (out["away_goals"] == 0)
    out.loc[goalless, ["home_goals_ht", "away_goals_ht"]] = 0
    out["country"] = teams.country(parsed["home_raw"])
    out["extra_time"] = out["home_goals_aet"].notna().astype("Int64")
    out["result"] = derive_result(out["home_goals"], out["away_goals"])
    out["home_points"], out["away_points"] = result_points(out["result"])
    out["source"] = "openfootball"
    out["date"] = pd.to_datetime(out["date"])
    out["match_id"] = build_match_id(out)
    out = assign_legs(out)
    # Default: the listed home team played at its own ground. Finals,
    # relocated and displaced matches are overridden from reference data.
    out["neutral_venue"] = 0
    out = apply_venue_exceptions(out)
    return out[SILVER_COLUMNS].sort_values(["date", "home_team"]).reset_index(drop=True)
