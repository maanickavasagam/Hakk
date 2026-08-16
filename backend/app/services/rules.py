"""Loads the per-sector JSON rule files.

Adding a sector means dropping a new JSON file into app/sector_rules/ — nothing
here or in the drafter hardcodes a sector name.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

RULES_DIR = Path(__file__).resolve().parent.parent / "sector_rules"


@lru_cache(maxsize=1)
def load_all() -> dict[str, dict[str, Any]]:
    rules: dict[str, dict[str, Any]] = {}
    for path in sorted(RULES_DIR.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        rules[data["sector"]] = data
    if not rules:
        raise RuntimeError(f"No sector rule files found in {RULES_DIR}")
    return rules


def get(sector: str) -> dict[str, Any] | None:
    return load_all().get(sector)


def sectors() -> list[dict[str, Any]]:
    return [
        {
            "sector": r["sector"],
            "label": r["label"],
            "blurb": r["blurb"],
            "primary_statute": r["primary_statute"],
            "stage_count": len(r["stages"]),
            "bundle_price_paise": r["bundle_price_paise"],
        }
        for r in load_all().values()
    ]
