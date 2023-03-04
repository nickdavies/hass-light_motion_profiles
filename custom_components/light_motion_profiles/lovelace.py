from abc import ABC, abstractmethod

from homeassistant.components.lovelace.dashboard import LovelaceConfig
from homeassistant.components.lovelace import _register_panel
from homeassistant.components.lovelace.const import MODE_YAML


ENTITY = "entity"
NAME = "name"


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
        self.entities = []
        for entity in entities:
            if isinstance(entity, dict):
                self.entities.append(entity)
            else:
                self.entities.append({"entity": entity})

    def render(self):
        config = {
            "type": "entities",
            "entities": self.entities,
        }

        if self.title is not None:
            config["title"] = self.title

        return config


class ManualLovelaceYAML(LovelaceConfig):
    def __init__(self, hass, url_path, config, dashboard):
        super().__init__(hass, url_path, config)
        self._dashboard = dashboard
        self._cache = None

    @property
    def mode(self) -> str:
        """Return mode of the lovelace config."""
        return self.config["mode"]

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

        config = await self._dashboard.render()
        self._cache = config
        return True, config


class GeneratedDashboard(ABC):
    @property
    def mode(self) -> str:
        """Return mode of the lovelace config."""
        return MODE_YAML

    @property
    @abstractmethod
    def title(self) -> str:
        """The title of the dashboard displayed on the sidebar"""

    @property
    @abstractmethod
    def url_path(self) -> str:
        """The url slug for the dashboard"""

    @property
    def show_in_sidebar(self) -> bool:
        """Determines if the dashboard is listed on the main sidebar"""
        return True

    @property
    def require_admin(self) -> bool:
        """Determines if the dashboard requires admin to access"""
        return False

    @property
    def config(self):
        return {
            "mode": self.mode,
            "title": self.title,
            "show_in_sidebar": self.show_in_sidebar,
            "require_admin": self.require_admin,
        }

    @abstractmethod
    async def render(self) -> str:
        """Build the YAML for the dashboard"""

    def add_to_hass(self, hass):
        url = self.url_path
        dashboard_config = self.config

        hass.data["lovelace"]["dashboards"][url] = ManualLovelaceYAML(
            hass,
            self.url_path,
            dashboard_config,
            self,
        )
        _register_panel(hass, url, dashboard_config["mode"], dashboard_config, False)
