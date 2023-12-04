"""
This file contains only the "pure" structs for the config without
any templating in them at all. This is all fully resolved after
templates are applied
"""
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class Match:
    value: str | List[str]

    def match_single(self, value: str) -> bool:
        if self.value == "*":
            return True
        return self.value == value

    def match(self, value: str | List[str]) -> bool:
        if isinstance(self.value, list):
            return any(self.match_single(v) for v in self.value)
        return self.match_single(value)


@dataclass
class UserState:
    user: Match
    state_any: Match | None
    state_exact: Match | None


@dataclass
class LightRule:
    state_name: Match
    room_state: Match
    occupancy: Match
    user_state: UserState
    light_profile: str


@dataclass
class LightProfileConfig:
    lights: str
    occupancy_sensors: str | List[str]
    occupancy_timeout: int
    users: str | List[str]
    light_profile_rules: List[LightRule]


@dataclass
class WholeConfig:
    light_profiles: None
    light_configs: Dict[str, LightProfileConfig]
