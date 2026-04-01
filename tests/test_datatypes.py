"""Tests for datatypes/__init__.py - data model and validation."""

import pytest

from custom_components.light_motion_profiles.config.light_profiles import (
    LightProfile as RawLightProfile,
)
from custom_components.light_motion_profiles.config.settings import (
    AllSettings as RawAllSettings,
)
from custom_components.light_motion_profiles.config.users_groups import (
    UserConfig as RawUserConfig,
)
from custom_components.light_motion_profiles.config.validators import InvalidConfigError
from custom_components.light_motion_profiles.datatypes import (
    Settings,
    LightState,
    User,
    Group,
    UsersGroups,
    Domains,
    Entity,
)
from custom_components.light_motion_profiles.datatypes.entity import Domain, InputEntity
from custom_components.light_motion_profiles.datatypes.source import DataSource


def _make_domains():
    return Domains(
        person_home_away=Domain.SENSOR,
        person_home_away_override=Domain.SELECT,
        person_state=Domain.SELECT,
        person_presence=Domain.SENSOR,
        group_presence=Domain.SENSOR,
        person_exists=Domain.SWITCH,
        killswitch=Domain.SWITCH,
        motion_sensor_group=Domain.BINARY_SENSOR,
        room_occupancy=Domain.SENSOR,
        light_rule=Domain.SENSOR,
        light_automation=Domain.SENSOR,
    )


def _make_settings_raw():
    return RawAllSettings.from_yaml(
        {
            "room": {"valid_room_states": ["default", "night"]},
            "user_group": {"valid_person_states": ["awake", "winddown", "asleep"]},
        }
    )


def _make_settings():
    return Settings(_make_settings_raw(), _make_domains())


def _make_user_config(guest=False, tracking_entity=None):
    return RawUserConfig(
        guest=guest,
        exists_icon="mdi:account" if guest else None,
        home_away_icons={},
        state_icons={},
        tracking_entity=tracking_entity,
    )


# --- Group.resolve_group_states ---


class TestGroupResolveGroupStates:
    def test_single_state(self):
        result = Group.resolve_group_states(iter(["awake"]), "absent")
        assert result == {"awake"}

    def test_multiple_same_state(self):
        result = Group.resolve_group_states(iter(["awake", "awake"]), "absent")
        assert result == {"awake"}

    def test_multiple_different_states(self):
        result = Group.resolve_group_states(iter(["awake", "asleep"]), "absent")
        assert result == {"awake", "asleep"}

    def test_absent_discarded_when_multiple(self):
        result = Group.resolve_group_states(iter(["awake", "absent"]), "absent")
        assert result == {"awake"}

    def test_absent_kept_when_only_state(self):
        result = Group.resolve_group_states(iter(["absent", "absent"]), "absent")
        assert result == {"absent"}

    def test_set_input_merged(self):
        result = Group.resolve_group_states(
            iter([{"awake", "winddown"}, "asleep"]), "absent"
        )
        assert result == {"awake", "winddown", "asleep"}

    def test_set_input_with_absent_discarded(self):
        # When a set with multiple states is provided, absent is discarded
        result = Group.resolve_group_states(iter([{"awake", "absent"}]), "absent")
        assert result == {"awake"}


# --- UsersGroups validation ---


class TestUsersGroupsValidation:
    def test_valid_users_and_groups(self):
        settings = _make_settings()
        ug = UsersGroups(
            users={"nick": _make_user_config(), "partner": _make_user_config()},
            groups={"everyone": {"nick", "partner"}},
            settings=settings,
        )
        assert "nick" in ug.users
        assert "everyone" in ug.groups

    def test_unknown_group_member_raises(self):
        settings = _make_settings()
        with pytest.raises(InvalidConfigError, match="unknown member"):
            UsersGroups(
                users={"nick": _make_user_config()},
                groups={"everyone": {"nick", "ghost"}},
                settings=settings,
            )

    def test_group_loop_raises(self):
        settings = _make_settings()
        with pytest.raises(InvalidConfigError, match="Loop"):
            UsersGroups(
                users={"nick": _make_user_config()},
                groups={
                    "group_a": {"nick", "group_b"},
                    "group_b": {"group_a"},
                },
                settings=settings,
            )

    def test_group_same_name_as_user_raises(self):
        settings = _make_settings()
        with pytest.raises(InvalidConfigError, match="same name as a user"):
            UsersGroups(
                users={"nick": _make_user_config()},
                groups={"nick": {"nick"}},
                settings=settings,
            )

    def test_invalid_state_icon_raises(self):
        settings = _make_settings()
        bad_config = RawUserConfig(
            guest=False,
            exists_icon=None,
            home_away_icons={},
            state_icons={"nonexistent_state": "mdi:bug"},
            tracking_entity=None,
        )
        with pytest.raises(InvalidConfigError, match="invalid icon"):
            UsersGroups(
                users={"nick": bad_config},
                groups={},
                settings=settings,
            )

    def test_valid_state_icons(self):
        settings = _make_settings()
        config = RawUserConfig(
            guest=False,
            exists_icon=None,
            home_away_icons={},
            state_icons={"awake": "mdi:eye", "absent": "mdi:exit"},
            tracking_entity=None,
        )
        ug = UsersGroups(
            users={"nick": config},
            groups={},
            settings=settings,
        )
        assert "nick" in ug.users


# --- UsersGroups.get and .members ---


class TestUsersGroupsLookup:
    def _make_ug(self):
        settings = _make_settings()
        return UsersGroups(
            users={"nick": _make_user_config(), "partner": _make_user_config()},
            groups={"everyone": {"nick", "partner"}},
            settings=settings,
        )

    def test_get_user(self):
        ug = self._make_ug()
        result = ug.get("nick")
        assert isinstance(result, User)
        assert result.name == "nick"

    def test_get_group(self):
        ug = self._make_ug()
        result = ug.get("everyone")
        assert isinstance(result, Group)
        assert result.name == "everyone"

    def test_get_unknown_raises(self):
        ug = self._make_ug()
        with pytest.raises(ValueError, match="unknown"):
            ug.get("nobody")

    def test_members_user(self):
        ug = self._make_ug()
        result = ug.members("nick")
        assert set(result.keys()) == {"nick"}

    def test_members_group(self):
        ug = self._make_ug()
        result = ug.members("everyone")
        assert set(result.keys()) == {"nick", "partner"}


# --- Entity properties ---


class TestEntityProperties:
    def test_entity_full(self):
        e = Entity(domain=Domain.SENSOR, name="test_sensor")
        assert e.full == "sensor.test_sensor"

    def test_user_entities(self):
        settings = _make_settings()
        user = User("nick", _make_user_config(), settings)
        assert user.home_away_entity.full == "sensor.person_nick"
        assert user.presence_entity.full == "sensor.person_presence_nick"
        assert user.state_entity.full == "select.person_nick_awake_state"

    def test_guest_exists_entity(self):
        settings = _make_settings()
        user = User("guest_1", _make_user_config(guest=True), settings)
        assert user.exists_entity.full == "switch.person_guest_1_exists"

    def test_non_guest_exists_raises(self):
        settings = _make_settings()
        user = User("nick", _make_user_config(guest=False), settings)
        with pytest.raises(AssertionError):
            _ = user.exists_entity

    def test_group_presence_entity(self):
        settings = _make_settings()
        group = Group("everyone", {"nick", "partner"}, settings)
        assert group.presence_entity.full == "sensor.group_presence_everyone"


# --- LightState ---


class TestLightState:
    def test_full_profile(self):
        settings = _make_settings()
        raw = RawLightProfile(
            enabled=True, icon="mdi:light", brightness_pct=75, transition=2
        )
        ls = LightState("full", raw, settings)
        assert ls.source_profile == "full"
        assert ls.enable.value is True
        assert ls.brightness.value == 75
        assert ls.icon.value == "mdi:light"
        assert ls.transition.value == 2

    def test_minimal_profile(self):
        settings = _make_settings()
        raw = RawLightProfile(
            enabled=None, icon=None, brightness_pct=None, transition=None
        )
        ls = LightState("noop", raw, settings)
        assert ls.enable is None
        assert ls.brightness is None
        assert ls.icon is None
        assert ls.transition.value == 0


# --- DataSource / InputEntity ---


class TestDataSource:
    def test_holds_value(self):
        ds = DataSource(42)
        assert ds.value == 42

    def test_holds_string(self):
        ds = DataSource("hello")
        assert ds.value == "hello"


class TestInputEntity:
    def test_holds_entity(self):
        ie = InputEntity("sensor.test")
        assert ie.entity == "sensor.test"
