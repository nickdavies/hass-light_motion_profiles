from dataclasses import dataclass, field
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


@dataclass(frozen=True)
class Floorplan:
    """One floor plan from homelab-data, as its `floorplan_areas_<floor>.yaml`
    lists it: where the plan is served, and the ids of the areas drawn on it,
    each an `area-<id>` element to colour and tap."""

    name: str
    image: str
    areas: List[str]

    FIELD_IMAGE = "image"
    FIELD_AREAS = "areas"

    @classmethod
    def from_yaml(cls, name: str, data: Mapping[str, Any]) -> "Floorplan":
        return cls(
            name=name,
            image=data[cls.FIELD_IMAGE],
            areas=list(data.get(cls.FIELD_AREAS, {})),
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        # Extra keys, in the file and on each area, are homelab-data's to add.
        # `areas` may be missing: Home Assistant's package merge drops an empty
        # mapping, so a plan with no areas arrives without the key.
        return vol.Schema(
            {
                vol.Required(cls.FIELD_IMAGE): cv.string,
                vol.Optional(cls.FIELD_AREAS, default={}): {
                    cv.slug: vol.Any(None, dict)
                },
            },
            extra=vol.ALLOW_EXTRA,
        )


@dataclass
class DashboardSettings:
    # Floor plans the Debug dashboard places its rooms on, by name, each the
    # area list homelab-data generates for it, `!include`d.
    floorplans: List[Floorplan] = field(default_factory=list)

    FIELD_FLOORPLANS = "floorplans"

    @classmethod
    def from_yaml(cls, data: Mapping[str, Any] | None) -> "DashboardSettings":
        plans = (data or {}).get(cls.FIELD_FLOORPLANS, {})
        return cls(
            floorplans=[Floorplan.from_yaml(name, plan) for name, plan in plans.items()]
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(
            vol.Any(
                None,
                {vol.Optional(cls.FIELD_FLOORPLANS): {cv.slug: Floorplan.vol()}},
            )
        )


@dataclass
class RefreshSettings:
    """How lights are refreshed when an entity a profile reads changes.

    A refresh brings lights to the current profile's new values (e.g. the
    next circadian color temperature) without the rule changing, so it fades
    over its own `transition` in seconds rather than the profile's, which is
    meant for switching profiles.
    """

    FIELD_TRANSITION = "transition"

    DEFAULT_TRANSITION = 10

    transition: int

    @classmethod
    def from_yaml(cls, data: Mapping[str, int] | None) -> "RefreshSettings":
        data = data or {}
        return cls(
            transition=data.get(cls.FIELD_TRANSITION, cls.DEFAULT_TRANSITION),
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(
            vol.Any(None, {vol.Optional(cls.FIELD_TRANSITION): cv.positive_int})
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
