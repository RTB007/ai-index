"""TOML config loader."""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def load(path: str | Path | None = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else PROJECT_ROOT / "config.toml"
    with cfg_path.open("rb") as f:
        return tomllib.load(f)


def db_path(cfg: dict[str, Any]) -> Path:
    p = Path(cfg["db"]["path"])
    return p if p.is_absolute() else PROJECT_ROOT / p


def export_path(cfg: dict[str, Any]) -> Path:
    p = Path(cfg["export"]["json_path"])
    return p if p.is_absolute() else PROJECT_ROOT / p
