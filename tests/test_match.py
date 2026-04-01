"""Tests for datatypes/match.py - the core rule matching logic."""

import pytest

from custom_components.light_motion_profiles.config.light_profiles import (
    Match as RawMatch,
    UserState as RawUserState,
)
from custom_components.light_motion_profiles.config.validators import InvalidConfigError
from custom_components.light_motion_profiles.datatypes.match import (
    MatchSingle,
    MatchSingleExplicit,
    MatchSingleWildcard,
    MatchSingleAny,
    MatchMultiAny,
    MatchMultiAll,
    MatchMultiExact,
    MatchUser,
    MatchUserSingle,
    MatchUserWildcard,
    MatchError,
    RuleMatch,
)


# --- MatchSingle ---


class TestMatchSingleExplicit:
    def test_matches_exact_value(self):
        m = MatchSingleExplicit("awake")
        assert m.match("awake") is True

    def test_rejects_different_value(self):
        m = MatchSingleExplicit("awake")
        assert m.match("asleep") is False

    def test_rejects_empty_string(self):
        m = MatchSingleExplicit("awake")
        assert m.match("") is False


class TestMatchSingleWildcard:
    def test_matches_any_value(self):
        m = MatchSingleWildcard()
        assert m.match("awake") is True
        assert m.match("asleep") is True
        assert m.match("") is True
        assert m.match("anything") is True


class TestMatchSingleAny:
    def test_matches_value_in_set(self):
        m = MatchSingleAny({"awake", "winddown"})
        assert m.match("awake") is True
        assert m.match("winddown") is True

    def test_rejects_value_not_in_set(self):
        m = MatchSingleAny({"awake", "winddown"})
        assert m.match("asleep") is False

    def test_empty_set_matches_nothing(self):
        m = MatchSingleAny(set())
        assert m.match("anything") is False


class TestMatchSingleFromRaw:
    def test_explicit_string(self):
        result = MatchSingle.from_raw(RawMatch(value="awake"))
        assert isinstance(result, MatchSingleExplicit)
        assert result.match("awake") is True

    def test_wildcard(self):
        result = MatchSingle.from_raw(RawMatch(value="*"))
        assert isinstance(result, MatchSingleWildcard)

    def test_set_of_values(self):
        result = MatchSingle.from_raw(RawMatch(value={"awake", "winddown"}))
        assert isinstance(result, MatchSingleAny)
        assert result.match("awake") is True
        assert result.match("asleep") is False


# --- MatchMulti ---


class TestMatchMultiAny:
    def test_single_string_match(self):
        m = MatchMultiAny(MatchSingleExplicit("awake"))
        assert m.match("awake") is True
        assert m.match("asleep") is False

    def test_set_any_match(self):
        m = MatchMultiAny(MatchSingleExplicit("awake"))
        assert m.match({"awake", "asleep"}) is True

    def test_set_no_match(self):
        m = MatchMultiAny(MatchSingleExplicit("awake"))
        assert m.match({"asleep", "winddown"}) is False

    def test_wildcard_always_matches(self):
        m = MatchMultiAny(MatchSingleWildcard())
        assert m.match({"asleep", "winddown"}) is True


class TestMatchMultiAll:
    def test_single_string_match(self):
        m = MatchMultiAll(MatchSingleExplicit("awake"))
        assert m.match("awake") is True

    def test_set_all_match(self):
        m = MatchMultiAll(MatchSingleAny({"awake", "winddown"}))
        assert m.match({"awake", "winddown"}) is True

    def test_set_not_all_match(self):
        m = MatchMultiAll(MatchSingleAny({"awake", "winddown"}))
        assert m.match({"awake", "asleep"}) is False

    def test_wildcard_all_match(self):
        m = MatchMultiAll(MatchSingleWildcard())
        assert m.match({"awake", "asleep"}) is True


class TestMatchMultiExact:
    def test_wildcard_never_matches(self):
        m = MatchMultiExact(MatchSingleWildcard())
        assert m.match("awake") is False
        assert m.match({"awake"}) is False

    def test_explicit_single_string(self):
        m = MatchMultiExact(MatchSingleExplicit("awake"))
        assert m.match("awake") is True
        assert m.match("asleep") is False

    def test_explicit_set_must_be_exact(self):
        m = MatchMultiExact(MatchSingleExplicit("awake"))
        assert m.match({"awake"}) is True
        assert m.match({"awake", "winddown"}) is False

    def test_any_set_exact_match(self):
        m = MatchMultiExact(MatchSingleAny({"awake", "winddown"}))
        assert m.match({"awake", "winddown"}) is True
        assert m.match({"awake"}) is False
        assert m.match({"awake", "winddown", "asleep"}) is False

    def test_string_target_wrapped_to_set(self):
        m = MatchMultiExact(MatchSingleAny({"awake"}))
        assert m.match("awake") is True


# --- MatchUser ---


class TestMatchUserSingle:
    def test_matches_user_state(self):
        m = MatchUserSingle(
            user="nick", match_multi=MatchMultiAny(MatchSingleExplicit("awake"))
        )
        assert m.match({"nick": "awake", "partner": "asleep"}) is True

    def test_rejects_wrong_state(self):
        m = MatchUserSingle(
            user="nick", match_multi=MatchMultiAny(MatchSingleExplicit("awake"))
        )
        assert m.match({"nick": "asleep", "partner": "asleep"}) is False

    def test_missing_user_raises_error(self):
        m = MatchUserSingle(
            user="nick", match_multi=MatchMultiAny(MatchSingleExplicit("awake"))
        )
        with pytest.raises(MatchError, match="nick"):
            m.match({"partner": "asleep"})


class TestMatchUserWildcard:
    def test_always_matches(self):
        m = MatchUserWildcard()
        assert m.match({"nick": "awake"}) is True
        assert m.match({}) is True


class TestMatchUserFromRaw:
    def test_state_any(self):
        raw = RawUserState(
            user="nick",
            state_any=RawMatch(value="awake"),
            state_all=None,
            state_exact=None,
        )
        result = MatchUser.from_raw(raw)
        assert isinstance(result, MatchUserSingle)
        assert result.match({"nick": "awake"}) is True

    def test_state_all(self):
        raw = RawUserState(
            user="nick", state_any=None, state_all=RawMatch(value="*"), state_exact=None
        )
        result = MatchUser.from_raw(raw)
        assert isinstance(result, MatchUserSingle)
        assert result.match({"nick": {"awake", "winddown"}}) is True

    def test_state_exact(self):
        raw = RawUserState(
            user="nick",
            state_any=None,
            state_all=None,
            state_exact=RawMatch(value={"awake", "winddown"}),
        )
        result = MatchUser.from_raw(raw)
        assert isinstance(result, MatchUserSingle)
        assert result.match({"nick": {"awake", "winddown"}}) is True
        assert result.match({"nick": {"awake"}}) is False


# --- RuleMatch ---


class TestRuleMatch:
    def test_full_match(self):
        rm = RuleMatch(
            room_state=RawMatch(value="default"),
            occupancy=RawMatch(value="occupied"),
            user_state=[
                RawUserState(
                    user="nick",
                    state_any=RawMatch(value="awake"),
                    state_all=None,
                    state_exact=None,
                ),
            ],
        )
        assert rm.match("default", "occupied", {"nick": "awake"}) is True

    def test_room_state_mismatch(self):
        rm = RuleMatch(
            room_state=RawMatch(value="default"),
            occupancy=RawMatch(value="occupied"),
            user_state=RawMatch(value="*"),
        )
        assert rm.match("other", "occupied", {"nick": "awake"}) is False

    def test_occupancy_mismatch(self):
        rm = RuleMatch(
            room_state=RawMatch(value="default"),
            occupancy=RawMatch(value="occupied"),
            user_state=RawMatch(value="*"),
        )
        assert rm.match("default", "empty", {"nick": "awake"}) is False

    def test_wildcard_user_state(self):
        rm = RuleMatch(
            room_state=RawMatch(value="*"),
            occupancy=RawMatch(value="*"),
            user_state=RawMatch(value="*"),
        )
        assert rm.match("anything", "anything", {"nick": "anything"}) is True

    def test_non_wildcard_single_user_state_raises(self):
        with pytest.raises(InvalidConfigError):
            RuleMatch(
                room_state=RawMatch(value="default"),
                occupancy=RawMatch(value="occupied"),
                user_state=RawMatch(value="awake"),
            )

    def test_get_users(self):
        rm = RuleMatch(
            room_state=RawMatch(value="*"),
            occupancy=RawMatch(value="*"),
            user_state=[
                RawUserState(
                    user="nick",
                    state_any=RawMatch(value="awake"),
                    state_all=None,
                    state_exact=None,
                ),
                RawUserState(
                    user="partner",
                    state_any=RawMatch(value="*"),
                    state_all=None,
                    state_exact=None,
                ),
            ],
        )
        assert rm.get_users() == {"nick", "partner"}

    def test_get_users_wildcard_returns_empty(self):
        rm = RuleMatch(
            room_state=RawMatch(value="*"),
            occupancy=RawMatch(value="*"),
            user_state=RawMatch(value="*"),
        )
        assert rm.get_users() == set()

    def test_multiple_user_states_all_must_match(self):
        rm = RuleMatch(
            room_state=RawMatch(value="*"),
            occupancy=RawMatch(value="*"),
            user_state=[
                RawUserState(
                    user="nick",
                    state_any=RawMatch(value="awake"),
                    state_all=None,
                    state_exact=None,
                ),
                RawUserState(
                    user="partner",
                    state_any=RawMatch(value="asleep"),
                    state_all=None,
                    state_exact=None,
                ),
            ],
        )
        assert (
            rm.match("default", "occupied", {"nick": "awake", "partner": "asleep"})
            is True
        )
        assert (
            rm.match("default", "occupied", {"nick": "awake", "partner": "awake"})
            is False
        )

    def test_set_match_in_room_state(self):
        rm = RuleMatch(
            room_state=RawMatch(value={"default", "night"}),
            occupancy=RawMatch(value="*"),
            user_state=RawMatch(value="*"),
        )
        assert rm.match("default", "occupied", {}) is True
        assert rm.match("night", "occupied", {}) is True
        assert rm.match("other", "occupied", {}) is False
