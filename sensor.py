import logging

from .schema_users_groups import (
    FIELD_STATE_IF_UNKNOWN,
    FIELD_SETTINGS,
    FIELD_GUEST,
    FIELD_GROUPS,
    FIELD_USERS,
    FIELD_TRACKING_ENTITY,
    DEFAULT_STATE_IF_UNKNOWN,
)
from .entity_names import (
    group_presence_entity,
    person_exists_entity,
    person_home_away_entity,
    person_override_home_away_entity,
    person_state_entity,
    person_presence_entity,
)
from homeassistant.helpers.event import (
    async_track_state_change_event,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    whole_config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info,
) -> None:
    state_if_unknown = discovery_info.get(FIELD_SETTINGS, {}).get(
        FIELD_STATE_IF_UNKNOWN, DEFAULT_STATE_IF_UNKNOWN
    )

    user_sensors = []
    for user, user_config in discovery_info.get(FIELD_USERS, {}).items():
        user_sensors.append(
            UserHomeAwaySensor(
                name=user,
                tracking_entity=user_config.get(FIELD_TRACKING_ENTITY),
            )
        )
        user_sensors.append(
            UserPresenceSensor(
                name=user,
                state_if_unknown=state_if_unknown,
                guest=user_config.get(FIELD_GUEST, False),
            )
        )

    async_add_entities(user_sensors)

    users = set(discovery_info.get(FIELD_USERS, {}))
    group_sensors = []
    for group_name, members in discovery_info.get(FIELD_GROUPS, {}).items():
        members = {name: name in users for name in members}
        group_sensors.append(
            GroupPresenceSensor(
                group_name,
                members,
            )
        )
    async_add_entities(group_sensors)


class CalculatedSensor:
    def __init__(self):
        super().__init__()
        self._attr_native_value = None

    def _force_update(self):
        new_state = self.calculate_current_state()
        _LOGGER.info(f"new_state for {self._attr_name}={new_state}")
        self._attr_native_value = new_state
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        @callback
        def dependent_entity_change(event):
            self._force_update()

        _LOGGER.debug(
            f"subscribing {self._attr_name} up for {self._dependent_entities} updates"
        )
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._dependent_entities, dependent_entity_change
            )
        )
        self._force_update()


class UserHomeAwaySensor(CalculatedSensor, SensorEntity):
    def __init__(
        self,
        name,
        tracking_entity=None,
    ):
        super().__init__()

        self._attr_name = person_home_away_entity(name, without_domain=True)
        self._tracking_entity = tracking_entity
        self._override_entity = person_override_home_away_entity(name)

        self._dependent_entities = [self._override_entity]
        if self._tracking_entity:
            self._dependent_entities.append(self._tracking_entity)

    def calculate_current_state(self):
        override = self.hass.states.get(self._override_entity)
        if override is not None and override.state != "auto":
            return override.state

        if self._tracking_entity:
            auto = self.hass.states.get(self._tracking_entity)
            if auto is not None:
                return auto.state

        return "unknown"


class UserPresenceSensor(CalculatedSensor, SensorEntity):
    def __init__(
        self,
        name,
        state_if_unknown,
        guest=False,
    ):
        super().__init__()
        self._attr_name = person_presence_entity(name, without_domain=True)

        self._home_away_entity = person_home_away_entity(name)
        self._state_entity = person_state_entity(name)
        self._state_if_unknown = state_if_unknown
        self._exists_entity = None

        self._dependent_entities = [self._home_away_entity, self._state_entity]
        if guest:
            self._exists_entity = person_exists_entity(name)
            self._dependent_entities.append(self._exists_entity)

    def calculate_current_state(self):
        if self._exists_entity:
            exists = self.hass.states.get(self._exists_entity)
            if exists is None or exists.state == "off":
                return "absent"

        home_away = self.hass.states.get(self._home_away_entity)
        if home_away is not None:
            if home_away.state == "not_home":
                return "absent"
            if home_away.state.lower() == "unknown":
                return self._state_if_unknown

        user_state = self.hass.states.get(self._state_entity)
        if user_state is not None:
            return user_state.state
        else:
            return None


class GroupPresenceSensor(CalculatedSensor, SensorEntity):
    def __init__(
        self,
        group_name,
        members,
    ):
        super().__init__()
        self._attr_name = group_presence_entity(group_name, without_domain=True)

        self._members = members
        self._member_entities = {}
        for member, is_user in members.items():
            if is_user:
                self._member_entities[member] = person_presence_entity(member)
            else:
                self._member_entities[member] = group_presence_entity(member)

        self._dependent_entities = list(self._member_entities.values())

    @classmethod
    def deserialize(cls, value):
        return set(value.split("_"))

    @classmethod
    def serialize(cls, states):
        return "_".join(sorted(set(states)))

    def calculate_current_state(self):
        member_states = {}
        for member, member_entity in self._member_entities.items():
            member_state = self.hass.states.get(member_entity)
            if member_state is None:
                member_states[member] = None
            else:
                member_states[member] = self.deserialize(member_state.state)

        states = set()
        for member, state in member_states.items():
            if isinstance(state, set):
                states.update(state)
            else:
                states.add(state)
        if len(states) != 1:
            states.discard("absent")

        return self.serialize(states)
