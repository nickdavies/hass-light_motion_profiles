from typing import List, Set, Any, Mapping
from dataclasses import dataclass

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .light_profiles import LightRule, LightProfile, UserState
from .light_templates import AllTemplates
from .settings import AllSettings
from .users_groups import UserConfig
from .validators import unique_list


@dataclass
class LightConfig:
    FIELD_LIGHTS = "lights"
    FIELD_OCCUPANCY_SENSORS = "occupancy_sensors"
    FIELD_OCCUPANCY_TIMEOUT = "occupancy_timeout"
    FIELD_USER = "user"
    FIELD_LIGHT_PROFILE_RULES = "light_profile_rules"
    FIELD_AREA = "area"

    FIELD_TEMPLATE = "template"
    FIELD_VALUES = "values"

    lights: str
    occupancy_sensors: str | List[str]
    occupancy_timeout: str | int
    user: str
    light_profile_rules: List[LightRule]
    area: str | None = None
    """The id of the Home Assistant area the lights are in."""

    @classmethod
    def from_yaml(
        cls,
        data: Mapping[str, Any],
        templates: AllTemplates,
    ) -> "LightConfig":
        light_profile_rules: List[LightRule] = []
        for rule in data[cls.FIELD_LIGHT_PROFILE_RULES]:
            if cls.FIELD_TEMPLATE in rule:
                light_profile_rules.extend(
                    templates.materialize_light_config_template(
                        rule[cls.FIELD_TEMPLATE], rule[cls.FIELD_VALUES]
                    )
                )
            else:
                light_profile_rules.append(LightRule.from_yaml(rule))

        return cls(
            lights=data[cls.FIELD_LIGHTS],
            occupancy_sensors=data[cls.FIELD_OCCUPANCY_SENSORS],
            occupancy_timeout=data[cls.FIELD_OCCUPANCY_TIMEOUT],
            user=data[cls.FIELD_USER],
            light_profile_rules=light_profile_rules,
            area=data.get(cls.FIELD_AREA),
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(cls.FIELD_LIGHTS): cv.string,
                vol.Required(cls.FIELD_OCCUPANCY_SENSORS): vol.Any(
                    cv.string, [cv.string]
                ),
                vol.Required(cls.FIELD_OCCUPANCY_TIMEOUT): cv.positive_int,
                vol.Required(cls.FIELD_USER): cv.string,
                vol.Optional(cls.FIELD_AREA): cv.slug,
                vol.Required(cls.FIELD_LIGHT_PROFILE_RULES): [
                    vol.Any(
                        LightRule.vol(),
                        vol.Schema(
                            {
                                vol.Required(cls.FIELD_TEMPLATE): cv.string,
                                vol.Required(cls.FIELD_VALUES): {cv.string: cv.string},
                            }
                        ),
                    )
                ],
            }
        )


@dataclass
class PresenceOutputConfig:
    """A named presence rule, published as a binary sensor for other systems.

    Reuses the `user_state` conditions light rules are written with, so an
    output means exactly what the same conditions would mean in a rule.
    """

    FIELD_MATCH = "match"
    FIELD_USER_STATE = "user_state"

    MATCH_ALL = "all"
    MATCH_ANY = "any"

    match: str
    user_state: List[UserState]

    @classmethod
    def from_yaml(cls, data: Mapping[str, Any]) -> "PresenceOutputConfig":
        return cls(
            match=data.get(cls.FIELD_MATCH, cls.MATCH_ALL),
            user_state=[UserState.from_yaml(us) for us in data[cls.FIELD_USER_STATE]],
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Optional(cls.FIELD_MATCH, default=cls.MATCH_ALL): vol.In(
                    [cls.MATCH_ALL, cls.MATCH_ANY]
                ),
                vol.Required(cls.FIELD_USER_STATE): vol.All(
                    [UserState.vol()], vol.Length(min=1)
                ),
            }
        )


@dataclass
class RawConfig:
    FIELD_TEMPLATES = "templates"
    FIELD_LIGHT_PROFILES = "light_profiles"
    FIELD_LIGHT_CONFIGS = "light_configs"
    FIELD_USERS = "users"
    FIELD_GROUPS = "groups"
    FIELD_SETTINGS = "settings"
    FIELD_PRESENCE_OUTPUTS = "presence_outputs"

    light_profiles: Mapping[str, LightProfile]
    light_configs: Mapping[str, LightConfig]

    users: Mapping[str, UserConfig]
    groups: Mapping[str, Set[str]]

    settings: AllSettings

    presence_outputs: Mapping[str, PresenceOutputConfig]

    @classmethod
    def from_yaml(cls, data: Mapping[str, Any]) -> "RawConfig":
        templates = AllTemplates.from_yaml(data[cls.FIELD_TEMPLATES])
        return cls(
            light_configs={
                name: LightConfig.from_yaml(value, templates)
                for name, value in data[cls.FIELD_LIGHT_CONFIGS].items()
            },
            light_profiles={
                name: LightProfile.from_yaml(value)
                for name, value in data[cls.FIELD_LIGHT_PROFILES].items()
            },
            users={
                name: UserConfig.from_yaml(value)
                for name, value in data[cls.FIELD_USERS].items()
            },
            groups={name: set(users) for name, users in data[cls.FIELD_GROUPS].items()},
            settings=AllSettings.from_yaml(data[cls.FIELD_SETTINGS]),
            presence_outputs={
                name: PresenceOutputConfig.from_yaml(value)
                for name, value in data.get(cls.FIELD_PRESENCE_OUTPUTS, {}).items()
            },
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(
            {
                cls.FIELD_TEMPLATES: AllTemplates.vol(),
                cls.FIELD_LIGHT_PROFILES: {cv.string: LightProfile.vol()},
                cls.FIELD_LIGHT_CONFIGS: {cv.string: LightConfig.vol()},
                cls.FIELD_USERS: {cv.string: UserConfig.vol()},
                cls.FIELD_GROUPS: {cv.string: unique_list(cv.string)},
                cls.FIELD_SETTINGS: AllSettings.vol(),
                vol.Optional(cls.FIELD_PRESENCE_OUTPUTS): {
                    cv.string: PresenceOutputConfig.vol()
                },
            }
        )

    @classmethod
    def validate_config(cls, data: Mapping[str, Any]) -> Mapping[str, Any]:
        try:
            cls.from_yaml(data)
            return data
        except vol.Invalid as e:
            raise e
        except Exception as e:
            raise vol.Invalid(f"Failed to load config: {e}") from e
