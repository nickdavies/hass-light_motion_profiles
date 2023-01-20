import logging
import voluptuous as vol

from homeassistant.helpers import discovery
from homeassistant.const import (
    Platform,
)

from .schema import TOP_LEVEL_SCHEMA


_LOGGER = logging.getLogger(__name__)

DOMAIN = "light_motion_profiles"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: TOP_LEVEL_SCHEMA,
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass, whole_config):
    hass.states.async_set("light_motion_profiles.hello_world", "Hello!")

    config = whole_config[DOMAIN]

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

    # Return boolean to indicate that initialization was successful.
    return True
