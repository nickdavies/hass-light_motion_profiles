import voluptuous as vol
from collections import Counter

from homeassistant.helpers import config_validation as cv


# Top level fields
FIELD_GROUPS = "groups"
FIELD_USER_GROUP_SETTINGS = "user_group_settings"
FIELD_USERS = "users"

# Lower layer fields
FIELD_GUEST = "guest"
FIELD_STATE_ICONS = "icons_state"
FIELD_HOME_AWAY_ICONS = "icons_home_away"
FIELD_EXISTS_ICON = "icon_exists"
FIELD_TRACKING_ENTITY = "tracking_entity"
FIELD_PERSON_STATES = "valid_person_states"

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


# defaults if reused in code
DEFAULT_STATE_IF_UNKNOWN = PERSON_STATE_ABSENT
DEFAULT_PERSON_STATES = [
    "asleep",
    "winddown",
    "awake",
]


def get_person_states(config):
    """
    This function can be used on non-processed configs to
    get the person states from the config applying defaults
    """

    settings = config.get(FIELD_USER_GROUP_SETTINGS) or {}
    return settings.get(FIELD_PERSON_STATES, DEFAULT_PERSON_STATES)


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


def validate_states_and_icons(config):
    field_name = f"{FIELD_USER_GROUP_SETTINGS}->{FIELD_PERSON_STATES}"
    person_states = get_person_states(config)
    if person_states is not None:
        if len(person_states) == 0:
            raise vol.Invalid(f"{field_name} must be a " "non-empty list of states")
    else:
        person_states = DEFAULT_PERSON_STATES

    duplicate_fields = {k for k, v in Counter(person_states).items() if v != 1}
    if duplicate_fields:
        raise vol.Invalid(
            f"{field_name} has duplicate values: {','.join(duplicate_fields)}"
        )

    if PERSON_STATE_ABSENT in person_states:
        raise vol.Invalid(
            f"{field_name} contains reserved state name '{PERSON_STATE_ABSENT}' "
            "please pick a different name"
        )

    for state in person_states:
        if state in HOME_AWAY_STATES:
            raise vol.Invalid(
                f"{field_name}: person state '{state}' is also a "
                "home/away state which isn't allowed"
            )

    valid_icon_names = set(person_states) | {PERSON_STATE_ABSENT}
    for user, user_config in config.get(FIELD_USERS, {}).items():
        for icon in user_config.get(FIELD_STATE_ICONS, {}):
            if icon not in valid_icon_names:
                raise vol.Invalid(
                    f"User '{user}' has an invalid icon '{icon}' defined. Options are: "
                    f"{','.join(valid_icon_names)}"
                )
    return config


def preprocess_users_groups_config(config):
    groups = config[FIELD_GROUPS] = config.get(FIELD_GROUPS) or {}
    for group_name in groups:
        # Groups may be None instead of an empty dict
        groups[group_name] = groups[group_name] or {}

    # Settings could be present but empty (which will be an empty dict)
    settings = config[FIELD_USER_GROUP_SETTINGS] = (
        config.get(FIELD_USER_GROUP_SETTINGS) or {}
    )
    settings.setdefault(FIELD_STATE_IF_UNKNOWN, DEFAULT_STATE_IF_UNKNOWN)
    settings.setdefault(FIELD_PERSON_STATES, DEFAULT_PERSON_STATES)

    users = config[FIELD_USERS] = config.get(FIELD_USERS) or {}
    for name, user_config in users.items():
        user_config.setdefault(FIELD_GUEST, False)
        user_config.setdefault(FIELD_HOME_AWAY_ICONS, {})
        user_config.setdefault(FIELD_STATE_ICONS, {})
        user_config.setdefault(FIELD_TRACKING_ENTITY, None)

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
            vol.Optional(FIELD_STATE_IF_UNKNOWN): cv.string,
            vol.Optional(FIELD_PERSON_STATES): [cv.string],
        },
    )
)

USER_SCHEMA = vol.Schema(
    vol.Any(
        None,
        {
            vol.Optional(FIELD_GUEST): cv.boolean,
            vol.Optional(FIELD_EXISTS_ICON): cv.string,
            vol.Optional(FIELD_HOME_AWAY_ICONS): vol.Schema(
                {key: cv.string for key in HOME_AWAY_STATES}
            ),
            vol.Optional(FIELD_STATE_ICONS): vol.Schema({cv.string: cv.string}),
            vol.Optional(FIELD_TRACKING_ENTITY): cv.string,
        },
    )
)

USERS_GROUPS_SCHEMA = {
    vol.Optional(FIELD_GROUPS): {cv.string: GROUP_SCHEMA},
    vol.Optional(FIELD_USER_GROUP_SETTINGS): SETTINGS_SCHEMA,
    vol.Optional(FIELD_USERS): {cv.string: USER_SCHEMA},
}

USERS_GROUPS_VALIDATIONS = [
    validate_users_groups,
    validate_states_and_icons,
]
