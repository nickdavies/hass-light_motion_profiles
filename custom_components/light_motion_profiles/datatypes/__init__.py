from dataclasses import dataclass
from typing import List

from .entity import Entity
from .match import RuleMatch
from .source import DataSource


@dataclass
class LightState:
    icon: DataSource
    enable: DataSource
    brightness: DataSource
    color: DataSource
    transition: DataSource


@dataclass
class LightRule:
    state_name: str
    rule_match: RuleMatch


@dataclass
class LightGroup:
    name: str
    lights: Entity
    users: List[str]
    occupancy_sensors: List[Entity]
    occupancy_timeout: DataSource
    rules: List[LightRule]
