"""Tests for config/settings.py."""

import pytest
import voluptuous as vol

from custom_components.light_motion_profiles.config.settings import (
    OccupancyStates,
    HomeAwayStates,
    KillswitchSettings,
    RoomSettings,
    UserGroupSettings,
    DashboardSettings,
    Floorplan,
    RefreshSettings,
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


# homelab-data's area list for a floor, as `!include` reads it.
MAIN_PLAN = {
    "image": "/local/floorplan/main.svg",
    "areas": {"kitchen": {"room": "kitchen"}, "pantry": {"room": "pantry"}},
}


class TestDashboardSettings:
    def test_from_yaml(self):
        s = DashboardSettings.from_yaml({})
        assert s.floorplans == []

    def test_empty_key_has_no_floorplans(self):
        assert DashboardSettings.vol()(None) is None
        assert DashboardSettings.from_yaml(None).floorplans == []

    def test_a_floorplan_is_its_image_and_area_ids(self):
        data = DashboardSettings.vol()({"floorplans": {"main": MAIN_PLAN}})
        s = DashboardSettings.from_yaml(data)
        assert s.floorplans == [
            Floorplan("main", "/local/floorplan/main.svg", ["kitchen", "pantry"])
        ]

    def test_floorplans_keep_their_order(self):
        data = {"floorplans": {"upstairs": MAIN_PLAN, "main": MAIN_PLAN}}
        s = DashboardSettings.from_yaml(DashboardSettings.vol()(data))
        assert [plan.name for plan in s.floorplans] == ["upstairs", "main"]

    def test_homelab_data_can_add_keys(self):
        plan = {**MAIN_PLAN, "areas": {"patio": {"kind": "outdoor"}}, "floor": 0}
        DashboardSettings.vol()({"floorplans": {"main": plan}})

    def test_a_plan_without_areas_has_none(self):
        """Home Assistant's package merge drops an empty `areas: {}`."""
        data = {"floorplans": {"main": {"image": "/local/floorplan/main.svg"}}}
        s = DashboardSettings.from_yaml(DashboardSettings.vol()(data))
        assert s.floorplans == [Floorplan("main", "/local/floorplan/main.svg", [])]

    @pytest.mark.parametrize(
        "plan",
        [
            {"areas": {}},
            {"image": "/local/floorplan/main.svg", "areas": ["kitchen"]},
        ],
    )
    def test_rejects_what_isnt_an_area_list(self, plan):
        with pytest.raises(vol.Invalid):
            DashboardSettings.vol()({"floorplans": {"main": plan}})


class TestRefreshSettings:
    def test_transition_defaults_to_ten_seconds(self):
        for data in (None, {}):
            assert (
                RefreshSettings.from_yaml(RefreshSettings.vol()(data)).transition == 10
            )

    def test_transition(self):
        data = RefreshSettings.vol()({"transition": 0})
        assert RefreshSettings.from_yaml(data).transition == 0

    def test_rejects_an_unknown_key(self):
        with pytest.raises(vol.Invalid):
            RefreshSettings.vol()({"spread": 300})


class TestAllSettings:
    def test_refresh_is_optional(self):
        data = {
            "room": {"valid_room_states": ["default"]},
            "user_group": {"valid_person_states": ["awake"]},
        }
        AllSettings.vol()({**data, "debug_dashboard": None})
        assert AllSettings.from_yaml(data).refresh == RefreshSettings(transition=10)

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
