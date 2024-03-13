from dataclasses import dataclass
from typing import List, Mapping, Set, Dict

from ..config import RawConfig, LightConfig as RawLightConfig
from ..config.light_profiles import (
    LightRule as RawLightRule,
    LightProfile as RawLightProfile,
)
from ..config.validators import InvalidConfigError
from ..config.users_groups import UserConfig
from ..config.settings import (
    AllSettings as RawAllSettings,
    RoomSettings as RawRoomSettings,
    UserGroupSettings as RawUserGroupSettings,
    DashboardSettings as RawDashboardSettings,
    KillswitchSettings as RawKillswitchSettings,
)

from .entity import InputEntity, Domains as Domains
from .match import RuleMatch
from .source import DataSource


class Settings:
    room: RawRoomSettings
    users_groups: RawUserGroupSettings
    dashboard: RawDashboardSettings | None
    killswitch: RawKillswitchSettings

    def __init__(self, config: RawAllSettings, domains: Domains):
        self.domains = domains
        self.room = config.room
        self.users_groups = config.users_groups
        self.dashboard = config.dashboard
        self.killswitch = config.killswitch


@dataclass
class LightState:
    icon: DataSource
    enable: DataSource
    brightness: DataSource | None
    color: DataSource | None
    transition: DataSource

    def __init__(self, config: RawLightProfile, settings: Settings):
        self._settings = settings
        self.icon = DataSource(str(config.icon))
        self.enable = DataSource(bool(config.enabled))
        self.brightness = (
            DataSource(int(config.brightness_pct)) if config.brightness_pct else None
        )
        self.color = None
        self.transition = DataSource(0)


@dataclass
class LightRule:
    state_name: str
    state: LightState
    rule_match: RuleMatch

    def __init__(
        self,
        config: RawLightRule,
        light_profiles: Dict[str, LightState],
        settings: Settings,
    ):
        self._settings = settings
        if config.light_profile not in light_profiles:
            raise InvalidConfigError(
                f"Rule '{config.state_name}' specified light profile "
                f"'{config.light_profile}' which doesn't exist"
            )
        self.state_name = config.state_name
        self.state = light_profiles[config.light_profile]
        self.rule_match = RuleMatch(
            config.room_state, config.occupancy, config.user_state
        )


@dataclass
class LightGroup:
    name: str
    lights: InputEntity
    users: List[str]
    occupancy_sensors: List[InputEntity]
    occupancy_timeout: DataSource
    rules: List[LightRule]

    def __init__(
        self,
        name: str,
        config: RawLightConfig,
        light_profiles: Dict[str, LightState],
        settings: Settings,
    ):
        self._settings = settings
        self.name = name
        self.lights = InputEntity(config.lights)
        self.users = config.users if isinstance(config.users, list) else [config.users]
        self.occupancy_sensors = (
            [InputEntity(os) for os in config.occupancy_sensors]
            if isinstance(config.occupancy_sensors, list)
            else [InputEntity(config.occupancy_sensors)]
        )
        self.occupancy_timeout = DataSource(config.occupancy_timeout)

        self.rules = [
            LightRule(r, light_profiles=light_profiles, settings=self._settings)
            for r in config.light_profile_rules
        ]


@dataclass
class UsersGroups:
    users: Mapping[str, UserConfig]
    groups: Mapping[str, Set[str]]

    def __init__(
        self,
        users: Mapping[str, UserConfig],
        groups: Mapping[str, Set[str]],
        settings: Settings,
    ) -> None:
        self._settings = settings
        self.users = users
        self.groups = groups
        # Don't allow an invalid version of this object to ever exist
        self._validate(settings)

    def _validate(self, settings: Settings) -> None:
        for group_name in self.groups:
            self._validate_group_members(group_name)

        self._validate_states_and_icons(settings)

    def _validate_states_and_icons(self, settings: Settings):
        ug_settings = settings.users_groups
        valid_state_names = set(ug_settings.valid_person_states) | {
            ug_settings.absent_state
        }
        for user, user_config in self.users.items():
            for state in user_config.state_icons:
                if state not in valid_state_names:
                    raise InvalidConfigError(
                        f"User '{user}' has an invalid icon '{state}' defined. Options "
                        f"are: {','.join(valid_state_names)}"
                    )

    def _validate_group_members(
        self, group_name: str, seen: List[str] | None = None
    ) -> None:
        if seen is None:
            seen = []
        if group_name in seen:
            seen.append(group_name)
            raise InvalidConfigError(f"Loop in groups found: {' -> '.join(seen)}")
        seen.append(group_name)

        if group_name in self.users:
            raise InvalidConfigError(
                f"Group '{group_name}' with the same name as a user is prohibited"
            )

        for member in self.groups[group_name]:
            if member not in self.groups and member not in self.users:
                raise InvalidConfigError(
                    f"Group '{group_name}' contains unknown member '{member}'"
                )

            if member in self.groups:
                self._validate_group_members(member, seen=seen)
        seen.pop()


@dataclass
class Config:
    settings: Settings
    users: UsersGroups
    lights: Mapping[str, LightGroup]

    def __init__(self, raw_config: RawConfig, domains: Domains):
        self.settings = Settings(raw_config.settings, domains)
        light_profiles: Dict[str, LightState] = {
            name: LightState(config, settings=self.settings)
            for name, config in raw_config.light_profiles.items()
        }
        self.users = UsersGroups(
            users=raw_config.users,
            groups=raw_config.groups,
            settings=self.settings,
        )
        self.lights = {
            name: LightGroup(name, light_config, light_profiles, settings=self.settings)
            for name, light_config in raw_config.light_configs.items()
        }
