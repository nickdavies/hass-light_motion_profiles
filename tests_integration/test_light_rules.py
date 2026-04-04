"""Tests for end-to-end light rule matching.

Chain: Occupancy + UserPresence/GroupPresence → LightRuleEntity
"""

from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from pytest_homeassistant_custom_component.common import async_fire_time_changed

from .conftest import (
    USER_A_OVERRIDE,
    USER_A_STATE,
    USER_B_EXISTS,
    USER_B_OVERRIDE,
    USER_B_STATE,
    PERSON_USER_A,
    SIMPLE_ROOM_MOTION,
    SIMPLE_ROOM_OCCUPANCY,
    SIMPLE_ROOM_RULE,
    BEDSIDE_RULE,
    flush,
    set_select,
    set_switch,
)


# --- Simple room rules (default_rules + prefer_awake with group "everyone") ---


async def test_awake_occupied(hass: HomeAssistant, integration):
    """Occupied + user awake → someone_awake rule (full)."""
    # Fixture default: user_a awake, motion on (occupied)
    assert hass.states.get(SIMPLE_ROOM_RULE).state == "someone_awake"


async def test_winddown_occupied(hass: HomeAssistant, integration):
    """Occupied + user winddown → someone_winddown rule (dim)."""
    await set_select(hass, USER_A_STATE, "winddown")
    await flush(hass)

    assert hass.states.get(SIMPLE_ROOM_RULE).state == "someone_winddown"


async def test_asleep_occupied(hass: HomeAssistant, integration):
    """Occupied + user asleep → someone_asleep rule (disabled)."""
    await set_select(hass, USER_A_STATE, "asleep")
    await flush(hass)

    assert hass.states.get(SIMPLE_ROOM_RULE).state == "someone_asleep"


async def test_absent_occupied(hass: HomeAssistant, integration):
    """Occupied + all users absent → absent rule (disabled)."""
    hass.states.async_set(PERSON_USER_A, "not_home")
    await set_select(hass, USER_A_OVERRIDE, "auto")
    await set_switch(hass, USER_B_EXISTS, False)
    await flush(hass)

    assert hass.states.get(SIMPLE_ROOM_RULE).state == "absent"


async def test_empty_room(hass: HomeAssistant, integration):
    """Empty room → empty rule (disable_slowly)."""
    hass.states.async_set(SIMPLE_ROOM_MOTION, "off")
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_OCCUPANCY).state == "occupied_timeout"

    # Advance past timeout to get to "empty"
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=181))
    await flush(hass)

    assert hass.states.get(SIMPLE_ROOM_OCCUPANCY).state == "empty"
    assert hass.states.get(SIMPLE_ROOM_RULE).state == "empty"


async def test_awake_wins_over_winddown(hass: HomeAssistant, integration):
    """With prefer_awake, if any user is awake the room is full even if another is winddown."""
    await set_switch(hass, USER_B_EXISTS, True)
    await set_select(hass, USER_B_OVERRIDE, "home")
    await set_select(hass, USER_B_STATE, "winddown")
    # user_a is still awake from fixture
    await flush(hass)

    assert hass.states.get(SIMPLE_ROOM_RULE).state == "someone_awake"


async def test_awake_wins_over_asleep(hass: HomeAssistant, integration):
    """With prefer_awake, awake wins over asleep."""
    await set_switch(hass, USER_B_EXISTS, True)
    await set_select(hass, USER_B_OVERRIDE, "home")
    await set_select(hass, USER_B_STATE, "asleep")
    # user_a is still awake
    await flush(hass)

    assert hass.states.get(SIMPLE_ROOM_RULE).state == "someone_awake"


# --- Bedside lamp rules (default_rules + bedside + prefer_awake) ---


async def test_bedside_cross_user_rule(hass: HomeAssistant, integration):
    """Owner (user_a) winddown + other (user_b) asleep → nightlight_bedside."""
    await set_select(hass, USER_A_STATE, "winddown")
    await set_switch(hass, USER_B_EXISTS, True)
    await set_select(hass, USER_B_OVERRIDE, "home")
    await set_select(hass, USER_B_STATE, "asleep")
    await flush(hass)

    assert hass.states.get(BEDSIDE_RULE).state == "nightlight_bedside"


async def test_bedside_both_winddown_no_bedside(hass: HomeAssistant, integration):
    """Both winddown → someone_winddown (bedside requires exact owner=winddown + other=asleep)."""
    await set_select(hass, USER_A_STATE, "winddown")
    await set_switch(hass, USER_B_EXISTS, True)
    await set_select(hass, USER_B_OVERRIDE, "home")
    await set_select(hass, USER_B_STATE, "winddown")
    await flush(hass)

    assert hass.states.get(BEDSIDE_RULE).state == "someone_winddown"


async def test_bedside_awake_wins(hass: HomeAssistant, integration):
    """Owner awake + other asleep → someone_awake (prefer_awake wins, bedside needs winddown)."""
    await set_select(hass, USER_A_STATE, "awake")
    await set_switch(hass, USER_B_EXISTS, True)
    await set_select(hass, USER_B_OVERRIDE, "home")
    await set_select(hass, USER_B_STATE, "asleep")
    await flush(hass)

    assert hass.states.get(BEDSIDE_RULE).state == "someone_awake"
