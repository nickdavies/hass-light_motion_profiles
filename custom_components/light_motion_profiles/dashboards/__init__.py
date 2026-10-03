"""The debug dashboards, and the fragments they are built from.

Each card is built by one function, and each function is also registered with
lovelace_codegen as a fragment, so a hand-written dashboard can embed any of
these cards (`custom:codegen-fragment`). The generated dashboards are only
these functions put together, so they cannot drift from the embedded copies.
"""

import logging

from dataclasses import dataclass
from typing import Any, List, Dict, Mapping, Set, Sequence

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
    FloorplanCard,
    GridCard,
    NAME,
    Params,
    Renderable,
    TileCard,
    VerticalStackCard,
    View,
    floorplan_on_state,
    floorplan_style_set,
    floorplan_tap,
    floorplan_text_set,
    navigate,
)

from ..config.settings import Floorplan
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


# --- The details behind the Debug dashboard ---
#
# The Debug dashboard itself is hand-written in hass-configs, where cards from
# several components and homelab-data sit side by side. What it can't write by
# hand is anything there is one of per light config, user or group, so those
# pages are generated here, on a dashboard of their own, and the cards that
# lead to them are fragments. Their paths are how hass-configs links here, so
# they are kept stable.
#
# No page sets a back path: the back arrow goes back in browser history, to
# whichever dashboard the link was followed from.

DETAILS_URL_PATH = "debug-details"
DETAILS_COLUMNS = 4


def details_path(view: str) -> str:
    """A view on the Debug details dashboard, as a navigation path."""
    return f"/{DETAILS_URL_PATH}/{view}"


def room_view(room: Room) -> str:
    return f"room-{room.key}"


def user_view(name: str) -> str:
    return f"user-{name}"


def group_view(name: str) -> str:
    return f"group-{name}"


PEOPLE_VIEW = "people"
KILLSWITCHES_VIEW = "killswitches"


def _tile(entity: str, name: str, view: str, icon: str | None = None) -> TileCard:
    return TileCard(
        entity,
        name=display_name(name),
        icon=icon,
        vertical=True,
        tap_action=navigate(details_path(view)),
    )


def people_card(ug_config: UsersGroups) -> GridCard:
    """A tile per user, showing their presence, each opening their page."""
    return GridCard(
        [
            _tile(user.presence_entity.full, name, user_view(name))
            for name, user in ug_config.users.items()
        ],
        columns=DETAILS_COLUMNS,
        title="People",
    )


def groups_card(ug_config: UsersGroups) -> GridCard:
    """A tile per group, showing its presence, each opening its page."""
    return GridCard(
        [
            _tile(
                group.presence_entity.full,
                name,
                group_view(name),
                icon="mdi:account-group",
            )
            for name, group in ug_config.groups.items()
        ],
        columns=DETAILS_COLUMNS,
        title="Groups",
    )


def people_page_cards(config: Config) -> list[Renderable]:
    """Everything about presence: who, which groups, and what is published."""
    cards: list[Renderable] = [
        people_card(config.users_groups),
        groups_card(config.users_groups),
    ]
    if config.presence_outputs:
        cards.append(presence_outputs_card(config.presence_outputs))
    return cards


# --- Floor plans ---
#
# homelab-data draws each floor with every Home Assistant area on it as an
# `area-<area id>` element to colour and tap, and lists those areas in a file
# that the `floorplans` setting `!include`s.

# An area with no light configs, over the plan's own room fill.
NO_LIGHTS_FILL = "--area-fill: #cfcfcf"

# The rooms' rules' helpers, for ha-floorplan's templates. `fill` colours a room
# by its lights: the off colour when none is on, else the average colour of
# those on (warm white for one with no colour), nearer the off colour the dimmer
# the brightest of them is. `profiles` is each light config's profile, once
# each, a line apiece.
#
# ha-floorplan runs these in a sandboxed interpreter that parses ES2019 and
# can't spread its own Sets, so no `??`, `?.` or `[...new Set()]`: either one
# fails every room's template, leaving the plan uncoloured and unlabelled.
ROOM_FUNCTIONS = """\
const off = [125, 133, 144], warm = [255, 197, 120];
return {
  fill: (lights) => {
    const on = lights.filter((light) => light && light.state === 'on');
    if (!on.length) return `--area-fill: rgb(${off.join(', ')})`;
    const colour = (light) => light.attributes.rgb_color || warm;
    const brightness = (light) =>
      light.attributes.brightness == null ? 255 : light.attributes.brightness;
    const level = Math.max(...on.map(brightness)) / 255;
    const rgb = off.map((c, i) => {
      const lit = on.reduce((sum, light) => sum + colour(light)[i], 0) / on.length;
      return Math.round(c + (lit - c) * (0.4 + 0.6 * level));
    });
    return `--area-fill: rgb(${rgb.join(', ')})`;
  },
  profiles: (sensors) =>
    sensors
      .map((sensor) => (sensor ? sensor.state : 'unknown'))
      .filter((state, i, states) => states.indexOf(state) === i)
      .join('\\n'),
};"""


def area_element(area_id: str) -> str:
    return f"area-{area_id}"


def area_value_element(area_id: str) -> str:
    """The text under an area's name on the plan."""
    return f"area-{area_id}-value"


def _entities_template(entity_ids: Sequence[str]) -> str:
    """The entities' states, as a JavaScript list in a template."""
    return "[" + ", ".join(f"entities['{e}']" for e in entity_ids) + "]"


def _room_rules(config: Config, room: Room) -> list[dict[str, Any]]:
    """A room on a plan: coloured by its lights, its text the profiles its
    configs apply, and a tap opening it."""
    configs = [config.lights[name] for name in room.lights]
    lights = list(dict.fromkeys(c.lights.entity for c in configs))
    profiles = [c.light_automation_entity.full for c in configs]
    return [
        floorplan_on_state(
            [*lights, *profiles],
            [
                floorplan_style_set(
                    [area_element(room.key)],
                    f"${{functions.fill({_entities_template(lights)})}}",
                ),
                floorplan_text_set(
                    area_value_element(room.key),
                    f"${{functions.profiles({_entities_template(profiles)})}}",
                ),
            ],
        ),
        floorplan_tap(area_element(room.key), navigate(details_path(room_view(room)))),
    ]


def _floorplan_card(
    config: Config, plan: Floorplan, by_key: Mapping[str, Room], title: str
) -> FloorplanCard:
    """The plan, where a room with light configs shows them and opens on a
    tap, and a room without any is greyed."""
    unlit = [area_element(a) for a in plan.areas if a not in by_key]
    return FloorplanCard(
        plan.image,
        rules=[
            rule
            for area_id in plan.areas
            if area_id in by_key
            for rule in _room_rules(config, by_key[area_id])
        ],
        startup_actions=[floorplan_style_set(unlit, NO_LIGHTS_FILL)] if unlit else [],
        title=title,
        functions=ROOM_FUNCTIONS,
    )


def rooms_card(hass: HomeAssistant, config: Config) -> VerticalStackCard:
    """Every room with light configs, each opening its page.

    Rooms are found on the floor plans in the `floorplans` setting, by their
    area: a tap anywhere in a room with light configs opens it, and a room
    without any is greyed. A room with light configs is coloured by its lights,
    the colour of those on or grey when all are off, and its text on the plan
    is the profile each of its configs is applying, one line per profile. Rooms
    on no plan, or all of them without plans, are a grid of buttons.

    Room names and icons come from the area registry, so a change to either
    shows on the next render.
    """
    by_room = rooms(hass, config.lights)
    by_key = {room.key: room for room in by_room}

    settings = config.settings.dashboard
    plans = settings.floorplans if settings is not None else []
    on_plans = {area_id for plan in plans for area_id in plan.areas}
    cards: list[Renderable] = [
        _floorplan_card(
            config,
            plan,
            by_key,
            "Rooms" if len(plans) == 1 else display_name(plan.name),
        )
        for plan in plans
    ]
    off_plans = [room for room in by_room if room.key not in on_plans]
    if off_plans:
        cards.append(
            GridCard(
                [
                    ButtonCard(
                        room.name,
                        room.icon,
                        tap_action=navigate(details_path(room_view(room))),
                    )
                    for room in off_plans
                ],
                columns=DETAILS_COLUMNS,
                title="Other rooms" if plans else "Rooms",
            )
        )
    return VerticalStackCard(cards=cards)


def details_fragments(hass: HomeAssistant, config: Config) -> list[Fragment]:
    """The cards that lead into the Debug details dashboard, so only offered
    with it."""
    return [
        Fragment(
            "rooms",
            lambda params: rooms_card(hass, config),
            description="Each room on the floor plans, opening its light configs",
        ),
        Fragment(
            "people",
            lambda params: people_card(config.users_groups),
            description="A tile per user, opening every input to their presence",
        ),
        Fragment(
            "groups",
            lambda params: groups_card(config.users_groups),
            description="A tile per group, opening it and its members",
        ),
    ]


class DebugDetailsDashboard(GeneratedDashboard):
    """The pages behind hass-configs' Debug dashboard, off the sidebar.

    - main: the rooms (the `rooms` fragment), so the dashboard opened on its
      own still leads everywhere;
    - people: the `people` and `groups` tiles, then the presence outputs;
    - killswitches: every killswitch;
    - a page per room, with each of its light configs' cards, one config after
      another; per user, with every input to their presence; and per group,
      with its presence and each member's.

    It is rendered the first time it is opened, then cached until Home
    Assistant restarts.
    """

    def __init__(self, hass: HomeAssistant, config: Config) -> None:
        self._hass = hass
        self._config = config

    @property
    def title(self) -> str:
        return "Debug details"

    @property
    def url_path(self) -> str:
        return DETAILS_URL_PATH

    @property
    def show_in_sidebar(self) -> bool:
        return False

    def _subview(self, title: str, path: str, cards: Sequence[Renderable]) -> View:
        return View(
            title=title,
            path=path,
            subview=True,
            cards=[VerticalStackCard(cards=cards)],
        )

    def _room_subview(self, room: Room) -> View:
        """Each of the room's light configs' cards, one config after another."""
        cards: list[Renderable] = []
        for name in room.lights:
            light = self._config.lights[name]
            cards += [
                light_config_card(name, light),
                manual_lights_card(self._hass, name, light),
            ]
        return self._subview(room.name, room_view(room), cards)

    async def render(self) -> DBT:
        ug = self._config.users_groups
        views = [
            View(
                title=self.title,
                path="main",
                cards=[rooms_card(self._hass, self._config)],
            ),
            self._subview("People", PEOPLE_VIEW, people_page_cards(self._config)),
            self._subview(
                "Killswitches", KILLSWITCHES_VIEW, [killswitches_card(self._config)]
            ),
        ]
        views += [
            self._subview(display_name(name), user_view(name), [user_card(name, user)])
            for name, user in ug.users.items()
        ]
        views += [
            self._subview(
                display_name(name),
                group_view(name),
                [
                    group_card(ug, name, group),
                    *(user_card(m, ug.users[m]) for m in group_members(ug, group)),
                ],
            )
            for name, group in ug.groups.items()
        ]
        views += [
            self._room_subview(room) for room in rooms(self._hass, self._config.lights)
        ]
        return Dashboard(views).render()
