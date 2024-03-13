from typing import Any, Mapping
from dataclasses import dataclass

import voluptuous as vol
from homeassistant.helpers import config_validation as cv


@dataclass
class UserConfig:
    FIELD_GUEST = "guest"
    FIELD_EXISTS_ICON = "icon_exists"
    FIELD_STATE_ICONS = "icons_state"
    FIELD_HOME_AWAY_ICONS = "icons_home_away"
    FIELD_TRACKING_ENTITY = "tracking_entity"

    guest: bool
    exists_icon: str | None
    home_away_icons: Mapping[str, str]
    state_icons: Mapping[str, str]
    tracking_entity: str | None

    @classmethod
    def from_yaml(cls, data: Mapping[str, Any]) -> "UserConfig":
        return cls(
            guest=data[cls.FIELD_GUEST],
            exists_icon=data.get(cls.FIELD_EXISTS_ICON),
            home_away_icons=data.get(cls.FIELD_HOME_AWAY_ICONS, {}),
            state_icons=data.get(cls.FIELD_STATE_ICONS, {}),
            tracking_entity=data.get(cls.FIELD_TRACKING_ENTITY),
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(
            {
                cls.FIELD_GUEST: cv.boolean,
                vol.Optional(cls.FIELD_EXISTS_ICON): cv.string,
                vol.Optional(cls.FIELD_HOME_AWAY_ICONS): vol.Schema(
                    {cv.string: cv.string}
                ),
                vol.Optional(cls.FIELD_STATE_ICONS): vol.Schema({cv.string: cv.string}),
                vol.Optional(cls.FIELD_TRACKING_ENTITY): cv.string,
            }
        )
