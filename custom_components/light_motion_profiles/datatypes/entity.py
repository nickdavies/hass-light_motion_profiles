from enum import StrEnum
from dataclasses import dataclass


class Domain(StrEnum):
    SENSOR = "sensor"
    SELECT = "select"
    SWITCH = "switch"
    BINARY_SENSOR = "binary_sensor"


@dataclass
class Domains:
    """
    Contains a list of all domains for all the various types of entities
    that can exist in this automation
    """

    # This is the entity for the final calculated home/away it is the
    # combination of the automatic home/away and manual override
    person_home_away: Domain

    # This is the entity for manually overwriting a users home/away status
    person_home_away_override: Domain

    # This is the entity that holds the state of a user
    person_state: Domain

    # This is the entity for the final calculated presence of a person
    person_presence: Domain

    # This is the entity for the final calculated presence of a group
    group_presence: Domain

    # This is the entity for specifying if guests exist currently or not
    person_exists: Domain

    # This is the entity for a single killswitch toggle
    killswitch: Domain

    # This is the entity used for any aggregated motion for an area
    motion_sensor_group: Domain

    # this entity represents if we have seen movement in the timeout window
    movement: Domain

    # This represents the current profile that is currently selected ignoring
    # killswitches and movement
    light_profile: Domain

    # This entity represents the final profile that is currently applied to the light
    light_automation: Domain


@dataclass
class InputEntity:
    entity: str


@dataclass
class Entity:
    domain: Domain
    name: str

    @property
    def full(self) -> str:
        return f"{self.domain}.{self.name}"
