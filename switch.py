from .entity_names import (
    person_exists_entity,
    killswitch_entity,
)
from .schema_users_groups import (
    FIELD_USERS,
    FIELD_GUEST,
    FIELD_EXISTS_ICON,
)
from .schema_motion_profiles import (
    MOTION_KILLSWITCH_GLOBAL,
    FIELD_LIGHT_BINDINGS,
    FIELD_LIGHT_PROFILE_SETTINGS,
    FIELD_ICON_KILLSWITCH,
    FIELD_ICON_GLOBAL_KILLSWITCH,
    DEFAULT_KILLSWITCH_ICON,
    DEFAULT_GLOBAL_KILLSWITCH_ICON,
)

from homeassistant.const import STATE_ON

from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_platform(
    hass: HomeAssistant,
    whole_config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info,
) -> None:
    user_switches = []
    for user, user_config in discovery_info.get(FIELD_USERS, {}).items():
        if user_config.get(FIELD_GUEST, False):
            user_switches.append(
                GuestExistsSwitch(user, user_config.get(FIELD_EXISTS_ICON))
            )

    async_add_entities(user_switches)

    killswitches = []

    settings = discovery_info.get(FIELD_LIGHT_PROFILE_SETTINGS, {})

    killswitches.append(
        KillSwitch(
            MOTION_KILLSWITCH_GLOBAL,
            icon=settings.get(
                FIELD_ICON_GLOBAL_KILLSWITCH,
                DEFAULT_GLOBAL_KILLSWITCH_ICON,
            ),
        )
    )

    killswitch_icon = settings.get(FIELD_ICON_KILLSWITCH, DEFAULT_KILLSWITCH_ICON)
    for binding_name, _ in discovery_info.get(FIELD_LIGHT_BINDINGS).items():
        killswitches.append(KillSwitch(binding_name, icon=killswitch_icon))

    async_add_entities(killswitches)


class _BasicSwitch(SwitchEntity):
    def turn_on(self, **kwargs):
        self._attr_is_on = True

    def turn_off(self, **kwargs):
        self._attr_is_on = False


class GuestExistsSwitch(_BasicSwitch, RestoreEntity):
    def __init__(self, name, icon):
        self._attr_name = person_exists_entity(name, without_domain=True)
        self._attr_icon = icon

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if not (last_state := await self.async_get_last_state()):
            return
        self._attr_is_on = last_state.state == STATE_ON


class KillSwitch(_BasicSwitch, RestoreEntity):
    def __init__(self, name, icon):
        self._attr_name = killswitch_entity(name, without_domain=True)
        self._attr_icon = icon

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if not (last_state := await self.async_get_last_state()):
            return
        self._attr_is_on = last_state.state == STATE_ON
