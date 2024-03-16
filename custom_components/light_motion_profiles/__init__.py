import logging
import voluptuous as vol
from typing import Any, Mapping

from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery
from homeassistant.const import (
    Platform,
)

from .dashboards import (
    PresenceDebugDashboard,
    MotionDebugDashboard,
)
from .config import RawConfig
from .datatypes import Config
from .datatypes.entity import Domain, Domains


LOGGER = logging.getLogger(__name__)

DOMAIN = "light_motion_profiles"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            RawConfig.vol(),
            RawConfig.validate_config,
        )
    },
    extra=vol.ALLOW_EXTRA,
)

GROUP_SEPARATOR = ","


def build_domains() -> Domains:
    return Domains(
        person_home_away=Domain.SENSOR,
        person_home_away_override=Domain.SELECT,
        person_state=Domain.SELECT,
        person_presence=Domain.SENSOR,
        group_presence=Domain.SENSOR,
        person_exists=Domain.SWITCH,
        killswitch=Domain.SWITCH,
        motion_sensor_group=Domain.BINARY_SENSOR,
        room_occupancy=Domain.SENSOR,
        light_rule=Domain.SENSOR,
        light_automation=Domain.SENSOR,
    )


async def async_setup(hass: HomeAssistant, whole_config: Mapping[str, Any]) -> bool:
    # LOGGER.warning(whole_config[DOMAIN])
    raw_config = RawConfig.from_yaml(whole_config[DOMAIN])
    domains = build_domains()
    # LOGGER.warning(domains)
    config = Config(raw_config, domains)
    # LOGGER.warning(config)

    await discovery.async_load_platform(
        hass,
        Platform.SELECT,
        DOMAIN,
        config,
        whole_config,
    )

    await discovery.async_load_platform(
        hass,
        Platform.SWITCH,
        DOMAIN,
        config,
        whole_config,
    )

    await discovery.async_load_platform(
        hass,
        Platform.SENSOR,
        DOMAIN,
        config,
        whole_config,
    )

    await discovery.async_load_platform(
        hass,
        Platform.BINARY_SENSOR,
        DOMAIN,
        config,
        whole_config,
    )

    if config.settings.dashboard is not None:
        PresenceDebugDashboard(config.users_groups).add_to_hass(hass)
        MotionDebugDashboard(config).add_to_hass(hass)

    # Return boolean to indicate that initialization was successful.
    return True
