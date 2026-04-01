"""
Test configuration and Home Assistant mocks.

Since this integration imports from homeassistant extensively,
we mock the entire homeassistant package so tests can run without installing HA.
This must be imported before any custom_components imports.
"""
import sys
import types
from unittest.mock import MagicMock


def _setup_ha_mock():
    """Create a minimal mock of homeassistant modules used by the integration."""

    # Use MagicMock for modules that need arbitrary attribute access
    def mock_module(name, attrs=None):
        mod = types.ModuleType(name)
        if attrs:
            for k, v in attrs.items():
                setattr(mod, k, v)
        sys.modules[name] = mod
        return mod

    def magic_module(name):
        mod = MagicMock()
        mod.__name__ = name
        mod.__path__ = []
        mod.__file__ = name
        sys.modules[name] = mod
        return mod

    # -- homeassistant core --
    ha = mock_module("homeassistant")
    ha.__path__ = []

    # homeassistant.core
    ha_core = mock_module("homeassistant.core", {
        "HomeAssistant": MagicMock,
        "callback": lambda f: f,
    })

    # homeassistant.const
    ha_const = mock_module("homeassistant.const", {
        "Platform": MagicMock(),
        "STATE_ON": "on",
        "STATE_OFF": "off",
        "SERVICE_TURN_ON": "turn_on",
        "SERVICE_TURN_OFF": "turn_off",
        "ATTR_ENTITY_ID": "entity_id",
    })

    # homeassistant.config_entries
    magic_module("homeassistant.config_entries")

    # -- homeassistant.helpers --
    ha_helpers = mock_module("homeassistant.helpers")
    ha_helpers.__path__ = []

    # homeassistant.helpers.config_validation
    ha_cv = mock_module("homeassistant.helpers.config_validation", {
        "string": str,
        "boolean": bool,
        "positive_int": int,
    })

    ha_helpers.config_validation = ha_cv

    # homeassistant.helpers.discovery
    magic_module("homeassistant.helpers.discovery")

    # homeassistant.helpers.event
    magic_module("homeassistant.helpers.event")

    # homeassistant.helpers.entity_platform
    magic_module("homeassistant.helpers.entity_platform")

    # homeassistant.helpers.restore_state
    magic_module("homeassistant.helpers.restore_state")

    # homeassistant.helpers.json
    ha_json = mock_module("homeassistant.helpers.json", {
        "json_bytes": MagicMock(),
        "json_fragment": MagicMock(),
    })

    # -- homeassistant.util --
    ha_util = mock_module("homeassistant.util")
    ha_util.__path__ = []
    ha_util_dt = magic_module("homeassistant.util.dt")
    ha_util.dt = ha_util_dt

    # -- homeassistant.components --
    ha_components = mock_module("homeassistant.components")
    ha_components.__path__ = []

    # homeassistant.components.light
    mock_module("homeassistant.components.light", {
        "ATTR_BRIGHTNESS_PCT": "brightness_pct",
        "ATTR_TRANSITION": "transition",
        "DOMAIN": "light",
    })

    # homeassistant.components.sensor
    mock_module("homeassistant.components.sensor", {
        "SensorEntity": MagicMock,
        "DOMAIN": "sensor",
    })

    # homeassistant.components.select
    mock_module("homeassistant.components.select", {
        "SelectEntity": MagicMock,
        "DOMAIN": "select",
    })

    # homeassistant.components.switch
    mock_module("homeassistant.components.switch", {
        "SwitchEntity": MagicMock,
        "DOMAIN": "switch",
    })

    # homeassistant.components.binary_sensor
    mock_module("homeassistant.components.binary_sensor", {
        "BinarySensorDeviceClass": MagicMock(),
        "BinarySensorEntity": MagicMock,
        "DOMAIN": "binary_sensor",
    })

    # homeassistant.components.lovelace
    ha_lovelace = mock_module("homeassistant.components.lovelace", {
        "_register_panel": MagicMock(),
    })
    ha_lovelace.__path__ = []

    mock_module("homeassistant.components.lovelace.const", {
        "MODE_YAML": "yaml",
    })

    # LovelaceConfig needs to be a real class (it's subclassed)
    class _MockLovelaceConfig:
        def __init__(self, hass, url_path, config):
            self.hass = hass
            self.url_path = url_path
            self.config = config

        def _config_updated(self):
            pass

    mock_module("homeassistant.components.lovelace.dashboard", {
        "LovelaceConfig": _MockLovelaceConfig,
    })


# Must run before any custom_components imports
_setup_ha_mock()
