"""Tests for what happens across a Home Assistant restart.

Motion while Home Assistant was down was never seen, so after a restart:
  - a room starts unknown, and its lights are left alone;
  - motion makes it occupied as usual;
  - until then, a light that is on means the room was in use, so it goes to
    occupied_timeout;
  - with no motion for one timeout after Home Assistant started, it's empty.

And a light can't take calls until its integration loads, so the profile is
applied again once it can.
"""

from datetime import timedelta

from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant, ServiceCall
from homeassistant.util import dt as dt_util

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .conftest import (
    SIMPLE_ROOM_LIGHT,
    SIMPLE_ROOM_MOTION,
    SIMPLE_ROOM_OCCUPANCY,
    flush,
    setup_integration,
)
from .test_light_automation import find_calls, last_call

TIMEOUT = 180


def occupancy(hass: HomeAssistant) -> str:
    return hass.states.get(SIMPLE_ROOM_OCCUPANCY).state


async def wait(hass: HomeAssistant, seconds: int) -> None:
    """Fire timers due `seconds` from now (from the real now, so not cumulative)."""
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=seconds))
    await flush(hass)


# --- Occupancy after a restart ---


async def test_light_off_no_motion(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """A light that is off is left alone, then the room is empty."""
    await setup_integration(hass, simple_room_motion="off", simple_room_light="off")
    assert occupancy(hass) == "unknown"
    before = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    await wait(hass, TIMEOUT - 10)
    assert occupancy(hass) == "unknown"
    assert len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT)) == before

    await wait(hass, TIMEOUT + 1)
    assert occupancy(hass) == "empty"
    assert last_call(light_service_calls, SIMPLE_ROOM_LIGHT).service == "turn_off"


async def test_light_off_then_motion(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """Motion turns a light that is off on straight away."""
    await setup_integration(hass, simple_room_motion="off", simple_room_light="off")

    hass.states.async_set(SIMPLE_ROOM_MOTION, "on")
    await flush(hass)
    assert occupancy(hass) == "occupied"
    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call.service == "turn_on"
    assert call.data.get("brightness_pct") == 100

    # The startup timeout no longer applies.
    await wait(hass, TIMEOUT + 1)
    assert occupancy(hass) == "occupied"


async def test_light_on_no_motion(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """A light that is on gets a whole timeout, then turns off."""
    await setup_integration(hass, simple_room_motion="off", simple_room_light="on")
    assert occupancy(hass) == "occupied_timeout"

    await wait(hass, TIMEOUT - 10)
    assert occupancy(hass) == "occupied_timeout"

    await wait(hass, TIMEOUT + 1)
    assert occupancy(hass) == "empty"
    assert last_call(light_service_calls, SIMPLE_ROOM_LIGHT).service == "turn_off"


async def test_light_on_then_motion(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """Motion with a light that is on carries on as normal."""
    await setup_integration(hass, simple_room_motion="off", simple_room_light="on")
    await wait(hass, TIMEOUT - 10)

    hass.states.async_set(SIMPLE_ROOM_MOTION, "on")
    await flush(hass)
    assert occupancy(hass) == "occupied"

    # The startup timeout is gone; the timeout runs from when motion stops.
    await wait(hass, TIMEOUT + 1)
    assert occupancy(hass) == "occupied"
    hass.states.async_set(SIMPLE_ROOM_MOTION, "off")
    await flush(hass)
    assert occupancy(hass) == "occupied_timeout"
    await wait(hass, TIMEOUT * 2)
    assert occupancy(hass) == "empty"


async def test_light_reports_on_later(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """A light reporting on part way through keeps the startup deadline."""
    await setup_integration(hass, simple_room_motion=None, simple_room_light=None)
    assert occupancy(hass) == "unknown"

    hass.states.async_set(SIMPLE_ROOM_MOTION, "off")
    hass.states.async_set(SIMPLE_ROOM_LIGHT, "unknown")
    await wait(hass, 60)
    assert occupancy(hass) == "unknown"

    hass.states.async_set(SIMPLE_ROOM_LIGHT, "on")
    await flush(hass)
    assert occupancy(hass) == "occupied_timeout"

    await wait(hass, TIMEOUT + 1)
    assert occupancy(hass) == "empty"


async def test_light_never_reports(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """A light with no known state is left alone, then turned off."""
    await setup_integration(
        hass, simple_room_motion="unknown", simple_room_light="unknown"
    )
    assert occupancy(hass) == "unknown"
    before = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    await wait(hass, TIMEOUT - 10)
    assert len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT)) == before

    await wait(hass, TIMEOUT + 1)
    assert occupancy(hass) == "empty"
    assert last_call(light_service_calls, SIMPLE_ROOM_LIGHT).service == "turn_off"


async def test_timeout_starts_once_started(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """Time spent starting Home Assistant isn't counted as no motion."""
    hass.set_state(CoreState.starting)
    await setup_integration(hass, simple_room_motion="off", simple_room_light="on")
    await wait(hass, TIMEOUT + 1)
    assert occupancy(hass) == "occupied_timeout"

    hass.set_state(CoreState.running)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await flush(hass)
    await wait(hass, TIMEOUT - 10)
    assert occupancy(hass) == "occupied_timeout"

    await wait(hass, TIMEOUT + 1)
    assert occupancy(hass) == "empty"


async def test_after_startup_only_motion_counts(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """Once empty, neither the sensor coming back nor the light changes it."""
    await setup_integration(hass, simple_room_motion="off", simple_room_light="off")
    await wait(hass, TIMEOUT + 1)
    assert occupancy(hass) == "empty"

    hass.states.async_set(SIMPLE_ROOM_MOTION, "unavailable")
    await flush(hass)
    hass.states.async_set(SIMPLE_ROOM_MOTION, "off")
    hass.states.async_set(SIMPLE_ROOM_LIGHT, "on")
    await flush(hass)
    assert occupancy(hass) == "empty"

    await wait(hass, TIMEOUT * 2)
    assert occupancy(hass) == "empty"


# --- Lights that can't take calls yet ---


async def test_unavailable_light_is_set_when_it_loads(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """No call to an unavailable light; the call is made once it loads."""
    await setup_integration(hass, simple_room_light="unavailable")
    assert find_calls(light_service_calls, SIMPLE_ROOM_LIGHT) == []

    # Lights from MQTT load as unknown: calls go through from here.
    hass.states.async_set(SIMPLE_ROOM_LIGHT, "unknown")
    await flush(hass)

    calls = find_calls(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert len(calls) == 1
    assert calls[0].service == "turn_on"
    assert calls[0].data.get("brightness_pct") == 100


async def test_missing_light_is_set_when_it_loads(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """The same for a light with no state at all yet."""
    await setup_integration(hass, simple_room_light=None)
    assert find_calls(light_service_calls, SIMPLE_ROOM_LIGHT) == []

    hass.states.async_set(SIMPLE_ROOM_LIGHT, "on")
    await flush(hass)

    calls = find_calls(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert len(calls) == 1
    assert calls[0].service == "turn_on"


async def test_light_reporting_is_left_alone(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """A light reporting its state, or changed by hand, isn't set again."""
    await setup_integration(hass, simple_room_light="unknown")
    before = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    for state in ("on", "off", "on"):
        hass.states.async_set(SIMPLE_ROOM_LIGHT, state)
        await flush(hass)

    assert len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT)) == before


async def test_light_going_unavailable_then_back(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """A light that drops off and comes back is set again."""
    await setup_integration(hass)
    before = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    hass.states.async_set(SIMPLE_ROOM_LIGHT, "unavailable")
    await flush(hass)
    assert len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT)) == before

    hass.states.async_set(SIMPLE_ROOM_LIGHT, "off")
    await flush(hass)
    calls = find_calls(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert len(calls) == before + 1
    assert calls[-1].service == "turn_on"
