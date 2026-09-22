"""Tests for presence outputs: presence rules published as binary sensors.

Chain: UserPresenceSensor → GroupPresenceSensor → PresenceOutputSensor
"""

from homeassistant.core import HomeAssistant

from .conftest import (
    EVERYONE_ANY_ASLEEP,
    EVERYONE_ANY_AWAKE,
    GROUP_PRESENCE,
    HOUSE_EMPTY,
    USER_A_OVERRIDE,
    USER_A_STATE,
    USER_B_EXISTS,
    USER_B_OVERRIDE,
    USER_B_STATE,
    flush,
    set_select,
    set_switch,
)


async def test_one_awake_user(hass: HomeAssistant, integration):
    """Fixture: user_a awake, guest user_b absent."""
    assert hass.states.get(EVERYONE_ANY_AWAKE).state == "on"
    assert hass.states.get(EVERYONE_ANY_ASLEEP).state == "off"
    assert hass.states.get(HOUSE_EMPTY).state == "off"


async def test_guest_asleep_while_user_awake(hass: HomeAssistant, integration):
    """The case that motivated outputs: one person up, a guest asleep."""
    await set_switch(hass, USER_B_EXISTS, True)
    await set_select(hass, USER_B_OVERRIDE, "home")
    await set_select(hass, USER_B_STATE, "asleep")
    await flush(hass)

    assert hass.states.get(EVERYONE_ANY_ASLEEP).state == "on"
    assert hass.states.get(EVERYONE_ANY_AWAKE).state == "on"


async def test_absent_guest_is_ignored(hass: HomeAssistant, integration):
    """A guest who is not staying cannot be asleep in the house."""
    await set_select(hass, USER_B_STATE, "asleep")
    await flush(hass)

    assert hass.states.get(EVERYONE_ANY_ASLEEP).state == "off"


async def test_everyone_absent(hass: HomeAssistant, integration):
    await set_select(hass, USER_A_OVERRIDE, "not_home")
    await flush(hass)

    assert hass.states.get(GROUP_PRESENCE).state == "absent"
    assert hass.states.get(EVERYONE_ANY_AWAKE).state == "off"
    assert hass.states.get(EVERYONE_ANY_ASLEEP).state == "off"
    assert hass.states.get(HOUSE_EMPTY).state == "on"


async def test_winddown_is_neither(hass: HomeAssistant, integration):
    await set_select(hass, USER_A_STATE, "winddown")
    await flush(hass)

    assert hass.states.get(EVERYONE_ANY_AWAKE).state == "off"
    assert hass.states.get(EVERYONE_ANY_ASLEEP).state == "off"


async def test_inputs_are_exposed(hass: HomeAssistant, integration):
    """So "why is this on" is answered on the entity itself."""
    state = hass.states.get(EVERYONE_ANY_ASLEEP)
    assert state.attributes["inputs"] == {"everyone": "awake"}


async def test_unavailable_input_is_unknown(hass: HomeAssistant, integration):
    """Unknown rather than off, so each consumer picks its own failure mode."""
    hass.states.async_set(GROUP_PRESENCE, "unavailable")
    await flush(hass)

    assert hass.states.get(EVERYONE_ANY_ASLEEP).state == "unknown"
