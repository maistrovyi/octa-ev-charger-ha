"""English and Ukrainian translations."""

from __future__ import annotations

import json
from pathlib import Path
import re
import string
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from .conftest import STATUS_URL, eid

COMPONENT = Path(__file__).parents[1] / "custom_components" / "octa_ev_charger"
LANGUAGES = sorted(p.stem for p in (COMPONENT / "translations").glob("*.json"))


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _flatten(data: dict[str, Any], prefix: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            out |= _flatten(value, f"{prefix}{key}.")
        else:
            out[f"{prefix}{key}"] = value
    return out


def _placeholders(text: str) -> list[str]:
    return sorted(re.findall(r"\{(\w+)\}", text))


def test_languages_present() -> None:
    assert LANGUAGES == ["en", "uk"]


def test_en_matches_strings() -> None:
    assert _load(COMPONENT / "translations" / "en.json") == _load(COMPONENT / "strings.json")


@pytest.mark.parametrize("lang", [lang for lang in LANGUAGES if lang != "en"])
def test_same_keys_and_placeholders(lang: str) -> None:
    en = _flatten(_load(COMPONENT / "translations" / "en.json"))
    other = _flatten(_load(COMPONENT / "translations" / f"{lang}.json"))
    assert other.keys() == en.keys()
    for key, text in en.items():
        assert _placeholders(other[key]) == _placeholders(text), key


# Same rules hassfest (script/hassfest/translations.py) applies, so CI failures show up locally.
RE_URL = re.compile(
    r"(((ftp|ftps|scp|http|https|mqtt|mqtts|socket|socks5):\/\/|www\.)"
    r"[a-z0-9]+([\-\.]{1}[a-z0-9]+)*\.[a-z]{2,5}(:[0-9]{1,5})?(\/.*)?)",
    re.IGNORECASE,
)
RE_HTML = re.compile(r"<[a-z].*?>", re.IGNORECASE)
RE_KEY = re.compile(r"^(?!.+[_-]{2})(?![_-])[a-z0-9-_]+(?<![_-])$")


def _hassfest_errors(value: str) -> list[str]:
    errors = []
    if RE_URL.search(value):
        errors.append("contains a URL (use a description placeholder)")
    if RE_HTML.search(value):
        errors.append("contains HTML")
    if value != value.strip():
        errors.append("has leading/trailing spaces")
    if re.search(r"'\{\w+\}'", value):
        errors.append("placeholder inside single quotes")
    if re.search(r"(.+\[%)|(%\].+)", value):
        errors.append("combined translation reference")
    for _, field, _, _ in string.Formatter().parse(value):
        if field and not field.isidentifier():
            errors.append(f"invalid placeholder {{{field}}}")
    return errors


@pytest.mark.parametrize("lang", LANGUAGES)
def test_hassfest_rules(lang: str) -> None:
    data = _load(COMPONENT / "translations" / f"{lang}.json")
    problems = {k: e for k, v in _flatten(data).items() if (e := _hassfest_errors(v))}
    assert not problems

    for platform, entities in data["entity"].items():
        for key in entities:
            assert RE_KEY.match(key), f"entity.{platform}.{key}: invalid translation key"
    for section in ("config", "options"):
        for step_id, step in data[section]["step"].items():
            extra = set(step.get("data_description", {})) - set(step.get("data", {}))
            assert not extra, f"{section}.step.{step_id}: data_description without data: {extra}"


async def test_ukrainian_names_keep_english_entity_ids(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    entity_registry: er.EntityRegistry,
    mock_entry: MockConfigEntry,
    status: dict[str, Any],
) -> None:
    """Names follow the HA language; entity IDs stay English so automations keep working."""
    hass.config.language = "uk"
    aioclient_mock.get(STATUS_URL, json=status)
    mock_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_entry.entry_id)
    await hass.async_block_till_done()

    expected = {
        eid("sensor", "port_1_power"): "EV Station station-1 Порт 1 потужність",
        eid("sensor", "total_power"): "EV Station station-1 Загальна потужність",
        eid("switch", "port_2_charging"): "EV Station station-1 Порт 2 зарядка",
        eid("number", "port_1_current_limit"): "EV Station station-1 Порт 1 ліміт струму",
        eid("binary_sensor", "online"): "EV Station station-1 На зв'язку",
        eid("binary_sensor", "port_1_plugged_in"): "EV Station station-1 Порт 1 авто підключено",
    }
    for entity_id, name in expected.items():
        state = hass.states.get(entity_id)
        assert state is not None, entity_id
        assert state.attributes["friendly_name"] == name


async def test_every_entity_has_a_translated_name(
    hass: HomeAssistant, entity_registry: er.EntityRegistry, init_integration: MockConfigEntry
) -> None:
    """No entity falls back to a device-class default or a missing translation."""
    entries = er.async_entries_for_config_entry(entity_registry, init_integration.entry_id)
    for entry in entries:
        assert entry.translation_key, entry.entity_id
        assert entry.original_name, entry.entity_id
        assert "{port}" not in entry.original_name, entry.entity_id
