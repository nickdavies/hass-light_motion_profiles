"""Tests for LightConfig in config/__init__.py: the `area` key."""

from custom_components.light_motion_profiles.config import LightConfig
from custom_components.light_motion_profiles.config.light_templates import (
    AllTemplates,
)

BASE = {
    "lights": "light.kitchen_lights_all",
    "occupancy_sensors": "binary_sensor.kitchen_motion",
    "occupancy_timeout": 180,
    "user": "everyone",
    "light_profile_rules": [],
}


def _parse(data):
    return LightConfig.from_yaml(LightConfig.vol()(data), AllTemplates.from_yaml({}))


def test_area_is_optional():
    assert _parse(BASE).area is None


def test_area_is_kept():
    assert _parse({**BASE, "area": "kitchen"}).area == "kitchen"
