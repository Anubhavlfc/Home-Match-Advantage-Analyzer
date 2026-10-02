"""Load: write validated tables and data-quality reports to disk."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.config import repo_path
from src.data.clean import season_code
from src.data.validate import CheckResult


def silver_path(competition: str, season: str) -> Path:
    return repo_path("interim") / "matches" / f"{competition}_{season_code(season)}.csv"


def write_silver(df: pd.DataFrame, competition: str, season: str) -> Path:
    path = silver_path(competition, season)
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, date_format="%Y-%m-%d")
    return path


def read_silver(path: Path) -> pd.DataFrame:
    from src.schema import DTYPES

    dtypes = {c: t for c, t in DTYPES.items() if t != "datetime64[ns]"}
    df = pd.read_csv(path, dtype={c: t for c, t in dtypes.items()}, parse_dates=["date"])
    return df


def write_quality_report(
    competition: str, season: str, checks: list[CheckResult], missingness: pd.DataFrame
) -> tuple[Path, Path]:
    out = repo_path("data_quality_reports")
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{competition}_{season_code(season)}"
    checks_path = out / f"{stem}_checks.csv"
    miss_path = out / f"{stem}_missingness.csv"
    pd.DataFrame([c.__dict__ for c in checks]).to_csv(checks_path, index=False)
    missingness.to_csv(miss_path, index=False)
    return checks_path, miss_path
