import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .schema_users_groups import get_person_states, FIELD_USERS, FIELD_GROUPS
from .entity_names import (
    group_presence_entity,
    motion_sensor_group_entity,
    person_presence_entity,
)


FIELD_LIGHT_PROFILES = "light_profiles"
FIELD_LIGHT_RULE_TEMPLATES = "light_rule_templates"
FIELD_LIGHT_TEMPLATES = "light_templates"
FIELD_LIGHT_BINDINGS = "light_bindings"
FIELD_LIGHT_PROFILE_SETTINGS = "light_profile_settings"

# Automatically generated top level field. Not valid in config
FIELD_MATERIALIZED_BINDINGS = "materialized_bindings"
FIELD_USER_OR_GROUP_ENTITY = "user_or_group_entity"
FIELD_RULES = "rules"

# Derived fields from materializing
FIELD_MOTION_SENSOR_ENTITY = "motion_sensor_entity"

FIELD_ENABLED = "enabled"
FIELD_BRIGHTNESS_PCT = "brightness_pct"
FIELD_NO_MOTION_WAIT = "no_motion_wait"
FIELD_NO_MOTION_PROFILE = "no_motion_profile"
FIELD_DEFAULT_PROFILE = "default_profile"
FIELD_LIGHT_PROFILE_RULE_SETS = "light_profile_rule_sets"
FIELD_USER_OR_GROUP = "user_or_group"
FIELD_RULE_TEMPLATE = "rule_template"

FIELD_LIGHTS = "lights"
FIELD_MOTION_SENSORS = "motion_sensors"
FIELD_LIGHT_TEMPLATE = "light_template"


FIELD_ICON_GLOBAL_KILLSWITCH = "icon_global_killswitch"
FIELD_ICON_KILLSWITCH = "icon_killswitch"

FIELD_PROFILE = "profile"
FIELD_STATES = "states"
FIELD_MATCH_TYPE = "match_type"


MATCH_TYPE_EXACT = "exact"
MATCH_TYPE_ANY = "any"
MATCH_TYPE_ALL = "all"
MATCH_TYPES = [MATCH_TYPE_EXACT, MATCH_TYPE_ANY, MATCH_TYPE_ALL]


MOTION_KILLSWITCH_GLOBAL = "global"
DEFAULT_GLOBAL_KILLSWITCH_ICON = "mdi:cancel"
DEFAULT_KILLSWITCH_ICON = "mdi:motion-sensor-off"


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
            user_or_group = rule_set[FIELD_USER_OR_GROUP]
            if user_or_group not in users_and_groups:
                raise vol.Invalid(
                    f"Light template '{name}' references non-existant user/group "
                    f"'{user_or_group}'"
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
        if binding_name == MOTION_KILLSWITCH_GLOBAL:
            raise cv.Invalid(
                f"Light binding '{binding_name}' conflicts with global killswitch named "
                f"'{MOTION_KILLSWITCH_GLOBAL}'"
            )
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

    # Lastly we make sure we can materialize the binding configs. This checks for things
    # like fields existing in either the template or directly on the binding but not
    # missing from both
    materialize_binding(config)

    return config


def materialize_binding(whole_config):
    materialized = {}
    for binding_name, raw_config in whole_config.get(FIELD_LIGHT_BINDINGS).items():
        out_config = {}

        # For now no validation on lights
        out_config[FIELD_LIGHTS] = raw_config[FIELD_LIGHTS]

        # We copy over the motion sensors field but we also build a single new
        # field for the entity to use for the motion sensing
        out_config[FIELD_MOTION_SENSORS] = raw_config[FIELD_MOTION_SENSORS]
        if isinstance(raw_config[FIELD_MOTION_SENSORS], list):
            out_config[FIELD_MOTION_SENSOR_ENTITY] = motion_sensor_group_entity(
                binding_name
            )
        else:
            out_config[FIELD_MOTION_SENSOR_ENTITY] = raw_config[FIELD_MOTION_SENSORS]

        # Next merge the template and directly specified fields. Preferring the the
        # direct fields if they exist. A field must be on either the template or the
        # rule itself otherwise it's invalid
        template = {}
        template_name = raw_config[FIELD_LIGHT_TEMPLATE]
        if template_name:
            # this is validated elsewhere so we still call .get in case this is run
            # before that validation is
            template = whole_config[FIELD_LIGHT_TEMPLATES].get(template_name, {})

        fields = [
            FIELD_NO_MOTION_WAIT,
            FIELD_NO_MOTION_PROFILE,
            FIELD_DEFAULT_PROFILE,
            FIELD_LIGHT_PROFILE_RULE_SETS,
        ]

        for field in fields:
            direct_value = raw_config.get(field, None)
            template_value = template.get(field, None)

            value = None
            if direct_value is not None:
                value = direct_value
            elif template_value is not None:
                value = template_value
            else:
                raise vol.Invalid(
                    f"Light binding '{binding_name}' has no field '{field}' and neither "
                    f"does it's template {template_name}"
                )

            out_config[field] = value

        # At this point we have copied over all the fields and resolved the fields from
        # the FIELD_LIGHT_TEMPLATE if there is one.
        #
        # Next we need to flatten out the rules in FIELD_LIGHT_PROFILE_RULE_SETS with the
        # values found in FIELD_LIGHT_RULE_TEMPLATES if they aren't directly added to the
        # config
        all_rules = whole_config[FIELD_LIGHT_RULE_TEMPLATES]
        light_rules = []
        # We can use out_config here because we have resolved the template values above
        for rule in out_config[FIELD_LIGHT_PROFILE_RULE_SETS]:
            person_or_group = rule[FIELD_USER_OR_GROUP]
            if person_or_group in whole_config.get(FIELD_USERS, {}):
                user_group_entity = person_presence_entity(person_or_group)
            elif person_or_group in whole_config.get(FIELD_GROUPS, {}):
                user_group_entity = group_presence_entity(person_or_group)
            else:
                raise cv.Invalid(
                    f"Light binding '{binding_name}' referrs to non-existant "
                    f"user/group '{person_or_group}'"
                )

            light_rules.append(
                {
                    FIELD_USER_OR_GROUP: person_or_group,
                    FIELD_USER_OR_GROUP_ENTITY: user_group_entity,
                    FIELD_RULE_TEMPLATE: rule[FIELD_RULE_TEMPLATE],
                    FIELD_RULES: all_rules[rule[FIELD_RULE_TEMPLATE]],
                }
            )

        out_config[FIELD_LIGHT_PROFILE_RULE_SETS] = light_rules

        # A this point we have flattened out everything except the light profiles which
        # we won't do here because the output of the generated entity will be which
        # profile should be active
        materialized[binding_name] = out_config

    return materialized


def preprocess_motion_profiles_config(config):
    config[FIELD_MATERIALIZED_BINDINGS] = materialize_binding(config)

    config[FIELD_LIGHT_PROFILES] = config.get(FIELD_LIGHT_PROFILES) or {}
    config[FIELD_LIGHT_RULE_TEMPLATES] = config.get(FIELD_LIGHT_RULE_TEMPLATES) or {}
    config[FIELD_LIGHT_TEMPLATES] = config.get(FIELD_LIGHT_TEMPLATES) or {}

    config[FIELD_LIGHT_BINDINGS] = config.get(FIELD_LIGHT_BINDINGS) or {}

    settings = config[FIELD_LIGHT_PROFILE_SETTINGS] = (
        config.get(FIELD_LIGHT_PROFILE_SETTINGS) or {}
    )
    settings.setdefault(FIELD_ICON_GLOBAL_KILLSWITCH, DEFAULT_GLOBAL_KILLSWITCH_ICON)
    settings.setdefault(FIELD_ICON_KILLSWITCH, DEFAULT_KILLSWITCH_ICON)

    return config


COMMON_LIGHT_FIELDS = {
    vol.Optional(FIELD_NO_MOTION_WAIT): cv.positive_int,
    vol.Optional(FIELD_NO_MOTION_PROFILE): cv.string,
    vol.Optional(FIELD_DEFAULT_PROFILE): cv.string,
    vol.Optional(FIELD_LIGHT_PROFILE_RULE_SETS): vol.Schema(
        [
            {
                FIELD_USER_OR_GROUP: cv.string,
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

SETTINGS_SCHEMA = vol.Schema(
    vol.Any(
        None,
        {
            vol.Optional(FIELD_ICON_GLOBAL_KILLSWITCH): cv.string,
            vol.Optional(FIELD_ICON_KILLSWITCH): cv.string,
        },
    )
)

MOTION_PROFILES_SCHEMA = {
    vol.Optional(FIELD_LIGHT_PROFILES): {cv.string: LIGHT_PROFILE_SCHEMA},
    vol.Optional(FIELD_LIGHT_RULE_TEMPLATES): {cv.string: LIGHT_RULE_TEMPLATE_SCHEMA},
    vol.Optional(FIELD_LIGHT_TEMPLATES): {cv.string: LIGHT_TEMPLATE_SCHEMA},
    vol.Optional(FIELD_LIGHT_BINDINGS): {cv.string: LIGHT_BINDINGS},
    vol.Optional(FIELD_LIGHT_PROFILE_SETTINGS): SETTINGS_SCHEMA,
}

MOTION_PROFILES_VALIDATIONS = [
    validate_light_rule_templates,
    validate_light_templates_and_bindings,
]
