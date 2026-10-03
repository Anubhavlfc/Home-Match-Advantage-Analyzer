"""End-to-end ETL (bronze -> silver).

    python -m src.pipeline --competition EPL --season 2016/17   # one season
    python -m src.pipeline --all                                # everything

Steps per competition-season: extract raw files -> clean to the silver
schema -> validate -> write the silver table and data-quality reports. Any
failed hard check aborts before anything is written to ``data/interim``.
``--all`` then stacks every season into ``data/interim/matches_all.csv`` and
re-validates the combined table.
"""
from __future__ import annotations

import argparse
import logging

import pandas as pd

from src.config import REPO_ROOT, competition_config, load_config, repo_path
from src.data import clean as clean_mod
from src.data import extract, load, validate
from src.data.ucl import clean_openfootball_cl
from src.data.clean import (
    TeamNameNormalizer,
    clean_football_data,
    clean_openfootball_json,
    normalize_competition,
    normalize_season,
    read_football_data_csv,
)
from src.schema import SILVER_COLUMNS

log = logging.getLogger("pipeline")


def run_domestic_season(competition: str, season: str, refresh: bool = False) -> pd.DataFrame:
    competition = normalize_competition(competition)
    season = normalize_season(season)
    comp = competition_config(competition)
    teams = TeamNameNormalizer.from_reference()

    primary = extract.extract_domestic_results(competition, season, refresh=refresh)
    log.info("Primary raw file: %s (source=%s, sha256=%s)", primary.path, primary.source_id, primary.sha256[:12])
    silver = clean_football_data(
        read_football_data_csv(REPO_ROOT / primary.path), competition, season, teams, primary.source_id
    )

    reference_scores: dict[str, pd.DataFrame] = {}
    try:
        of = extract.extract_openfootball_results(competition, season, refresh=refresh)
        reference_scores["openfootball"] = clean_openfootball_json(REPO_ROOT / of.path, competition, season, teams)
    except extract.ExtractError as err:
        # The cross-check is reported as skipped, not silently treated as passed.
        log.warning("Cross-source check skipped: %s", err)

    tables = pd.read_csv(repo_path("reference") / "final_tables.csv")
    ref_table = tables[(tables["competition"] == competition) & (tables["season"] == season)].copy()
    ref_table["team"] = teams.canonical(ref_table["team"])

    checks = validate.run_league_checks(silver, comp["n_teams"], reference_scores, ref_table)
    if "openfootball" in reference_scores and next(
        (c.passed for c in checks if c.name == "scores_match_openfootball"), False
    ):
        silver = clean_mod.fill_kickoff_times(silver, reference_scores["openfootball"])
    if "openfootball" not in reference_scores:
        checks.append(
            validate.CheckResult("scores_match_openfootball", False, "skipped: source unavailable", severity="warning")
        )
    if ref_table.empty:
        log.warning("No published final table in reference data for %s %s", competition, season)

    _report(competition, season, silver, checks)

    out = load.write_silver(silver, competition, season)
    log.info("Wrote %d matches to %s", len(silver), out.relative_to(REPO_ROOT))
    return silver


def _report(competition: str, season: str, silver: pd.DataFrame, checks: list) -> None:
    missing = validate.missingness_report(silver)
    load.write_quality_report(competition, season, checks, missing)
    for c in checks:
        status = "PASS" if c.passed else ("WARN" if c.severity == "warning" else "FAIL")
        log.info("[%s] %-30s %s", status, c.name, c.detail)
    validate.assert_all_passed(checks)


def run_ucl_season(season: str, refresh: bool = False) -> pd.DataFrame:
    season = normalize_season(season)
    teams = TeamNameNormalizer.from_reference()
    raw = extract.extract_openfootball_cl(season, refresh=refresh)
    silver = clean_openfootball_cl(REPO_ROOT / raw.path, season, teams)
    finals = pd.read_csv(repo_path("reference") / "ucl_finals.csv")
    finals["winner"] = teams.canonical(finals["winner"])
    _report("UCL", season, silver, validate.run_ucl_checks(silver, finals))
    out = load.write_silver(silver, "UCL", season)
    log.info("Wrote %d matches to %s", len(silver), out.relative_to(REPO_ROOT))
    return silver


def run_all(refresh: bool = False) -> pd.DataFrame:
    seasons = load_config()["project"]["seasons"]
    frames = []
    for comp in ("EPL", "LALIGA"):
        for season in seasons:
            frames.append(run_domestic_season(comp, season, refresh=refresh))
    for season in seasons:
        frames.append(run_ucl_season(season, refresh=refresh))
    combined = pd.concat(frames, ignore_index=True)
    checks = [
        validate.check_row_count(combined, sum(len(f) for f in frames)),
        validate.check_unique_match_id(combined),
        validate.CheckResult(
            "schema_columns", list(combined.columns) == SILVER_COLUMNS, f"{len(combined.columns)} columns"
        ),
    ]
    _report("ALL", "2016/17", combined, checks)
    path = load.write_combined(combined)
    log.info("Combined table: %d matches -> %s", len(combined), path.relative_to(REPO_ROOT))

    # Warm-up seasons feed Elo and rolling form only (see config.yaml).
    warm = []
    for season in load_config()["project"].get("warmup_seasons", []):
        for comp in ("EPL", "LALIGA"):
            warm.append(run_domestic_season(comp, season, refresh=refresh))
        warm.append(run_ucl_season(season, refresh=refresh))
    if warm:
        wpath = load.write_combined(pd.concat(warm, ignore_index=True), name="matches_warmup.csv")
        log.info("Warm-up table: %d matches -> %s", sum(len(w) for w in warm), wpath.relative_to(REPO_ROOT))
    return combined


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--competition", default="EPL")
    parser.add_argument("--season", default="2016/17")
    parser.add_argument("--all", action="store_true", help="Run every competition and season, then combine")
    parser.add_argument("--refresh", action="store_true", help="Re-download raw files (old copies are kept)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    if args.all:
        run_all(refresh=args.refresh)
    elif normalize_competition(args.competition) == "UCL":
        run_ucl_season(args.season, refresh=args.refresh)
    else:
        run_domestic_season(args.competition, args.season, refresh=args.refresh)


if __name__ == "__main__":
    main()
