"""Tests for light automation service calls, killswitch, and full lifecycle scenarios.

Chain: LightRuleEntity → LightAutomationEntity → light.turn_on/turn_off
"""

from datetime import timedelta

from homeassistant.core import HomeAssistant, ServiceCall
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
    SIMPLE_ROOM_AUTOMATION,
    SIMPLE_ROOM_KS,
    SIMPLE_ROOM_LIGHT,
    BEDSIDE_LIGHT,
    BEDSIDE_RULE,
    GLOBAL_KS,
    flush,
    set_select,
    set_switch,
)


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


# --- Service call tests ---


async def test_awake_turns_on_full(
    hass: HomeAssistant, integration, light_service_calls
):
    """Rule someone_awake → light.turn_on with brightness_pct=100."""
    await flush(hass)

    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_on"
    assert call.data.get("brightness_pct") == 100


async def test_winddown_turns_on_dim(
    hass: HomeAssistant, integration, light_service_calls
):
    """Rule someone_winddown → light.turn_on with brightness_pct=25."""
    await set_select(hass, USER_A_STATE, "winddown")
    await flush(hass)

    from .conftest import SIMPLE_ROOM_RULE

    assert hass.states.get(SIMPLE_ROOM_RULE).state == "someone_winddown"

    # Filter only simple_room light calls and check the last one
    # (the automation may re-fire during cascading state updates)
    calls = find_calls(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert len(calls) > 0
    # The last call should reflect the final settled state (winddown → dim)
    call = calls[-1]
    assert call.service == "turn_on"
    assert call.data.get("brightness_pct") == 25


async def test_asleep_turns_off(hass: HomeAssistant, integration, light_service_calls):
    """Rule someone_asleep → light.turn_off."""
    await set_select(hass, USER_A_STATE, "asleep")
    await flush(hass)

    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_off"


async def test_absent_turns_off(hass: HomeAssistant, integration, light_service_calls):
    """Rule absent → light.turn_off."""
    hass.states.async_set(PERSON_USER_A, "not_home")
    await set_select(hass, USER_A_OVERRIDE, "auto")
    await flush(hass)

    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_off"


async def test_empty_turns_off_with_transition(
    hass: HomeAssistant, integration, light_service_calls
):
    """Rule empty (disable_slowly) → light.turn_off with transition=10."""
    hass.states.async_set(SIMPLE_ROOM_MOTION, "off")
    await flush(hass)

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=181))
    await flush(hass)

    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_off"
    assert call.data.get("transition") == 10


async def test_no_transition_sends_zero(
    hass: HomeAssistant, integration, light_service_calls
):
    """Rules without transition must explicitly send transition=0.

    Regression test: previously, omitting transition meant HA would reuse the
    last transition value (e.g. 10s from disable_slowly), causing lights to
    fade out/in when they should snap immediately.
    """
    # First trigger disable_slowly so HA sees transition=10
    hass.states.async_set(SIMPLE_ROOM_MOTION, "off")
    await flush(hass)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=181))
    await flush(hass)
    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call.data.get("transition") == 10

    # Now trigger someone_awake (full profile — no transition configured)
    hass.states.async_set(SIMPLE_ROOM_MOTION, "on")
    await flush(hass)
    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None
    assert call.service == "turn_on"
    # Must explicitly send transition=0, not omit it
    assert call.data.get("transition") == 0


# --- Killswitch tests ---


async def test_local_killswitch_blocks(
    hass: HomeAssistant, integration, light_service_calls
):
    """Local killswitch on → no service call, display shows (local_ks)."""
    await flush(hass)
    # Record initial call count
    initial_count = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    await set_switch(hass, SIMPLE_ROOM_KS, True)
    await flush(hass)

    # Change state to trigger a new evaluation
    await set_select(hass, USER_A_STATE, "winddown")
    await flush(hass)

    # No new service call should have been made
    new_calls = find_calls(light_service_calls, SIMPLE_ROOM_LIGHT)[initial_count:]
    assert len(new_calls) == 0

    # Automation display should show the killswitch suffix
    auto_state = hass.states.get(SIMPLE_ROOM_AUTOMATION).state
    assert "(local_ks)" in auto_state


async def test_global_killswitch_blocks(
    hass: HomeAssistant, integration, light_service_calls
):
    """Global killswitch on → no service call, display shows (global_ks)."""
    await flush(hass)
    initial_count = len(find_calls(light_service_calls, SIMPLE_ROOM_LIGHT))

    await set_switch(hass, GLOBAL_KS, True)
    await flush(hass)

    await set_select(hass, USER_A_STATE, "winddown")
    await flush(hass)

    new_calls = find_calls(light_service_calls, SIMPLE_ROOM_LIGHT)[initial_count:]
    assert len(new_calls) == 0

    auto_state = hass.states.get(SIMPLE_ROOM_AUTOMATION).state
    assert "(global_ks)" in auto_state


# --- Full day lifecycle ---


async def test_full_day_lifecycle(
    hass: HomeAssistant, integration, light_service_calls
):
    """Full lifecycle: wake up, leave, return, guest arrives, bedtime.

    Step  | user_a         | user_b (guest)       | Motion | Expected Rule
    ------|----------------|---------------------|--------|-------------
    1     | awake, home    | absent (no exist)    | on     | someone_awake
    2     | leaves         | absent               | on     | absent
    3     | not_home       | absent               | off→empty | empty
    4     | returns home   | absent               | on     | someone_awake
    5     | home           | guest arrives, awake | on     | someone_awake
    6     | leaves again   | awake                | on     | someone_awake
    7     | not_home       | winddown             | on     | someone_winddown
    8     | returns, awake | winddown             | on     | someone_awake
    9     | winddown       | asleep               | on     | someone_winddown
    10    | asleep         | asleep               | on     | someone_asleep
    """
    from .conftest import SIMPLE_ROOM_RULE, SIMPLE_ROOM_OCCUPANCY

    # Step 1: user_a awake, home. Motion on (fixture default).
    assert hass.states.get(SIMPLE_ROOM_RULE).state == "someone_awake"
    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call is not None and call.service == "turn_on"
    assert call.data.get("brightness_pct") == 100

    # Step 2: user_a leaves
    hass.states.async_set(PERSON_USER_A, "not_home")
    await set_select(hass, USER_A_OVERRIDE, "auto")
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_RULE).state == "absent"
    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call.service == "turn_off"

    # Step 3: motion off → timeout → empty, but absent rule still wins
    # (absent rule has occupancy=* and matches before empty when all users gone)
    hass.states.async_set(SIMPLE_ROOM_MOTION, "off")
    await flush(hass)
    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=181))
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_OCCUPANCY).state == "empty"
    # When all users absent, "absent" rule matches regardless of occupancy
    assert hass.states.get(SIMPLE_ROOM_RULE).state == "absent"

    # Step 4: user_a returns home, motion on
    hass.states.async_set(PERSON_USER_A, "home")
    hass.states.async_set(SIMPLE_ROOM_MOTION, "on")
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_RULE).state == "someone_awake"
    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call.service == "turn_on"
    assert call.data.get("brightness_pct") == 100

    # Step 5: guest arrives (exists=on, override=home, state=awake)
    await set_switch(hass, USER_B_EXISTS, True)
    await set_select(hass, USER_B_OVERRIDE, "home")
    await set_select(hass, USER_B_STATE, "awake")
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_RULE).state == "someone_awake"

    # Step 6: user_a leaves again — user_b keeps lights on
    hass.states.async_set(PERSON_USER_A, "not_home")
    await set_select(hass, USER_A_OVERRIDE, "auto")
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_RULE).state == "someone_awake"

    # Step 7: user_b goes to winddown
    await set_select(hass, USER_B_STATE, "winddown")
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_RULE).state == "someone_winddown"
    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call.service == "turn_on"
    assert call.data.get("brightness_pct") == 25

    # Step 8: user_a returns, awake → awake wins
    hass.states.async_set(PERSON_USER_A, "home")
    await set_select(hass, USER_A_OVERRIDE, "auto")
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_RULE).state == "someone_awake"
    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call.service == "turn_on"
    assert call.data.get("brightness_pct") == 100

    # Step 9: user_a winddown, user_b asleep
    await set_select(hass, USER_A_STATE, "winddown")
    await set_select(hass, USER_B_STATE, "asleep")
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_RULE).state == "someone_winddown"
    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call.service == "turn_on"
    assert call.data.get("brightness_pct") == 25

    # Step 10: user_a asleep, user_b asleep
    await set_select(hass, USER_A_STATE, "asleep")
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_RULE).state == "someone_asleep"
    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call.service == "turn_off"


# --- Bedside cross-user lifecycle ---


async def test_bedside_lifecycle(hass: HomeAssistant, integration, light_service_calls):
    """Bedside lamp cross-user lifecycle.

    Step  | user_a (owner)  | user_b (other) | Expected Rule      | Light
    ------|----------------|---------------|--------------------|---------
    1     | awake          | awake          | someone_awake      | full
    2     | awake          | asleep         | someone_awake      | full
    3     | winddown       | asleep         | nightlight_bedside | extra_dim
    4     | asleep         | asleep         | someone_asleep     | off
    5     | winddown       | winddown       | someone_winddown   | dim
    """
    # Make both users present
    await set_switch(hass, USER_B_EXISTS, True)
    await set_select(hass, USER_B_OVERRIDE, "home")
    await set_select(hass, USER_B_STATE, "awake")
    await flush(hass)

    # Step 1: both awake
    assert hass.states.get(BEDSIDE_RULE).state == "someone_awake"
    call = last_call(light_service_calls, BEDSIDE_LIGHT)
    assert call.service == "turn_on"
    assert call.data.get("brightness_pct") == 100

    # Step 2: user_b asleep, user_a still awake → awake wins
    await set_select(hass, USER_B_STATE, "asleep")
    await flush(hass)
    assert hass.states.get(BEDSIDE_RULE).state == "someone_awake"

    # Step 3: user_a winddown, user_b asleep → bedside rule
    await set_select(hass, USER_A_STATE, "winddown")
    await flush(hass)
    assert hass.states.get(BEDSIDE_RULE).state == "nightlight_bedside"
    call = last_call(light_service_calls, BEDSIDE_LIGHT)
    assert call.service == "turn_on"
    assert call.data.get("brightness_pct") == 10

    # Step 4: both asleep
    await set_select(hass, USER_A_STATE, "asleep")
    await flush(hass)
    assert hass.states.get(BEDSIDE_RULE).state == "someone_asleep"
    call = last_call(light_service_calls, BEDSIDE_LIGHT)
    assert call.service == "turn_off"

    # Step 5: both winddown (no bedside match — needs exact states)
    await set_select(hass, USER_A_STATE, "winddown")
    await set_select(hass, USER_B_STATE, "winddown")
    await flush(hass)
    assert hass.states.get(BEDSIDE_RULE).state == "someone_winddown"
    call = last_call(light_service_calls, BEDSIDE_LIGHT)
    assert call.service == "turn_on"
    assert call.data.get("brightness_pct") == 25


# --- Guest toggle scenario ---


async def test_guest_exists_toggle(
    hass: HomeAssistant, integration, light_service_calls
):
    """Toggling guest exists changes group presence and light behavior.

    Step  | user_b exists | user_a | Expected Rule
    ------|--------------|--------|-------------
    1     | off          | absent | absent → disabled
    2     | on (awake)   | absent | someone_awake → full
    3     | off          | absent | absent → disabled
    """
    from .conftest import SIMPLE_ROOM_RULE

    # Step 1: user_a absent, user_b not existing → absent
    hass.states.async_set(PERSON_USER_A, "not_home")
    await set_select(hass, USER_A_OVERRIDE, "auto")
    await set_switch(hass, USER_B_EXISTS, False)
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_RULE).state == "absent"

    # Step 2: guest arrives → someone_awake
    await set_switch(hass, USER_B_EXISTS, True)
    await set_select(hass, USER_B_OVERRIDE, "home")
    await set_select(hass, USER_B_STATE, "awake")
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_RULE).state == "someone_awake"
    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call.service == "turn_on"

    # Step 3: guest leaves → absent again
    await set_switch(hass, USER_B_EXISTS, False)
    await flush(hass)
    assert hass.states.get(SIMPLE_ROOM_RULE).state == "absent"
    call = last_call(light_service_calls, SIMPLE_ROOM_LIGHT)
    assert call.service == "turn_off"
