from typing import Any, Dict, Mapping, Set

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    DOMAIN as BS_DOMAIN,
)
from homeassistant.const import STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .sensor import CalculatedSensor, GroupPresenceSensor
from .datatypes import Config, LightGroup, PresenceOutput, UsersGroups


async def async_setup_platform(
    hass: HomeAssistant,
    raw_config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    config: Config,
) -> None:
    motion_groups = []
    for light_config in config.lights.values():
        if isinstance(light_config.occupancy_sensors, list):
            motion_groups.append(MotionGroup(light_config))

    async_add_entities(motion_groups)

    async_add_entities(
        [
            PresenceOutputSensor(output, config.users_groups)
            for output in config.presence_outputs.values()
        ]
    )


class MotionGroup(CalculatedSensor[bool], BinarySensorEntity):
    PRIMARY_ATTR = "_attr_is_on"

    def __init__(self, config: LightGroup) -> None:
        super().__init__()

        entity = config.motion_sensor_group_entity
        assert entity.domain.value == BS_DOMAIN
        assert isinstance(config.occupancy_sensors, list)

        self._attr_name = entity.name
        self._attr_unique_id = entity.name
        self._attr_device_class = BinarySensorDeviceClass.MOTION
        self._dependent_entities = [e.entity for e in config.occupancy_sensors]

    def calculate_current_state(self) -> bool:
        for entity in self._dependent_entities:
            state = self.hass.states.get(entity)
            if state is not None and state.state == STATE_ON:
                return True
        return False


class PresenceOutputSensor(CalculatedSensor[bool | None], BinarySensorEntity):
    """One presence output: on while its rule holds.

    Unknown, rather than off, when any presence it reads is missing or
    unavailable. A consumer cannot tell a false "nobody is asleep" from a real
    one, and each should decide for itself which way a broken input fails.
    """

    PRIMARY_ATTR = "_attr_is_on"

    def __init__(self, output: PresenceOutput, users_groups: UsersGroups) -> None:
        super().__init__()

        entity = output.entity
        assert entity.domain.value == BS_DOMAIN

        self._attr_name = entity.name
        self._output = output
        self._input_entities = {
            user: users_groups.presence_entity(user).full
            for user in sorted(output.get_users())
        }
        self._dependent_entities = list(self._input_entities.values())
        self._attr_extra_state_attributes: Mapping[str, Any] = {}

    def calculate_current_state(self) -> bool | None:
        raw: Dict[str, str | None] = {}
        user_states: Dict[str, str | Set[str]] = {}
        for user, entity_id in self._input_entities.items():
            state = self.hass.states.get(entity_id)
            value = state.state if state is not None else None
            raw[user] = value
            if value is not None and value not in (STATE_UNKNOWN, STATE_UNAVAILABLE):
                user_states[user] = GroupPresenceSensor.deserialize(value)

        # Which inputs it saw, so "why is this on" is answered on the entity.
        self._attr_extra_state_attributes = {"inputs": raw}

        if len(user_states) != len(self._input_entities):
            return None
        return self._output.match(user_states)
