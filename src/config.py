"""Load project configuration and resolve repository paths."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "config" / "config.yaml"


@lru_cache(maxsize=1)
def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def repo_path(key: str) -> Path:
    """Absolute path for an entry under ``paths`` in config.yaml."""
    return REPO_ROOT / load_config()["paths"][key]


def competition_config(code: str) -> dict[str, Any]:
    comps = load_config()["competitions"]
    if code not in comps:
        raise KeyError(f"Unknown competition code {code!r}; expected one of {sorted(comps)}")
    return comps[code]
