import logging
import voluptuous as vol

from homeassistant.helpers import discovery
from homeassistant.const import (
    Platform,
)

from .dashboards import (
    PresenceDebugDashboard,
    MotionDebugDashboard,
)
from .schema_users_groups import (
    USERS_GROUPS_SCHEMA,
    USERS_GROUPS_VALIDATIONS,
    preprocess_users_groups_config,
)
from .schema_motion_profiles import (
    FIELD_DASHBOARD_SETTINGS,
    MOTION_PROFILES_SCHEMA,
    MOTION_PROFILES_VALIDATIONS,
    preprocess_motion_profiles_config,
)


_LOGGER = logging.getLogger(__name__)

DOMAIN = "light_motion_profiles"

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.All(
            vol.Schema({}).extend(USERS_GROUPS_SCHEMA).extend(MOTION_PROFILES_SCHEMA),
            *USERS_GROUPS_VALIDATIONS,
            *MOTION_PROFILES_VALIDATIONS,
        )
    },
    extra=vol.ALLOW_EXTRA,
)

GROUP_SEPARATOR = ","


def preprocess_config(config):
    config = preprocess_users_groups_config(config)
    config = preprocess_motion_profiles_config(config)
    return config


async def async_setup(hass, whole_config):
    config = preprocess_config(whole_config[DOMAIN])

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

    if FIELD_DASHBOARD_SETTINGS in config:
        PresenceDebugDashboard(config).add_to_hass(hass)
        MotionDebugDashboard(config).add_to_hass(hass)

    # Return boolean to indicate that initialization was successful.
    return True
