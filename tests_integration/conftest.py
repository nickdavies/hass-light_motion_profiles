"""Integration test configuration and fixtures.

Uses pytest-homeassistant-custom-component for realistic HA testing.
"""

import pathlib
from typing import Any

import pytest
from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import SERVICE_TURN_ON, SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.loader import DATA_CUSTOM_COMPONENTS
from homeassistant.setup import async_setup_component


DOMAIN = "light_motion_profiles"

# Simplified test config with templates, mirroring real-world patterns.
# Uses generic names (user_a, user_b, simple_room, bedside_lamp).
TEST_CONFIG: dict[str, Any] = {
    DOMAIN: {
        "settings": {
            "room": {
                "valid_room_states": ["auto", "manual"],
            },
            "user_group": {
                "valid_person_states": ["awake", "winddown", "asleep"],
            },
        },
        "users": {
            "user_a": {
                "guest": False,
                "tracking_entity": "person.user_a",
                "icons_state": {
                    "awake": "mdi:human",
                    "winddown": "mdi:sleep",
                    "asleep": "mdi:bed",
                    "absent": "mdi:cancel",
                },
                "icons_home_away": {
                    "auto": "mdi:auto-fix",
                    "home": "mdi:home",
                    "not_home": "mdi:home-off",
                    "unknown": "mdi:home-search",
                },
            },
            "user_b": {
                "guest": True,
                "icon_exists": "mdi:account-question",
                "icons_state": {
                    "awake": "mdi:account-clock",
                    "winddown": "mdi:arrow-down-bold-box",
                    "asleep": "mdi:bed-double",
                    "absent": "mdi:cancel",
                },
            },
        },
        "groups": {
            "everyone": ["user_a", "user_b"],
        },
        "light_profiles": {
            "enabled": {
                "enabled": True,
                "icon": "mdi:lightbulb-on",
            },
            "disabled": {
                "enabled": False,
                "icon": "mdi:lightbulb-off",
            },
            "disable_slowly": {
                "enabled": False,
                "icon": "mdi:transfer-down",
                "transition": 10,
            },
            "full": {
                "enabled": True,
                "brightness_pct": 100,
                "icon": "mdi:weather-sunny",
            },
            "dim": {
                "enabled": True,
                "brightness_pct": 25,
                "icon": "mdi:lamp",
            },
            "extra_dim": {
                "enabled": True,
                "brightness_pct": 10,
                "icon": "mdi:lamp",
            },
            "nightlight": {
                "enabled": True,
                "brightness_pct": 5,
                "icon": "mdi:weather-night",
            },
            "noop": {},
        },
        "templates": {
            "light_config_rules": {
                "default_rules": {
                    "inputs": ["users"],
                    "template": [
                        {
                            "state_name": "absent",
                            "room_state": "auto",
                            "occupancy": "*",
                            "user_state": [
                                {"user": "{users}", "state_exact": "absent"},
                            ],
                            "light_profile": "disabled",
                        },
                        {
                            "state_name": "empty",
                            "room_state": "auto",
                            "occupancy": "empty",
                            "user_state": "*",
                            "light_profile": "disable_slowly",
                        },
                        {
                            "state_name": "manual",
                            "room_state": "manual",
                            "occupancy": "*",
                            "user_state": "*",
                            "light_profile": "noop",
                        },
                        {
                            "state_name": "unknown_occ",
                            "room_state": "*",
                            "occupancy": "unknown",
                            "user_state": "*",
                            "light_profile": "noop",
                        },
                    ],
                },
                "prefer_awake": {
                    "inputs": ["users"],
                    "template": [
                        {
                            "state_name": "someone_awake",
                            "room_state": "auto",
                            "occupancy": ["occupied", "occupied_timeout"],
                            "user_state": [
                                {"user": "{users}", "state_any": "awake"},
                            ],
                            "light_profile": "full",
                        },
                        {
                            "state_name": "someone_winddown",
                            "room_state": "auto",
                            "occupancy": ["occupied", "occupied_timeout"],
                            "user_state": [
                                {"user": "{users}", "state_any": "winddown"},
                            ],
                            "light_profile": "dim",
                        },
                        {
                            "state_name": "someone_asleep",
                            "room_state": "auto",
                            "occupancy": ["occupied", "occupied_timeout"],
                            "user_state": [
                                {"user": "{users}", "state_any": "asleep"},
                            ],
                            "light_profile": "disabled",
                        },
                    ],
                },
                "bedside": {
                    "inputs": ["owner", "other"],
                    "template": [
                        {
                            "state_name": "nightlight_bedside",
                            "room_state": "auto",
                            "occupancy": ["occupied", "occupied_timeout"],
                            "user_state": [
                                {"user": "{owner}", "state_exact": "winddown"},
                                {"user": "{other}", "state_exact": "asleep"},
                            ],
                            "light_profile": "extra_dim",
                        },
                    ],
                },
            },
        },
        "light_configs": {
            "simple_room": {
                "lights": "light.simple_room",
                "occupancy_sensors": "binary_sensor.simple_room_motion",
                "occupancy_timeout": 180,
                "user": "everyone",
                "light_profile_rules": [
                    {"template": "default_rules", "values": {"users": "everyone"}},
                    {"template": "prefer_awake", "values": {"users": "everyone"}},
                ],
            },
            "bedside_lamp": {
                "lights": "light.bedside",
                "occupancy_sensors": "binary_sensor.bedside_motion",
                "occupancy_timeout": 180,
                "user": "everyone",
                "light_profile_rules": [
                    {"template": "default_rules", "values": {"users": "everyone"}},
                    {
                        "template": "bedside",
                        "values": {"owner": "user_a", "other": "user_b"},
                    },
                    {"template": "prefer_awake", "values": {"users": "everyone"}},
                ],
            },
        },
    },
}

# --- Entity ID constants ---
# Users
USER_A_OVERRIDE = "select.user_a_status_override"
USER_A_STATE = "select.person_user_a_awake_state"
USER_A_HOME_AWAY = "sensor.person_user_a"
USER_A_PRESENCE = "sensor.person_presence_user_a"

USER_B_OVERRIDE = "select.user_b_status_override"
USER_B_STATE = "select.person_user_b_awake_state"
USER_B_PRESENCE = "sensor.person_presence_user_b"
USER_B_EXISTS = "switch.person_user_b_exists"

GROUP_PRESENCE = "sensor.group_presence_everyone"

# Simple room
SIMPLE_ROOM_MOTION = "binary_sensor.simple_room_motion"
SIMPLE_ROOM_OCCUPANCY = "sensor.light_binding_occupancy_simple_room"
SIMPLE_ROOM_RULE = "sensor.light_binding_rule_simple_room"
SIMPLE_ROOM_AUTOMATION = "sensor.light_binding_automation_simple_room"
SIMPLE_ROOM_KS = "switch.killswitch_motion_simple_room"
SIMPLE_ROOM_LIGHT = "light.simple_room"

# Bedside lamp
BEDSIDE_MOTION = "binary_sensor.bedside_motion"
BEDSIDE_OCCUPANCY = "sensor.light_binding_occupancy_bedside_lamp"
BEDSIDE_RULE = "sensor.light_binding_rule_bedside_lamp"
BEDSIDE_AUTOMATION = "sensor.light_binding_automation_bedside_lamp"
BEDSIDE_LIGHT = "light.bedside"

# Global
GLOBAL_KS = "switch.killswitch_motion_global"

# Tracking entity
PERSON_USER_A = "person.user_a"


async def set_select(hass: HomeAssistant, entity_id: str, option: str) -> None:
    """Set a select entity's value using the HA service (not direct state set)."""
    await hass.services.async_call(
        "select",
        "select_option",
        {"entity_id": entity_id, "option": option},
        blocking=True,
    )


async def set_switch(hass: HomeAssistant, entity_id: str, on: bool) -> None:
    """Toggle a switch entity using the HA service."""
    await hass.services.async_call(
        "switch",
        "turn_on" if on else "turn_off",
        {"entity_id": entity_id},
        blocking=True,
    )


async def flush(hass: HomeAssistant, rounds: int = 10) -> None:
    """Flush the HA event loop multiple times to propagate cascading entity updates.

    The entity chain has multiple async levels:
      select → home_away sensor → presence sensor → group sensor → rule → automation → service call
    Each level uses schedule_update_ha_state() (async task), and the automation
    level additionally creates a task via async_create_task for the service call.
    We need enough rounds for the full chain to settle.
    """
    for _ in range(rounds):
        await hass.async_block_till_done()


def _ensure_custom_components_path():
    """Ensure our project's custom_components is on the namespace path.

    The pytest-homeassistant-custom-component plugin overrides the
    custom_components namespace package path to its own testing_config directory.
    We need our project's custom_components to be discoverable too.
    """
    import custom_components

    project_cc = str(pathlib.Path(__file__).parent.parent / "custom_components")
    if project_cc not in custom_components.__path__:
        custom_components.__path__.insert(0, project_cc)


@pytest.fixture
async def light_service_calls(hass: HomeAssistant) -> list[ServiceCall]:
    """Register mock light services and return list of captured calls."""
    calls: list[ServiceCall] = []

    async def mock_service(call: ServiceCall) -> None:
        calls.append(call)

    hass.services.async_register(LIGHT_DOMAIN, SERVICE_TURN_ON, mock_service)
    hass.services.async_register(LIGHT_DOMAIN, SERVICE_TURN_OFF, mock_service)
    return calls


@pytest.fixture
async def integration(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
) -> HomeAssistant:
    """Set up the integration with test config and pre-create external entities."""
    # Pre-create external entities that the integration reads from.
    # Motion sensors start "on" to avoid creating occupancy timeout timers
    # during setup. Individual tests change states as needed.
    hass.states.async_set(PERSON_USER_A, "home")
    hass.states.async_set(SIMPLE_ROOM_MOTION, "on")
    hass.states.async_set(BEDSIDE_MOTION, "on")
    hass.states.async_set(SIMPLE_ROOM_LIGHT, "off")
    hass.states.async_set(BEDSIDE_LIGHT, "off")

    # Allow HA to discover our custom component
    hass.data.pop(DATA_CUSTOM_COMPONENTS, None)
    _ensure_custom_components_path()

    result = await async_setup_component(hass, DOMAIN, TEST_CONFIG)
    assert result, "Integration setup failed"
    await hass.async_block_till_done()

    # Set initial states using HA services so the entities properly track the
    # values (direct hass.states.async_set bypasses entity attrs and gets overwritten).
    await set_select(hass, USER_A_OVERRIDE, "auto")
    await set_select(hass, USER_A_STATE, "awake")
    await set_select(hass, USER_B_OVERRIDE, "auto")
    await set_switch(hass, USER_B_EXISTS, False)
    await set_select(hass, USER_B_STATE, "awake")
    # The chain: selects → home_away → presence → group → rule → automation
    # Each level is async, so flush multiple times.
    await flush(hass)

    return hass
