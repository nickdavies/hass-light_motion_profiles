from dataclasses import dataclass
from typing import List, Set, Mapping, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .validators import unique_list


@dataclass
class KillswitchSettings:
    FIELD_GLOBAL_NAME = "global_killswitch_name"
    FIELD_GLOBAL_ICON = "global_killswitch_icon"
    FIELD_DEFAULT_ICON = "default_killswitch_icon"

    global_name: str
    global_icon: str
    default_icon: str

    @classmethod
    def from_yaml(cls) -> "KillswitchSettings":
        return cls(
            global_name="global",
            global_icon="mdi:cancel",
            default_icon="mdi:motion-sensor-off",
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(vol.Any(None, {}))


@dataclass
class OccupancyStates:
    occupied: str
    occupied_timeout: str
    empty: str
    unknown: str

    def all_states(cls) -> Set[str]:
        return {
            cls.occupied,
            cls.occupied_timeout,
            cls.empty,
            cls.unknown,
        }

    @classmethod
    def from_yaml(cls) -> "OccupancyStates":
        return cls(
            occupied="occupied",
            occupied_timeout="occupied_timeout",
            empty="empty",
            unknown="unknown",
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(vol.Any(None, {}))


@dataclass
class RoomSettings:
    FIELD_VALID_ROOM_STATES = "valid_room_states"

    valid_room_states: Set[str]
    occupancy_states: OccupancyStates

    @classmethod
    def from_yaml(cls, data: Mapping[str, List[str]]) -> "RoomSettings":
        return cls(
            valid_room_states=set(data[cls.FIELD_VALID_ROOM_STATES]),
            occupancy_states=OccupancyStates.from_yaml(),
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(cls.FIELD_VALID_ROOM_STATES): unique_list(cv.string),
            },
        )


@dataclass
class HomeAwayStates:
    auto: str
    unknown: str
    home: str
    not_home: str

    def all_states(cls) -> Set[str]:
        return {
            cls.auto,
            cls.unknown,
            cls.home,
            cls.not_home,
        }

    @classmethod
    def from_yaml(cls) -> "HomeAwayStates":
        return cls(
            auto="auto",
            unknown="unknown",
            home="home",
            not_home="not_home",
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(vol.Any(None, {}))


@dataclass
class UserGroupSettings:
    FIELD_VALID_PERSON_STATES = "valid_person_states"

    valid_person_states: Set[str]
    absent_state: str
    home_away_states: HomeAwayStates
    state_if_unknown: str

    @classmethod
    def from_yaml(cls, data: Mapping[str, List[str]]) -> "UserGroupSettings":
        return cls(
            valid_person_states=set(data[cls.FIELD_VALID_PERSON_STATES]),
            absent_state="absent",
            state_if_unknown="absent",
            home_away_states=HomeAwayStates.from_yaml(),
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(
            {vol.Required(cls.FIELD_VALID_PERSON_STATES): unique_list(cv.string)}
        )


@dataclass
class DashboardSettings:
    @classmethod
    def from_yaml(cls, data: Mapping[str, List[str]]) -> "DashboardSettings":
        return cls()

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(vol.Any(None, {}))


@dataclass
class RefreshSettings:
    """How a light is refreshed when an entity its profile reads changes.

    A refresh re-applies the current rule's profile (e.g. a new circadian
    color temperature) rather than switching rules. Sources like circadian
    lighting change on a fixed interval, so every light config would refresh
    in the same instant; instead each config waits a fixed offset, spread
    evenly across `spread` seconds, and fades over `transition` seconds.
    """

    FIELD_SPREAD = "spread"
    FIELD_TRANSITION = "transition"

    DEFAULT_SPREAD = 300
    DEFAULT_TRANSITION = 10

    spread: int
    transition: int

    @classmethod
    def from_yaml(cls, data: Mapping[str, int] | None) -> "RefreshSettings":
        data = data or {}
        return cls(
            spread=data.get(cls.FIELD_SPREAD, cls.DEFAULT_SPREAD),
            transition=data.get(cls.FIELD_TRANSITION, cls.DEFAULT_TRANSITION),
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(
            vol.Any(
                None,
                {
                    vol.Optional(cls.FIELD_SPREAD): cv.positive_int,
                    vol.Optional(cls.FIELD_TRANSITION): cv.positive_int,
                },
            )
        )


@dataclass
class AllSettings:
    room: RoomSettings
    users_groups: UserGroupSettings
    dashboard: DashboardSettings | None
    killswitch: KillswitchSettings
    refresh: RefreshSettings

    FIELD_ROOM_SETTINGS = "room"
    FIELD_USER_GROUP_SETTINGS = "user_group"
    FIELD_DASHBOARD_SETTINGS = "debug_dashboard"
    FIELD_REFRESH_SETTINGS = "refresh"

    @classmethod
    def from_yaml(cls, data: Mapping[str, Any]) -> "AllSettings":
        return cls(
            room=RoomSettings.from_yaml(data[cls.FIELD_ROOM_SETTINGS]),
            users_groups=UserGroupSettings.from_yaml(
                data[cls.FIELD_USER_GROUP_SETTINGS]
            ),
            dashboard=DashboardSettings.from_yaml(data[cls.FIELD_DASHBOARD_SETTINGS])
            if cls.FIELD_DASHBOARD_SETTINGS in data
            else None,
            killswitch=KillswitchSettings.from_yaml(),
            refresh=RefreshSettings.from_yaml(data.get(cls.FIELD_REFRESH_SETTINGS)),
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(cls.FIELD_ROOM_SETTINGS): RoomSettings.vol(),
                vol.Required(cls.FIELD_USER_GROUP_SETTINGS): UserGroupSettings.vol(),
                cls.FIELD_DASHBOARD_SETTINGS: DashboardSettings.vol(),
                vol.Optional(cls.FIELD_REFRESH_SETTINGS): RefreshSettings.vol(),
            }
        )
