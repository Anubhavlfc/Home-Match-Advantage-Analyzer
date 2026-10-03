"""Clean / standardise (Silver): reusable normalisation helpers.

Every helper fails loudly on input it does not understand (unknown team name,
unparseable date, unknown season label) instead of guessing.
"""
from __future__ import annotations

import io
import json
import re
import unicodedata
from datetime import date
from pathlib import Path

import pandas as pd

from src.config import competition_config, repo_path
from src.schema import DTYPES, SILVER_COLUMNS

# ---------------------------------------------------------------------------
# Seasons
# ---------------------------------------------------------------------------
_SEASON_PATTERNS = (
    re.compile(r"^(?P<y1>\d{4})\s*[/\-_]\s*(?P<y2>\d{2}|\d{4})$"),  # 2016/17, 2016-2017
    re.compile(r"^(?P<y1>\d{2})(?P<y2>\d{2})$"),  # 1617 (football-data code)
)


def normalize_season(value: str | int) -> str:
    """Return the canonical ``YYYY/YY`` label for many common spellings."""
    s = str(value).strip()
    for pat in _SEASON_PATTERNS:
        m = pat.match(s)
        if not m:
            continue
        y1, y2 = m.group("y1"), m.group("y2")
        start = int(y1) if len(y1) == 4 else 2000 + int(y1)
        end2 = int(y2[-2:])
        if (start + 1) % 100 != end2:
            raise ValueError(f"Season {value!r} does not span consecutive years")
        return f"{start}/{end2:02d}"
    raise ValueError(f"Unrecognised season label: {value!r}")


def season_start_year(season: str) -> int:
    return int(normalize_season(season)[:4])


def season_code(season: str) -> str:
    """football-data.co.uk style code, e.g. ``1617``."""
    y = season_start_year(season)
    return f"{y % 100:02d}{(y + 1) % 100:02d}"


def season_dash(season: str) -> str:
    """openfootball style folder, e.g. ``2016-17``."""
    return normalize_season(season).replace("/", "-")


def season_window(season: str) -> tuple[date, date]:
    """Inclusive date bounds a match of this season can fall in.

    1 July to 31 August of the following year: wide enough for the 2019/20
    season, which finished in July (domestic) and August (UCL) 2020.
    """
    y = season_start_year(season)
    return date(y, 7, 1), date(y + 1, 8, 31)


# ---------------------------------------------------------------------------
# Dates
# ---------------------------------------------------------------------------
_DATE_FORMATS = ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d")


def parse_match_dates(values: pd.Series) -> pd.Series:
    """Parse a column of dates using ONE explicit format for the whole column.

    football-data.co.uk uses ``dd/mm/yy`` in older files and ``dd/mm/yyyy``
    in newer ones, and mirrors use ISO. Mixed or unknown formats raise rather than
    letting pandas guess month/day order.
    """
    non_null = values.dropna().astype(str).str.strip()
    for fmt in _DATE_FORMATS:
        parsed = pd.to_datetime(non_null, format=fmt, errors="coerce")
        if parsed.notna().all():
            return pd.to_datetime(values, format=fmt)
    bad = non_null.head(5).tolist()
    raise ValueError(f"Dates do not match a single known format {_DATE_FORMATS}: {bad}")


# ---------------------------------------------------------------------------
# Teams
# ---------------------------------------------------------------------------
def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


class UnmappedTeamError(KeyError):
    pass


class TeamNameNormalizer:
    """Map source-specific spellings to one canonical club name.

    Backed by ``data/reference/team_aliases.csv`` (columns: alias,
    canonical_name, team_id, country, note). Unknown aliases raise, listing
    every missing name so the reference table can be extended in one pass.
    """

    def __init__(self, aliases: pd.DataFrame):
        aliases = aliases.copy()
        aliases["key"] = aliases["alias"].map(self._key)
        dupes = aliases[aliases.duplicated("key", keep=False)]
        conflicting = dupes.groupby("key")["team_id"].nunique()
        if (conflicting > 1).any():
            raise ValueError(f"Alias maps to several teams: {conflicting[conflicting > 1].index.tolist()}")
        aliases = aliases.drop_duplicates("key")
        self._name = dict(zip(aliases["key"], aliases["canonical_name"]))
        self._id = dict(zip(aliases["key"], aliases["team_id"]))
        self._country = dict(zip(aliases["key"], aliases["country"])) if "country" in aliases else {}

    @classmethod
    def from_reference(cls, path: Path | None = None) -> "TeamNameNormalizer":
        path = path or repo_path("reference") / "team_aliases.csv"
        return cls(pd.read_csv(path, dtype=str, keep_default_na=False))

    @staticmethod
    def _key(name: str) -> str:
        return re.sub(r"\s+", " ", str(name)).strip().casefold()

    def _check(self, names: pd.Series) -> None:
        missing = sorted({n for n in names.dropna().unique() if self._key(n) not in self._name})
        if missing:
            raise UnmappedTeamError(f"Add these names to team_aliases.csv: {missing}")

    def canonical(self, names: pd.Series) -> pd.Series:
        self._check(names)
        return names.map(lambda n: self._name[self._key(n)]).astype("string")

    def team_id(self, names: pd.Series) -> pd.Series:
        self._check(names)
        return names.map(lambda n: self._id[self._key(n)]).astype("string")

    def country(self, names: pd.Series) -> pd.Series:
        """Country of the club's home ground (e.g. Wales for Swansea City)."""
        self._check(names)
        return names.map(lambda n: self._country.get(self._key(n)) or pd.NA).astype("string")


# ---------------------------------------------------------------------------
# Competitions
# ---------------------------------------------------------------------------
_COMPETITION_ALIASES = {
    "epl": "EPL", "e0": "EPL", "premier league": "EPL", "english premier league": "EPL",
    "premier-league": "EPL",
    "laliga": "LALIGA", "la liga": "LALIGA", "sp1": "LALIGA", "primera division": "LALIGA",
    "spanish la liga": "LALIGA", "la-liga": "LALIGA",
    "ucl": "UCL", "champions league": "UCL", "uefa champions league": "UCL", "cl": "UCL",
}


def normalize_competition(value: str) -> str:
    key = re.sub(r"\s+", " ", str(value)).strip().casefold()
    if key not in _COMPETITION_ALIASES:
        raise ValueError(f"Unknown competition name: {value!r}")
    return _COMPETITION_ALIASES[key]


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
def derive_result(home_goals: pd.Series, away_goals: pd.Series) -> pd.Series:
    """H / D / A from goals; missing goals give a missing result."""
    out = pd.Series(pd.NA, index=home_goals.index, dtype="string")
    known = home_goals.notna() & away_goals.notna()
    out[known & (home_goals > away_goals)] = "H"
    out[known & (home_goals == away_goals)] = "D"
    out[known & (home_goals < away_goals)] = "A"
    return out


def result_points(result: pd.Series) -> tuple[pd.Series, pd.Series]:
    home = result.map({"H": 3, "D": 1, "A": 0}).astype("Int64")
    away = result.map({"H": 0, "D": 1, "A": 3}).astype("Int64")
    return home, away


def build_match_id(df: pd.DataFrame) -> pd.Series:
    return (
        df["competition"]
        + "_"
        + df["season"].map(season_code)
        + "_"
        + df["date"].dt.strftime("%Y%m%d")
        + "_"
        + df["home_team_id"]
        + "_"
        + df["away_team_id"]
    ).astype("string")


# ---------------------------------------------------------------------------
# Attendance
# ---------------------------------------------------------------------------
def validate_attendance(attendance: pd.Series, capacity: pd.Series, tolerance: float = 1.05) -> pd.Series:
    """Boolean mask of attendance values that are implausible.

    Negative, or above ``tolerance`` x capacity (small overshoots happen when
    published capacity lags stadium changes, so they are not flagged).
    Missing values are not flagged here; missingness is reported separately.
    """
    att = pd.to_numeric(attendance, errors="coerce")
    cap = pd.to_numeric(capacity, errors="coerce")
    return (att < 0) | (cap.notna() & (att > cap * tolerance))


# ---------------------------------------------------------------------------
# Source-specific cleaners
# ---------------------------------------------------------------------------
_FOOTBALL_DATA_COLUMNS = {
    "Time": "kickoff_time",
    "FTHG": "home_goals", "FTAG": "away_goals",
    "HTHG": "home_goals_ht", "HTAG": "away_goals_ht",
    "Referee": "referee",
    "HS": "home_shots", "AS": "away_shots",
    "HST": "home_shots_on_target", "AST": "away_shots_on_target",
    "HF": "home_fouls", "AF": "away_fouls",
    "HC": "home_corners", "AC": "away_corners",
    "HY": "home_yellow_cards", "AY": "away_yellow_cards",
    "HR": "home_red_cards", "AR": "away_red_cards",
    "Attendance": "attendance",
}


def read_football_data_csv(path: Path) -> pd.DataFrame:
    """Read a football-data.co.uk CSV without altering values.

    Files are mostly UTF-8 but some seasons are Latin-1 and carry trailing
    blank rows/columns; those structural artefacts are dropped here.
    """
    raw = Path(path).read_bytes()
    for enc in ("utf-8-sig", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    df = pd.read_csv(io.StringIO(text), dtype=str)
    df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
    return df.dropna(how="all")


def _empty_silver(n: int, index: pd.Index) -> pd.DataFrame:
    return pd.DataFrame(
        {c: pd.Series(pd.NA, index=index, dtype=DTYPES[c] if DTYPES[c] != "datetime64[ns]" else "object") for c in SILVER_COLUMNS}
    )


def clean_football_data(
    raw: pd.DataFrame,
    competition: str,
    season: str,
    teams: TeamNameNormalizer,
    source_id: str,
) -> pd.DataFrame:
    """Standardise one football-data.co.uk league file to the silver schema."""
    competition = normalize_competition(competition)
    season = normalize_season(season)
    comp = competition_config(competition)

    raw = raw.dropna(subset=["HomeTeam", "AwayTeam"]).reset_index(drop=True)
    out = _empty_silver(len(raw), raw.index)

    out["date"] = parse_match_dates(raw["Date"])
    out["season"] = pd.Series(season, index=raw.index, dtype="string")
    out["season_start_year"] = pd.Series(season_start_year(season), index=raw.index, dtype="Int64")
    out["competition"] = competition
    out["competition_type"] = comp["competition_type"]
    out["stage"] = "league"
    out["stage_type"] = "league"
    out["knockout_match"] = 0
    out["two_legged_tie"] = 0
    out["home_team"] = teams.canonical(raw["HomeTeam"])
    out["away_team"] = teams.canonical(raw["AwayTeam"])
    out["home_team_id"] = teams.team_id(raw["HomeTeam"])
    out["away_team_id"] = teams.team_id(raw["AwayTeam"])
    # Domestic league fixtures are played at the home club's ground. Known
    # exceptions (e.g. relocated fixtures) are applied from reference data in
    # Phase 3; none exist in EPL 2016/17.
    out["neutral_venue"] = 0
    out["extra_time"] = 0
    # Venue country = home club's country (Swansea and Cardiff play in Wales).
    out["country"] = teams.country(raw["HomeTeam"])

    for src_col, dst_col in _FOOTBALL_DATA_COLUMNS.items():
        if src_col not in raw.columns:
            continue  # stays <NA>: the source does not publish it
        if DTYPES[dst_col] == "Int64":
            out[dst_col] = pd.to_numeric(raw[src_col], errors="raise").astype("Int64")
        else:
            out[dst_col] = raw[src_col].str.strip().replace("", pd.NA).astype("string")

    out["match_id"] = build_match_id(out.assign(date=pd.to_datetime(out["date"])))
    out = apply_stat_overrides(out)

    out = apply_venue_exceptions(out)

    out["result"] = derive_result(out["home_goals"], out["away_goals"])
    if "FTR" in raw.columns:
        mismatch = raw["FTR"].notna() & (raw["FTR"].str.strip() != out["result"].fillna(""))
        if mismatch.any():
            raise ValueError(f"Source FTR disagrees with goals on rows {raw.index[mismatch].tolist()}")
    out["home_points"], out["away_points"] = result_points(out["result"])
    out["source"] = source_id

    out["date"] = pd.to_datetime(out["date"])
    return out[SILVER_COLUMNS].sort_values(["date", "home_team"]).reset_index(drop=True)


def load_stat_overrides(path: Path | None = None) -> pd.DataFrame:
    path = path or repo_path("reference") / "stat_overrides.csv"
    if not Path(path).exists():
        return pd.DataFrame(columns=["match_id", "column", "action", "reason"])
    return pd.read_csv(path, dtype=str)


def apply_stat_overrides(df: pd.DataFrame, overrides: pd.DataFrame | None = None) -> pd.DataFrame:
    """Blank source values that are logically impossible.

    Only ``set_missing`` is supported: the correct value is unknown, so an
    impossible one is replaced by <NA>, never by an estimate. Each override is
    listed with its reason in ``data/reference/stat_overrides.csv``.
    """
    overrides = load_stat_overrides() if overrides is None else overrides
    df = df.copy()
    for o in overrides.itertuples():
        if o.action != "set_missing":
            raise ValueError(f"Unsupported override action {o.action!r}")
        mask = df["match_id"] == o.match_id
        if mask.any():
            df.loc[mask, o.column] = pd.NA
    return df


def apply_venue_exceptions(df: pd.DataFrame, exceptions: pd.DataFrame | None = None) -> pd.DataFrame:
    """Record matches not played at the listed home team's usual ground.

    Rows in ``data/reference/venue_exceptions.csv`` match on competition,
    season, stage, home and away team, where ``*`` matches anything. Every
    reference row must match at least one match, so a typo cannot silently
    leave a final or relocated tie marked as a normal home game.
    """
    if exceptions is None:
        exceptions = pd.read_csv(repo_path("reference") / "venue_exceptions.csv", dtype=str)
    df = df.copy()
    keys = ["competition", "season", "stage", "home_team", "away_team"]
    exceptions = exceptions[
        exceptions["competition"].isin(df["competition"].unique()) & exceptions["season"].isin(df["season"].unique())
    ]
    unmatched = []
    for ex in exceptions.itertuples(index=False):
        mask = pd.Series(True, index=df.index)
        for k in keys:
            v = getattr(ex, k)
            if v != "*":
                mask &= df[k] == v
        if not mask.any():
            unmatched.append(f"{ex.season} {ex.stage} {ex.home_team} v {ex.away_team}")
            continue
        df.loc[mask, ["stadium", "city", "country"]] = [ex.stadium, ex.city, ex.country]
        df.loc[mask, "neutral_venue"] = int(ex.neutral_venue)
        df.loc[mask, "venue_note"] = ex.reason
    if unmatched:
        raise ValueError(f"venue_exceptions.csv rows matched no match: {unmatched}")
    return df


def fill_kickoff_times(silver: pd.DataFrame, reference: pd.DataFrame) -> pd.DataFrame:
    """Take kick-off times from an independent source where ours is missing.

    Only used after the two sources agree on every fixture and score, and only
    fills gaps; existing values are never overwritten.
    """
    if "kickoff_time" not in reference:
        return silver
    ref = reference.dropna(subset=["kickoff_time"]).drop_duplicates(["season", "home_team", "away_team"])
    m = silver.merge(ref[["season", "home_team", "away_team", "kickoff_time"]], on=["season", "home_team", "away_team"],
                     how="left", suffixes=("", "_ref"))
    out = silver.copy()
    fill = pd.Series(m["kickoff_time_ref"].values, index=out.index, dtype="string")
    out["kickoff_time"] = out["kickoff_time"].fillna(fill)
    return out


def clean_openfootball_json(path: Path, competition: str, season: str, teams: TeamNameNormalizer) -> pd.DataFrame:
    """Minimal standardisation of an openfootball season JSON (scores only)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = []
    for m in data["matches"]:
        score = m.get("score")
        # Usually {"ft": [h, a], "ht": [...]}; some files give a bare [h, a].
        ft = score.get("ft") if isinstance(score, dict) else score
        rows.append(
            {
                "date": m["date"],
                "home_raw": m["team1"],
                "away_raw": m["team2"],
                "home_goals": ft[0] if ft else pd.NA,
                "away_goals": ft[1] if ft else pd.NA,
                "kickoff_time": m.get("time"),
            }
        )
    df = pd.DataFrame(rows)
    df["date"] = parse_match_dates(df["date"])
    df["season"] = normalize_season(season)
    df["competition"] = normalize_competition(competition)
    df["home_team"] = teams.canonical(df["home_raw"])
    df["away_team"] = teams.canonical(df["away_raw"])
    df["home_goals"] = df["home_goals"].astype("Int64")
    df["away_goals"] = df["away_goals"].astype("Int64")
    return df.drop(columns=["home_raw", "away_raw"])
