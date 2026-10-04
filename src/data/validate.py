"""Data-quality checks for the silver match table.

Each check returns a ``CheckResult``. ``run_league_checks`` bundles the checks
for a single domestic-league season; ``assert_all_passed`` turns failures into
an exception so a broken season can never flow downstream silently.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.data.clean import season_window


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    # "error" aborts the pipeline; "warning" is reported but the data are kept
    # exactly as published (e.g. plausible-but-unusual source values).
    severity: str = "error"


class ValidationError(AssertionError):
    pass


def check_row_count(df: pd.DataFrame, expected: int) -> CheckResult:
    return CheckResult("row_count", len(df) == expected, f"{len(df)} rows, expected {expected}")


def check_unique_match_id(df: pd.DataFrame) -> CheckResult:
    dupes = df[df["match_id"].duplicated(keep=False)]["match_id"].tolist()
    return CheckResult("unique_match_id", not dupes, f"duplicates: {dupes[:5]}" if dupes else "all unique")


def find_duplicate_fixtures(df: pd.DataFrame) -> pd.DataFrame:
    """Same home/away pairing more than once in a league season."""
    key = ["competition", "season", "home_team", "away_team"]
    return df[df.duplicated(key, keep=False)].sort_values(key)


def check_no_duplicate_fixtures(df: pd.DataFrame) -> CheckResult:
    d = find_duplicate_fixtures(df)
    return CheckResult("no_duplicate_fixtures", d.empty, f"{len(d)} duplicated rows" if len(d) else "none")


def check_double_round_robin(df: pd.DataFrame, n_teams: int) -> CheckResult:
    """Each team plays every other team exactly once at home and once away."""
    teams = sorted(set(df["home_team"]) | set(df["away_team"]))
    home = df["home_team"].value_counts()
    away = df["away_team"].value_counts()
    want = n_teams - 1
    bad = [t for t in teams if home.get(t, 0) != want or away.get(t, 0) != want]
    ok = len(teams) == n_teams and not bad
    return CheckResult(
        "double_round_robin",
        ok,
        f"{len(teams)} teams; each with {want} home/{want} away" if ok else f"{len(teams)} teams; off-count: {bad}",
    )


def check_dates_in_season(df: pd.DataFrame) -> CheckResult:
    bad = []
    for season, grp in df.groupby("season"):
        lo, hi = season_window(season)
        out = grp[(grp["date"].dt.date < lo) | (grp["date"].dt.date > hi)]
        bad += out["match_id"].tolist()
    return CheckResult(
        "dates_in_season_window",
        not bad,
        f"{df['date'].min():%Y-%m-%d} to {df['date'].max():%Y-%m-%d}" if not bad else f"outside window: {bad[:5]}",
    )


def check_result_consistency(df: pd.DataFrame) -> CheckResult:
    hg, ag, r = df["home_goals"], df["away_goals"], df["result"]
    exp = pd.Series("D", index=df.index).mask(hg > ag, "H").mask(hg < ag, "A")
    bad = df.loc[(r != exp).fillna(True), "match_id"].tolist()
    pts_ok = ((df["home_points"] + df["away_points"]).isin([2, 3])).all()
    return CheckResult("result_matches_goals", not bad and bool(pts_ok), f"{len(bad)} inconsistent")


def check_logical_bounds(df: pd.DataFrame) -> CheckResult:
    """Hard constraints: non-negative counts, half-time <= full-time, on-target <= shots."""
    problems: list[str] = []
    count_cols = [c for c in df.columns if str(df[c].dtype) == "Int64" and c.startswith(("home_", "away_"))]
    for c in count_cols:
        if (df[c] < 0).any():
            problems.append(f"{c} negative")
    for side in ("home", "away"):
        pairs = [
            (f"{side}_goals_ht", f"{side}_goals"),
            (f"{side}_shots_on_target", f"{side}_shots"),
        ]
        for small, big in pairs:
            if small in df and big in df:
                n = int((df[small] > df[big]).fillna(False).sum())
                if n:
                    problems.append(f"{small} > {big} in {n} rows")
        if (df[f"{side}_red_cards"] > 5).fillna(False).any():
            problems.append(f"{side}_red_cards > 5")
    return CheckResult("logical_bounds", not problems, "; ".join(problems) or "ok")


def check_goals_vs_shots_on_target(df: pd.DataFrame) -> CheckResult:
    """Soft check: goals above shots on target.

    Legitimate when own goals are scored (they are not the scoring team's
    shots), so this is a warning that lists the matches for manual review.
    """
    m = (df["home_goals"] > df["home_shots_on_target"]).fillna(False) | (
        df["away_goals"] > df["away_shots_on_target"]
    ).fillna(False)
    ids = df.loc[m, "match_id"].tolist()
    return CheckResult(
        "goals_exceed_shots_on_target", not ids, f"{len(ids)} matches: {ids}" if ids else "none", severity="warning"
    )


def check_scores_match_reference(df: pd.DataFrame, ref: pd.DataFrame, ref_name: str) -> CheckResult:
    """Every match in ``df`` has the same score in an independent source."""
    key = ["season", "home_team", "away_team"]
    m = df.merge(ref[key + ["home_goals", "away_goals", "date"]], on=key, how="outer", suffixes=("", "_ref"), indicator=True)
    only_left = int((m["_merge"] == "left_only").sum())
    only_right = int((m["_merge"] == "right_only").sum())
    both = m[m["_merge"] == "both"]
    score_diff = both[(both["home_goals"] != both["home_goals_ref"]) | (both["away_goals"] != both["away_goals_ref"])]
    date_diff = int((both["date"] != both["date_ref"]).sum())
    ok = only_left == 0 and only_right == 0 and score_diff.empty
    detail = (
        f"{len(both)} matched; {only_left} missing from {ref_name}; {only_right} extra in {ref_name}; "
        f"{len(score_diff)} score mismatches; {date_diff} date differences (informational)"
    )
    return CheckResult(f"scores_match_{ref_name}", ok, detail)


def compute_table(df: pd.DataFrame) -> pd.DataFrame:
    home = df.assign(team=df["home_team"], gf=df["home_goals"], ga=df["away_goals"], pts=df["home_points"])
    away = df.assign(team=df["away_team"], gf=df["away_goals"], ga=df["home_goals"], pts=df["away_points"])
    long = pd.concat([home, away])[["season", "team", "gf", "ga", "pts"]]
    long = long.assign(won=(long["pts"] == 3).astype(int), drawn=(long["pts"] == 1).astype(int), lost=(long["pts"] == 0).astype(int))
    t = long.groupby(["season", "team"], as_index=False).agg(
        played=("pts", "size"), won=("won", "sum"), drawn=("drawn", "sum"), lost=("lost", "sum"),
        goals_for=("gf", "sum"), goals_against=("ga", "sum"), points=("pts", "sum"),
    )
    return t.sort_values(["season", "points", "goals_for"], ascending=[True, False, False]).reset_index(drop=True)


def check_table_matches_reference(df: pd.DataFrame, ref_table: pd.DataFrame) -> CheckResult:
    """Standings rebuilt from match rows equal the published final table."""
    cols = ["played", "won", "drawn", "lost", "goals_for", "goals_against", "points"]
    ours = compute_table(df)
    m = ours.merge(ref_table, on=["season", "team"], how="outer", suffixes=("", "_ref"), indicator=True)
    unmatched = m[m["_merge"] != "both"]["team"].tolist()
    diffs = [
        f"{r.team}:{c} {getattr(r, c)}!={getattr(r, c + '_ref')}"
        for r in m[m["_merge"] == "both"].itertuples()
        for c in cols
        if getattr(r, c) != getattr(r, c + "_ref")
    ]
    ok = not unmatched and not diffs
    return CheckResult("table_matches_published", ok, "all teams identical" if ok else f"unmatched {unmatched}; diffs {diffs[:5]}")


def missingness_report(df: pd.DataFrame) -> pd.DataFrame:
    """Share of missing values per column (100% = not provided by any source)."""
    rep = pd.DataFrame({"n_missing": df.isna().sum(), "pct_missing": (df.isna().mean() * 100).round(2)})
    rep["status"] = pd.cut(rep["pct_missing"], [-0.1, 0, 99.99, 100], labels=["complete", "partial", "unavailable"])
    return rep.rename_axis("column").reset_index()


def run_league_checks(
    df: pd.DataFrame,
    n_teams: int,
    reference_scores: dict[str, pd.DataFrame] | None = None,
    reference_table: pd.DataFrame | None = None,
) -> list[CheckResult]:
    results = [
        check_row_count(df, n_teams * (n_teams - 1)),
        check_unique_match_id(df),
        check_no_duplicate_fixtures(df),
        check_double_round_robin(df, n_teams),
        check_dates_in_season(df),
        check_result_consistency(df),
        check_logical_bounds(df),
        check_goals_vs_shots_on_target(df),
    ]
    for name, ref in (reference_scores or {}).items():
        results.append(check_scores_match_reference(df, ref, name))
    if reference_table is not None and not reference_table.empty:
        results.append(check_table_matches_reference(df, reference_table))
    return results


def assert_all_passed(results: list[CheckResult]) -> None:
    failed = [r for r in results if not r.passed and r.severity == "error"]
    if failed:
        raise ValidationError("\n".join(f"{r.name}: {r.detail}" for r in failed))
