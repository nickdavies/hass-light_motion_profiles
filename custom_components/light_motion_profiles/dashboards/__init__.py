import logging

from typing import List, Dict, Set, Sequence

from ..lovelace import (
    DBT,
    Dashboard,
    EntitiesCard,
    ENTITY,
    GeneratedDashboard,
    NAME,
    Renderable,
    VerticalStackCard,
    View,
)

from ..datatypes import Config, UsersGroups


_LOGGER = logging.getLogger(__name__)


class PresenceDebugDashboard(GeneratedDashboard):
    def __init__(self, config: UsersGroups) -> None:
        self._ug_config = config

    @property
    def title(self) -> str:
        return "Presence Debug"

    @property
    def url_path(self) -> str:
        return "presence-debug"

    def _build_user_group_presence(self) -> Renderable:
        entities = []
        for name, user in self._ug_config.users.items():
            entities.append(user.presence_entity.full)
        for name, group in self._ug_config.groups.items():
            entities.append(group.presence_entity.full)

        return EntitiesCard(entities, title="User and Group presence")

    def _build_per_user_overrides(self) -> Renderable:
        cards: List[Renderable] = []
        for name, user in self._ug_config.users.items():
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

            cards.append(
                EntitiesCard(
                    title=name.replace("_", " ").capitalize(), entities=entities
                )
            )

        return VerticalStackCard(cards=cards)

    async def render(self) -> DBT:
        views = [
            View(
                title=self.title,
                cards=[
                    VerticalStackCard(
                        cards=[
                            self._build_user_group_presence(),
                            self._build_per_user_overrides(),
                        ]
                    )
                ],
            )
        ]

        rendered_dashboard = Dashboard(views).render()
        _LOGGER.warning(f"{rendered_dashboard}")
        return rendered_dashboard


class MotionDebugDashboard(GeneratedDashboard):
    def __init__(self, config: Config) -> None:
        self._motion_config = config

    @property
    def title(self) -> str:
        return "Motion Debug"

    @property
    def url_path(self) -> str:
        return "motion-debug"

    def _build_killswitches(self) -> EntitiesCard:
        killswitches: List[str | Dict[str, str]] = [
            self._motion_config.global_killswitch_entity.full
        ]
        for name, config in self._motion_config.lights.items():
            killswitches.append({ENTITY: config.killswitch_entity.full, NAME: name})

        return EntitiesCard(title="Killswitches", entities=killswitches)

    def _build_light_bindings(self) -> VerticalStackCard:
        bindings = []
        light_automation = []

        for name, config in self._motion_config.lights.items():
            light_automation.append(
                {ENTITY: config.light_automation_entity.full, NAME: name}
            )
            entities: List[str | Dict[str, str]] = [
                {
                    NAME: "Killswitch",
                    ENTITY: config.killswitch_entity.full,
                },
                {NAME: "Light", ENTITY: config.lights.entity},
                {
                    NAME: "Light state",
                    ENTITY: config.light_automation_entity.full,
                },
                {
                    NAME: "Rule",
                    ENTITY: config.light_rule_entity.full,
                },
                {
                    NAME: "Occupancy",
                    ENTITY: config.room_occupancy_entity.full,
                },
                {
                    NAME: "Motion",
                    ENTITY: config.motion_sensor_group_entity.full
                    if isinstance(config.occupancy_sensors, list)
                    else config.occupancy_sensors.entity,
                },
            ]
            if isinstance(config.occupancy_sensors, list):
                entities += [
                    {NAME: e.entity, ENTITY: e.entity} for e in config.occupancy_sensors
                ]
            else:
                entities.append(
                    {
                        NAME: config.occupancy_sensors.entity,
                        ENTITY: config.occupancy_sensors.entity,
                    }
                )
            bindings.append(EntitiesCard(title=name, entities=entities))

        cards: Sequence[Renderable] = [
            EntitiesCard(entities=light_automation, title="Light Automation States")
        ] + bindings
        return VerticalStackCard(cards=cards)

    def _build_all_motion_inputs(self) -> EntitiesCard:
        entities: Set[str] = set()
        for name, config in self._motion_config.lights.items():
            motion = config.occupancy_sensors
            if isinstance(motion, list):
                entities.update(e.entity for e in motion)
            else:
                entities.add(motion.entity)

        return EntitiesCard(
            entities=sorted(entities), title="All input motion sensor states"
        )

    async def render(self) -> DBT:
        views = [
            View(
                title=self.title,
                cards=[
                    VerticalStackCard(
                        cards=[
                            self._build_killswitches(),
                            self._build_light_bindings(),
                            self._build_all_motion_inputs(),
                        ]
                    )
                ],
            )
        ]

        rendered_dashboard = Dashboard(views).render()
        _LOGGER.warning(f"{rendered_dashboard}")
        return rendered_dashboard
