"""Manifest rules hassfest checks (script/hassfest/manifest.py)."""

from __future__ import annotations

import json
from pathlib import Path
import re

MANIFEST = json.loads(
    (
        Path(__file__).parents[1] / "custom_components" / "octa_ev_charger" / "manifest.json"
    ).read_text(encoding="utf-8")
)


def test_key_order() -> None:
    """domain and name first, everything else alphabetical."""
    keys = list(MANIFEST)
    assert keys[:2] == ["domain", "name"]
    assert keys[2:] == sorted(keys[2:])


def test_custom_integration_fields() -> None:
    for key in ("version", "documentation", "issue_tracker", "codeowners"):
        assert MANIFEST.get(key), key
    assert all(owner.startswith("@") for owner in MANIFEST["codeowners"])


def test_categories() -> None:
    categories = MANIFEST["categories"]
    assert 1 <= len(categories) <= 3
    assert len(set(categories)) == len(categories)
    assert all(re.fullmatch(r"[a-z0-9_]+(\.[a-z0-9_]+)?", c) for c in categories)
    assert categories == ["energy.ev_charging"]
