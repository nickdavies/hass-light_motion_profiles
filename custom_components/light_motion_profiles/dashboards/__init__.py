import logging

from ..lovelace import (
    ENTITY,
    NAME,
    GeneratedDashboard,
    EntitiesCard,
    Dashboard,
    View,
    VerticalStackCard,
)


from ..schema_motion_profiles import (
    FIELD_GROUPS,
    FIELD_MATERIALIZED_BINDINGS,
    FIELD_USERS,
    MOTION_KILLSWITCH_GLOBAL,
    FIELD_MOTION_SENSOR_ENTITY,
)

from ..schema_users_groups import (
    FIELD_GUEST,
    FIELD_TRACKING_ENTITY,
)

from ..entity_names import (
    group_presence_entity,
    killswitch_entity,
    light_automation_entity,
    light_binding_profile_entity,
    person_exists_entity,
    person_home_away_entity,
    person_override_home_away_entity,
    person_presence_entity,
    person_state_entity,
    light_movement_entity,
)


_LOGGER = logging.getLogger(__name__)


class PresenceDebugDashboard(GeneratedDashboard):
    def __init__(self, motion_config):
        self._motion_config = motion_config

    @property
    def title(self):
        return "Presence Debug"

    @property
    def url_path(self) -> str:
        return "presence-debug"

    def _build_user_group_presence(self):
        entities = []
        for user in self._motion_config[FIELD_USERS]:
            entities.append(person_presence_entity(user))
        for group in self._motion_config[FIELD_GROUPS]:
            entities.append(group_presence_entity(group))

        return EntitiesCard(entities, title="User and Group presence")

    def _build_per_user_overrides(self):
        cards = []
        for user, user_config in self._motion_config[FIELD_USERS].items():
            entities = []
            if user_config[FIELD_GUEST]:
                entities.append(person_exists_entity(user))

            if user_config[FIELD_TRACKING_ENTITY] is not None:
                entities.append(user_config[FIELD_TRACKING_ENTITY])
            elif not user_config[FIELD_GUEST]:
                entities.append(
                    {
                        "entity": person_home_away_entity(user),
                        "name": f"No tracking for {user}",
                    }
                )

            entities += [
                # Manual override
                person_override_home_away_entity(user),
                # Overall home/away status
                person_home_away_entity(user),
                # awake status selector
                person_state_entity(user),
                # final state for the user
                person_presence_entity(user),
            ]

            cards.append(
                EntitiesCard(
                    title=user.replace("_", " ").capitalize(), entities=entities
                )
            )

        return VerticalStackCard(cards=cards)

    async def render(self):
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
    def __init__(self, motion_config):
        self._motion_config = motion_config

    @property
    def title(self):
        return "Motion Debug"

    @property
    def url_path(self) -> str:
        return "motion-debug"

    def _build_motion_and_killswitches(self):
        binding_configs = self._motion_config[FIELD_MATERIALIZED_BINDINGS]

        motion = []
        killswitches = [killswitch_entity(MOTION_KILLSWITCH_GLOBAL)]
        for binding_name, binding_config in binding_configs.items():
            motion.append(binding_config[FIELD_MOTION_SENSOR_ENTITY])
            killswitches.append(
                {ENTITY: killswitch_entity(binding_name), NAME: binding_name}
            )

        return VerticalStackCard(
            cards=[
                EntitiesCard(title="Motion states", entities=motion),
                EntitiesCard(title="Killswitches", entities=killswitches),
            ]
        )

    def _build_light_bindings(self):
        light_profile = []
        light_movement = []
        light_automation = []
        for binding_name in self._motion_config[FIELD_MATERIALIZED_BINDINGS]:
            light_profile.append(
                {ENTITY: light_binding_profile_entity(binding_name), NAME: binding_name}
            )
            light_movement.append(
                {ENTITY: light_movement_entity(binding_name), NAME: binding_name}
            )
            light_automation.append(
                {ENTITY: light_automation_entity(binding_name), NAME: binding_name}
            )

        return VerticalStackCard(
            cards=[
                EntitiesCard(
                    entities=light_automation, title="Light Automation States"
                ),
                EntitiesCard(entities=light_profile, title="Light Profiles"),
                EntitiesCard(entities=light_movement, title="Movement states"),
            ]
        )

    async def render(self):
        views = [
            View(
                title=self.title,
                cards=[
                    VerticalStackCard(
                        cards=[
                            self._build_motion_and_killswitches(),
                            self._build_light_bindings(),
                        ]
                    )
                ],
            )
        ]

        rendered_dashboard = Dashboard(views).render()
        _LOGGER.warning(f"{rendered_dashboard}")
        return rendered_dashboard
