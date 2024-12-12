from abc import ABC, abstractmethod
from typing import Sequence, Dict, Mapping, Any, Tuple


from homeassistant.components.lovelace.const import MODE_YAML
from homeassistant.components.lovelace.dashboard import LovelaceConfig
from homeassistant.components.lovelace import _register_panel
from homeassistant.helpers.json import json_bytes, json_fragment

DBT = Mapping[str, Any]

ENTITY = "entity"
NAME = "name"


class Renderable(ABC):
    @abstractmethod
    def render(self) -> DBT:
        pass


class View(Renderable):
    def __init__(self, title: str, cards: Sequence[Renderable]) -> None:
        self.title = title
        self.cards = cards

    def render(self) -> DBT:
        return {
            "panel": True,
            "title": self.title,
            "cards": [card.render() for card in self.cards],
        }


class VerticalStackCard(Renderable):
    def __init__(self, cards: Sequence[Renderable]) -> None:
        self.cards = cards

    def render(self) -> DBT:
        return {
            "type": "vertical-stack",
            "cards": [card.render() for card in self.cards],
        }


class HorizontalStackCard(Renderable):
    def __init__(self, cards: Sequence[Renderable]) -> None:
        self.cards = cards

    def render(self) -> DBT:
        return {
            "type": "horizontal-stack",
            "cards": [card.render() for card in self.cards],
        }


class EntitiesCard(Renderable):
    def __init__(
        self,
        entities: Sequence[str | Dict[str, str]],
        title: str | None = None,
    ) -> None:
        self.title = title
        self.entities = []
        for entity in entities:
            if isinstance(entity, dict):
                self.entities.append(entity)
            else:
                self.entities.append({"entity": entity})

    def render(self) -> DBT:
        config = {
            "type": "entities",
            "entities": self.entities,
        }

        if self.title is not None:
            config["title"] = self.title

        return config


class Dashboard(Renderable):
    def __init__(self, views: Sequence[View]) -> None:
        self.views = views

    def render(self) -> DBT:
        return {
            "views": [view.render() for view in self.views],
        }


class GeneratedDashboard(ABC):
    @property
    def mode(self) -> str:
        """Return mode of the lovelace config."""
        return str(MODE_YAML)

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
    def config(self) -> Mapping[str, str | bool]:
        return {
            "mode": self.mode,
            "title": self.title,
            "show_in_sidebar": self.show_in_sidebar,
            "require_admin": self.require_admin,
        }

    @abstractmethod
    async def render(self) -> DBT:
        """Build the YAML for the dashboard"""

    def add_to_hass(self, hass: Any) -> None:
        url = self.url_path
        dashboard_config = self.config

        hass.data["lovelace"]["dashboards"][url] = ManualLovelaceYAML(
            hass,
            self.url_path,
            dashboard_config,
            self,
        )
        _register_panel(hass, url, dashboard_config["mode"], dashboard_config, False)


class ManualLovelaceYAML(LovelaceConfig):
    def __init__(
        self, hass: Any, url_path: str, config: Any, dashboard: GeneratedDashboard
    ) -> None:
        super().__init__(hass, url_path, config)
        self._dashboard = dashboard
        self._cache: DBT | None = None

    @property
    def mode(self) -> str:
        """Return mode of the lovelace config."""
        return str(self.config["mode"])

    async def async_get_info(self) -> Mapping[str, str | int]:
        config = await self.async_load(False)
        return {"mode": self.mode, "views": len(config["views"])}

    async def async_load(self, force: bool) -> Mapping[str, Any]:
        is_updated, config = await self._load_config(force)
        if is_updated:
            self._config_updated()
        return config

    async def async_json(self, force: bool) -> json_fragment:
        config = await self.async_load(force)
        return json_fragment(json_bytes(config))

    async def _load_config(self, force: bool) -> Tuple[bool, DBT]:
        if self._cache is not None:
            return False, self._cache

        config = await self._dashboard.render()
        self._cache = config
        return True, config
