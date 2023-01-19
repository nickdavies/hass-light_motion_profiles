import logging
from homeassistant.helpers import discovery
import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.const import (
    Platform,
)


_LOGGER = logging.getLogger(__name__)

DOMAIN = "light_motion_profiles"

# Top level fields
FIELD_GROUPS = "groups"
FIELD_SETTINGS = "settings"
FIELD_USERS = "users"

# Lower layer fields
FIELD_GUEST = "guest"
FIELD_ICONS = "icons"
FIELD_TRACKING_ENTITY = "tracking_entity"

FIELD_STATE_IF_UNKNOWN = "state_if_unknown"

# defaults if reused in code
DEFAULT_STATE_IF_UNKNOWN = "absent"


def validate_group_members(group_name, groups, users, seen=None):
    if seen is None:
        seen = []
    if group_name in seen:
        seen.append(group_name)
        raise vol.Invalid(f"Loop in groups found: {' -> '.join(seen)}")
    seen.append(group_name)

    if group_name in users:
        raise vol.Invalid(
            f"Group '{group_name}' with the same name as a user is prohibited"
        )

    for member in groups[group_name]:
        if member not in groups and member not in users:
            raise vol.Invalid(
                f"Group '{group_name}' contains unknown member '{member}'"
            )

        if member in groups:
            validate_group_members(member, groups, users, seen=seen)
    seen.pop()


def validate_users_groups(config):
    users = set(config.get(FIELD_USERS, {}))
    groups = config.get(FIELD_GROUPS, {})
    for group_name in groups:
        validate_group_members(group_name, groups, users)
    return config


# For now we have no metadata about groups but we will define
# them as dicts still so we can add some later if we need to
GROUP_SCHEMA = vol.Schema(
    {
        cv.string: vol.Any(None, vol.Schema({})),
    },
)


SETTINGS_SCHEMA = vol.Schema(
    vol.Any(
        None,
        {
            vol.Optional(
                FIELD_STATE_IF_UNKNOWN, default=DEFAULT_STATE_IF_UNKNOWN
            ): cv.string
        },
    )
)

USER_SCHEMA = vol.Schema(
    vol.Any(
        None,
        {
            vol.Optional(FIELD_GUEST, default=False): cv.boolean,
            vol.Optional(FIELD_ICONS): vol.Schema({cv.string: cv.string}),
            vol.Optional(FIELD_TRACKING_ENTITY): cv.string,
        },
    )
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            vol.All(
                {
                    vol.Optional(FIELD_GROUPS): {cv.string: GROUP_SCHEMA},
                    vol.Optional(FIELD_SETTINGS): SETTINGS_SCHEMA,
                    vol.Optional(FIELD_USERS): {cv.string: USER_SCHEMA},
                },
                validate_users_groups,
            )
        )
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
        Platform.SENSOR,
        DOMAIN,
        config,
        whole_config,
    )

    # Return boolean to indicate that initialization was successful.
    return True
