from typing import Set, List

from .datatypes import Config, User
from .config.settings import HomeAwayStates

from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.components.select import SelectEntity, DOMAIN as SELECT_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_platform(
    hass: HomeAssistant,
    raw_config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    config: Config,
) -> None:
    user_sensors: List[SelectEntity] = []
    for user in config.users_groups.users.values():
        user_sensors.append(
            HomeAwaySelect(
                user,
                home_away_states=config.settings.users_groups.home_away_states,
            )
        )
        user_sensors.append(
            PersonStateSelect(
                user,
                person_states=config.settings.users_groups.valid_person_states,
            )
        )

    async_add_entities(user_sensors)


class HomeAwaySelect(SelectEntity, RestoreEntity):
    def __init__(self, user: User, home_away_states: HomeAwayStates) -> None:
        entity = user.home_away_override_entity
        assert entity.domain.value == SELECT_DOMAIN

        self._attr_name = entity.name
        self._attr_options = list(home_away_states.all_states())
        self._attr_current_option: str | None = None
        self._icons = user.home_away_icons

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if self.current_option is not None:
            return

        state = await self.async_get_last_state()
        if not state or state.state not in self.options:
            self._attr_current_option = None
        else:
            self.select_option(state.state)

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        self._attr_current_option = option
        self._attr_icon = self._icons.get(option)


class PersonStateSelect(SelectEntity, RestoreEntity):
    def __init__(self, user: User, person_states: Set[str]):
        entity = user.state_entity
        assert entity.domain.value == SELECT_DOMAIN
        self._attr_name = entity.name
        self._attr_options = list(person_states)
        self._attr_current_option: str | None = None
        self._icons = user.state_icons

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if self.current_option is not None:
            return

        state = await self.async_get_last_state()
        if not state or state.state not in self.options:
            self._attr_current_option = None
        else:
            self.select_option(state.state)

    def select_option(self, option: str) -> None:
        """Change the selected option."""
        self._attr_current_option = option
        self._attr_icon = self._icons.get(option)
