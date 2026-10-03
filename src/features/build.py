"""Build the gold analytical table (Phase 3).

Silver warm-up seasons (2014/15, 2015/16) and analysis seasons are combined so
that Elo, form and rest have history, then only the analysis seasons are
written to ``data/processed/matches_gold.csv``. In-match statistics are carried
through unchanged but are never inputs to any feature here.

Run with ``python -m src.features.build``.
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

from src.config import load_config, repo_path
from src.data import other_fixtures
from src.data.load import read_silver
from src.features import crowd_features, team_history, venues
from src.schema import GOLD_COLUMNS

RELIABLE_MIN_MATCHES = 20


def build_features(silver: pd.DataFrame, warmup_seasons: list[str], extra: pd.DataFrame | None = None,
                   covered_seasons: list[str] | None = None) -> tuple[pd.DataFrame, dict]:
    df = silver.sort_values(["date", "match_id"]).reset_index(drop=True)
    if df["match_id"].duplicated().any():
        raise ValueError("Duplicate match_id in silver input")

    df = venues.add_venue_and_travel(df)
    df = crowd_features.assign_crowd_status(df)
    df = crowd_features.assign_covid_period(df)

    long = team_history.long_format(df)
    long = team_history.add_rest_days(long)
    if extra is None:
        extra = pd.DataFrame({"team_id": pd.Series(dtype="string"), "date": pd.Series(dtype="datetime64[ns]"),
                              "season": pd.Series(dtype="string")})
    long = team_history.add_full_rest(long, extra, covered_seasons or [])
    long = team_history.add_form(long)
    df = team_history.attach_team_features(df, long)
    # Full-coverage rest exists only for EPL and La Liga clubs: other UCL clubs'
    # domestic fixtures are not in any source we use.
    league = df[df["competition"].isin(["EPL", "LALIGA"])]
    members = set(zip(league["season"], league["home_team_id"]))
    for side in ("home", "away"):
        ok = pd.Series([(s, t) in members for s, t in zip(df["season"], df[f"{side}_team_id"])], index=df.index)
        df.loc[~ok, f"{side}_rest_days_all"] = np.nan
    df["rest_difference_all_capped"] = df["home_rest_days_all"].clip(upper=team_history.REST_CAP_DAYS) - df[
        "away_rest_days_all"].clip(upper=team_history.REST_CAP_DAYS)
    df["form_difference"] = df["home_form"] - df["away_form"]

    # Elo home-advantage term chosen on warm-up seasons only.
    warm = df[df["season"].isin(warmup_seasons)]
    home_adv = team_history.fit_home_advantage(warm)
    elo = team_history.run_elo(df, home_adv)
    df["home_strength"] = elo["home_elo"].round(1)
    df["away_strength"] = elo["away_elo"].round(1)
    df["strength_difference"] = (df["home_strength"] - df["away_strength"]).round(1)
    df["strength_reliable"] = (
        (df["home_matches_before"] >= RELIABLE_MIN_MATCHES) & (df["away_matches_before"] >= RELIABLE_MIN_MATCHES)
    ).astype("Int64")
    return df, {"elo_home_advantage": home_adv, "elo_k": team_history.ELO_K}


def validate_gold(gold: pd.DataFrame, n_expected: int, full: pd.DataFrame, n_samples: int = 300) -> list[str]:
    """Hard checks: row count, uniqueness, and a brute-force leakage check."""
    errors = []
    if len(gold) != n_expected:
        errors.append(f"row count {len(gold)} != silver {n_expected}")
    if gold["match_id"].duplicated().any():
        errors.append("duplicate match_id")
    if gold["travel_distance_km"].isna().any():
        errors.append("missing travel distance")
    if (gold.loc[gold["neutral_venue"] == 0, "home_travel_distance_km"] > 100).sum() > 0:
        n = int((gold.loc[gold["neutral_venue"] == 0, "home_travel_distance_km"] > 100).sum())
        # Allowed only for relocated home games recorded in venue_exceptions.
        if gold.loc[(gold["neutral_venue"] == 0) & (gold["home_travel_distance_km"] > 100), "venue_note"].isna().any():
            errors.append(f"{n} non-neutral home games far from the home ground without a venue note")

    # Recompute form and rest for a random sample directly from the raw rows
    # dated strictly before the match, and compare.
    rng = np.random.default_rng(0)
    sample = gold.iloc[rng.choice(len(gold), size=min(n_samples, len(gold)), replace=False)]
    for r in sample.itertuples(index=False):
        for side in ("home", "away"):
            team = getattr(r, f"{side}_team_id")
            prior = full[((full["home_team_id"] == team) | (full["away_team_id"] == team)) & (full["date"] < r.date)]
            prior = prior.sort_values(["date", "match_id"])
            pts = np.where(prior["home_team_id"] == team, prior["home_points"], prior["away_points"])
            expected_form = float(pts[-5:].sum()) if len(pts) >= 5 else np.nan
            got = getattr(r, f"{side}_form")
            if not (np.isnan(expected_form) and pd.isna(got)) and expected_form != got:
                errors.append(f"form mismatch {r.match_id} {side}: {got} vs {expected_form}")
            if len(prior) and prior["season"].iloc[-1] == r.season:
                expected_rest = (r.date - prior["date"].iloc[-1]).days
            else:
                expected_rest = np.nan
            got = getattr(r, f"{side}_rest_days")
            if not (np.isnan(expected_rest) and pd.isna(got)) and expected_rest != got:
                errors.append(f"rest mismatch {r.match_id} {side}: {got} vs {expected_rest}")
    # Adding fixtures can only shorten rest, never lengthen it.
    for side in ("home", "away"):
        both = gold[[f"{side}_rest_days", f"{side}_rest_days_all"]].dropna()
        if (both[f"{side}_rest_days_all"] > both[f"{side}_rest_days"]).any():
            errors.append(f"{side}_rest_days_all exceeds {side}_rest_days")
    return errors


def main() -> None:
    cfg = load_config()
    interim = repo_path("interim")
    analysis = read_silver(interim / "matches_all.csv")
    warm = read_silver(interim / "matches_warmup.csv")
    full = pd.concat([warm, analysis], ignore_index=True)

    extra, coverage = other_fixtures.build(analysis, cfg["project"]["seasons"])
    covered = coverage.loc[coverage["covered"], "season"].tolist()
    df, params = build_features(full, cfg["project"]["warmup_seasons"], extra, covered)
    params["rest_all_covered_seasons"] = covered
    params["extra_fixture_dates"] = int(len(extra))
    gold = df[df["season"].isin(cfg["project"]["seasons"])].sort_values(["date", "match_id"]).reset_index(drop=True)
    gold = gold[GOLD_COLUMNS]

    errors = validate_gold(gold, len(analysis), full)
    if errors:
        raise SystemExit("Gold validation failed:\n" + "\n".join(errors[:20]))

    out = repo_path("processed")
    out.mkdir(parents=True, exist_ok=True)
    gold.to_csv(out / "matches_gold.csv", index=False, date_format="%Y-%m-%d")
    summary = {
        "rows": len(gold),
        "params": params,
        "crowd_status": gold["crowd_status"].value_counts().to_dict(),
        "missing_share": gold[[c for c in GOLD_COLUMNS[GOLD_COLUMNS.index("crowd_status"):]]].isna().mean().round(4).to_dict(),
    }
    (out / "matches_gold_summary.json").write_text(json.dumps(summary, indent=2, default=str) + "\n")
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
