"""
This file contains only the "pure" structs for the config without
any templating in them at all. This is all fully resolved after
templates are applied
"""
from dataclasses import dataclass
from typing import List, Mapping, Any, Set

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .validators import unique_list, InvalidConfigError


@dataclass
class Match:
    value: str | Set[str]

    @classmethod
    def from_yaml(cls, data: str | Set[str]) -> "Match":
        return cls(value=data)

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(vol.Required(vol.Any(cv.string, unique_list(cv.string))))


@dataclass
class UserState:
    FIELD_USER = "user"
    FIELD_STATE_ANY = "state_any"
    FIELD_STATE_ALL = "state_all"
    FIELD_STATE_EXACT = "state_exact"

    user: str

    # Test to see if the user/group is in any of these states
    state_any: Match | None

    # Test to make sure the user/group is in all of these states
    state_all: Match | None

    # Test to make sure the user/group is in exactly this state. So if
    # the user is in state {asleep, winddown} neither awake nor winddown will match
    # and neither will {asleep, winddown, awake}.
    state_exact: Match | None

    @classmethod
    def from_yaml(cls, data: Mapping[str, Any]) -> "UserState":
        out = cls(
            user=data[cls.FIELD_USER],
            state_any=Match.from_yaml(data[cls.FIELD_STATE_ANY])
            if cls.FIELD_STATE_ANY in data
            else None,
            state_all=Match.from_yaml(data[cls.FIELD_STATE_ALL])
            if cls.FIELD_STATE_ALL in data
            else None,
            state_exact=Match.from_yaml(data[cls.FIELD_STATE_EXACT])
            if cls.FIELD_STATE_EXACT in data
            else None,
        )

        states = [out.state_any, out.state_all, out.state_exact]
        states = [s for s in states if s is not None]
        if not states:
            raise InvalidConfigError(
                f"Expected either {cls.FIELD_STATE_ANY}, {cls.FIELD_STATE_ALL} or "
                f"{cls.FIELD_STATE_EXACT} but found none"
            )

        if len(states) > 1:
            raise InvalidConfigError(
                f"Expected either {cls.FIELD_STATE_ANY}, {cls.FIELD_STATE_ALL} or "
                f"{cls.FIELD_STATE_EXACT} but found multiple"
            )

        return out

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(cls.FIELD_USER): cv.string,
                vol.Required(
                    vol.Any(
                        cls.FIELD_STATE_ANY,
                        cls.FIELD_STATE_ALL,
                        cls.FIELD_STATE_EXACT,
                    )
                ): Match.vol(),
            }
        )


@dataclass
class LightRule:
    FIELD_STATE_NAME = "state_name"
    FIELD_ROOM_STATE = "room_state"
    FIELD_OCCUPANCY = "occupancy"
    FIELD_USER_STATE = "user_state"
    FIELD_LIGHT_PROFILE = "light_profile"

    state_name: str
    room_state: Match
    occupancy: Match
    user_state: List[UserState] | Match
    light_profile: str

    @classmethod
    def from_yaml(cls, data: Mapping[str, Any]) -> "LightRule":
        user_state: List[UserState] | Match
        if isinstance(data[cls.FIELD_USER_STATE], str):
            user_state = Match.from_yaml(data[cls.FIELD_USER_STATE])
        else:
            user_state = [UserState.from_yaml(d) for d in data[cls.FIELD_USER_STATE]]

        return cls(
            state_name=data[cls.FIELD_STATE_NAME],
            room_state=Match.from_yaml(data[cls.FIELD_ROOM_STATE]),
            occupancy=Match.from_yaml(data[cls.FIELD_OCCUPANCY]),
            user_state=user_state,
            light_profile=data[cls.FIELD_LIGHT_PROFILE],
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(cls.FIELD_STATE_NAME): cv.string,
                vol.Required(cls.FIELD_ROOM_STATE): Match.vol(),
                vol.Required(cls.FIELD_OCCUPANCY): Match.vol(),
                vol.Required(cls.FIELD_USER_STATE): vol.Any(
                    [UserState.vol()],
                    Match.vol(),
                ),
                vol.Required(cls.FIELD_LIGHT_PROFILE): cv.string,
            }
        )


@dataclass
class LightProfile:
    FIELD_ENABLED = "enabled"
    FIELD_ICON = "icon"
    FIELD_BRIGHTNESS = "brightness_pct"
    FIELD_TRANSITION = "transition"

    enabled: bool | None
    icon: str | None
    brightness_pct: int | None
    transition: int | None

    @classmethod
    def from_yaml(
        cls,
        data: Mapping[str, Any],
    ) -> "LightProfile":
        return cls(
            enabled=data.get(cls.FIELD_ENABLED),
            icon=data.get(cls.FIELD_ICON),
            brightness_pct=data.get(cls.FIELD_BRIGHTNESS),
            transition=data.get(cls.FIELD_TRANSITION),
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Optional(cls.FIELD_ENABLED): cv.boolean,
                vol.Optional(cls.FIELD_ICON): cv.string,
                vol.Optional(cls.FIELD_BRIGHTNESS): cv.positive_int,
                vol.Optional(cls.FIELD_TRANSITION): cv.positive_int,
            }
        )
