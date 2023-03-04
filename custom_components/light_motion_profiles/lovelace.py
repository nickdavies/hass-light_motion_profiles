import itertools
import logging

from .schema_motion_profiles import (
    FIELD_GROUPS,
    FIELD_MATERIALIZED_BINDINGS,
    FIELD_USERS,
    MOTION_KILLSWITCH_GLOBAL,
    FIELD_MOTION_SENSOR_ENTITY,
)

from .schema_users_groups import (
    FIELD_GUEST,
    FIELD_TRACKING_ENTITY,
)

from .entity_names import (
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

from homeassistant.components.lovelace.dashboard import LovelaceConfig
from homeassistant.components.lovelace import _register_panel
from homeassistant.components.lovelace.const import MODE_YAML


_LOGGER = logging.getLogger(__name__)


class Dashboard:
    def __init__(self, views):
        self.views = views

    def render(self):
        return {
            "views": [view.render() for view in self.views],
        }


class View:
    def __init__(self, title, cards):
        self.title = title
        self.cards = cards

    def render(self):
        return {
            "panel": True,
            "title": self.title,
            "cards": [card.render() for card in self.cards],
        }


class VerticalStackCard:
    def __init__(self, cards):
        self.cards = cards

    def render(self):
        return {
            "type": "vertical-stack",
            "cards": [card.render() for card in self.cards],
        }


class HorizontalStackCard:
    def __init__(self, cards):
        self.cards = cards

    def render(self):
        return {
            "type": "horizontal-stack",
            "cards": [card.render() for card in self.cards],
        }


class EntitiesCard:
    def __init__(self, entities, title=None):
        self.title = title
        self.entities = entities

    def render(self):
        config = {
            "type": "entities",
            "entities": self.entities,
        }

        if self.title is not None:
            config["title"] = self.title

        return config


class ManualLovelaceYAML(LovelaceConfig):
    def __init__(self, hass, url_path, config, motion_config):
        super().__init__(hass, url_path, config)
        self._motion_config = motion_config
        self._cache = None

    @property
    def mode(self) -> str:
        """Return mode of the lovelace config."""
        return MODE_YAML

    async def async_get_info(self):
        config = await self.async_load(False)
        return {"mode": self.mode, "views": len(config["views"])}

    async def async_load(self, force):
        is_updated, config = await self._load_config(force)
        if is_updated:
            self._config_updated()
        return config

    async def _load_config(self, force):
        if self._cache is not None:
            return False, self._cache

        config = await self._build_dashboard()
        self._cache = config
        return True, config

    def _build_user_group_presence(self):
        entities = []
        for user in self._motion_config[FIELD_USERS]:
            entities.append(person_presence_entity(user))
        for group in self._motion_config[FIELD_GROUPS]:
            entities.append(group_presence_entity(group))

        return EntitiesCard(entities, title="User and Group presence")

    def _build_motion_and_killswitches(self):
        binding_configs = self._motion_config[FIELD_MATERIALIZED_BINDINGS]

        motion = []
        killswitches = [killswitch_entity(MOTION_KILLSWITCH_GLOBAL)]
        for binding_name, binding_config in binding_configs.items():
            motion.append(binding_config[FIELD_MOTION_SENSOR_ENTITY])
            killswitches.append(killswitch_entity(binding_name))

        return HorizontalStackCard(
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
            light_profile.append(light_binding_profile_entity(binding_name))
            light_movement.append(light_movement_entity(binding_name))
            light_automation.append(light_automation_entity(binding_name))

        return [
            EntitiesCard(entities=light_automation, title="Light Automation States"),
            HorizontalStackCard(
                cards=[
                    EntitiesCard(entities=light_profile, title="Light Profiles"),
                    EntitiesCard(entities=light_movement, title="Movement states"),
                ]
            ),
        ]

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

        rows = []
        for left, right in itertools.zip_longest(cards[::2], cards[1::2]):
            columns = []
            columns.append(left)
            if right is not None:
                columns.append(right)

            _LOGGER.warning(f"{left.title} {right.title}")
            rows.append(HorizontalStackCard(cards=columns))

        return VerticalStackCard(cards=rows)

    async def _build_dashboard(self):
        views = [
            View(
                title="Presence Debug",
                cards=[
                    VerticalStackCard(
                        cards=[
                            self._build_user_group_presence(),
                            self._build_motion_and_killswitches(),
                            self._build_per_user_overrides(),
                            *self._build_light_bindings(),
                        ]
                    )
                ],
            )
        ]

        rendered_dashboard = Dashboard(views).render()
        _LOGGER.warning(f"{rendered_dashboard}")
        return rendered_dashboard


def setup_dashboard(hass, config):
    dashboard_url = "presence-debug"
    dashboard_config = {
        "mode": "yaml",
        "title": "Presence Debug",
        "show_in_sidebar": True,
        "require_admin": False,
    }

    hass.data["lovelace"]["dashboards"][dashboard_url] = ManualLovelaceYAML(
        hass, dashboard_url, dashboard_config, config
    )

    _register_panel(hass, dashboard_url, "yaml", dashboard_config, False)
