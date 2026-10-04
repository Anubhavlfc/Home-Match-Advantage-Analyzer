"""Fixture dates from competitions outside the analysis dataset.

Rest days need every match a club played, not only EPL, La Liga and UCL
matches. openfootball publishes the FA Cup, EFL Cup, Copa del Rey, Europa
League and Conference League as text files, but only for some seasons. This
module downloads whatever exists, keeps only the dates on which an EPL or
La Liga club played, and records which seasons are fully covered.

Only dates and team names are used here. Scores from these competitions are
never read into the analysis.

Coverage (checked October 2026): every one of those competitions is
available for 2020/21 to 2024/25 (the Conference League started in 2021/22).
Before 2020/21 and in 2025/26 at least one is missing, so rest days built
from them are left missing rather than mixed with incomplete fixture lists.

Still missing in covered seasons: one-off matches (Community Shield,
Supercopa de España, UEFA Super Cup, Club World Cup) and European qualifying
rounds. They affect a handful of matches per affected club.

Run with ``python -m src.data.other_fixtures``.
"""
from __future__ import annotations

import logging
import re
from datetime import date

import pandas as pd

from src.config import load_config, repo_path
from src.data.clean import TeamNameNormalizer, normalize_season, season_code, season_dash, season_start_year
from src.data.extract import ExtractError, _fetch_first_available

log = logging.getLogger(__name__)

URL = "https://raw.githubusercontent.com/openfootball/{repo}/master/{season_dash}/{file}"

# code: (repo, file, first season the competition existed)
COMPETITIONS = {
    "FACUP": ("england", "facup.txt", "2016/17"),
    "EFLCUP": ("england", "eflcup.txt", "2016/17"),
    "COPADELREY": ("espana", "cup.txt", "2016/17"),
    "UEL": ("champions-league", "el.txt", "2016/17"),
    "UECL": ("champions-league", "conf.txt", "2021/22"),
}

_MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}
_DATE_RE = re.compile(r"^\s*(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s+([A-Z][a-z]{2})\s+(\d{1,2})(?:\s+(\d{4}))?\s*$")
_TIME_RE = re.compile(r"^\d{1,2}[:.]\d{2}\s+")
_COUNTRY_RE = re.compile(r"\s*\([A-Z]{3}\)\s*$")
_SCORE_RE = re.compile(r"\d+-\d+")
# "[awarded]" is kept: those matches were played and the result changed later.
_NOT_PLAYED = ("[cancelled]", "[postponed]", "[abandoned]", "[annulled]", "w/o")
_TAG_RE = re.compile(r"\s*\[[a-z ]+\]\s*$")


def expected(season: str) -> list[str]:
    """Competitions that existed in a season (all must be present for coverage)."""
    return [c for c, (_, _, first) in COMPETITIONS.items() if season_start_year(season) >= season_start_year(first)]


def extract(comp: str, season: str, refresh: bool = False):
    repo, file, _ = COMPETITIONS[comp]
    url = URL.format(repo=repo, season_dash=season_dash(season), file=file)
    dest = repo_path("raw") / "openfootball" / "OTHER" / f"{comp}_{season_code(season)}.txt"
    return _fetch_first_available([("openfootball", url)], dest, comp, season, refresh)


def _split_teams(line: str) -> tuple[str, str, str] | None:
    """Return (home, away, rest-of-line) for a fixture line, else None."""
    body = _TIME_RE.sub("", line.strip())
    tag = _TAG_RE.search(body)
    if tag:
        body = body[: tag.start()]
    if " v " in body:
        home, rest = body.split(" v ", 1)
        parts = re.split(r"\s{2,}", rest.strip(), maxsplit=1)
        away, tail = parts[0], parts[1] if len(parts) > 1 else ""
    else:  # Copa del Rey layout: "Home   score   Away"
        parts = re.split(r"\s{2,}", body)
        if len(parts) < 3:
            return None
        home, away, tail = parts[0], parts[-1], " ".join(parts[1:-1])
    tail = f"{tail} {tag.group(0).strip()}" if tag else tail
    return _COUNTRY_RE.sub("", home.strip()), _COUNTRY_RE.sub("", away.strip()), tail


def parse_dates(text: str, season: str) -> pd.DataFrame:
    """One row per fixture line: date, home and away names, played flag."""
    start = season_start_year(season)
    current: date | None = None
    rows = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s[0] in "=#▪" or s.startswith("("):
            continue
        m = _DATE_RE.match(s)
        if m:
            month = _MONTHS[m[1]]
            year = int(m[3]) if m[3] else (start if month >= 7 else start + 1)
            current = date(year, month, int(m[2]))
            continue
        teams = _split_teams(s)
        if teams is None or current is None:
            raise ValueError(f"Unrecognised line in {season}: {line!r}")
        home, away, tail = teams
        played = bool(_SCORE_RE.search(tail)) and not any(t in tail for t in _NOT_PLAYED)
        rows.append({"date": pd.Timestamp(current), "home": home, "away": away, "played": played})
    return pd.DataFrame(rows)


def build(silver: pd.DataFrame, seasons: list[str], refresh: bool = False) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Extra (team_id, date) rows for EPL and La Liga clubs, plus a coverage table.

    A season counts as covered only when every competition that existed that
    season was downloaded. Every league club of a covered season must appear
    in its domestic cup(s); otherwise a name is unmapped and this raises.
    """
    norm = TeamNameNormalizer.from_reference()
    rows, coverage = [], []
    for season in seasons:
        season = normalize_season(season)
        league = silver[(silver["season"] == season) & silver["competition"].isin(["EPL", "LALIGA"])]
        clubs = {c: set(league.loc[league["competition"] == c, "home_team_id"]) for c in ("EPL", "LALIGA")}
        found = {}
        for comp in expected(season):
            try:
                raw = extract(comp, season, refresh)
            except ExtractError:
                found[comp] = None
                continue
            text = (repo_path("raw").parents[1] / raw.path).read_text(encoding="utf-8")
            fx = parse_dates(text, season)
            for side in ("home", "away"):
                keys = fx[side].map(norm._key)
                fx[f"{side}_id"] = keys.map(norm._id)
            found[comp] = fx
        covered = all(v is not None for v in found.values())
        coverage.append({"season": season, "covered": covered,
                         **{c: (found.get(c) is not None) if c in found else pd.NA for c in COMPETITIONS}})
        if not covered:
            continue
        cups = {"EPL": ["FACUP", "EFLCUP"], "LALIGA": ["COPADELREY"]}
        for league_code, comps in cups.items():
            for comp in comps:
                fx = found[comp]
                seen = set(fx["home_id"].dropna()) | set(fx["away_id"].dropna())
                missing = clubs[league_code] - seen
                if missing:
                    raise ValueError(f"{season} {comp}: league clubs not found {sorted(missing)}; "
                                     "add their spellings to team_aliases.csv")
        ours = clubs["EPL"] | clubs["LALIGA"]
        for comp, fx in found.items():
            fx = fx[fx["played"]]
            for side in ("home", "away"):
                hit = fx[fx[f"{side}_id"].isin(ours)]
                rows.append(pd.DataFrame({"team_id": hit[f"{side}_id"], "date": hit["date"], "season": season,
                                          "competition": comp}))
    extra = pd.concat(rows, ignore_index=True) if rows else pd.DataFrame(columns=["team_id", "date", "season", "competition"])
    return extra.drop_duplicates(["team_id", "date"]).reset_index(drop=True), pd.DataFrame(coverage)


def main() -> None:
    from src.data.load import read_silver

    logging.basicConfig(level=logging.INFO)
    cfg = load_config()
    silver = read_silver(repo_path("interim") / "matches_all.csv")
    extra, coverage = build(silver, cfg["project"]["seasons"])
    print(coverage.to_string(index=False))
    print(extra.groupby(["season", "competition"]).size().unstack(fill_value=0))


if __name__ == "__main__":
    main()
