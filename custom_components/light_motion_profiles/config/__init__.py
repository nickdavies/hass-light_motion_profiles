from typing import List, Set, Any, Mapping
from dataclasses import dataclass

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .light_profiles import LightRule, LightProfile
from .light_templates import AllTemplates
from .settings import AllSettings
from .users_groups import UserConfig
from .validators import unique_list


@dataclass
class LightConfig:
    FIELD_LIGHTS = "lights"
    FIELD_OCCUPANCY_SENSORS = "occupancy_sensors"
    FIELD_OCCUPANCY_TIMEOUT = "occupancy_timeout"
    FIELD_USERS = "users"
    FIELD_LIGHT_PROFILE_RULES = "light_profile_rules"

    FIELD_TEMPLATE = "template"
    FIELD_VALUES = "values"

    lights: str
    occupancy_sensors: str | List[str]
    occupancy_timeout: str | int
    users: str | List[str]
    light_profile_rules: List[LightRule]

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
            users=data[cls.FIELD_USERS],
            light_profile_rules=light_profile_rules,
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(
            {
                cls.FIELD_LIGHTS: cv.string,
                cls.FIELD_OCCUPANCY_SENSORS: vol.Any(cv.string, [cv.string]),
                cls.FIELD_OCCUPANCY_TIMEOUT: cv.positive_int,
                cls.FIELD_USERS: vol.Any(cv.string, [cv.string]),
                cls.FIELD_LIGHT_PROFILE_RULES: [
                    vol.Any(
                        LightRule.vol(),
                        vol.Schema(
                            {
                                cls.FIELD_TEMPLATE: cv.string,
                                cls.FIELD_VALUES: {cv.string: cv.string},
                            }
                        ),
                    )
                ],
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

    light_profiles: Mapping[str, LightProfile]
    light_configs: Mapping[str, LightConfig]

    users: Mapping[str, UserConfig]
    groups: Mapping[str, Set[str]]

    settings: AllSettings

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
