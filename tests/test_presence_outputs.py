"""Tests for presence outputs - presence rules published as binary sensors."""

import copy

import pytest
import voluptuous as vol

from custom_components.light_motion_profiles import build_domains
from custom_components.light_motion_profiles.config import RawConfig
from custom_components.light_motion_profiles.config.validators import InvalidConfigError
from custom_components.light_motion_profiles.datatypes import Config


BASE_CONFIG = {
    "settings": {
        "room": {"valid_room_states": ["auto", "manual"]},
        "user_group": {"valid_person_states": ["awake", "winddown", "asleep"]},
    },
    "templates": {},
    "light_profiles": {},
    "light_configs": {},
    "users": {
        "nick": {"guest": False},
        "britta": {"guest": False},
        "guest_1": {"guest": True},
    },
    "groups": {
        "primary": ["nick", "britta"],
        "everyone": ["nick", "britta", "guest_1"],
    },
}


def _config(**extra):
    data = copy.deepcopy(BASE_CONFIG)
    data.update(extra)
    data = RawConfig.vol()(data)
    return Config(RawConfig.from_yaml(data), build_domains())


class TestAutomaticOutputs:
    def test_every_group_gets_any_awake_and_any_asleep(self):
        config = _config()
        assert set(config.presence_outputs) == {
            "primary_any_awake",
            "primary_any_asleep",
            "everyone_any_awake",
            "everyone_any_asleep",
        }

    def test_entity_is_a_prefixed_binary_sensor(self):
        output = _config().presence_outputs["everyone_any_asleep"]
        assert output.entity.full == "binary_sensor.presence_output_everyone_any_asleep"

    def test_reads_the_group_presence(self):
        output = _config().presence_outputs["everyone_any_asleep"]
        assert output.get_users() == {"everyone"}

    def test_any_asleep_is_on_when_one_member_sleeps(self):
        """The guest asleep while Nick is up: the case a group presence
        sensor alone cannot answer."""
        outputs = _config().presence_outputs
        states = {"everyone": {"awake", "asleep"}}
        assert outputs["everyone_any_asleep"].match(states) is True
        assert outputs["everyone_any_awake"].match(states) is True

    def test_any_asleep_is_off_when_everyone_is_up(self):
        outputs = _config().presence_outputs
        states = {"everyone": {"awake", "winddown"}}
        assert outputs["everyone_any_asleep"].match(states) is False
        assert outputs["everyone_any_awake"].match(states) is True

    def test_winddown_is_neither_awake_nor_asleep(self):
        outputs = _config().presence_outputs
        states = {"everyone": {"winddown"}}
        assert outputs["everyone_any_asleep"].match(states) is False
        assert outputs["everyone_any_awake"].match(states) is False

    def test_everyone_absent_is_neither(self):
        outputs = _config().presence_outputs
        states = {"everyone": {"absent"}}
        assert outputs["everyone_any_asleep"].match(states) is False
        assert outputs["everyone_any_awake"].match(states) is False

    def test_only_generated_for_states_the_house_uses(self):
        """An output that can never turn on would look like a working rule."""
        data = copy.deepcopy(BASE_CONFIG)
        data["settings"]["user_group"]["valid_person_states"] = ["awake", "away"]
        config = Config(RawConfig.from_yaml(data), build_domains())
        assert "everyone_any_awake" in config.presence_outputs
        assert "everyone_any_asleep" not in config.presence_outputs


class TestConfiguredOutputs:
    def test_parses_with_all_by_default(self):
        config = _config(
            presence_outputs={
                "nick_up_guest_asleep": {
                    "user_state": [
                        {"user": "nick", "state_any": "awake"},
                        {"user": "guest_1", "state_any": "asleep"},
                    ]
                }
            }
        )
        output = config.presence_outputs["nick_up_guest_asleep"]
        assert output.match_any is False
        assert output.get_users() == {"nick", "guest_1"}
        assert (
            output.entity.full == "binary_sensor.presence_output_nick_up_guest_asleep"
        )
        assert output.match({"nick": {"awake"}, "guest_1": {"asleep"}}) is True
        assert output.match({"nick": {"asleep"}, "guest_1": {"asleep"}}) is False

    def test_match_any(self):
        config = _config(
            presence_outputs={
                "either_asleep": {
                    "match": "any",
                    "user_state": [
                        {"user": "nick", "state_any": "asleep"},
                        {"user": "guest_1", "state_any": "asleep"},
                    ],
                }
            }
        )
        output = config.presence_outputs["either_asleep"]
        assert output.match({"nick": {"awake"}, "guest_1": {"asleep"}}) is True
        assert output.match({"nick": {"awake"}, "guest_1": {"awake"}}) is False

    def test_can_match_on_absent(self):
        config = _config(
            presence_outputs={
                "house_empty": {
                    "user_state": [{"user": "everyone", "state_exact": "absent"}]
                }
            }
        )
        output = config.presence_outputs["house_empty"]
        assert output.match({"everyone": {"absent"}}) is True
        assert output.match({"everyone": {"awake"}}) is False

    def test_unknown_user_is_rejected(self):
        with pytest.raises(InvalidConfigError, match="unknown user or group 'bob'"):
            _config(
                presence_outputs={
                    "x": {"user_state": [{"user": "bob", "state_any": "asleep"}]}
                }
            )

    def test_name_colliding_with_an_automatic_output_is_rejected(self):
        with pytest.raises(InvalidConfigError, match="same name as an automatic"):
            _config(
                presence_outputs={
                    "everyone_any_asleep": {
                        "user_state": [{"user": "nick", "state_any": "asleep"}]
                    }
                }
            )

    def test_bad_match_mode_is_rejected(self):
        with pytest.raises(vol.Invalid):
            _config(
                presence_outputs={
                    "x": {
                        "match": "most",
                        "user_state": [{"user": "nick", "state_any": "asleep"}],
                    }
                }
            )

    def test_empty_user_state_is_rejected(self):
        with pytest.raises(vol.Invalid):
            _config(presence_outputs={"x": {"user_state": []}})

    def test_configs_without_outputs_still_load(self):
        data = RawConfig.from_yaml(copy.deepcopy(BASE_CONFIG))
        assert data.presence_outputs == {}
