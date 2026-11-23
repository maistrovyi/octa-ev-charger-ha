"""Example YAML in examples/ only references entities the integration creates."""

from __future__ import annotations

import json
from pathlib import Path
import re

from homeassistant.util import slugify
import pytest
import yaml

ROOT = Path(__file__).parents[1]
EN = json.loads(
    (ROOT / "custom_components" / "octa_ev_charger" / "translations" / "en.json").read_text(
        encoding="utf-8"
    )
)
PREFIX = "ev_station_my_station_"  # device "EV Station my-station"


def _known_entities() -> set[str]:
    """Entity IDs from the English entity names, for a two-port station."""
    known = set()
    for platform, entities in EN["entity"].items():
        for entry in entities.values():
            for port in ("1", "2"):
                name = entry["name"].replace("{port}", port)
                known.add(f"{platform}.{PREFIX}{slugify(name)}")
    return known


KNOWN = _known_entities()
EXAMPLES = sorted((ROOT / "examples").glob("*.yaml"))


def test_examples_present() -> None:
    assert {p.name for p in EXAMPLES} >= {"automations.yaml", "dashboard.yaml"}


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_is_valid_yaml(path: Path) -> None:
    assert yaml.safe_load(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", EXAMPLES, ids=lambda p: p.name)
def test_example_entities_exist(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    used = set(re.findall(r"\b[a-z_]+\.ev_station_my_station_[a-z0-9_]+", text))
    # Templates build some IDs, e.g. 'sensor.ev_station_my_station_port_' ~ port ~ '_...'
    used = {e for e in used if not e.endswith("_")}
    assert used, "example references no entities"
    assert used <= KNOWN, sorted(used - KNOWN)


def test_dashboard_has_no_personal_station_id() -> None:
    text = (ROOT / "examples" / "dashboard.yaml").read_text(encoding="utf-8")
    ids = set(re.findall(r"ev_station_([a-z0-9]+)_", text))
    assert ids == {"my"}  # only ev_station_my_station_…
