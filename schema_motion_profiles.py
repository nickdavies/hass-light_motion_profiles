import voluptuous as vol
from homeassistant.helpers import config_validation as cv

FIELD_LIGHT_PROFILES = "light_profiles"

FIELD_ENABLED = "enabled"
FIELD_BRIGHTNESS_PCT = "brightness_pct"

LIGHT_PROFILE_SCHEMA = vol.Schema(
    {
        FIELD_ENABLED: cv.boolean,
        vol.Optional(FIELD_BRIGHTNESS_PCT): cv.positive_int,
    }
)

MOTION_PROFILES_SCHEMA = {
    vol.Optional(FIELD_LIGHT_PROFILES): {cv.string: LIGHT_PROFILE_SCHEMA},
}
