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
    _make_data_source,
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
            enabled=True,
            icon="mdi:light",
            brightness_pct=75,
            color_temp_kelvin=3000,
            transition=2,
        )
        ls = LightState("full", raw, settings)
        assert ls.source_profile == "full"
        assert ls.enable.value is True
        assert ls.brightness.value == 75
        assert ls.color_temp.value == 3000
        assert ls.icon.value == "mdi:light"
        assert ls.transition.value == 2

    def test_minimal_profile(self):
        settings = _make_settings()
        raw = RawLightProfile(
            enabled=None,
            icon=None,
            brightness_pct=None,
            color_temp_kelvin=None,
            transition=None,
        )
        ls = LightState("noop", raw, settings)
        assert ls.enable is None
        assert ls.brightness is None
        assert ls.icon is None
        assert ls.color_temp is None
        assert ls.transition.value == 0

    def test_color_not_set_when_not_configured(self):
        """When color_temp_kelvin is not specified, LightState.color must be None.

        This ensures color temp is never included in the service call,
        preserving external color management.
        """
        settings = _make_settings()
        raw = RawLightProfile(
            enabled=True,
            icon=None,
            brightness_pct=100,
            color_temp_kelvin=None,
            transition=None,
        )
        ls = LightState("no_color", raw, settings)
        assert ls.color_temp is None

    def test_color_temp_kelvin_static(self):
        settings = _make_settings()
        raw = RawLightProfile(
            enabled=True,
            icon=None,
            brightness_pct=None,
            color_temp_kelvin=2700,
            transition=None,
        )
        ls = LightState("warm", raw, settings)
        assert ls.color_temp is not None
        assert ls.color_temp.value == 2700
        assert ls.color_temp.entity_id is None

    def test_color_temp_kelvin_entity(self):
        settings = _make_settings()
        raw = RawLightProfile(
            enabled=True,
            icon=None,
            brightness_pct=None,
            color_temp_kelvin={"entity_id": "input_number.color_temp"},
            transition=None,
        )
        ls = LightState("adaptive_color", raw, settings)
        assert ls.color_temp is not None
        assert ls.color_temp.entity_id == "input_number.color_temp"
        assert ls.color_temp.value is None

    def test_brightness_entity(self):
        settings = _make_settings()
        raw = RawLightProfile(
            enabled=True,
            icon=None,
            brightness_pct={"entity_id": "input_number.brightness"},
            color_temp_kelvin=None,
            transition=None,
        )
        ls = LightState("adaptive_bright", raw, settings)
        assert ls.brightness is not None
        assert ls.brightness.entity_id == "input_number.brightness"

    def test_transition_entity(self):
        settings = _make_settings()
        raw = RawLightProfile(
            enabled=True,
            icon=None,
            brightness_pct=None,
            color_temp_kelvin=None,
            transition={"entity_id": "input_number.transition"},
        )
        ls = LightState("adaptive_transition", raw, settings)
        assert ls.transition.entity_id == "input_number.transition"

    def test_get_entity_ids_collects_all(self):
        settings = _make_settings()
        raw = RawLightProfile(
            enabled=True,
            icon=None,
            brightness_pct={"entity_id": "input_number.brightness"},
            color_temp_kelvin={"entity_id": "input_number.color_temp"},
            transition={"entity_id": "input_number.transition"},
        )
        ls = LightState("all_entities", raw, settings)
        ids = ls.get_entity_ids()
        assert "input_number.brightness" in ids
        assert "input_number.color_temp" in ids
        assert "input_number.transition" in ids

    def test_get_entity_ids_empty_for_static(self):
        settings = _make_settings()
        raw = RawLightProfile(
            enabled=True,
            icon=None,
            brightness_pct=75,
            color_temp_kelvin=2700,
            transition=5,
        )
        ls = LightState("static", raw, settings)
        assert ls.get_entity_ids() == []


# --- DataSource / InputEntity ---


class TestDataSource:
    def test_holds_value(self):
        ds = DataSource(42)
        assert ds.value == 42

    def test_holds_string(self):
        ds = DataSource("hello")
        assert ds.value == "hello"

    def test_static_resolve_returns_value(self):
        ds = DataSource(75)
        assert ds.resolve(None) == 75

    def test_entity_resolve_returns_entity_state(self):
        class MockState:
            state = "80.0"

        class MockHass:
            class states:
                @staticmethod
                def get(entity_id):
                    if entity_id == "input_number.brightness":
                        return MockState()
                    return None

        ds = DataSource(entity_id="input_number.brightness")
        assert ds.resolve(MockHass()) == "80.0"

    def test_entity_resolve_falls_back_when_unavailable(self):
        class MockState:
            state = "unavailable"

        class MockHass:
            class states:
                @staticmethod
                def get(entity_id):
                    return MockState()

        ds = DataSource(value=50, entity_id="input_number.brightness")
        assert ds.resolve(MockHass()) == 50

    def test_entity_resolve_falls_back_when_missing(self):
        class MockHass:
            class states:
                @staticmethod
                def get(entity_id):
                    return None

        ds = DataSource(value=50, entity_id="input_number.brightness")
        assert ds.resolve(MockHass()) == 50

    def test_entity_resolve_no_fallback_returns_none(self):
        class MockHass:
            class states:
                @staticmethod
                def get(entity_id):
                    return None

        ds = DataSource(entity_id="input_number.brightness")
        assert ds.resolve(MockHass()) is None

    def test_get_entity_ids_with_entity(self):
        ds = DataSource(entity_id="input_number.brightness")
        assert ds.get_entity_ids() == ["input_number.brightness"]

    def test_get_entity_ids_without_entity(self):
        ds = DataSource(42)
        assert ds.get_entity_ids() == []


class TestMakeDataSource:
    def test_none_returns_none(self):
        assert _make_data_source(None) is None

    def test_static_int(self):
        ds = _make_data_source(75, int)
        assert ds is not None
        assert ds.value == 75
        assert ds.entity_id is None

    def test_static_string_with_cast(self):
        ds = _make_data_source("100", int)
        assert ds is not None
        assert ds.value == 100

    def test_static_without_cast(self):
        ds = _make_data_source("hello")
        assert ds is not None
        assert ds.value == "hello"

    def test_entity_dict(self):
        ds = _make_data_source({"entity_id": "input_number.brightness"}, int)
        assert ds is not None
        assert ds.entity_id == "input_number.brightness"
        assert ds.value is None

    def test_entity_dict_without_cast(self):
        ds = _make_data_source({"entity_id": "input_number.test"})
        assert ds is not None
        assert ds.entity_id == "input_number.test"
        assert ds.value is None

    def test_dict_without_entity_id_treated_as_static(self):
        ds = _make_data_source({"other_key": "val"})
        assert ds is not None
        assert ds.value == {"other_key": "val"}
        assert ds.entity_id is None


class TestDataSourceResolveUnknown:
    def test_entity_resolve_falls_back_when_unknown(self):
        class MockState:
            state = "unknown"

        class MockHass:
            class states:
                @staticmethod
                def get(entity_id):
                    return MockState()

        ds = DataSource(value=42, entity_id="input_number.test")
        assert ds.resolve(MockHass()) == 42


class TestInputEntity:
    def test_holds_entity(self):
        ie = InputEntity("sensor.test")
        assert ie.entity == "sensor.test"
