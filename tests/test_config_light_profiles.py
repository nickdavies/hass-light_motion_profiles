"""Tests for config/light_profiles.py."""
import pytest

from custom_components.light_motion_profiles.config.light_profiles import (
    Match,
    UserState,
    LightRule,
    LightProfile,
)
from custom_components.light_motion_profiles.config.validators import InvalidConfigError


class TestMatch:
    def test_from_yaml_string(self):
        m = Match.from_yaml("awake")
        assert m.value == "awake"

    def test_from_yaml_set(self):
        m = Match.from_yaml({"awake", "winddown"})
        assert m.value == {"awake", "winddown"}

    def test_from_yaml_wildcard(self):
        m = Match.from_yaml("*")
        assert m.value == "*"


class TestUserState:
    def test_from_yaml_state_any(self):
        data = {"user": "nick", "state_any": "awake"}
        us = UserState.from_yaml(data)
        assert us.user == "nick"
        assert us.state_any is not None
        assert us.state_all is None
        assert us.state_exact is None

    def test_from_yaml_state_all(self):
        data = {"user": "nick", "state_all": "awake"}
        us = UserState.from_yaml(data)
        assert us.state_all is not None
        assert us.state_any is None

    def test_from_yaml_state_exact(self):
        data = {"user": "nick", "state_exact": {"awake", "winddown"}}
        us = UserState.from_yaml(data)
        assert us.state_exact is not None
        assert us.state_any is None

    def test_from_yaml_no_state_raises(self):
        data = {"user": "nick"}
        with pytest.raises(InvalidConfigError, match="found none"):
            UserState.from_yaml(data)

    def test_from_yaml_multiple_states_raises(self):
        data = {"user": "nick", "state_any": "awake", "state_all": "awake"}
        with pytest.raises(InvalidConfigError, match="found multiple"):
            UserState.from_yaml(data)


class TestLightRule:
    def test_from_yaml_with_user_state_list(self):
        data = {
            "state_name": "test_rule",
            "room_state": "default",
            "occupancy": "occupied",
            "user_state": [{"user": "nick", "state_any": "awake"}],
            "light_profile": "full",
        }
        rule = LightRule.from_yaml(data)
        assert rule.state_name == "test_rule"
        assert rule.room_state.value == "default"
        assert rule.occupancy.value == "occupied"
        assert rule.light_profile == "full"
        assert isinstance(rule.user_state, list)
        assert len(rule.user_state) == 1

    def test_from_yaml_with_wildcard_user_state(self):
        data = {
            "state_name": "test_rule",
            "room_state": "*",
            "occupancy": "*",
            "user_state": "*",
            "light_profile": "disabled",
        }
        rule = LightRule.from_yaml(data)
        assert isinstance(rule.user_state, Match)
        assert rule.user_state.value == "*"

    def test_from_yaml_with_set_room_state(self):
        data = {
            "state_name": "test_rule",
            "room_state": {"default", "night"},
            "occupancy": "occupied",
            "user_state": "*",
            "light_profile": "full",
        }
        rule = LightRule.from_yaml(data)
        assert rule.room_state.value == {"default", "night"}


class TestLightProfile:
    def test_from_yaml_all_fields(self):
        data = {
            "enabled": True,
            "icon": "mdi:lightbulb",
            "brightness_pct": 100,
            "transition": 5,
        }
        lp = LightProfile.from_yaml(data)
        assert lp.enabled is True
        assert lp.icon == "mdi:lightbulb"
        assert lp.brightness_pct == 100
        assert lp.transition == 5

    def test_from_yaml_no_fields(self):
        lp = LightProfile.from_yaml({})
        assert lp.enabled is None
        assert lp.icon is None
        assert lp.brightness_pct is None
        assert lp.transition is None

    def test_from_yaml_partial(self):
        data = {"enabled": False, "brightness_pct": 50}
        lp = LightProfile.from_yaml(data)
        assert lp.enabled is False
        assert lp.brightness_pct == 50
        assert lp.icon is None
        assert lp.transition is None
