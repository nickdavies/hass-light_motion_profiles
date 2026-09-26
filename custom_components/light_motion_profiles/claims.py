"""Pinning each light config's own entities through the config bridge.

A light config's own entities (its killswitch, occupancy, rule and automation
sensors, and its motion group) have unique ids, so they are in the entity
registry, where the UI can rename them, move them to another area or hide
them. Each is claimed with the config bridge, which puts it back at every
boot to what the config says: in the config's `area`, or in no area of its
own if it has none, and with nothing else changed from the integration's own
values.

The bridge is optional. Without it set up, nothing is claimed and a warning
says so: the entities work the same, but nothing puts them in their areas or
undoes UI changes to them.
"""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

from . import DOMAIN
from .datatypes import Config, LightGroup

_LOGGER = logging.getLogger(__name__)

CONFIG_BRIDGE = "config_bridge"


def light_config_entities(light: LightGroup) -> list[str]:
    """The entity ids a light config creates with unique ids."""
    entities = [
        light.killswitch_entity.full,
        light.room_occupancy_entity.full,
        light.light_rule_entity.full,
        light.light_automation_entity.full,
    ]
    if isinstance(light.occupancy_sensors, list):
        entities.append(light.motion_sensor_group_entity.full)
    return entities


def claimed_entities(config: Config) -> dict[str, dict[str, Any]]:
    """Every light config entity, as a config bridge `entities` item."""
    return {
        entity: {"area_id": light.area} if light.area is not None else {}
        for light in config.lights.values()
        for entity in light_config_entities(light)
    }


def async_claim_entities(hass: HomeAssistant, config: Config) -> None:
    if CONFIG_BRIDGE not in hass.config.components:
        _LOGGER.warning(
            "config_bridge isn't set up, so light configs' entities aren't put "
            "in their areas, and UI changes to them are kept"
        )
        return
    # Imported here: the bridge is a separate custom component, and only
    # there when it is set up.
    from custom_components.config_bridge import claim_entities

    claim_entities(hass, DOMAIN, claimed_entities(config))
