"""Tests for the user presence and group presence entity chain.

Chain: PersonStateSelect + HomeAwaySelect + GuestExistsSwitch
       → UserHomeAwaySensor → UserPresenceSensor → GroupPresenceSensor
"""

from homeassistant.core import HomeAssistant

from .conftest import (
    USER_A_HOME_AWAY,
    USER_A_OVERRIDE,
    USER_A_PRESENCE,
    USER_A_STATE,
    USER_B_EXISTS,
    USER_B_OVERRIDE,
    USER_B_PRESENCE,
    USER_B_STATE,
    GROUP_PRESENCE,
    PERSON_USER_A,
    flush,
    set_select,
    set_switch,
)


async def test_user_awake(hass: HomeAssistant, integration):
    """User with tracking entity home + state awake → presence awake."""
    # Fixture already sets user_a to awake+home
    assert hass.states.get(USER_A_PRESENCE).state == "awake"


async def test_user_winddown(hass: HomeAssistant, integration):
    """User state winddown → presence winddown."""
    await set_select(hass, USER_A_STATE, "winddown")
    await flush(hass)

    assert hass.states.get(USER_A_PRESENCE).state == "winddown"


async def test_user_asleep(hass: HomeAssistant, integration):
    """User state asleep → presence asleep."""
    await set_select(hass, USER_A_STATE, "asleep")
    await flush(hass)

    assert hass.states.get(USER_A_PRESENCE).state == "asleep"


async def test_user_not_home_override(hass: HomeAssistant, integration):
    """Setting home/away override to not_home → presence absent."""
    await set_select(hass, USER_A_OVERRIDE, "not_home")
    await flush(hass)

    assert hass.states.get(USER_A_HOME_AWAY).state == "not_home"
    assert hass.states.get(USER_A_PRESENCE).state == "absent"


async def test_user_override_home_overrides_tracking(hass: HomeAssistant, integration):
    """Override 'home' takes precedence over tracking entity showing not_home."""
    hass.states.async_set(PERSON_USER_A, "not_home")
    await set_select(hass, USER_A_OVERRIDE, "home")
    await flush(hass)

    assert hass.states.get(USER_A_HOME_AWAY).state == "home"
    assert hass.states.get(USER_A_PRESENCE).state == "awake"


async def test_user_tracking_not_home(hass: HomeAssistant, integration):
    """Tracking entity not_home (no override) → presence absent."""
    hass.states.async_set(PERSON_USER_A, "not_home")
    await set_select(hass, USER_A_OVERRIDE, "auto")
    await flush(hass)

    assert hass.states.get(USER_A_HOME_AWAY).state == "not_home"
    assert hass.states.get(USER_A_PRESENCE).state == "absent"


async def test_guest_not_exists(hass: HomeAssistant, integration):
    """Guest with exists switch off → presence absent regardless of state."""
    # Fixture default: user_b exists=off
    assert hass.states.get(USER_B_PRESENCE).state == "absent"


async def test_guest_exists_awake(hass: HomeAssistant, integration):
    """Guest with exists=on, override=home, state=awake → presence awake."""
    await set_switch(hass, USER_B_EXISTS, True)
    await set_select(hass, USER_B_OVERRIDE, "home")
    await set_select(hass, USER_B_STATE, "awake")
    await flush(hass)

    assert hass.states.get(USER_B_PRESENCE).state == "awake"


async def test_guest_exists_winddown(hass: HomeAssistant, integration):
    """Guest with exists=on, override=home, state=winddown → presence winddown."""
    await set_switch(hass, USER_B_EXISTS, True)
    await set_select(hass, USER_B_OVERRIDE, "home")
    await set_select(hass, USER_B_STATE, "winddown")
    await flush(hass)

    assert hass.states.get(USER_B_PRESENCE).state == "winddown"


# --- Group presence tests ---


async def test_group_one_awake_one_absent(hass: HomeAssistant, integration):
    """One user awake + guest absent → group shows awake."""
    # Fixture default: user_a=awake, user_b=absent
    assert hass.states.get(GROUP_PRESENCE).state == "awake"


async def test_group_mixed_states(hass: HomeAssistant, integration):
    """User awake + guest winddown → group shows both states."""
    await set_switch(hass, USER_B_EXISTS, True)
    await set_select(hass, USER_B_OVERRIDE, "home")
    await set_select(hass, USER_B_STATE, "winddown")
    await flush(hass)

    group_state = hass.states.get(GROUP_PRESENCE).state
    states = set(group_state.split(","))
    assert states == {"awake", "winddown"}


async def test_group_all_absent(hass: HomeAssistant, integration):
    """Both users absent → group shows absent."""
    hass.states.async_set(PERSON_USER_A, "not_home")
    await set_select(hass, USER_A_OVERRIDE, "auto")
    await set_switch(hass, USER_B_EXISTS, False)
    await flush(hass)

    assert hass.states.get(GROUP_PRESENCE).state == "absent"


async def test_group_both_awake(hass: HomeAssistant, integration):
    """Both users awake → group shows awake (deduplicated)."""
    await set_switch(hass, USER_B_EXISTS, True)
    await set_select(hass, USER_B_OVERRIDE, "home")
    await set_select(hass, USER_B_STATE, "awake")
    await flush(hass)

    assert hass.states.get(GROUP_PRESENCE).state == "awake"
