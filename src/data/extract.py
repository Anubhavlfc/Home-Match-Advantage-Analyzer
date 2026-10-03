"""Extract (Bronze): download source files byte-for-byte into ``data/raw/``.

Rules
-----
* Raw files are written once and never modified. Re-running is a no-op unless
  ``refresh=True``, in which case the old file is kept and a new timestamped
  copy is written alongside it.
* Every download is logged to ``data/raw/_manifest.jsonl`` with URL, SHA-256,
  size and UTC access time so the exact inputs of any run can be traced.
* When a primary source is unreachable a configured mirror may be used, and
  the manifest records which one was actually used. Nothing is ever
  synthesised when every source fails: the extract raises.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import requests

from src.config import competition_config, load_config, repo_path
from src.data.clean import normalize_season, season_code, season_dash

log = logging.getLogger(__name__)


@dataclass
class RawFile:
    source_id: str
    url: str
    path: str  # relative to repo root
    sha256: str
    n_bytes: int
    accessed_at_utc: str
    competition: str
    season: str
    reused_existing: bool = False


class ExtractError(RuntimeError):
    pass


def _http_get(url: str) -> bytes:
    http = load_config()["http"]
    last_err: Exception | None = None
    for attempt in range(1, http["retries"] + 1):
        try:
            resp = requests.get(
                url,
                timeout=http["timeout_seconds"],
                headers={"User-Agent": http["user_agent"]},
            )
            resp.raise_for_status()
            if not resp.content:
                raise ExtractError(f"Empty response from {url}")
            return resp.content
        except (requests.RequestException, ExtractError) as err:
            last_err = err
            log.warning("GET %s failed (attempt %d/%d): %s", url, attempt, http["retries"], err)
            if attempt < http["retries"]:
                time.sleep(http["backoff_seconds"] * 2 ** (attempt - 1))
    raise ExtractError(f"Could not download {url}: {last_err}")


def _append_manifest(entry: RawFile) -> None:
    manifest = repo_path("manifest")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(asdict(entry)) + "\n")


def _save_raw(content: bytes, dest: Path, refresh: bool) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and refresh:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        dest = dest.with_name(f"{dest.stem}.{stamp}{dest.suffix}")
    dest.write_bytes(content)
    return dest


def _fetch_first_available(
    candidates: list[tuple[str, str]],
    dest: Path,
    competition: str,
    season: str,
    refresh: bool,
) -> RawFile:
    """Try ``(source_id, url)`` candidates in order; store the first success."""
    root = repo_path("raw").parents[1]
    if dest.exists() and not refresh:
        content = dest.read_bytes()
        return RawFile(
            source_id=dest.parent.parent.name,
            url="(existing local file)",
            path=str(dest.relative_to(root)),
            sha256=hashlib.sha256(content).hexdigest(),
            n_bytes=len(content),
            accessed_at_utc="",
            competition=competition,
            season=season,
            reused_existing=True,
        )

    errors = []
    for source_id, url in candidates:
        try:
            content = _http_get(url)
        except ExtractError as err:
            errors.append(f"{source_id}: {err}")
            continue
        # Each source gets its own directory so mirrors never masquerade as
        # the primary source.
        source_dest = dest.parents[1].parent / source_id / dest.parent.name / dest.name
        saved = _save_raw(content, source_dest, refresh)
        entry = RawFile(
            source_id=source_id,
            url=url,
            path=str(saved.relative_to(root)),
            sha256=hashlib.sha256(content).hexdigest(),
            n_bytes=len(content),
            accessed_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            competition=competition,
            season=season,
        )
        _append_manifest(entry)
        log.info("Saved %s -> %s (%d bytes)", url, entry.path, entry.n_bytes)
        return entry
    raise ExtractError("All sources failed:\n  " + "\n  ".join(errors))


def find_existing_raw(source_ids: list[str], competition: str, filename: str) -> Path | None:
    raw = repo_path("raw")
    for source_id in source_ids:
        p = raw / source_id / competition / filename
        if p.exists():
            return p
    return None


def extract_domestic_results(competition: str, season: str, refresh: bool = False) -> RawFile:
    """Download a football-data.co.uk season file (falls back to the mirror)."""
    season = normalize_season(season)
    comp = competition_config(competition)
    sources = load_config()["sources"]
    code = season_code(season)
    candidates = [
        (
            "football_data_co_uk",
            sources["football_data_co_uk"]["url_template"].format(
                season_code=code, division=comp["football_data_division"]
            ),
        ),
        (
            "datahub_football_datasets",
            sources["datahub_football_datasets"]["url_template"].format(
                slug=comp["datahub_slug"], season_code=code
            ),
        ),
    ]
    filename = f"{code}.csv"
    existing = None if refresh else find_existing_raw([s for s, _ in candidates], competition, filename)
    dest = existing or repo_path("raw") / candidates[0][0] / competition / filename
    return _fetch_first_available(candidates, dest, competition, season, refresh)


def extract_openfootball_results(competition: str, season: str, refresh: bool = False) -> RawFile:
    """Download the independent openfootball JSON used for cross-validation."""
    season = normalize_season(season)
    comp = competition_config(competition)
    tmpl = load_config()["sources"]["openfootball_json"]["url_template"]
    url = tmpl.format(season_dash=season_dash(season), code=comp["openfootball_json_code"])
    dest = repo_path("raw") / "openfootball" / competition / f"{season_code(season)}.json"
    return _fetch_first_available([("openfootball", url)], dest, competition, season, refresh)


def extract_openfootball_cl(season: str, refresh: bool = False) -> RawFile:
    """Download the openfootball Champions League text file for a season."""
    season = normalize_season(season)
    tmpl = load_config()["sources"]["openfootball_cl_txt"]["url_template"]
    url = tmpl.format(season_dash=season_dash(season))
    dest = repo_path("raw") / "openfootball" / "UCL" / f"{season_code(season)}.txt"
    return _fetch_first_available([("openfootball", url)], dest, "UCL", season, refresh)
