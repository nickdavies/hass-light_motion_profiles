import voluptuous as vol
from homeassistant.helpers import config_validation as cv

FIELD_LIGHT_PROFILES = "light_profiles"
FIELD_LIGHT_RULE_TEMPLATES = "light_rule_templates"
FIELD_LIGHT_TEMPLATES = "light_templates"
FIELD_LIGHT_BINDINGS = "light_bindings"

FIELD_ENABLED = "enabled"
FIELD_BRIGHTNESS_PCT = "brightness_pct"
FIELD_NO_MOTION_WAIT = "no_motion_wait"
FIELD_NO_MOTION_PROFILE = "no_motion_profile"
FIELD_DEFAULT_PROFILE = "default_profile"
FIELD_LIGHT_PROFILE_RULE_SETS = "light_profile_rule_sets"
FIELD_GROUP = "group"
FIELD_RULE_TEMPLATE = "rule_template"

FIELD_LIGHTS = "lights"
FIELD_MOTION_SENSORS = "motion_sensors"
FIELD_LIGHT_TEMPLATE = "light_template"


COMMON_LIGHT_FIELDS = {
    vol.Optional(FIELD_NO_MOTION_WAIT): cv.positive_int,
    vol.Optional(FIELD_NO_MOTION_PROFILE): cv.string,
    vol.Optional(FIELD_DEFAULT_PROFILE): cv.string,
    vol.Optional(FIELD_LIGHT_PROFILE_RULE_SETS): vol.Schema(
        [
            {
                FIELD_GROUP: cv.string,
                FIELD_RULE_TEMPLATE: cv.string,
            }
        ]
    ),
}

LIGHT_RULE_TEMPLATE_SCHEMA = vol.Schema({cv.string: cv.string})

LIGHT_TEMPLATE_SCHEMA = vol.Schema(COMMON_LIGHT_FIELDS)

LIGHT_BINDINGS = vol.Schema(
    {
        FIELD_LIGHTS: cv.string,
        FIELD_MOTION_SENSORS: vol.Any(
            cv.string,
            [cv.string],
        ),
        vol.Optional(FIELD_LIGHT_TEMPLATE): cv.string,
    }
).extend(COMMON_LIGHT_FIELDS)


LIGHT_PROFILE_SCHEMA = vol.Schema(
    {
        FIELD_ENABLED: cv.boolean,
        vol.Optional(FIELD_BRIGHTNESS_PCT): cv.positive_int,
    }
)

MOTION_PROFILES_SCHEMA = {
    vol.Optional(FIELD_LIGHT_PROFILES): {cv.string: LIGHT_PROFILE_SCHEMA},
    vol.Optional(FIELD_LIGHT_RULE_TEMPLATES): {cv.string: LIGHT_RULE_TEMPLATE_SCHEMA},
    vol.Optional(FIELD_LIGHT_TEMPLATES): {cv.string: LIGHT_TEMPLATE_SCHEMA},
    vol.Optional(FIELD_LIGHT_BINDINGS): {cv.string: LIGHT_BINDINGS},
}
