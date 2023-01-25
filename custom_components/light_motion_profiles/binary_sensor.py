import logging

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_MOTION,
    BinarySensorEntity,
)
from homeassistant.const import STATE_ON
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .sensor import CalculatedSensor
from .entity_names import motion_sensor_group_entity
from .schema_motion_profiles import (
    FIELD_LIGHT_BINDINGS,
    FIELD_MOTION_SENSORS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    whole_config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info,
) -> None:
    motion_groups = []
    for name, binding_config in discovery_info[FIELD_LIGHT_BINDINGS].items():
        sensors = binding_config[FIELD_MOTION_SENSORS]
        if isinstance(sensors, list):
            motion_groups.append(MotionGroup(name, sensors))

    async_add_entities(motion_groups)


class MotionGroup(CalculatedSensor, BinarySensorEntity):
    PRIMARY_ATTR = "_attr_is_on"

    def __init__(self, name, sensors):
        super().__init__()
        self._attr_name = motion_sensor_group_entity(name, without_domain=True)
        self._attr_device_class = DEVICE_CLASS_MOTION
        self._dependent_entities = sensors

    def calculate_current_state(self):
        for entity in self._dependent_entities:
            state = self.hass.states.get(entity)
            if state is not None and state.state == STATE_ON:
                return True
        return False
