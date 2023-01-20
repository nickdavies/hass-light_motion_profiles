from .entity_names import (
    person_exists_entity,
)
from . import (
    FIELD_USERS,
    FIELD_GUEST,
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
    user_sensors = []
    for user, user_config in discovery_info.get(FIELD_USERS, {}).items():
        if user_config.get(FIELD_GUEST, False):
            user_sensors.append(GuestExistsSwitch(user))

    async_add_entities(user_sensors)


class GuestExistsSwitch(SwitchEntity, RestoreEntity):
    def __init__(self, name):
        self._attr_name = person_exists_entity(name, without_domain=True)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if not (last_state := await self.async_get_last_state()):
            return
        self._attr_is_on = last_state.state == STATE_ON

    def turn_on(self, **kwargs):
        self._attr_is_on = True

    def turn_off(self, **kwargs):
        self._attr_is_on = False
