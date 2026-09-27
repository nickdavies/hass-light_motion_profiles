"""Tests for what happens across a Home Assistant restart.

Two things go wrong on a restart without these:
  - Occupancy starts over: a motion sensor coming back as `off` looked like
    motion that just ended, so every room went `occupied_timeout` with a
    whole new timeout, and lights left on in an empty room waited it out.
  - Lights aren't set: at startup a light is unavailable until its
    integration loads, Home Assistant drops service calls to unavailable
    entities, and nothing re-sent the call once the light came back.
"""

from datetime import timedelta

from homeassistant.core import HomeAssistant, ServiceCall, State
from homeassistant.helpers import entity_component
from homeassistant.util import dt as dt_util

from pytest_homeassistant_custom_component.common import (
    async_fire_time_changed,
    mock_restore_cache_with_extra_data,
)

from .conftest import (
    SIMPLE_ROOM_LIGHT,
    SIMPLE_ROOM_MOTION,
    SIMPLE_ROOM_OCCUPANCY,
    flush,
    setup_integration,
)
from .test_light_automation import find_calls, last_call


def restore_occupancy(hass: HomeAssistant, state: str, deadline=None) -> None:
    """Make the occupancy sensor restore `state` and `deadline`."""
    extra = {"no_motion_deadline": deadline.isoformat() if deadline else None}
    mock_restore_cache_with_extra_data(
        hass, [(State(SIMPLE_ROOM_OCCUPANCY, state), extra)]
    )


def occupancy(hass: HomeAssistant) -> str:
    return hass.states.get(SIMPLE_ROOM_OCCUPANCY).state


# --- Occupancy across a restart ---


async def test_restored_empty_stays_empty(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """An empty room stays empty when its sensor comes back as off."""
    restore_occupancy(hass, "empty")
    await setup_integration(hass, simple_room_motion="off", simple_room_light="on")

    assert occupancy(hass) == "empty"
    # The light is turned off straight away, not after a timeout.
    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_off"

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=181))
    await flush(hass)
    assert occupancy(hass) == "empty"


async def test_restored_empty_sensor_loads_later(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """An empty room stays empty when its sensor goes unavailable then off."""
    restore_occupancy(hass, "empty")
    await setup_integration(hass, simple_room_motion=None)
    assert occupancy(hass) == "empty"

    hass.states.async_set(SIMPLE_ROOM_MOTION, "unavailable")
    await flush(hass)
    hass.states.async_set(SIMPLE_ROOM_MOTION, "off")
    await flush(hass)
    assert occupancy(hass) == "empty"


async def test_restored_timeout_keeps_deadline(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """A timeout running at the restart ends when it would have, not later."""
    restore_occupancy(
        hass, "occupied_timeout", dt_util.utcnow() + timedelta(seconds=60)
    )
    await setup_integration(hass, simple_room_motion="off")
    assert occupancy(hass) == "occupied_timeout"

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await flush(hass)
    assert occupancy(hass) == "empty"


async def test_restored_timeout_past_deadline(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """A timeout that ran out while Home Assistant was down is empty at once."""
    restore_occupancy(
        hass, "occupied_timeout", dt_util.utcnow() - timedelta(seconds=10)
    )
    await setup_integration(hass, simple_room_motion="off", simple_room_light="on")

    assert occupancy(hass) == "empty"
    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_off"


async def test_restored_timeout_motion(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """Motion after the restart cancels the restored timeout."""
    restore_occupancy(
        hass, "occupied_timeout", dt_util.utcnow() + timedelta(seconds=60)
    )
    await setup_integration(hass, simple_room_motion="on")
    assert occupancy(hass) == "occupied"

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=61))
    await flush(hass)
    assert occupancy(hass) == "occupied"


async def test_restored_timeout_without_deadline(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """With no deadline saved, the timeout starts over, as it used to."""
    restore_occupancy(hass, "occupied_timeout")
    await setup_integration(hass, simple_room_motion="off")
    assert occupancy(hass) == "occupied_timeout"

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=90))
    await flush(hass)
    assert occupancy(hass) == "occupied_timeout"

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=181))
    await flush(hass)
    assert occupancy(hass) == "empty"


async def test_restored_occupied_starts_timeout(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """Occupied, with no motion after the restart, starts a whole timeout.

    When the motion stopped isn't known, so this is the safe choice.
    """
    restore_occupancy(hass, "occupied")
    await setup_integration(hass, simple_room_motion="off")
    assert occupancy(hass) == "occupied_timeout"

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=181))
    await flush(hass)
    assert occupancy(hass) == "empty"


async def test_deadline_is_saved(hass: HomeAssistant, light_service_calls):
    """The deadline is saved while a timeout runs, and cleared after."""
    await setup_integration(hass)
    component = hass.data[entity_component.DATA_INSTANCES]["sensor"]
    entity = component.get_entity(SIMPLE_ROOM_OCCUPANCY)

    def saved_deadline():
        return entity.extra_restore_state_data.as_dict()["no_motion_deadline"]

    assert saved_deadline() is None

    before = dt_util.utcnow()
    hass.states.async_set(SIMPLE_ROOM_MOTION, "off")
    await flush(hass)
    deadline = dt_util.parse_datetime(saved_deadline())
    assert deadline >= before + timedelta(seconds=180)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=181))
    await flush(hass)
    assert saved_deadline() is None


# --- Lights that aren't there yet ---


async def test_unavailable_light_is_set_when_it_loads(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """No call to an unavailable light; the call is made once it has a state."""
    await setup_integration(hass, simple_room_light="unavailable")
    assert find_calls(light_service_calls, SIMPLE_ROOM_LIGHT) == []

    hass.states.async_set(SIMPLE_ROOM_LIGHT, "off")
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

    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_on"
    assert call.data.get("brightness_pct") == 100


async def test_unknown_light_is_set_when_it_reports(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """A light with no known state is set again once it reports one.

    Its calls go through (it is available), but a profile whose `enabled`
    isn't set only acts on a light that is on, so it is applied again then.
    """
    await setup_integration(hass, simple_room_light="unknown")
    before = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    hass.states.async_set(SIMPLE_ROOM_LIGHT, "on")
    await flush(hass)

    calls = find_calls(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert len(calls) == before + 1
    assert calls[-1].service == "turn_on"


async def test_light_on_off_is_left_alone(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
):
    """A light changed by hand isn't set back: only coming back counts."""
    await setup_integration(hass)
    before = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    hass.states.async_set(SIMPLE_ROOM_LIGHT, "on")
    await flush(hass)
    hass.states.async_set(SIMPLE_ROOM_LIGHT, "off")
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
