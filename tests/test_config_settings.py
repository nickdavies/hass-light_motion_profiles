"""Tests for config/settings.py."""

from custom_components.light_motion_profiles.config.settings import (
    OccupancyStates,
    HomeAwayStates,
    KillswitchSettings,
    RoomSettings,
    UserGroupSettings,
    DashboardSettings,
    AllSettings,
)


class TestOccupancyStates:
    def test_from_yaml_defaults(self):
        s = OccupancyStates.from_yaml()
        assert s.occupied == "occupied"
        assert s.occupied_timeout == "occupied_timeout"
        assert s.empty == "empty"
        assert s.unknown == "unknown"

    def test_all_states(self):
        s = OccupancyStates.from_yaml()
        assert s.all_states() == {"occupied", "occupied_timeout", "empty", "unknown"}


class TestHomeAwayStates:
    def test_from_yaml_defaults(self):
        s = HomeAwayStates.from_yaml()
        assert s.auto == "auto"
        assert s.home == "home"
        assert s.not_home == "not_home"
        assert s.unknown == "unknown"

    def test_all_states(self):
        s = HomeAwayStates.from_yaml()
        assert s.all_states() == {"auto", "unknown", "home", "not_home"}


class TestKillswitchSettings:
    def test_from_yaml_defaults(self):
        s = KillswitchSettings.from_yaml()
        assert s.global_name == "global"
        assert s.global_icon == "mdi:cancel"
        assert s.default_icon == "mdi:motion-sensor-off"


class TestRoomSettings:
    def test_from_yaml(self):
        data = {"valid_room_states": ["default", "night", "movie"]}
        s = RoomSettings.from_yaml(data)
        assert s.valid_room_states == {"default", "night", "movie"}
        assert isinstance(s.occupancy_states, OccupancyStates)


class TestUserGroupSettings:
    def test_from_yaml(self):
        data = {"valid_person_states": ["awake", "winddown", "asleep"]}
        s = UserGroupSettings.from_yaml(data)
        assert s.valid_person_states == {"awake", "winddown", "asleep"}
        assert s.absent_state == "absent"
        assert s.state_if_unknown == "absent"
        assert isinstance(s.home_away_states, HomeAwayStates)


class TestDashboardSettings:
    def test_from_yaml(self):
        s = DashboardSettings.from_yaml({})
        assert s is not None


class TestAllSettings:
    def test_from_yaml_with_dashboard(self):
        data = {
            "room": {"valid_room_states": ["default"]},
            "user_group": {"valid_person_states": ["awake"]},
            "debug_dashboard": {},
        }
        s = AllSettings.from_yaml(data)
        assert isinstance(s.room, RoomSettings)
        assert isinstance(s.users_groups, UserGroupSettings)
        assert s.dashboard is not None
        assert isinstance(s.killswitch, KillswitchSettings)

    def test_from_yaml_without_dashboard(self):
        data = {
            "room": {"valid_room_states": ["default"]},
            "user_group": {"valid_person_states": ["awake"]},
        }
        s = AllSettings.from_yaml(data)
        assert s.dashboard is None
