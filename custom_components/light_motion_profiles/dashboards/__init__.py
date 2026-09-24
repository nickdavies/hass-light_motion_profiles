"""The debug dashboards, and the fragments they are built from.

Each card is built by one function, and each function is also registered with
lovelace_codegen as a fragment, so a hand-written dashboard can embed any of
these cards (`custom:codegen-fragment`). The two generated dashboards are only
these functions put together, so they cannot drift from the embedded copies.
"""

import logging

from typing import List, Dict, Mapping, Set, Sequence

import voluptuous as vol

from custom_components.lovelace_codegen import (
    DBT,
    Dashboard,
    EntitiesCard,
    ENTITY,
    Fragment,
    GeneratedDashboard,
    NAME,
    Params,
    Renderable,
    VerticalStackCard,
    View,
)

from ..datatypes import Config, LightGroup, PresenceOutput, User, UsersGroups


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

    return EntitiesCard(title=name.replace("_", " ").capitalize(), entities=entities)


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


def motion_fragments(config: Config) -> list[Fragment]:
    def light(params: Params) -> EntitiesCard:
        return light_config_card(params["light"], config.lights[params["light"]])

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
            schema=vol.Schema({vol.Required("light"): vol.In(list(config.lights))}),
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


def all_fragments(config: Config) -> list[Fragment]:
    return [
        *presence_fragments(config.users_groups, config.presence_outputs),
        *motion_fragments(config),
    ]
