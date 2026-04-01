"""Tests for exhaustive.py - truth table generation and rule validation."""
import pytest

from custom_components.light_motion_profiles.exhaustive import (
    Wildcard,
    Options,
    MatchResult,
    UserCombinator,
    calculate_key,
)
from custom_components.light_motion_profiles.datatypes import (
    User,
    Group,
    UsersGroups,
    Domains,
    Settings,
)
from custom_components.light_motion_profiles.datatypes.entity import Domain
from custom_components.light_motion_profiles.config.settings import (
    AllSettings as RawAllSettings,
)
from custom_components.light_motion_profiles.config.users_groups import UserConfig as RawUserConfig


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


def _make_settings():
    raw = RawAllSettings.from_yaml({
        "room": {"valid_room_states": ["default", "night"]},
        "user_group": {"valid_person_states": ["awake", "winddown", "asleep"]},
    })
    return Settings(raw, _make_domains())


def _make_user_config(guest=False):
    return RawUserConfig(
        guest=guest,
        exists_icon=None,
        home_away_icons={},
        state_icons={},
        tracking_entity=None,
    )


# --- calculate_key ---


class TestCalculateKey:
    def test_string_values(self):
        result = calculate_key({"a": "x", "b": "y"})
        assert result == "x:y"

    def test_set_values_sorted(self):
        result = calculate_key({"a": {"c", "a", "b"}})
        assert result == "a,b,c"

    def test_mixed_values(self):
        result = calculate_key({"a": "x", "b": {"c", "a"}})
        assert result == "x:a,c"


# --- MatchResult.to_tabulate ---


class TestMatchResultToTabulate:
    def test_basic(self):
        mr = MatchResult(
            occupancy="occupied",
            room="default",
            user_state={"nick": "awake"},
            rule_name="rule1",
        )
        tab = mr.to_tabulate()
        assert tab["room_state"] == "default"
        assert tab["occupancy"] == "occupied"
        assert tab["user: nick"] == "awake"
        assert tab["rule_name"] == "rule1"

    def test_unassigned(self):
        mr = MatchResult(
            occupancy="occupied",
            room="default",
            user_state={},
            rule_name=None,
        )
        tab = mr.to_tabulate()
        assert tab["rule_name"] == "UNASSIGNED!"

    def test_wildcard_value(self):
        mr = MatchResult(
            occupancy="occupied",
            room="default",
            user_state={"nick": Wildcard()},
            rule_name="rule1",
        )
        tab = mr.to_tabulate()
        assert tab["user: nick"] == "*"

    def test_options_value(self):
        mr = MatchResult(
            occupancy="occupied",
            room="default",
            user_state={"nick": Options({"awake", "asleep"})},
            rule_name="rule1",
        )
        tab = mr.to_tabulate()
        # Options are joined with |, order may vary
        assert set(tab["user: nick"].split("|")) == {"awake", "asleep"}

    def test_set_value(self):
        mr = MatchResult(
            occupancy="occupied",
            room="default",
            user_state={"nick": {"awake", "asleep"}},
            rule_name="rule1",
        )
        tab = mr.to_tabulate()
        assert set(tab["user: nick"].split(",")) == {"awake", "asleep"}


# --- UserCombinator ---


class TestUserCombinator:
    def test_single_user_combinations(self):
        settings = _make_settings()
        ug = UsersGroups(
            users={"nick": _make_user_config()},
            groups={},
            settings=settings,
        )
        combinator = UserCombinator(
            users_groups=ug,
            single_person_states={"awake", "asleep"},
            absent_state="absent",
        )
        user = ug.get("nick")
        combos = list(combinator.combinations_for_target(user))
        # 2 person states + absent = 3 combinations
        assert len(combos) == 3
        states = {c["nick"] for c in combos}
        assert states == {"awake", "asleep", "absent"}

    def test_two_user_combinations(self):
        settings = _make_settings()
        ug = UsersGroups(
            users={"nick": _make_user_config(), "partner": _make_user_config()},
            groups={"both": {"nick", "partner"}},
            settings=settings,
        )
        combinator = UserCombinator(
            users_groups=ug,
            single_person_states={"awake", "asleep"},
            absent_state="absent",
        )
        group = ug.get("both")
        combos = list(combinator.combinations_for_target(group))
        # 3 states per user, 2 users = 9 combinations
        assert len(combos) == 9
        # Each combo should have nick, partner, and the group "both"
        for combo in combos:
            assert "nick" in combo
            assert "partner" in combo
            assert "both" in combo

    def test_group_state_resolution(self):
        settings = _make_settings()
        ug = UsersGroups(
            users={"nick": _make_user_config(), "partner": _make_user_config()},
            groups={"both": {"nick", "partner"}},
            settings=settings,
        )
        combinator = UserCombinator(
            users_groups=ug,
            single_person_states={"awake"},
            absent_state="absent",
        )
        group = ug.get("both")
        combos = list(combinator.combinations_for_target(group))
        # 2 states (awake, absent) per user = 4 combos
        for combo in combos:
            if combo["nick"] == "awake" and combo["partner"] == "awake":
                assert combo["both"] == {"awake"}
            elif combo["nick"] == "awake" and combo["partner"] == "absent":
                assert combo["both"] == {"awake"}
            elif combo["nick"] == "absent" and combo["partner"] == "absent":
                assert combo["both"] == {"absent"}
