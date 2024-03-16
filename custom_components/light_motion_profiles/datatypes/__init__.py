from dataclasses import dataclass
from typing import List, Mapping, Set, Dict, Iterator

from ..config import RawConfig, LightConfig as RawLightConfig
from ..config.light_profiles import (
    LightRule as RawLightRule,
    LightProfile as RawLightProfile,
)
from ..config.validators import InvalidConfigError
from ..config.users_groups import UserConfig as RawUserConfig
from ..config.settings import (
    AllSettings as RawAllSettings,
    RoomSettings as RoomSettings,
    UserGroupSettings as UserGroupSettings,
    DashboardSettings as DashboardSettings,
    KillswitchSettings as KillswitchSettings,
)

from .entity import InputEntity, Domains as Domains, Entity as Entity
from .match import RuleMatch
from .source import DataSource


class Settings:
    room: RoomSettings
    users_groups: UserGroupSettings
    dashboard: DashboardSettings | None
    killswitch: KillswitchSettings

    def __init__(self, config: RawAllSettings, domains: Domains):
        self.domains = domains
        self.room = config.room
        self.users_groups = config.users_groups
        self.dashboard = config.dashboard
        self.killswitch = config.killswitch


@dataclass
class LightState:
    source_profile: str | None
    icon: DataSource | None
    enable: DataSource | None
    brightness: DataSource | None
    color: DataSource | None
    transition: DataSource

    def __init__(self, profile_name: str, config: RawLightProfile, settings: Settings):
        self._settings = settings
        self.source_profile = profile_name
        self.icon = DataSource(str(config.icon)) if config.icon else None
        self.enable = (
            DataSource(bool(config.enabled)) if config.enabled is not None else None
        )
        self.brightness = (
            DataSource(int(config.brightness_pct))
            if config.brightness_pct is not None
            else None
        )
        self.color = None
        self.transition = DataSource(
            config.transition if config.transition is not None else 0
        )


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
    user: str
    occupancy_sensors: InputEntity | List[InputEntity]
    occupancy_timeout: DataSource
    rules: List[LightRule]

    def __init__(
        self,
        name: str,
        config: RawLightConfig,
        light_profiles: Dict[str, LightState],
        settings: Settings,
        users_groups: "UsersGroups",
    ):
        self._settings = settings
        self.name = name
        self.lights = InputEntity(config.lights)
        self.user = config.user
        self.occupancy_sensors = (
            [InputEntity(os) for os in config.occupancy_sensors]
            if isinstance(config.occupancy_sensors, list)
            else InputEntity(config.occupancy_sensors)
        )
        self.occupancy_timeout = DataSource(config.occupancy_timeout)

        self.rules = [
            LightRule(r, light_profiles=light_profiles, settings=self._settings)
            for r in config.light_profile_rules
        ]

        rule_users = self.get_rule_users()
        if self.user in users_groups.users:
            invalid = rule_users - {self.user}
        else:
            members = set(users_groups.members(self.user))
            invalid = rule_users - members - {self.user}
        if invalid:
            raise ValueError(
                f"Found invalid members '{', '.join(invalid)}' in rule '{name}'. "
                "All users specified in rule matches must be contained in the group "
                f"'{self.user}' listed in the rule definition"
            )

    def get_rule_users(self) -> Set[str]:
        out = set()
        for rule in self.rules:
            out |= rule.rule_match.get_users()
        return out

    @property
    def killswitch_entity(self) -> Entity:
        return Entity(
            domain=self._settings.domains.killswitch,
            name=f"killswitch_motion_{self.name}",
        )

    @property
    def motion_sensor_entity(self) -> InputEntity:
        if isinstance(self.occupancy_sensors, list):
            return InputEntity(self.motion_sensor_group_entity.full)
        else:
            return self.occupancy_sensors

    @property
    def motion_sensor_group_entity(self) -> Entity:
        assert isinstance(self.occupancy_sensors, list)
        return Entity(
            domain=self._settings.domains.motion_sensor_group,
            name=f"motion_sensor_group_{self.name}",
        )

    @property
    def room_occupancy_entity(self) -> Entity:
        return Entity(
            domain=self._settings.domains.room_occupancy,
            name=f"light_binding_occupancy_{self.name}",
        )

    @property
    def light_rule_entity(self) -> Entity:
        return Entity(
            domain=self._settings.domains.light_rule,
            name=f"light_binding_rule_{self.name}",
        )

    @property
    def light_automation_entity(self) -> Entity:
        return Entity(
            domain=self._settings.domains.light_automation,
            name=f"light_binding_automation_{self.name}",
        )


@dataclass
class User:
    name: str
    guest: bool
    exists_icon: str | None
    home_away_icons: Mapping[str, str]
    state_icons: Mapping[str, str]
    tracking_entity: InputEntity | None

    def __init__(self, name: str, config: RawUserConfig, settings: Settings):
        self._settings = settings
        self.name = name
        self.guest = config.guest
        self.exists_icon = config.exists_icon
        self.home_away_icons = config.home_away_icons
        self.state_icons = config.state_icons
        self.tracking_entity = (
            InputEntity(config.tracking_entity) if config.tracking_entity else None
        )

    @property
    def home_away_entity(self) -> Entity:
        return Entity(
            domain=self._settings.domains.person_home_away,
            name=f"person_{self.name}",
        )

    @property
    def home_away_override_entity(self) -> Entity:
        return Entity(
            domain=self._settings.domains.person_home_away_override,
            name=f"{self.name}_status_override",
        )

    @property
    def exists_entity(self) -> Entity:
        assert self.guest
        return Entity(
            domain=self._settings.domains.person_exists,
            name=f"person_{self.name}_exists",
        )

    @property
    def state_entity(self) -> Entity:
        return Entity(
            domain=self._settings.domains.person_state,
            name=f"person_{self.name}_awake_state",
        )

    @property
    def presence_entity(self) -> Entity:
        return Entity(
            domain=self._settings.domains.person_presence,
            name=f"person_presence_{self.name}",
        )


class Group:
    name: str
    members: Set[str]

    def __init__(self, name: str, members: Set[str], settings: Settings):
        self._settings = settings
        self.name = name
        self.members = members

    @property
    def presence_entity(self) -> Entity:
        return Entity(
            domain=self._settings.domains.group_presence,
            name=f"group_presence_{self.name}",
        )

    @classmethod
    def resolve_group_states(
        cls, input_states: Iterator[str | Set[str]], absent_state: str
    ) -> Set[str]:
        states = set()
        for state in input_states:
            if isinstance(state, set):
                states.update(state)
            else:
                states.add(state)
        if len(states) != 1:
            states.discard(absent_state)
        return states


@dataclass
class UsersGroups:
    users: Mapping[str, User]
    groups: Mapping[str, Group]

    def __init__(
        self,
        users: Mapping[str, RawUserConfig],
        groups: Mapping[str, Set[str]],
        settings: Settings,
    ) -> None:
        self._settings = settings
        self.users = {
            name: User(name, config, settings) for name, config in users.items()
        }
        self.groups = {
            name: Group(name, members, settings) for name, members in groups.items()
        }
        # Don't allow an invalid version of this object to ever exist
        self._validate(settings)

    def get(self, name: str) -> User | Group:
        if name in self.users:
            return self.users[name]
        elif name in self.groups:
            return self.groups[name]
        else:
            raise ValueError(f"Requested unknown user/group {name}")

    def members(self, name: str) -> Mapping[str, User]:
        if name in self.users:
            return {name: self.users[name]}
        else:
            out: Dict[str, User] = {}
            for member in self.groups[name].members:
                out.update(self.members(member))
            return out

    def presence_entity(self, target: str) -> Entity:
        if target in self.users:
            return self.users[target].presence_entity
        else:
            return self.groups[target].presence_entity

    def _validate(self, settings: Settings) -> None:
        for group_name in self.groups:
            self._validate_group_members(group_name)

        self._validate_states_and_icons(settings)

    def _validate_states_and_icons(self, settings: Settings) -> None:
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

        for member in self.groups[group_name].members:
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
    users_groups: UsersGroups
    lights: Mapping[str, LightGroup]

    def __init__(self, raw_config: RawConfig, domains: Domains):
        self.settings = Settings(raw_config.settings, domains)
        light_profiles: Dict[str, LightState] = {
            name: LightState(name, config, settings=self.settings)
            for name, config in raw_config.light_profiles.items()
        }
        self.users_groups = UsersGroups(
            users=raw_config.users,
            groups=raw_config.groups,
            settings=self.settings,
        )
        self.lights = {
            name: LightGroup(
                name,
                light_config,
                light_profiles,
                settings=self.settings,
                users_groups=self.users_groups,
            )
            for name, light_config in raw_config.light_configs.items()
        }

    @property
    def global_killswitch_entity(self) -> Entity:
        return Entity(
            domain=self.settings.domains.killswitch,
            name=f"killswitch_motion_{self.settings.killswitch.global_name}",
        )
