import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .schema_users_groups import get_person_states, FIELD_USERS, FIELD_GROUPS

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

FIELD_PROFILE = "profile"
FIELD_STATES = "states"
FIELD_MATCH_TYPE = "match_type"


MATCH_TYPE_EXACT = "exact"
MATCH_TYPES = [MATCH_TYPE_EXACT, "any", "all"]


def validate_light_rule_templates(config):
    person_states = set(get_person_states(config))
    light_profiles = set(config.get(FIELD_LIGHT_PROFILES, {}))

    for rule_name, ruleset in config.get(FIELD_LIGHT_RULE_TEMPLATES, {}).items():
        for rule in ruleset:
            profile = rule[FIELD_PROFILE]
            if profile not in light_profiles:
                raise vol.Invalid(
                    f"light rule template '{rule_name}' contains invalid "
                    f"profile '{profile}'"
                )

            for state in rule[FIELD_STATES]:
                if state not in person_states:
                    raise vol.Invalid(
                        f"Light rule template '{rule_name}' references invalid state "
                        f"'{state}'. Options are {','.join(person_states)}"
                    )

    return config


def validate_common_light_fields(
    name, config_snippet, light_profiles, light_rule_templates, users_and_groups
):
    for field in [FIELD_DEFAULT_PROFILE, FIELD_NO_MOTION_PROFILE]:
        profile = config_snippet.get(field)
        if profile is not None and profile not in light_profiles:
            raise vol.Invalid(
                f"Light template '{name}->{field}' references non-existant "
                f"profile '{profile}'"
            )

    rule_sets = config_snippet.get(FIELD_LIGHT_PROFILE_RULE_SETS)
    if rule_sets is not None:
        for rule_set in rule_sets:
            rule_template = rule_set[FIELD_RULE_TEMPLATE]
            if rule_template not in light_rule_templates:
                raise vol.Invalid(
                    f"Light template '{name}' references non-existant rule_template "
                    f"'{rule_template}'"
                )
            group_name = rule_set[FIELD_GROUP]
            if group_name not in users_and_groups:
                raise vol.Invalid(
                    f"Light template '{name}' references non-existant user/group "
                    f"'{group_name}'"
                )


def validate_light_templates_and_bindings(config):
    light_profiles = set(config.get(FIELD_LIGHT_PROFILES, {}))
    light_rule_templates = set(config.get(FIELD_LIGHT_RULE_TEMPLATES, {}))
    users_and_groups = set(config.get(FIELD_USERS, {})) | set(
        config.get(FIELD_GROUPS, {})
    )

    for template_name, template in config.get(FIELD_LIGHT_TEMPLATES).items():
        validate_common_light_fields(
            template_name,
            template,
            light_profiles,
            light_rule_templates,
            users_and_groups,
        )

    light_templates = set(config.get(FIELD_LIGHT_TEMPLATES))
    for binding_name, binding_config in config.get(FIELD_LIGHT_BINDINGS).items():
        validate_common_light_fields(
            binding_name,
            binding_config,
            light_profiles,
            light_rule_templates,
            users_and_groups,
        )

        light_template = binding_config.get(FIELD_LIGHT_TEMPLATE)
        if light_template is not None and light_template not in light_templates:
            raise vol.Invalid(
                f"Light binding {binding_name} references non-existant light_template "
                f"'{light_template}'"
            )

    return config


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

LIGHT_RULE_TEMPLATE_SCHEMA = vol.Schema(
    [
        {
            FIELD_STATES: [cv.string],
            FIELD_PROFILE: cv.string,
            vol.Optional(FIELD_MATCH_TYPE, default=MATCH_TYPE_EXACT): vol.Schema(
                vol.Any(*MATCH_TYPES)
            ),
        }
    ]
)

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

MOTION_PROFILES_VALIDATIONS = [
    validate_light_rule_templates,
    validate_light_templates_and_bindings,
]
