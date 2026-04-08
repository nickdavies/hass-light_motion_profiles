"""Tests for entity-based light properties (brightness, color_temp, transition).

Validates that light profiles with entity_id references resolve values from
HA entity states, respond to entity changes, and fall back correctly.
"""

import copy
from typing import Any

import pytest
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import SERVICE_TURN_ON, SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.loader import DATA_CUSTOM_COMPONENTS
from homeassistant.setup import async_setup_component

from .conftest import (
    TEST_CONFIG,
    DOMAIN,
    USER_A_OVERRIDE,
    USER_A_STATE,
    USER_B_EXISTS,
    USER_B_OVERRIDE,
    USER_B_STATE,
    SIMPLE_ROOM_MOTION,
    SIMPLE_ROOM_LIGHT,
    PERSON_USER_A,
    flush,
    set_select,
    _ensure_custom_components_path,
)

# Entity IDs for the input_number helpers used by entity-based profiles
INPUT_BRIGHTNESS = "input_number.profile_brightness"
INPUT_COLOR_TEMP = "input_number.profile_color_temp"
INPUT_TRANSITION = "input_number.profile_transition"
INPUT_CT_TRANSITION = "input_number.profile_ct_transition"


def _make_entity_config() -> dict[str, Any]:
    """Build a test config with entity-based light profiles."""
    config = copy.deepcopy(TEST_CONFIG)
    profiles = config[DOMAIN]["light_profiles"]

    # Replace "full" profile: entity-based brightness + static color_temp
    profiles["full"] = {
        "enabled": True,
        "brightness_pct": {"entity_id": INPUT_BRIGHTNESS},
        "color_temp_kelvin": 4000,
        "icon": "mdi:weather-sunny",
    }

    # Replace "dim" profile: entity-based color_temp + static brightness
    profiles["dim"] = {
        "enabled": True,
        "brightness_pct": 25,
        "color_temp_kelvin": {"entity_id": INPUT_COLOR_TEMP},
        "icon": "mdi:lamp",
    }

    # Replace "disable_slowly": entity-based transition
    profiles["disable_slowly"] = {
        "enabled": False,
        "icon": "mdi:transfer-down",
        "transition": {"entity_id": INPUT_TRANSITION},
    }

    return config


def find_calls(
    calls: list[ServiceCall],
    entity_id: str,
    service: str | None = None,
) -> list[ServiceCall]:
    """Filter service calls for a specific entity and optional service."""
    result = []
    for call in calls:
        if call.data.get("entity_id") == entity_id:
            if service is None or call.service == service:
                result.append(call)
    return result


def last_call(calls: list[ServiceCall], entity_id: str) -> ServiceCall | None:
    """Get the most recent service call for an entity."""
    matching = find_calls(calls, entity_id)
    return matching[-1] if matching else None


@pytest.fixture
async def entity_service_calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Register mock light services and return list of captured calls."""
    calls: list[ServiceCall] = []

    async def mock_service(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register(LIGHT_DOMAIN, SERVICE_TURN_ON, mock_service)
    hass.services.async_register(LIGHT_DOMAIN, SERVICE_TURN_OFF, mock_service)
    return calls


@pytest.fixture
async def entity_integration(
    hass: HomeAssistant, entity_service_calls: list[ServiceCall]
) -> HomeAssistant:
    """Set up integration with entity-based light profiles."""
    # Pre-create external entities
    hass.states.async_set(PERSON_USER_A, "home")
    hass.states.async_set(SIMPLE_ROOM_MOTION, "on")
    hass.states.async_set(SIMPLE_ROOM_LIGHT, "off")

    # Pre-create the input_number entities that profiles reference
    hass.states.async_set(INPUT_BRIGHTNESS, "80")
    hass.states.async_set(INPUT_COLOR_TEMP, "3000")
    hass.states.async_set(INPUT_TRANSITION, "15")

    hass.data.pop(DATA_CUSTOM_COMPONENTS, None)
    _ensure_custom_components_path()

    config = _make_entity_config()
    result = await async_setup_component(hass, DOMAIN, config)
    assert result, "Integration setup failed"
    await hass.async_block_till_done()

    await set_select(hass, USER_A_OVERRIDE, "auto")
    await set_select(hass, USER_A_STATE, "awake")
    await set_select(hass, USER_B_OVERRIDE, "auto")
    await set_switch(hass, USER_B_EXISTS, False)
    await set_select(hass, USER_B_STATE, "awake")
    await flush(hass)

    return hass


async def set_switch(hass: HomeAssistant, entity_id: str, on: bool) -> None:
    """Toggle a switch entity using the HA service."""
    await hass.services.async_call(
        "switch",
        "turn_on" if on else "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )


# --- Entity-based brightness ---


async def test_entity_brightness_in_service_call(
    hass: HomeAssistant, entity_integration, entity_service_calls
):
    """Full profile resolves brightness from input_number entity (80)."""
    await flush(hass)

    call = last_call(entity_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_on"
    # Entity INPUT_BRIGHTNESS is "80", should resolve to int 80
    assert call.data.get("brightness_pct") == 80


async def test_static_color_temp_in_service_call(
    hass: HomeAssistant, entity_integration, entity_service_calls
):
    """Full profile includes static color_temp_kelvin=4000."""
    await flush(hass)

    call = last_call(entity_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_on"
    assert call.data.get("color_temp_kelvin") == 4000


# --- Entity-based color_temp ---


async def test_entity_color_temp_in_service_call(
    hass: HomeAssistant, entity_integration, entity_service_calls
):
    """Dim profile resolves color_temp from input_number entity (3000)."""
    await set_select(hass, USER_A_STATE, "winddown")
    await flush(hass)

    call = last_call(entity_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_on"
    assert call.data.get("brightness_pct") == 25  # static
    assert call.data.get("color_temp_kelvin") == 3000  # from entity


# --- Entity value change triggers updated service call ---


async def test_brightness_entity_change_updates_service_call(
    hass: HomeAssistant, entity_integration, entity_service_calls
):
    """Changing the brightness entity triggers a new service call with updated value."""
    await flush(hass)

    # Verify initial brightness
    call = last_call(entity_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.data.get("brightness_pct") == 80

    initial_count = len(find_calls(entity_service_calls, SIMPLE_ROOM_LIGHT))

    # Change the brightness entity
    hass.states.async_set(INPUT_BRIGHTNESS, "50")
    await flush(hass)

    # Should have a new service call with updated brightness
    new_calls = find_calls(entity_service_calls, SIMPLE_ROOM_LIGHT)[initial_count:]
    assert len(new_calls) > 0
    assert new_calls[-1].data.get("brightness_pct") == 50


async def test_color_temp_entity_change_updates_service_call(
    hass: HomeAssistant, entity_integration, entity_service_calls
):
    """Changing the color_temp entity triggers a new service call with updated value."""
    # Switch to winddown to use the "dim" profile with entity color_temp
    await set_select(hass, USER_A_STATE, "winddown")
    await flush(hass)

    call = last_call(entity_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.data.get("color_temp_kelvin") == 3000

    initial_count = len(find_calls(entity_service_calls, SIMPLE_ROOM_LIGHT))

    # Change the color temp entity
    hass.states.async_set(INPUT_COLOR_TEMP, "2700")
    await flush(hass)

    new_calls = find_calls(entity_service_calls, SIMPLE_ROOM_LIGHT)[initial_count:]
    assert len(new_calls) > 0
    assert new_calls[-1].data.get("color_temp_kelvin") == 2700


# --- Entity unavailable falls back ---


async def test_entity_unavailable_omits_property(
    hass: HomeAssistant, entity_integration, entity_service_calls
):
    """When brightness entity is unavailable, brightness is omitted from service call."""
    hass.states.async_set(INPUT_BRIGHTNESS, "unavailable")
    await flush(hass)

    call = last_call(entity_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_on"
    # Brightness should not be in the service data (resolve returns None)
    assert "brightness_pct" not in call.data


async def test_entity_unknown_omits_property(
    hass: HomeAssistant, entity_integration, entity_service_calls
):
    """When brightness entity is unknown, brightness is omitted from service call."""
    hass.states.async_set(INPUT_BRIGHTNESS, "unknown")
    await flush(hass)

    call = last_call(entity_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_on"
    assert "brightness_pct" not in call.data


# --- Color temp transition ---


def _make_ct_transition_config() -> dict[str, Any]:
    """Build a test config with color_temp_transition on the full profile."""
    config = copy.deepcopy(TEST_CONFIG)
    profiles = config[DOMAIN]["light_profiles"]

    # "full" profile with entity-based color_temp and a color_temp_transition
    profiles["full"] = {
        "enabled": True,
        "brightness_pct": 100,
        "color_temp_kelvin": {"entity_id": INPUT_COLOR_TEMP},
        "transition": 1,
        "color_temp_transition": {"entity_id": INPUT_CT_TRANSITION},
        "icon": "mdi:weather-sunny",
    }

    # "dim" profile with static color_temp_transition
    profiles["dim"] = {
        "enabled": True,
        "brightness_pct": 25,
        "color_temp_kelvin": 3000,
        "transition": 1,
        "color_temp_transition": 30,
        "icon": "mdi:lamp",
    }

    # "disable_slowly" has no color_temp, should use regular transition
    profiles["disable_slowly"] = {
        "enabled": False,
        "icon": "mdi:transfer-down",
        "transition": 10,
    }

    return config


@pytest.fixture
async def ct_transition_service_calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Register mock light services and return list of captured calls."""
    calls: list[ServiceCall] = []

    async def mock_service(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register(LIGHT_DOMAIN, SERVICE_TURN_ON, mock_service)
    hass.services.async_register(LIGHT_DOMAIN, SERVICE_TURN_OFF, mock_service)
    return calls


@pytest.fixture
async def ct_transition_integration(
    hass: HomeAssistant, ct_transition_service_calls: list[ServiceCall]
) -> HomeAssistant:
    """Set up integration with color_temp_transition profiles."""
    hass.states.async_set(PERSON_USER_A, "home")
    hass.states.async_set(SIMPLE_ROOM_MOTION, "on")
    hass.states.async_set(SIMPLE_ROOM_LIGHT, "off")

    hass.states.async_set(INPUT_COLOR_TEMP, "4000")
    hass.states.async_set(INPUT_CT_TRANSITION, "45")

    hass.data.pop(DATA_CUSTOM_COMPONENTS, None)
    _ensure_custom_components_path()

    config = _make_ct_transition_config()
    result = await async_setup_component(hass, DOMAIN, config)
    assert result, "Integration setup failed"
    await hass.async_block_till_done()

    await set_select(hass, USER_A_OVERRIDE, "auto")
    await set_select(hass, USER_A_STATE, "awake")
    await set_select(hass, USER_B_OVERRIDE, "auto")
    await set_switch(hass, USER_B_EXISTS, False)
    await set_select(hass, USER_B_STATE, "awake")
    await flush(hass)

    return hass


async def test_color_temp_transition_overrides_transition(
    hass: HomeAssistant, ct_transition_integration, ct_transition_service_calls
):
    """When color_temp is present, color_temp_transition overrides regular transition."""
    await flush(hass)

    call = last_call(ct_transition_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_on"
    assert call.data.get("color_temp_kelvin") == 4000
    # Should use color_temp_transition (45), not regular transition (1)
    assert call.data.get("transition") == 45


async def test_color_temp_transition_static_value(
    hass: HomeAssistant, ct_transition_integration, ct_transition_service_calls
):
    """Static color_temp_transition value works correctly."""
    # Switch to winddown to use the "dim" profile with static color_temp_transition=30
    await set_select(hass, USER_A_STATE, "winddown")
    await flush(hass)

    call = last_call(ct_transition_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_on"
    assert call.data.get("color_temp_kelvin") == 3000
    assert call.data.get("transition") == 30


async def test_color_temp_transition_entity_change(
    hass: HomeAssistant, ct_transition_integration, ct_transition_service_calls
):
    """Changing the color_temp_transition entity updates the transition in service calls."""
    await flush(hass)

    call = last_call(ct_transition_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.data.get("transition") == 45

    initial_count = len(find_calls(ct_transition_service_calls, SIMPLE_ROOM_LIGHT))

    # Change the color_temp_transition entity
    hass.states.async_set(INPUT_CT_TRANSITION, "60")
    await flush(hass)

    new_calls = find_calls(ct_transition_service_calls, SIMPLE_ROOM_LIGHT)[
        initial_count:
    ]
    assert len(new_calls) > 0
    assert new_calls[-1].data.get("transition") == 60


async def test_regular_transition_used_when_no_color_temp(
    hass: HomeAssistant, ct_transition_integration, ct_transition_service_calls
):
    """Turn-off uses regular transition even when color_temp_transition is configured."""
    # Switch to asleep to use the "disable_slowly" profile (no color_temp)
    await set_select(hass, USER_A_STATE, "asleep")
    await flush(hass)

    call = last_call(ct_transition_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_off"
    # Should use regular transition (10), not color_temp_transition
    assert call.data.get("transition") == 10
