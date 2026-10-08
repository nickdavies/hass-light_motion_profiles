"""Tests for entity-based light properties (brightness, color_temp, transition).

Validates that light profiles with entity_id references resolve values from
HA entity states, respond to entity changes, and fall back correctly.
"""

import copy
from datetime import timedelta
from typing import Any

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.loader import DATA_CUSTOM_COMPONENTS
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed

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
    SIMPLE_ROOM_KS,
    SIMPLE_ROOM_OCCUPANCY,
    BEDSIDE_MOTION,
    PERSON_USER_A,
    flush,
    set_select,
    _ensure_custom_components_path,
)

# Entity IDs for the input_number helpers used by entity-based profiles
INPUT_BRIGHTNESS = "input_number.profile_brightness"
INPUT_COLOR_TEMP = "input_number.profile_color_temp"
INPUT_TRANSITION = "input_number.profile_transition"


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
async def entity_integration(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
) -> HomeAssistant:
    """The integration with entity-based light profiles, in a normal state."""
    return await setup_entity_integration(hass)


async def setup_entity_integration(
    hass: HomeAssistant,
    simple_room_motion: str = "on",
    simple_room_light: str = "off",
) -> HomeAssistant:
    """Set up integration with entity-based light profiles.

    `simple_room_motion` and `simple_room_light` are the states those start in.
    """
    # Pre-create external entities
    hass.states.async_set(PERSON_USER_A, "home")
    hass.states.async_set(SIMPLE_ROOM_MOTION, simple_room_motion)
    hass.states.async_set(BEDSIDE_MOTION, "on")
    hass.states.async_set(SIMPLE_ROOM_LIGHT, simple_room_light)

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
    hass: HomeAssistant, entity_integration, light_service_calls
):
    """Full profile resolves brightness from input_number entity (80)."""
    await flush(hass)

    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_on"
    # Entity INPUT_BRIGHTNESS is "80", should resolve to int 80
    assert call.data.get("brightness_pct") == 80


async def test_static_color_temp_in_service_call(
    hass: HomeAssistant, entity_integration, light_service_calls
):
    """Full profile includes static color_temp_kelvin=4000."""
    await flush(hass)

    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_on"
    assert call.data.get("color_temp_kelvin") == 4000


# --- Entity-based color_temp ---


async def test_entity_color_temp_in_service_call(
    hass: HomeAssistant, entity_integration, light_service_calls
):
    """Dim profile resolves color_temp from input_number entity (3000)."""
    await set_select(hass, USER_A_STATE, "winddown")
    await flush(hass)

    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_on"
    assert call.data.get("brightness_pct") == 25  # static
    assert call.data.get("color_temp_kelvin") == 3000  # from entity


# --- Entity value change triggers updated service call ---


async def test_brightness_entity_change_updates_service_call(
    hass: HomeAssistant, entity_integration, light_service_calls
):
    """Changing the brightness entity triggers a new service call with updated value."""
    await flush(hass)

    # Verify initial brightness
    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.data.get("brightness_pct") == 80

    initial_count = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    # Change the brightness entity
    hass.states.async_set(INPUT_BRIGHTNESS, "50")
    await flush(hass)

    # Should have a new service call with updated brightness
    new_calls = find_calls(light_service_calls, SIMPLE_ROOM_LIGHT)[initial_count:]
    assert len(new_calls) > 0
    assert new_calls[-1].data.get("brightness_pct") == 50


async def test_color_temp_entity_change_updates_service_call(
    hass: HomeAssistant, entity_integration, light_service_calls
):
    """Changing the color_temp entity triggers a new service call with updated value."""
    # Switch to winddown to use the "dim" profile with entity color_temp
    await set_select(hass, USER_A_STATE, "winddown")
    await flush(hass)

    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.data.get("color_temp_kelvin") == 3000

    initial_count = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    # Change the color temp entity
    hass.states.async_set(INPUT_COLOR_TEMP, "2700")
    await flush(hass)

    new_calls = find_calls(light_service_calls, SIMPLE_ROOM_LIGHT)[initial_count:]
    assert len(new_calls) > 0
    assert new_calls[-1].data.get("color_temp_kelvin") == 2700


# --- Entity unavailable falls back ---


async def test_entity_unavailable_omits_property(
    hass: HomeAssistant, entity_integration, light_service_calls
):
    """When brightness entity is unavailable, brightness is omitted from service call.

    Seen on a rule change into the profile: a refresh with only the color
    temperature the light already has sends nothing.
    """
    await set_select(hass, USER_A_STATE, "winddown")
    await flush(hass)
    hass.states.async_set(INPUT_BRIGHTNESS, "unavailable")
    await set_select(hass, USER_A_STATE, "awake")
    await flush(hass)

    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_on"
    # Brightness should not be in the service data (resolve returns None)
    assert "brightness_pct" not in call.data


async def test_entity_unknown_omits_property(
    hass: HomeAssistant, entity_integration, light_service_calls
):
    """When brightness entity is unknown, brightness is omitted from service call."""
    await set_select(hass, USER_A_STATE, "winddown")
    await flush(hass)
    hass.states.async_set(INPUT_BRIGHTNESS, "unknown")
    await set_select(hass, USER_A_STATE, "awake")
    await flush(hass)

    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_on"
    assert "brightness_pct" not in call.data


# --- A property change reconciles lights, skipping commands with no effect ---


def new_calls_after(
    calls: list[ServiceCall], entity_id: str, initial_count: int
) -> list[ServiceCall]:
    return find_calls(calls, entity_id)[initial_count:]


async def test_refresh_sends_nothing_to_off_light_under_off_profile(
    hass: HomeAssistant, entity_integration, light_service_calls
):
    """An off light under an off profile isn't sent turn_off again."""
    await set_select(hass, USER_A_STATE, "asleep")
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_LIGHT).state == "off"
    initial_count = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    hass.states.async_set(INPUT_BRIGHTNESS, "50")
    await flush(hass)

    assert new_calls_after(light_service_calls, SIMPLE_ROOM_LIGHT, initial_count) == []


async def test_refresh_turns_off_a_light_on_under_off_profile(
    hass: HomeAssistant, entity_integration, light_service_calls
):
    """A light turned on by hand under an off profile is turned back off."""
    await set_select(hass, USER_A_STATE, "asleep")
    await flush(hass)
    hass.states.async_set(SIMPLE_ROOM_LIGHT, "on")
    await flush(hass)
    initial_count = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    hass.states.async_set(INPUT_BRIGHTNESS, "50")
    await flush(hass)

    new_calls = new_calls_after(light_service_calls, SIMPLE_ROOM_LIGHT, initial_count)
    assert [c.service for c in new_calls] == ["turn_off"]


async def test_refresh_turns_on_a_light_off_under_on_profile(
    hass: HomeAssistant, entity_integration, light_service_calls
):
    """A light turned off by hand under an on profile is turned back on."""
    await flush(hass)
    hass.states.async_set(SIMPLE_ROOM_LIGHT, "off")
    await flush(hass)
    initial_count = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    hass.states.async_set(INPUT_BRIGHTNESS, "50")
    await flush(hass)

    new_calls = new_calls_after(light_service_calls, SIMPLE_ROOM_LIGHT, initial_count)
    assert [c.service for c in new_calls] == ["turn_on"]
    assert new_calls[0].data.get("brightness_pct") == 50


async def test_refresh_turns_off_unknown_light_under_off_profile(
    hass: HomeAssistant, entity_integration, light_service_calls
):
    """A light that hasn't reported isn't known to be off, so is sent turn_off."""
    await set_select(hass, USER_A_STATE, "asleep")
    await flush(hass)
    hass.states.async_set(SIMPLE_ROOM_LIGHT, "unknown")
    await flush(hass)
    initial_count = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    hass.states.async_set(INPUT_BRIGHTNESS, "50")
    await flush(hass)

    new_calls = new_calls_after(light_service_calls, SIMPLE_ROOM_LIGHT, initial_count)
    assert [c.service for c in new_calls] == ["turn_off"]


async def test_refresh_takes_unknown_light_out_of_unknown(
    hass: HomeAssistant, entity_integration, light_service_calls
):
    """A light that hasn't reported gets an on profile's values."""
    await flush(hass)
    hass.states.async_set(SIMPLE_ROOM_LIGHT, "unknown")
    await flush(hass)
    initial_count = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    hass.states.async_set(INPUT_BRIGHTNESS, "50")
    await flush(hass)

    new_calls = new_calls_after(light_service_calls, SIMPLE_ROOM_LIGHT, initial_count)
    assert [c.service for c in new_calls] == ["turn_on"]
    assert new_calls[0].data.get("brightness_pct") == 50
    assert hass.states.get(SIMPLE_ROOM_LIGHT).state == "on"


async def test_refresh_leaves_unknown_light_alone_under_noop(
    hass: HomeAssistant, light_service_calls
):
    """After a restart (unknown_occ → noop), a refresh doesn't switch a light on.

    A profile that doesn't say on or off only adjusts a light that is on.
    """
    await setup_entity_integration(
        hass, simple_room_motion="unknown", simple_room_light="unknown"
    )
    hass.states.async_set(SIMPLE_ROOM_LIGHT, "unknown")
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_OCCUPANCY).state == "unknown"
    initial_count = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    hass.states.async_set(INPUT_BRIGHTNESS, "50")
    await flush(hass)

    assert new_calls_after(light_service_calls, SIMPLE_ROOM_LIGHT, initial_count) == []

    # Let the startup timeout end, so its timer doesn't outlive the test.
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=181))
    await flush(hass)


async def test_refresh_skips_unavailable_light(
    hass: HomeAssistant, entity_integration, light_service_calls
):
    """An unavailable light isn't called; it's re-applied when it comes back."""
    await flush(hass)
    hass.states.async_set(SIMPLE_ROOM_LIGHT, "unavailable")
    await flush(hass)
    initial_count = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    hass.states.async_set(INPUT_BRIGHTNESS, "50")
    await flush(hass)

    assert new_calls_after(light_service_calls, SIMPLE_ROOM_LIGHT, initial_count) == []


async def test_killswitch_blocks_refresh(
    hass: HomeAssistant, entity_integration, light_service_calls
):
    """A killswitch holds the lights through a property change too."""
    await flush(hass)
    await set_switch(hass, SIMPLE_ROOM_KS, True)
    await flush(hass)
    initial_count = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    hass.states.async_set(INPUT_BRIGHTNESS, "50")
    await flush(hass)

    assert new_calls_after(light_service_calls, SIMPLE_ROOM_LIGHT, initial_count) == []


async def test_rule_change_switches_light_whatever_its_state(
    hass: HomeAssistant, entity_integration, light_service_calls
):
    """A rule change always sends its command, even to a light already off."""
    await flush(hass)
    hass.states.async_set(SIMPLE_ROOM_LIGHT, "off")
    await flush(hass)
    initial_count = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    await set_select(hass, USER_A_STATE, "asleep")
    await flush(hass)

    new_calls = new_calls_after(light_service_calls, SIMPLE_ROOM_LIGHT, initial_count)
    assert [c.service for c in new_calls] == ["turn_off"]


# --- A refresh skips a turn_on the light already has the values of ---


async def test_refresh_skips_light_that_already_has_values(
    hass: HomeAssistant, entity_integration, light_service_calls
):
    """An input the current profile doesn't read changing sends nothing."""
    await flush(hass)
    initial_count = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    # The full profile reads brightness, not this.
    hass.states.async_set(INPUT_COLOR_TEMP, "2700")
    await flush(hass)

    assert new_calls_after(light_service_calls, SIMPLE_ROOM_LIGHT, initial_count) == []


async def test_refresh_skips_change_within_a_mired(
    hass: HomeAssistant, entity_integration, light_service_calls
):
    """A color temperature change too small for the light to show sends nothing."""
    await set_select(hass, USER_A_STATE, "winddown")
    await flush(hass)
    initial_count = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    # 3000K and 3001K are both 333 mireds; 3010K is 332.
    hass.states.async_set(INPUT_COLOR_TEMP, "3001")
    await flush(hass)
    assert new_calls_after(light_service_calls, SIMPLE_ROOM_LIGHT, initial_count) == []

    hass.states.async_set(INPUT_COLOR_TEMP, "3010")
    await flush(hass)
    new_calls = new_calls_after(light_service_calls, SIMPLE_ROOM_LIGHT, initial_count)
    assert [c.data.get("color_temp_kelvin") for c in new_calls] == [3010]


async def test_refresh_compares_within_light_range(
    hass: HomeAssistant, entity_integration, light_service_calls
):
    """Targets past either end of the light's range match the light at that end."""
    await set_select(hass, USER_A_STATE, "winddown")
    await flush(hass)

    for first, second in (("1000", "1500"), ("9790", "9000")):
        hass.states.async_set(INPUT_COLOR_TEMP, first)
        await flush(hass)
        initial_count = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

        hass.states.async_set(INPUT_COLOR_TEMP, second)
        await flush(hass)
        assert (
            new_calls_after(light_service_calls, SIMPLE_ROOM_LIGHT, initial_count) == []
        )


async def test_refresh_sends_to_light_in_a_color_mode(
    hass: HomeAssistant, entity_integration, light_service_calls
):
    """A light set to a color reports no color temperature, so is sent one."""
    await set_select(hass, USER_A_STATE, "winddown")
    await flush(hass)
    attrs = dict(hass.states.get(SIMPLE_ROOM_LIGHT).attributes)
    del attrs["color_temp_kelvin"]
    hass.states.async_set(SIMPLE_ROOM_LIGHT, "on", attrs)
    await flush(hass)
    initial_count = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    # The dim profile reads color temperature, not this.
    hass.states.async_set(INPUT_BRIGHTNESS, "50")
    await flush(hass)

    new_calls = new_calls_after(light_service_calls, SIMPLE_ROOM_LIGHT, initial_count)
    assert [c.data.get("color_temp_kelvin") for c in new_calls] == [3000]


async def test_rule_change_sends_values_the_light_already_has(
    hass: HomeAssistant, entity_integration, light_service_calls
):
    """Only a refresh skips: a rule change always sends its command."""
    await set_select(hass, USER_A_STATE, "winddown")
    await flush(hass)
    dim = dict(hass.states.get(SIMPLE_ROOM_LIGHT).attributes)
    await set_select(hass, USER_A_STATE, "awake")
    await flush(hass)

    # The light is put back to the dim values by hand, then the rule moves there.
    hass.states.async_set(SIMPLE_ROOM_LIGHT, "on", dim)
    await flush(hass)
    initial_count = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))
    await set_select(hass, USER_A_STATE, "winddown")
    await flush(hass)

    new_calls = new_calls_after(light_service_calls, SIMPLE_ROOM_LIGHT, initial_count)
    assert [c.service for c in new_calls] == ["turn_on"]
