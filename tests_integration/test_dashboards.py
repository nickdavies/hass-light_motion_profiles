"""The debug dashboards, built with lovelace_codegen.

Every other test leaves `debug_dashboard` unset, so this is what shows that the
dashboards still register and render against the installed lovelace_codegen.
"""

import copy
from typing import Any

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.loader import DATA_CUSTOM_COMPONENTS
from homeassistant.setup import async_setup_component

from .conftest import (
    BEDSIDE_LIGHT,
    BEDSIDE_MOTION,
    DOMAIN,
    PERSON_USER_A,
    SIMPLE_ROOM_LIGHT,
    SIMPLE_ROOM_MOTION,
    TEST_CONFIG,
    _ensure_custom_components_path,
)


def _entity_ids(node: Any) -> list[str]:
    """Every entity id anywhere in a rendered card tree."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "entity" and isinstance(value, str):
                found.append(value)
            else:
                found.extend(_entity_ids(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_entity_ids(item))
    return found


@pytest.fixture
async def with_dashboards(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
) -> HomeAssistant:
    config = copy.deepcopy(TEST_CONFIG)
    config[DOMAIN]["settings"]["debug_dashboard"] = {}

    # The entities the config names but other integrations own.
    for entity_id in (PERSON_USER_A, SIMPLE_ROOM_MOTION, BEDSIDE_MOTION):
        hass.states.async_set(entity_id, "on")
    for entity_id in (SIMPLE_ROOM_LIGHT, BEDSIDE_LIGHT):
        hass.states.async_set(entity_id, "off")

    hass.data.pop(DATA_CUSTOM_COMPONENTS, None)
    _ensure_custom_components_path()

    assert await async_setup_component(hass, DOMAIN, config), "setup failed"
    await hass.async_block_till_done()
    return hass


@pytest.mark.parametrize("url_path", ["presence-debug", "motion-debug"])
async def test_the_dashboard_registers_and_renders(
    with_dashboards: HomeAssistant, url_path: str
) -> None:
    dashboard = with_dashboards.data["lovelace"].dashboards[url_path]
    config = await dashboard.async_load(False)

    assert config["views"], "rendered no views"
    assert _entity_ids(config), "rendered no entities"


async def test_every_entity_on_the_dashboards_exists(
    with_dashboards: HomeAssistant,
) -> None:
    """A card naming an entity the component never created renders as a blank
    row nobody notices."""
    missing = set()
    for url_path in ("presence-debug", "motion-debug"):
        dashboard = with_dashboards.data["lovelace"].dashboards[url_path]
        for entity_id in _entity_ids(await dashboard.async_load(False)):
            if with_dashboards.states.get(entity_id) is None:
                missing.add(entity_id)

    assert not missing
