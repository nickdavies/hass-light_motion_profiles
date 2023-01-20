import voluptuous as vol
from homeassistant.helpers import config_validation as cv


# Top level fields
FIELD_GROUPS = "groups"
FIELD_SETTINGS = "settings"
FIELD_USERS = "users"

# Lower layer fields
FIELD_GUEST = "guest"
FIELD_STATE_ICONS = "icons_state"
FIELD_HOME_AWAY_ICONS = "icons_home_away"
FIELD_EXISTS_ICON = "icon_exists"
FIELD_TRACKING_ENTITY = "tracking_entity"

FIELD_STATE_IF_UNKNOWN = "state_if_unknown"

# A special state for a person to say they are not at home and should not be
# a factor for determining group states
PERSON_STATE_ABSENT = "absent"

# States listed here have special meaning to the code and hence have constants
# to ensure they are all consistent
HOME_AWAY_STATE_UNKNOWN = "unknown"
HOME_AWAY_STATE_AUTO = "auto"
HOME_AWAY_STATE_NOT_HOME = "not_home"

HOME_AWAY_STATES = [
    HOME_AWAY_STATE_AUTO,
    HOME_AWAY_STATE_UNKNOWN,
    "home",
    HOME_AWAY_STATE_NOT_HOME,
]

PERSON_STATES = [
    "asleep",
    "winddown",
    "awake",
]


# defaults if reused in code
DEFAULT_STATE_IF_UNKNOWN = PERSON_STATE_ABSENT


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
            vol.Optional(FIELD_EXISTS_ICON): cv.string,
            vol.Optional(FIELD_HOME_AWAY_ICONS): vol.Schema(
                {key: cv.string for key in HOME_AWAY_STATES}
            ),
            vol.Optional(FIELD_STATE_ICONS): vol.Schema(
                {key: cv.string for key in PERSON_STATES + [PERSON_STATE_ABSENT]}
            ),
            vol.Optional(FIELD_TRACKING_ENTITY): cv.string,
        },
    )
)

USERS_GROUPS_SCHEMA = {
    vol.Optional(FIELD_GROUPS): {cv.string: GROUP_SCHEMA},
    vol.Optional(FIELD_SETTINGS): SETTINGS_SCHEMA,
    vol.Optional(FIELD_USERS): {cv.string: USER_SCHEMA},
}

USERS_GROUPS_VALIDATIONS = [
    validate_users_groups,
]
