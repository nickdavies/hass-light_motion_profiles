"""Tests for the occupancy lifecycle.

Chain: MotionSensor → RoomOccupancyEntity (with timeout timer)
States: occupied → occupied_timeout → empty
"""

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .conftest import (
    SIMPLE_ROOM_MOTION,
    SIMPLE_ROOM_OCCUPANCY,
    flush,
)


async def test_motion_on_occupied(hass: HomeAssistant, integration):
    """Motion ON → occupancy = occupied."""
    # Motion is already "on" from fixture setup
    assert hass.states.get(SIMPLE_ROOM_OCCUPANCY).state == "occupied"


async def test_motion_off_to_timeout(hass: HomeAssistant, integration):
    """Motion ON → OFF → occupancy = occupied_timeout."""
    hass.states.async_set(SIMPLE_ROOM_MOTION, "off")
    await flush(hass)

    assert hass.states.get(SIMPLE_ROOM_OCCUPANCY).state == "occupied_timeout"

    # Clean up timer by advancing past timeout
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=181))
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_OCCUPANCY).state == "empty"


async def test_timeout_to_empty(hass: HomeAssistant, integration):
    """Motion OFF → wait past timeout → occupancy = empty."""
    hass.states.async_set(SIMPLE_ROOM_MOTION, "off")
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_OCCUPANCY).state == "occupied_timeout"

    # Advance time past the 180s timeout
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=181))
    await flush(hass)

    assert hass.states.get(SIMPLE_ROOM_OCCUPANCY).state == "empty"


async def test_motion_cancels_timeout(hass: HomeAssistant, integration):
    """Motion OFF → partial wait → motion ON → occupied, timer cancelled."""
    hass.states.async_set(SIMPLE_ROOM_MOTION, "off")
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_OCCUPANCY).state == "occupied_timeout"

    # Motion ON again - should cancel timer and go back to occupied
    hass.states.async_set(SIMPLE_ROOM_MOTION, "on")
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_OCCUPANCY).state == "occupied"

    # Advance past original timeout — should still be occupied (timer was cancelled)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=200))
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_OCCUPANCY).state == "occupied"


async def test_motion_stays_timeout_during_wait(hass: HomeAssistant, integration):
    """During timeout period, occupancy stays occupied_timeout."""
    hass.states.async_set(SIMPLE_ROOM_MOTION, "off")
    await flush(hass)

    # Advance 90s — still within 180s timeout
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=90))
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_OCCUPANCY).state == "occupied_timeout"

    # Clean up: advance past timeout
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=200))
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_OCCUPANCY).state == "empty"
