from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    BinarySensorEntity,
    DOMAIN as BS_DOMAIN,
)
from homeassistant.const import STATE_ON
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .sensor import CalculatedSensor
from .datatypes import Config, LightGroup


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


class MotionGroup(CalculatedSensor[bool], BinarySensorEntity):
    PRIMARY_ATTR = "_attr_is_on"

    def __init__(self, config: LightGroup) -> None:
        super().__init__()

        entity = config.motion_sensor_group_entity
        assert entity.domain.value == BS_DOMAIN
        assert isinstance(config.occupancy_sensors, list)

        self._attr_name = entity.name
        self._attr_device_class = DEVICE_CLASS_MOTION
        self._dependent_entities = [e.entity for e in config.occupancy_sensors]

    def calculate_current_state(self) -> bool:
        for entity in self._dependent_entities:
            state = self.hass.states.get(entity)
            if state is not None and state.state == STATE_ON:
                return True
        return False
