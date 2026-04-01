"""Tests for config/validators.py."""
import pytest
import voluptuous as vol

from custom_components.light_motion_profiles.config.validators import (
    unique_list,
    InvalidConfigError,
)


class TestUniqueList:
    def test_valid_unique_list(self):
        validator = unique_list(str)
        result = validator(["a", "b", "c"])
        assert result == {"a", "b", "c"}

    def test_duplicate_raises(self):
        validator = unique_list(str)
        with pytest.raises(vol.Invalid, match="Duplicate"):
            validator(["a", "b", "a"])

    def test_non_list_raises(self):
        validator = unique_list(str)
        with pytest.raises(vol.Invalid, match="Expected list"):
            validator("not a list")

    def test_non_list_dict_raises(self):
        validator = unique_list(str)
        with pytest.raises(vol.Invalid, match="Expected list"):
            validator({"a": 1})

    def test_empty_list(self):
        validator = unique_list(str)
        result = validator([])
        assert result == set()

    def test_with_int_inner(self):
        validator = unique_list(int)
        result = validator([1, 2, 3])
        assert result == {1, 2, 3}

    def test_inner_transform_applied(self):
        validator = unique_list(str.upper)
        result = validator(["a", "b"])
        assert result == {"A", "B"}

    def test_inner_transform_causes_duplicate(self):
        validator = unique_list(str.upper)
        with pytest.raises(vol.Invalid, match="Duplicate"):
            validator(["a", "A"])


class TestInvalidConfigError:
    def test_is_exception(self):
        assert issubclass(InvalidConfigError, Exception)

    def test_message(self):
        e = InvalidConfigError("test message")
        assert str(e) == "test message"
