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
class RoomSettings:
    FIELD_VALID_ROOM_STATES = "valid_room_states"
    FIELD_VALID_OCCUPANCY_STATES = "valid_occupancy_states"

    valid_room_states: Set[str]
    valid_occupancy_states: Set[str]

    @classmethod
    def from_yaml(cls, data: Mapping[str, List[str]]) -> "RoomSettings":
        return cls(
            valid_room_states=set(data[cls.FIELD_VALID_ROOM_STATES]),
            valid_occupancy_states=set(data[cls.FIELD_VALID_OCCUPANCY_STATES]),
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(
            {
                cls.FIELD_VALID_ROOM_STATES: unique_list(cv.string),
                cls.FIELD_VALID_OCCUPANCY_STATES: unique_list(cv.string),
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

    @classmethod
    def from_yaml(cls, data: Mapping[str, List[str]]) -> "UserGroupSettings":
        return cls(
            valid_person_states=set(data[cls.FIELD_VALID_PERSON_STATES]),
            absent_state="absent",
            home_away_states=HomeAwayStates.from_yaml(),
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema({cls.FIELD_VALID_PERSON_STATES: unique_list(cv.string)})


@dataclass
class DashboardSettings:
    @classmethod
    def from_yaml(cls, data: Mapping[str, List[str]]) -> "DashboardSettings":
        return cls()

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(vol.Any(None, {}))


@dataclass
class AllSettings:
    room: RoomSettings
    users_groups: UserGroupSettings
    dashboard: DashboardSettings | None
    killswitch: KillswitchSettings

    FIELD_ROOM_SETTINGS = "room"
    FIELD_USER_GROUP_SETTINGS = "user_group"
    FIELD_DASHBOARD_SETTINGS = "debug_dashboard"

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
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(
            {
                cls.FIELD_ROOM_SETTINGS: RoomSettings.vol(),
                cls.FIELD_USER_GROUP_SETTINGS: UserGroupSettings.vol(),
                cls.FIELD_DASHBOARD_SETTINGS: DashboardSettings.vol(),
            }
        )
