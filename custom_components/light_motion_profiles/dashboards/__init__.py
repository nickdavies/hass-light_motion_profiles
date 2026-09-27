"""The debug dashboards, and the fragments they are built from.

Each card is built by one function, and each function is also registered with
lovelace_codegen as a fragment, so a hand-written dashboard can embed any of
these cards (`custom:codegen-fragment`). The two generated dashboards are only
these functions put together, so they cannot drift from the embedded copies.
"""

import logging

from dataclasses import dataclass
from typing import List, Dict, Mapping, Set, Sequence

import voluptuous as vol
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import area_registry as ar

from custom_components.lovelace_codegen import (
    DBT,
    ButtonCard,
    Dashboard,
    EntitiesCard,
    ENTITY,
    Fragment,
    GeneratedDashboard,
    GridCard,
    NAME,
    Params,
    Renderable,
    TileCard,
    VerticalStackCard,
    View,
    navigate,
)

from ..datatypes import (
    Config,
    Group,
    LightGroup,
    PresenceOutput,
    User,
    UsersGroups,
)


_LOGGER = logging.getLogger(__name__)


# --- Presence ---


def users_groups_card(ug_config: UsersGroups) -> EntitiesCard:
    """The final presence of every user, then every group."""
    entities = []
    for name, user in ug_config.users.items():
        entities.append(user.presence_entity.full)
    for name, group in ug_config.groups.items():
        entities.append(group.presence_entity.full)

    return EntitiesCard(entities, title="User and Group presence")


def presence_outputs_card(
    presence_outputs: Mapping[str, PresenceOutput],
) -> EntitiesCard:
    entities = [o.entity.full for o in presence_outputs.values()]
    return EntitiesCard(entities, title="Presence outputs")


def user_card(name: str, user: User) -> EntitiesCard:
    """Every input to one user's presence, down to the final state."""
    entities: List[str | Dict[str, str]] = []
    if user.guest:
        entities.append(user.exists_entity.full)

    if user.tracking_entity is not None:
        entities.append(user.tracking_entity.entity)
    elif not user.guest:
        entities.append(
            {
                "entity": user.home_away_entity.full,
                "name": f"No tracking for {user.name}",
            }
        )

    entities += [
        # Manual override
        user.home_away_override_entity.full,
        # Overall home/away status
        user.home_away_entity.full,
        # awake status selector
        user.state_entity.full,
        # final state for the user
        user.presence_entity.full,
    ]

    return EntitiesCard(title=display_name(name), entities=entities)


def display_name(name: str) -> str:
    """A config key as a title: `guest_1` is "Guest 1"."""
    return name.replace("_", " ").capitalize()


def group_members(ug_config: UsersGroups, group: Group) -> list[str]:
    """A group's members, in the order the users are configured."""
    return [name for name in ug_config.users if name in group.members]


def group_card(ug_config: UsersGroups, name: str, group: Group) -> EntitiesCard:
    """A group's presence, then the final presence of each member it is made of."""
    entities: List[str | Dict[str, str]] = [
        {ENTITY: group.presence_entity.full, NAME: display_name(name)}
    ]
    entities += [
        {
            ENTITY: ug_config.users[member].presence_entity.full,
            NAME: display_name(member),
        }
        for member in group_members(ug_config, group)
    ]
    return EntitiesCard(title=display_name(name), entities=entities)


def presence_fragments(
    ug_config: UsersGroups,
    presence_outputs: Mapping[str, PresenceOutput],
) -> list[Fragment]:
    return [
        Fragment(
            "users_groups",
            lambda params: users_groups_card(ug_config),
            description="Final presence of every user and group",
        ),
        Fragment(
            "presence_outputs",
            lambda params: presence_outputs_card(presence_outputs),
            description="Every presence output",
        ),
        Fragment(
            "user",
            lambda params: user_card(params["user"], ug_config.users[params["user"]]),
            description="Every input to one user's presence",
            schema=vol.Schema({vol.Required("user"): vol.In(list(ug_config.users))}),
        ),
        Fragment(
            "group",
            lambda params: group_card(
                ug_config, params["group"], ug_config.groups[params["group"]]
            ),
            description="One group's presence and each member's",
            schema=vol.Schema({vol.Required("group"): vol.In(list(ug_config.groups))}),
        ),
    ]


class PresenceDebugDashboard(GeneratedDashboard):
    def __init__(
        self,
        config: UsersGroups,
        presence_outputs: Mapping[str, PresenceOutput] | None = None,
    ) -> None:
        self._ug_config = config
        self._presence_outputs = presence_outputs or {}

    @property
    def title(self) -> str:
        return "Presence Debug"

    @property
    def url_path(self) -> str:
        return "presence-debug"

    async def render(self) -> DBT:
        users: Sequence[Renderable] = [
            user_card(name, user) for name, user in self._ug_config.users.items()
        ]
        views = [
            View(
                title=self.title,
                cards=[
                    VerticalStackCard(
                        cards=[
                            users_groups_card(self._ug_config),
                            *(
                                [presence_outputs_card(self._presence_outputs)]
                                if self._presence_outputs
                                else []
                            ),
                            VerticalStackCard(cards=users),
                        ]
                    )
                ],
            )
        ]

        rendered_dashboard = Dashboard(views).render()
        _LOGGER.warning(f"{rendered_dashboard}")
        return rendered_dashboard


# --- Motion ---


def killswitches_card(config: Config) -> EntitiesCard:
    """The global killswitch, then one per light config."""
    killswitches: List[str | Dict[str, str]] = [config.global_killswitch_entity.full]
    for name, light in config.lights.items():
        killswitches.append({ENTITY: light.killswitch_entity.full, NAME: name})

    return EntitiesCard(title="Killswitches", entities=killswitches)


def light_automation_states_card(config: Config) -> EntitiesCard:
    """What each light config's automation is doing."""
    light_automation = [
        {ENTITY: light.light_automation_entity.full, NAME: name}
        for name, light in config.lights.items()
    ]
    return EntitiesCard(entities=light_automation, title="Light Automation States")


def light_config_card(name: str, light: LightGroup) -> EntitiesCard:
    """Every input to one light config's automation, down to its motion sensors."""
    entities: List[str | Dict[str, str]] = [
        {
            NAME: "Killswitch",
            ENTITY: light.killswitch_entity.full,
        },
        {NAME: "Light", ENTITY: light.lights.entity},
        {
            NAME: "Light state",
            ENTITY: light.light_automation_entity.full,
        },
        {
            NAME: "Rule",
            ENTITY: light.light_rule_entity.full,
        },
        {
            NAME: "Occupancy",
            ENTITY: light.room_occupancy_entity.full,
        },
        {
            NAME: "Motion",
            ENTITY: light.motion_sensor_group_entity.full
            if isinstance(light.occupancy_sensors, list)
            else light.occupancy_sensors.entity,
        },
    ]
    if isinstance(light.occupancy_sensors, list):
        entities += [
            {NAME: e.entity, ENTITY: e.entity} for e in light.occupancy_sensors
        ]
    else:
        entities.append(
            {
                NAME: light.occupancy_sensors.entity,
                ENTITY: light.occupancy_sensors.entity,
            }
        )
    return EntitiesCard(title=name, entities=entities)


def motion_inputs_card(config: Config) -> EntitiesCard:
    """Every motion sensor any light config reads, once each."""
    entities: Set[str] = set()
    for name, light in config.lights.items():
        motion = light.occupancy_sensors
        if isinstance(motion, list):
            entities.update(e.entity for e in motion)
        else:
            entities.add(motion.entity)

    return EntitiesCard(
        entities=sorted(entities), title="All input motion sensor states"
    )


def manual_lights_card(
    hass: HomeAssistant, name: str, light: LightGroup
) -> EntitiesCard:
    """The light a config drives, then each light in it if it is a group.

    Members come from the group's `entity_id` attribute as it is when the card is
    built, so a light added to the group shows up on the next render.
    """
    group = light.lights.entity
    state = hass.states.get(group)
    members = state.attributes.get(ATTR_ENTITY_ID, []) if state is not None else []
    if isinstance(members, str):
        members = [members]
    entities: List[str | Dict[str, str]] = [group]
    entities += [member for member in members if member != group]
    return EntitiesCard(title=f"{display_name(name)} lights", entities=entities)


def motion_fragments(hass: HomeAssistant, config: Config) -> list[Fragment]:
    def light(params: Params) -> EntitiesCard:
        return light_config_card(params["light"], config.lights[params["light"]])

    def manual_lights(params: Params) -> EntitiesCard:
        return manual_lights_card(hass, params["light"], config.lights[params["light"]])

    light_schema = vol.Schema({vol.Required("light"): vol.In(list(config.lights))})

    return [
        Fragment(
            "killswitches",
            lambda params: killswitches_card(config),
            description="The global motion killswitch, then one per light config",
        ),
        Fragment(
            "light_automation_states",
            lambda params: light_automation_states_card(config),
            description="What each light config's automation is doing",
        ),
        Fragment(
            "light_config",
            light,
            description="Every input to one light config's automation",
            schema=light_schema,
        ),
        Fragment(
            "manual_lights",
            manual_lights,
            description="The light one light config drives, and its members",
            schema=light_schema,
        ),
        Fragment(
            "motion_inputs",
            lambda params: motion_inputs_card(config),
            description="Every motion sensor any light config reads",
        ),
    ]


class MotionDebugDashboard(GeneratedDashboard):
    def __init__(self, config: Config) -> None:
        self._motion_config = config

    @property
    def title(self) -> str:
        return "Motion Debug"

    @property
    def url_path(self) -> str:
        return "motion-debug"

    async def render(self) -> DBT:
        config = self._motion_config
        bindings: Sequence[Renderable] = [
            light_automation_states_card(config),
            *(light_config_card(name, light) for name, light in config.lights.items()),
        ]
        views = [
            View(
                title=self.title,
                cards=[
                    VerticalStackCard(
                        cards=[
                            killswitches_card(config),
                            VerticalStackCard(cards=bindings),
                            motion_inputs_card(config),
                        ]
                    )
                ],
            )
        ]

        rendered_dashboard = Dashboard(views).render()
        _LOGGER.warning(f"{rendered_dashboard}")
        return rendered_dashboard


def all_fragments(hass: HomeAssistant, config: Config) -> list[Fragment]:
    return [
        *presence_fragments(config.users_groups, config.presence_outputs),
        *motion_fragments(hass, config),
    ]


# --- Rooms ---
#
# A light config's room is the Home Assistant area its `area:` key names.
# The area registry supplies the room's name and icon, so they are set in one
# place (the config bridge's areas, from homelab-data) and every dashboard
# shows the same ones.

UNASSIGNED = "unassigned"
DEFAULT_ROOM_ICON = "mdi:texture-box"  # Home Assistant's own default for an area
UNASSIGNED_ICON = "mdi:help-box-outline"
MISSING_AREA_ICON = "mdi:alert-circle-outline"


@dataclass(frozen=True)
class Room:
    key: str
    name: str
    icon: str
    lights: list[str]


def rooms(hass: HomeAssistant, lights: Mapping[str, LightGroup]) -> list[Room]:
    """Light configs grouped by the area each names.

    Rooms are sorted by name, and configs within one keep their configured
    order. An area the registry doesn't have still gets its room, named after
    the id with a warning icon, so a typo shows on the dashboard rather than
    hiding the config. Configs with no `area` come last, under "Unassigned".
    """
    areas = ar.async_get(hass)
    by_area: dict[str, list[str]] = {}
    unassigned: list[str] = []
    for name, light in lights.items():
        if light.area is None:
            unassigned.append(name)
        else:
            by_area.setdefault(light.area, []).append(name)

    found = []
    for area_id, names in by_area.items():
        area = areas.async_get_area(area_id)
        if area is None:
            _LOGGER.warning(
                "Light configs %s name area %r, which doesn't exist",
                ", ".join(names),
                area_id,
            )
            found.append(Room(area_id, display_name(area_id), MISSING_AREA_ICON, names))
        else:
            found.append(
                Room(area.id, area.name, area.icon or DEFAULT_ROOM_ICON, names)
            )
    found.sort(key=lambda room: room.name.lower())
    if unassigned:
        found.append(Room(UNASSIGNED, "Unassigned", UNASSIGNED_ICON, unassigned))
    return found


# --- Everything, as one dashboard ---


class DebugDashboard(GeneratedDashboard):
    """People and groups as grids of tiles, each opening a subview with that
    one's debug cards, then rooms, each opening a subview of its light configs.

    The tiles show live state: a user's presence sensor takes the icon
    configured for its state, and a light config's automation sensor takes the
    icon of the profile it is applying.

    Room names and icons are read from the area registry when the dashboard is
    first rendered, so a change to areas shows after Home Assistant restarts.
    """

    COLUMNS = 4

    def __init__(self, hass: HomeAssistant, config: Config) -> None:
        self._hass = hass
        self._config = config

    @property
    def title(self) -> str:
        return "Debug"

    @property
    def url_path(self) -> str:
        return "lovelace-debug"

    def _path(self, view: str) -> str:
        return f"/{self.url_path}/{view}"

    def _subview(
        self,
        title: str,
        path: str,
        cards: Sequence[Renderable],
        back: str = "main",
    ) -> View:
        return View(
            title=title,
            path=path,
            subview=True,
            back_path=self._path(back),
            cards=[VerticalStackCard(cards=cards)],
        )

    def _tile(
        self, entity: str, name: str, path: str, icon: str | None = None
    ) -> TileCard:
        return TileCard(
            entity,
            name=display_name(name),
            icon=icon,
            vertical=True,
            tap_action=navigate(self._path(path)),
        )

    async def render(self) -> DBT:
        ug = self._config.users_groups
        lights = self._config.lights
        by_room = rooms(self._hass, lights)

        main = View(
            title=self.title,
            path="main",
            cards=[
                VerticalStackCard(
                    cards=[
                        GridCard(
                            [
                                self._tile(
                                    user.presence_entity.full, name, f"user-{name}"
                                )
                                for name, user in ug.users.items()
                            ],
                            columns=self.COLUMNS,
                            title="People",
                        ),
                        GridCard(
                            [
                                self._tile(
                                    group.presence_entity.full,
                                    name,
                                    f"group-{name}",
                                    icon="mdi:account-group",
                                )
                                for name, group in ug.groups.items()
                            ],
                            columns=self.COLUMNS,
                            title="Groups",
                        ),
                        GridCard(
                            [
                                ButtonCard(
                                    room.name,
                                    room.icon,
                                    tap_action=navigate(self._path(f"room-{room.key}")),
                                )
                                for room in by_room
                            ],
                            columns=self.COLUMNS,
                            title="Rooms",
                        ),
                    ]
                )
            ],
        )

        views = [main]
        views += [
            self._subview(display_name(name), f"user-{name}", [user_card(name, user)])
            for name, user in ug.users.items()
        ]
        views += [
            self._subview(
                display_name(name),
                f"group-{name}",
                [
                    group_card(ug, name, group),
                    *(user_card(m, ug.users[m]) for m in group_members(ug, group)),
                ],
            )
            for name, group in ug.groups.items()
        ]
        for room in by_room:
            views.append(
                self._subview(
                    room.name,
                    f"room-{room.key}",
                    [
                        GridCard(
                            [
                                self._tile(
                                    lights[name].light_automation_entity.full,
                                    name,
                                    f"light-{name}",
                                )
                                for name in room.lights
                            ],
                            columns=self.COLUMNS,
                        ),
                        EntitiesCard(
                            [
                                {
                                    ENTITY: lights[name].light_automation_entity.full,
                                    NAME: display_name(name),
                                }
                                for name in room.lights
                            ],
                            title="Profiles",
                        ),
                    ],
                )
            )
            views += [
                self._subview(
                    display_name(name),
                    f"light-{name}",
                    [
                        light_config_card(name, lights[name]),
                        manual_lights_card(self._hass, name, lights[name]),
                    ],
                    back=f"room-{room.key}",
                )
                for name in room.lights
            ]
        return Dashboard(views).render()
