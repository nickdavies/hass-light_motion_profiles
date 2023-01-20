from .entity_names import (
    person_override_home_away_entity,
    person_state_entity,
)
from .schema_users_groups import (
    FIELD_USERS,
)

from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

HOME_AWAY_STATES = {
    "auto",
    "unknown",
    "home",
    "not_home",
}

PERSON_STATES = {
    "awake",
    "winddown",
    "asleep",
}


async def async_setup_platform(
    hass: HomeAssistant,
    whole_config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info,
) -> None:
    user_sensors = []
    for user, user_config in discovery_info.get(FIELD_USERS, {}).items():
        user_sensors.append(HomeAwaySelect(user))
        user_sensors.append(PersonStateSelect(user))

    async_add_entities(user_sensors)


class HomeAwaySelect(SelectEntity, RestoreEntity):
    def __init__(self, name):
        self._attr_name = person_override_home_away_entity(name, without_domain=True)
        self._attr_options = list(HOME_AWAY_STATES)
        self._attr_current_option = None

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if self.current_option is not None:
            return

        state = await self.async_get_last_state()
        if not state or state.state not in self.options:
            self._attr_current_option = None
        else:
            self._attr_current_option = state.state

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        self._attr_current_option = option


class PersonStateSelect(SelectEntity, RestoreEntity):
    def __init__(self, name):
        self._attr_name = person_state_entity(name, without_domain=True)
        self._attr_options = list(PERSON_STATES)
        self._attr_current_option = None

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if self.current_option is not None:
            return

        state = await self.async_get_last_state()
        if not state or state.state not in self.options:
            self._attr_current_option = None
        else:
            self._attr_current_option = state.state

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        self._attr_current_option = option
