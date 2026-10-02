"""End-to-end ETL for one domestic-league season.

    python -m src.pipeline --competition EPL --season 2016/17

Steps: extract raw files (bronze) -> clean to the silver schema -> validate
(structure, logic, cross-source scores, published final table) -> write the
silver table and data-quality reports. Any failed check aborts the run before
anything is written to ``data/interim``.
"""
from __future__ import annotations

import argparse
import logging

import pandas as pd

from src.config import REPO_ROOT, competition_config, repo_path
from src.data import extract, load, validate
from src.data.clean import (
    TeamNameNormalizer,
    clean_football_data,
    clean_openfootball_json,
    normalize_competition,
    normalize_season,
    read_football_data_csv,
)

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
    ref_table = tables[(tables["competition"] == competition) & (tables["season"] == season)]

    checks = validate.run_league_checks(silver, comp["n_teams"], reference_scores, ref_table)
    if "openfootball" not in reference_scores:
        checks.append(
            validate.CheckResult("scores_match_openfootball", False, "skipped: source unavailable", severity="warning")
        )
    if ref_table.empty:
        log.warning("No published final table in reference data for %s %s", competition, season)

    missing = validate.missingness_report(silver)
    checks_path, miss_path = load.write_quality_report(competition, season, checks, missing)
    for c in checks:
        status = "PASS" if c.passed else ("WARN" if c.severity == "warning" else "FAIL")
        log.info("[%s] %-28s %s", status, c.name, c.detail)
    validate.assert_all_passed(checks)

    out = load.write_silver(silver, competition, season)
    log.info("Wrote %d matches to %s", len(silver), out.relative_to(REPO_ROOT))
    log.info("Quality reports: %s, %s", checks_path.relative_to(REPO_ROOT), miss_path.relative_to(REPO_ROOT))
    return silver


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--competition", default="EPL")
    parser.add_argument("--season", default="2016/17")
    parser.add_argument("--refresh", action="store_true", help="Re-download raw files (old copies are kept)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    run_domestic_season(args.competition, args.season, refresh=args.refresh)


if __name__ == "__main__":
    main()
