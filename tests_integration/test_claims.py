"""Light configs' entities claimed with the config bridge, and pinned by it."""

import copy
import logging
from typing import Any

import pytest
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant, ServiceCall
from homeassistant.helpers import (
    area_registry as ar,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.loader import DATA_CUSTOM_COMPONENTS
from homeassistant.setup import async_setup_component

from .conftest import (
    BEDSIDE_AUTOMATION,
    BEDSIDE_LIGHT,
    BEDSIDE_MOTION,
    BEDSIDE_OCCUPANCY,
    BEDSIDE_RULE,
    DOMAIN,
    PERSON_USER_A,
    SIMPLE_ROOM_AUTOMATION,
    SIMPLE_ROOM_KS,
    SIMPLE_ROOM_LIGHT,
    SIMPLE_ROOM_MOTION,
    SIMPLE_ROOM_OCCUPANCY,
    SIMPLE_ROOM_RULE,
    TEST_CONFIG,
    _ensure_custom_components_path,
)

SIMPLE_ROOM_ENTITIES = [
    SIMPLE_ROOM_KS,
    SIMPLE_ROOM_OCCUPANCY,
    SIMPLE_ROOM_RULE,
    SIMPLE_ROOM_AUTOMATION,
]
BEDSIDE_KS = "switch.killswitch_motion_bedside_lamp"
BEDSIDE_ENTITIES = [BEDSIDE_KS, BEDSIDE_OCCUPANCY, BEDSIDE_RULE, BEDSIDE_AUTOMATION]
MOTION_GROUP = "binary_sensor.motion_sensor_group_simple_room"


@pytest.fixture(autouse=True)
def _light_services(light_service_calls: list[ServiceCall]) -> None:
    """Every test sets the component up, which calls light services."""


async def _boot(
    hass: HomeAssistant, lights: dict[str, dict[str, Any]], *, bridge: bool = True
) -> None:
    """A boot: the bridge (if any), then this component, then started.

    The bridge applies claims once Home Assistant has started, as it would
    after every integration has set up.
    """
    config = copy.deepcopy(TEST_CONFIG)
    for light, changes in lights.items():
        config[DOMAIN]["light_configs"][light].update(changes)

    hass.states.async_set(PERSON_USER_A, "home")
    for entity_id in (SIMPLE_ROOM_MOTION, BEDSIDE_MOTION):
        hass.states.async_set(entity_id, "on")
    for entity_id in (SIMPLE_ROOM_LIGHT, BEDSIDE_LIGHT):
        hass.states.async_set(entity_id, "off")

    hass.set_state(CoreState.starting)
    hass.data.pop(DATA_CUSTOM_COMPONENTS, None)
    _ensure_custom_components_path()
    if bridge:
        assert await async_setup_component(hass, "config_bridge", {"config_bridge": {}})
    assert await async_setup_component(hass, DOMAIN, config), "setup failed"
    await hass.async_block_till_done()
    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()


def entry(hass: HomeAssistant, entity_id: str) -> er.RegistryEntry:
    found = er.async_get(hass).async_get(entity_id)
    assert found is not None, f"{entity_id} isn't in the entity registry"
    return found


def bridge_report(hass: HomeAssistant) -> ir.IssueEntry | None:
    return ir.async_get(hass).async_get_issue("config_bridge", "report_entities")


async def test_a_config_puts_its_entities_in_its_area(hass: HomeAssistant) -> None:
    ar.async_get(hass).async_create("Living")

    await _boot(hass, {"simple_room": {"area": "living"}})

    assert {entry(hass, e).area_id for e in SIMPLE_ROOM_ENTITIES} == {"living"}
    assert {entry(hass, e).area_id for e in BEDSIDE_ENTITIES} == {None}
    assert bridge_report(hass) is None


async def test_entity_ids_are_unchanged_by_registering(hass: HomeAssistant) -> None:
    await _boot(hass, {})

    assert entry(hass, SIMPLE_ROOM_AUTOMATION).unique_id == (
        "light_binding_automation_simple_room"
    )


async def test_a_motion_group_is_claimed_too(hass: HomeAssistant) -> None:
    ar.async_get(hass).async_create("Living")

    await _boot(
        hass,
        {"simple_room": {"area": "living", "occupancy_sensors": [SIMPLE_ROOM_MOTION]}},
    )

    assert entry(hass, MOTION_GROUP).area_id == "living"


async def test_ui_changes_are_put_back(hass: HomeAssistant) -> None:
    areas = ar.async_get(hass)
    areas.async_create("Living")
    areas.async_create("Garage")
    # Registered on an earlier boot, and changed in the UI since.
    registry = er.async_get(hass)
    registry.async_get_or_create(
        "switch",
        DOMAIN,
        "killswitch_motion_simple_room",
        suggested_object_id="killswitch_motion_simple_room",
    )
    registry.async_update_entity(SIMPLE_ROOM_KS, area_id="garage", name="Mine")
    registry.async_get_or_create(
        "switch",
        DOMAIN,
        "killswitch_motion_bedside_lamp",
        suggested_object_id="killswitch_motion_bedside_lamp",
    )
    registry.async_update_entity(BEDSIDE_KS, area_id="garage")

    await _boot(hass, {"simple_room": {"area": "living"}})

    assert entry(hass, SIMPLE_ROOM_KS).area_id == "living"
    assert entry(hass, SIMPLE_ROOM_KS).name is None
    # No `area:` in git means no area of its own.
    assert entry(hass, BEDSIDE_KS).area_id is None


async def test_an_area_that_doesnt_exist_is_reported_by_the_bridge(
    hass: HomeAssistant,
) -> None:
    await _boot(hass, {"simple_room": {"area": "attic"}})

    reason = bridge_report(hass).translation_placeholders["reason"]
    assert f"{SIMPLE_ROOM_KS} (claimed by {DOMAIN}): area 'attic'" in reason


async def test_without_the_bridge_nothing_is_claimed(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        await _boot(hass, {"simple_room": {"area": "living"}}, bridge=False)

    assert "config_bridge isn't set up" in caplog.text
    assert "config_bridge_claims" not in hass.data
    assert entry(hass, SIMPLE_ROOM_KS).area_id is None
