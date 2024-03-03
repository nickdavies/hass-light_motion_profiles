from typing import Any, Mapping
from dataclasses import dataclass

import voluptuous as vol
from homeassistant.helpers import config_validation as cv


@dataclass
class UserConfig:
    FIELD_GUEST = "guest"
    FIELD_STATE_ICONS = "icons_state"
    FIELD_HOME_AWAY_ICONS = "icons_home_away"
    FIELD_EXISTS_ICON = "icon_exists"
    FIELD_TRACKING_ENTITY = "tracking_entity"

    guest: bool
    tracking_entity: str
    exists_icon: str | None
    home_awake_icons: Mapping[str, str]
    state_icons: Mapping[str, str]

    @classmethod
    def from_yaml(cls, data: Mapping[str, Any]) -> "UserConfig":
        return cls(**data)

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Optional(cls.FIELD_GUEST): cv.boolean,
                vol.Optional(cls.FIELD_EXISTS_ICON): cv.string,
                vol.Optional(cls.FIELD_HOME_AWAY_ICONS): vol.Schema(
                    {cv.string: cv.string}
                ),
                vol.Optional(cls.FIELD_STATE_ICONS): vol.Schema({cv.string: cv.string}),
                vol.Optional(cls.FIELD_TRACKING_ENTITY): cv.string,
            }
        )
