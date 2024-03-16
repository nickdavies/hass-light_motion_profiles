from typing import Mapping, Any

from homeassistant.const import STATE_ON

from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.components.switch import SwitchEntity, DOMAIN as SWITCH_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback


from .datatypes import Config, User, Entity


async def async_setup_platform(
    hass: HomeAssistant,
    raw_config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    config: Config,
) -> None:
    user_switches = []
    for user in config.users_groups.users.values():
        if user.guest:
            user_switches.append(GuestExistsSwitch(user))

    async_add_entities(user_switches)

    ks_settings = config.settings.killswitch

    killswitches = []
    killswitches.append(
        KillSwitch(config.global_killswitch_entity, icon=ks_settings.global_icon)
    )

    killswitch_icon = ks_settings.default_icon
    for light_config in config.lights.values():
        killswitches.append(
            KillSwitch(light_config.killswitch_entity, icon=killswitch_icon)
        )

    async_add_entities(killswitches)


class _BasicSwitch(SwitchEntity):
    def turn_on(self, **kwargs: Mapping[Any, Any]) -> None:
        self._attr_is_on = True

    def turn_off(self, **kwargs: Mapping[Any, Any]) -> None:
        self._attr_is_on = False


class GuestExistsSwitch(_BasicSwitch, RestoreEntity):
    def __init__(self, user: User) -> None:
        entity = user.exists_entity
        assert entity.domain.value == SWITCH_DOMAIN
        self._attr_name = entity.name
        self._attr_icon = user.exists_icon

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if not (last_state := await self.async_get_last_state()):
            return
        self._attr_is_on = last_state.state == STATE_ON


class KillSwitch(_BasicSwitch, RestoreEntity):
    def __init__(self, entity: Entity, icon: str | None) -> None:
        assert entity.domain.value == SWITCH_DOMAIN
        self._attr_name = entity.name
        self._attr_icon = icon

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        if not (last_state := await self.async_get_last_state()):
            return
        self._attr_is_on = last_state.state == STATE_ON
