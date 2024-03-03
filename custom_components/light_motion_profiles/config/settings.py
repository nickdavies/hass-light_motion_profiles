from dataclasses import dataclass
from typing import List, Set, Mapping

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .validators import unique_list


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
class UserGroupSettings:
    FIELD_VALID_PERSON_STATES = "valid_person_states"

    valid_person_states: Set[str]

    @classmethod
    def from_yaml(cls, data: Mapping[str, List[str]]) -> "UserGroupSettings":
        return cls(
            valid_person_states=set(data[cls.FIELD_VALID_PERSON_STATES]),
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
