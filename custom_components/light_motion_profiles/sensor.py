import logging
import asyncio
from datetime import timedelta, datetime
from typing import Mapping, List, Set, Any, TypeVar, Generic, Dict, Callable

from homeassistant.components.light import (
    ATTR_BRIGHTNESS_PCT,
    ATTR_TRANSITION,
    DOMAIN as LIGHT_DOMAIN,
)
from homeassistant.util import dt as dt_util
from homeassistant.const import (
    STATE_ON,
    STATE_OFF,
    SERVICE_TURN_ON,
    SERVICE_TURN_OFF,
    ATTR_ENTITY_ID,
)
from homeassistant.helpers.event import (
    async_track_point_in_utc_time,
    async_track_state_change_event,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.components.sensor import SensorEntity, DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import GROUP_SEPARATOR
from .datatypes import (
    Config,
    User,
    Group,
    UsersGroups,
    UserGroupSettings,
    LightGroup,
    RoomSettings,
    Entity,
)


_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(
    hass: HomeAssistant,
    whole_config: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
    config: Config,
) -> None:
    user_sensors: List[SensorEntity] = []
    for user in config.users_groups.users.values():
        user_sensors.append(
            UserHomeAwaySensor(
                user,
                config.settings.users_groups,
            )
        )
        user_sensors.append(UserPresenceSensor(user, config.settings.users_groups))

    async_add_entities(user_sensors)

    group_sensors = []
    for group in config.users_groups.groups.values():
        group_sensors.append(
            GroupPresenceSensor(
                group, config.users_groups, config.settings.users_groups
            )
        )
    async_add_entities(group_sensors)

    # profile_icons = {}
    # for name, profile in discovery_info[FIELD_LIGHT_PROFILES].items():
    #     if FIELD_LIGHT_ICON in profile:
    #         profile_icons[name] = profile[FIELD_LIGHT_ICON]

    # _LOGGER.warning(f"profile_icons={profile_icons}")

    light_sensors: List[SensorEntity] = []
    for light_config in config.lights.values():
        light_sensors.append(
            RoomOccupancyEntity(
                light_config,
                config.settings.room,
            )
        )
        light_sensors.append(
            LightRuleEntity(
                light_config,
                config.users_groups,
            )
        )
        light_sensors.append(
            LightAutomationEntity(
                light_config,
                config.global_killswitch_entity,
            )
        )

    async_add_entities(light_sensors)


T = TypeVar("T")


class CalculatedSensor(Generic[T]):
    PRIMARY_ATTR = "_attr_native_value"

    def __init__(self) -> None:
        super().__init__()
        setattr(self, self.PRIMARY_ATTR, None)
        self._icons: Mapping[T, str] | None = None

    def _apply_state(self, new_state: T) -> bool:
        setattr(self, self.PRIMARY_ATTR, new_state)
        return True

    def _apply_icon(self, new_state: T) -> None:
        if self._icons is not None:
            self._attr_icon = self._icons.get(new_state)

    def _apply_and_save_state(self, new_state: T) -> bool:
        changed = self._apply_state(new_state)
        if changed:
            self._apply_icon(new_state)
            self.async_write_ha_state()
        return changed

    def _force_update(self, event: Any) -> None:
        new_state = self.calculate_current_state()
        _LOGGER.info(f"new_state for {self._attr_name}={new_state}")
        self._apply_and_save_state(new_state)

    def calculate_current_state(self) -> T:
        raise NotImplementedError("Abstract")

    async def async_added_to_hass(self) -> None:
        @callback
        def dependent_entity_change(event: Any) -> None:
            self._force_update(event)

        _LOGGER.debug(
            f"subscribing {self._attr_name} up for {self._dependent_entities} updates"
        )
        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._dependent_entities, dependent_entity_change
            )
        )
        self._force_update(None)


class UserHomeAwaySensor(CalculatedSensor[str], SensorEntity):
    def __init__(
        self,
        user: User,
        settings: UserGroupSettings,
    ) -> None:
        super().__init__()

        entity = user.home_away_entity
        assert entity.domain.value == SENSOR_DOMAIN

        self._attr_name = entity.name
        self._icons = user.home_away_icons
        self._tracking_entity = (
            user.tracking_entity.entity if user.tracking_entity else None
        )
        self._override_entity = user.home_away_override_entity.full

        self._dependent_entities = [self._override_entity]
        if self._tracking_entity:
            self._dependent_entities.append(self._tracking_entity)

        self._state_auto = settings.home_away_states.auto
        self._state_unknown = settings.home_away_states.unknown

    def calculate_current_state(self) -> str:
        override = self.hass.states.get(self._override_entity)
        if override is not None and override.state != self._state_auto:
            return override.state

        if self._tracking_entity:
            auto = self.hass.states.get(self._tracking_entity)
            if auto is not None:
                return auto.state

        return self._state_unknown


class UserPresenceSensor(CalculatedSensor[str], SensorEntity):
    def __init__(self, user: User, settings: UserGroupSettings) -> None:
        super().__init__()
        entity = user.presence_entity
        assert entity.domain.value == SENSOR_DOMAIN

        self._attr_name = entity.name
        self._icons = user.state_icons

        self._home_away_entity = user.home_away_entity.full
        self._state_entity = user.state_entity.full
        self._state_if_unknown = settings.state_if_unknown
        self._exists_entity = None

        self._dependent_entities = [self._home_away_entity, self._state_entity]
        if user.guest:
            self._exists_entity = user.exists_entity.full
            self._dependent_entities.append(self._exists_entity)

        self._state_absent = settings.absent_state
        self._state_unknown = settings.home_away_states.unknown
        self._state_not_home = settings.home_away_states.not_home

    def calculate_current_state(self) -> str:
        if self._exists_entity:
            exists = self.hass.states.get(self._exists_entity)
            if exists is None or exists.state == "off":
                return self._state_absent

        home_away = self.hass.states.get(self._home_away_entity)
        if home_away is not None:
            if home_away.state == self._state_not_home:
                return self._state_absent
            if home_away.state.lower() == self._state_unknown:
                return self._state_if_unknown

        user_state = self.hass.states.get(self._state_entity)
        if user_state is not None:
            return user_state.state
        else:
            return self._state_if_unknown


class GroupPresenceSensor(CalculatedSensor[str], SensorEntity):
    def __init__(
        self, group: Group, users_groups: UsersGroups, settings: UserGroupSettings
    ) -> None:
        super().__init__()
        entity = group.presence_entity
        assert entity.domain.value == SENSOR_DOMAIN
        self._attr_name = entity.name

        self._member_entities = {}
        for member in group.members:
            self._member_entities[member] = users_groups.presence_entity(member).full

        self._dependent_entities = list(self._member_entities.values())
        self._state_absent = settings.absent_state
        self._state_if_unknown = settings.state_if_unknown

    @classmethod
    def deserialize(cls, value: str) -> Set[str]:
        return set(value.split(GROUP_SEPARATOR))

    @classmethod
    def serialize(cls, states: Set[str]) -> str:
        return GROUP_SEPARATOR.join(sorted(set(states)))

    def calculate_current_state(self) -> str:
        member_states: Dict[str, str | Set[str]] = {}
        for member, member_entity in self._member_entities.items():
            member_state = self.hass.states.get(member_entity)
            if member_state is None:
                member_states[member] = self._state_if_unknown
            else:
                member_states[member] = self.deserialize(member_state.state)

        states = Group.resolve_group_states(
            iter(member_states.values()), self._state_absent
        )
        return self.serialize(states)


class RoomOccupancyEntity(CalculatedSensor[str], SensorEntity):
    def __init__(self, config: LightGroup, settings: RoomSettings) -> None:
        super().__init__()

        entity = config.room_occupancy_entity
        assert entity.domain.value == SENSOR_DOMAIN

        self._attr_name = entity.name
        self._no_motion_cb_cancel: Callable[[], None] | None = None

        self._motion_entity = config.motion_sensor_entity.entity
        self._no_motion_timeout = timedelta(seconds=config.occupancy_timeout.value)

        self._dependent_entities = [
            self._motion_entity,
        ]

        self._state_occupied = settings.occupancy_states.occupied
        self._state_occupied_timeout = settings.occupancy_states.occupied_timeout
        self._state_empty = settings.occupancy_states.empty

    async def async_added_to_hass(self) -> None:
        def on_remove() -> None:
            if self._no_motion_cb_cancel is not None:
                self._no_motion_cb_cancel()
                self._no_motion_cb_cancel = None

        self.async_on_remove(on_remove)
        return await super().async_added_to_hass()

    def _no_motion_callback(self, dt: datetime) -> None:
        _LOGGER.warning(f"No motion callback {self._attr_name}")
        self._apply_and_save_state(self._state_empty)

    def _force_update(self, event: Any) -> None:
        motion_state = self.hass.states.get(self._motion_entity)
        if motion_state is None:
            return
        motion_state = motion_state.state

        new_state = None
        if motion_state == STATE_ON:
            # If we detect motion we cancel the callback if it exists
            if self._no_motion_cb_cancel is not None:
                self._no_motion_cb_cancel()
                self._no_motion_cb_cancel = None
            new_state = self._state_occupied
        elif motion_state == STATE_OFF:
            # If we we don't see motion but already have a callback we do nothing
            if self._no_motion_cb_cancel:
                return

            # Otherwise we schedule the callback
            self._no_motion_cb_cancel = async_track_point_in_utc_time(
                self.hass,
                self._no_motion_callback,
                dt_util.utcnow() + self._no_motion_timeout,
            )
            new_state = self._state_occupied_timeout
        else:
            _LOGGER.warning(f"Unknown state for motion entity {motion_state}")
            return

        _LOGGER.info(f"new_state for {self._attr_name}={new_state}")
        self._apply_and_save_state(new_state)


class LightRuleEntity(CalculatedSensor[str | None], SensorEntity):
    def __init__(self, config: LightGroup, users_groups: UsersGroups) -> None:
        super().__init__()
        entity = config.light_rule_entity
        assert entity.domain.value == SENSOR_DOMAIN
        self._attr_name = entity.name

        self._icons = {
            r.state_name: r.state.icon.value
            for r in config.rules
            if r.state.icon is not None
        }

        self._rules = config.rules
        self._user_group_entities = {
            member: users_groups.presence_entity(member).full
            for member in config.get_rule_users()
        }
        self._occupancy_entity = config.room_occupancy_entity.full
        self._dependent_entities = list(self._user_group_entities.values()) + [
            self._occupancy_entity
        ]

    def calculate_current_state(self) -> str | None:
        # TODO make this auto when it's a thing
        room_state = "auto"
        occupancy = self.hass.states.get(self._occupancy_entity)
        if occupancy is None:
            return None
        else:
            occupancy = occupancy.state
        user_states = {
            member: self.hass.states.get(e)
            for member, e in self._user_group_entities.items()
        }
        if any(v is None for v in user_states.values()):
            pass
        else:
            user_states = {
                m: GroupPresenceSensor.deserialize(e.state)
                for m, e in user_states.items()
            }

        for rule in self._rules:
            if rule.rule_match.match(room_state, occupancy, user_states):
                return rule.state_name

        _LOGGER.warning(
            f"No rules matched for {self._attr_name}: "
            f"occupancy={occupancy} user_state={user_states}"
        )
        return None


class LightAutomationEntity(CalculatedSensor[str | None], SensorEntity):
    def __init__(self, light_config: LightGroup, global_ks: Entity) -> None:
        super().__init__()
        entity = light_config.light_automation_entity
        assert entity.domain.value == SENSOR_DOMAIN
        self._attr_name = entity.name

        self._global_killswitch_entity = global_ks.full
        self._killswitch_entity = light_config.killswitch_entity.full
        self._light_rule_entity = light_config.light_rule_entity.full

        self._dependent_entities = [
            self._global_killswitch_entity,
            self._killswitch_entity,
            self._light_rule_entity,
        ]

        self._light_entity = light_config.lights.entity
        self._states = {r.state_name: r.state for r in light_config.rules}
        self._icons = {
            r.state_name: r.state.icon.value
            for r in light_config.rules
            if r.state.icon is not None
        }

    def calculate_current_state(self) -> str | None:
        rule_state = self.hass.states.get(self._light_rule_entity)
        # TODO: Deal with this better
        if rule_state is None:
            return None

        return rule_state.state

    def _apply_state(self, light_rule: str | None) -> bool:
        if light_rule is None or light_rule == "unknown":
            return False
        target = self._states[light_rule]

        base_display_name = (
            target.source_profile if target.source_profile else light_rule
        )
        display_name = base_display_name
        global_killswitch = self.hass.states.get(self._global_killswitch_entity)
        change_light = True
        if global_killswitch is not None and global_killswitch.state == STATE_ON:
            _LOGGER.info(
                "refusing to update {self._attr_name} because of global killswitch"
            )
            change_light = False
            display_name = f"{base_display_name}(global_ks)"

        killswitch = self.hass.states.get(self._killswitch_entity)
        if killswitch is not None and killswitch.state == STATE_ON:
            _LOGGER.info(
                "refusing to update {self._attr_name} because of local killswitch"
            )
            change_light = False
            display_name = f"{base_display_name}(local_ks)"

        # This sets the user facing attribute but doesn't change the light
        super()._apply_state(display_name)

        light_state = self.hass.states.get(self._light_entity)
        if light_state is None:
            pass
            # _LOGGER.warning(
            #     f"Requested to update light {self._light_entity} for automation "
            #     f"{self._attr_name} but that light appears to not exists"
            # )
        elif change_light:
            service = None
            if target.enable is None:
                if light_state.state == STATE_ON:
                    service = SERVICE_TURN_ON
            elif target.enable.value is True:
                service = SERVICE_TURN_ON
            elif target.enable.value is False:
                service = SERVICE_TURN_OFF
            else:
                _LOGGER.warning(
                    "Got unexpected value for target.enable " f"'{target.enable}'"
                )

            service_data = {
                ATTR_ENTITY_ID: self._light_entity,
            }
            if service is None:
                return True
            elif service == SERVICE_TURN_ON:
                if target.brightness:
                    service_data[ATTR_BRIGHTNESS_PCT] = target.brightness.value

            if target.transition is not None:
                service_data[ATTR_TRANSITION] = target.transition.value

            _LOGGER.warning(
                f"calling service {LIGHT_DOMAIN}.{service}, {service_data} for "
                f"automation {self._attr_name}"
            )
            asyncio.run_coroutine_threadsafe(
                self.hass.services.async_call(
                    LIGHT_DOMAIN,
                    service,
                    service_data,
                    blocking=False,
                ),
                self.hass.loop,
            )

        return True
