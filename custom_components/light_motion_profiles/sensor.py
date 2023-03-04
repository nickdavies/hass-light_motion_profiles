import logging
import asyncio
from datetime import timedelta

from . import GROUP_SEPARATOR
from .schema_users_groups import (
    PERSON_STATE_ABSENT,
    HOME_AWAY_STATE_AUTO,
    HOME_AWAY_STATE_NOT_HOME,
    HOME_AWAY_STATE_UNKNOWN,
    FIELD_GROUPS,
    FIELD_GUEST,
    FIELD_HOME_AWAY_ICONS,
    FIELD_STATE_ICONS,
    FIELD_STATE_IF_UNKNOWN,
    FIELD_TRACKING_ENTITY,
    FIELD_USER_GROUP_SETTINGS,
    FIELD_USERS,
)
from .schema_motion_profiles import (
    FIELD_BRIGHTNESS_PCT,
    FIELD_DEFAULT_PROFILE,
    FIELD_ENABLED,
    FIELD_LIGHT_ICON,
    FIELD_LIGHT_PROFILE_RULE_SETS,
    FIELD_LIGHT_PROFILES,
    FIELD_LIGHTS,
    FIELD_MATCH_TYPE,
    FIELD_MATERIALIZED_BINDINGS,
    FIELD_MOTION_SENSOR_ENTITY,
    FIELD_NO_MOTION_PROFILE,
    FIELD_NO_MOTION_WAIT,
    FIELD_PROFILE,
    FIELD_RULES,
    FIELD_STATES,
    FIELD_USER_OR_GROUP_ENTITY,
    MATCH_TYPE_ALL,
    MATCH_TYPE_ANY,
    MATCH_TYPE_EXACT,
    MOTION_KILLSWITCH_GLOBAL,
)
from .entity_names import (
    group_presence_entity,
    killswitch_entity,
    light_automation_entity,
    light_binding_profile_entity,
    person_exists_entity,
    person_home_away_entity,
    person_override_home_away_entity,
    person_presence_entity,
    person_state_entity,
    light_movement_entity,
)

from homeassistant.components.light import (
    ATTR_BRIGHTNESS_PCT,
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
    state_if_unknown = discovery_info[FIELD_USER_GROUP_SETTINGS][FIELD_STATE_IF_UNKNOWN]

    user_sensors = []
    for user, user_config in discovery_info[FIELD_USERS].items():
        user_sensors.append(
            UserHomeAwaySensor(
                name=user,
                icons=user_config[FIELD_HOME_AWAY_ICONS],
                tracking_entity=user_config[FIELD_TRACKING_ENTITY],
            )
        )
        user_sensors.append(
            UserPresenceSensor(
                name=user,
                state_if_unknown=state_if_unknown,
                icons=user_config[FIELD_STATE_ICONS],
                guest=user_config[FIELD_GUEST],
            )
        )

    async_add_entities(user_sensors)

    users = set(discovery_info[FIELD_USERS])
    group_sensors = []
    for group_name, members in discovery_info[FIELD_GROUPS].items():
        members = {name: name in users for name in members}
        group_sensors.append(
            GroupPresenceSensor(
                group_name,
                members,
            )
        )
    async_add_entities(group_sensors)

    profile_icons = {}
    for name, profile in discovery_info[FIELD_LIGHT_PROFILES].items():
        if FIELD_LIGHT_ICON in profile:
            profile_icons[name] = profile[FIELD_LIGHT_ICON]

    light_sensors = []
    materialized_bindings = discovery_info[FIELD_MATERIALIZED_BINDINGS]
    for binding_name, materialized_binding in materialized_bindings.items():
        light_sensors.append(
            LightProfileEntity(
                binding_name,
                materialized_binding,
                profile_icons,
            )
        )
        light_sensors.append(
            LightMovementEntity(
                binding_name,
                materialized_binding,
            )
        )
        light_sensors.append(
            LightAutomationEntity(
                binding_name,
                materialized_binding,
                discovery_info[FIELD_LIGHT_PROFILES],
                profile_icons,
            )
        )

    async_add_entities(light_sensors)


class CalculatedSensor:
    PRIMARY_ATTR = "_attr_native_value"

    def __init__(self):
        super().__init__()
        setattr(self, self.PRIMARY_ATTR, None)
        self._icons = None

    def _apply_state(self, new_state):
        setattr(self, self.PRIMARY_ATTR, new_state)
        return True

    def _apply_icon(self, new_state):
        if self._icons is not None:
            self._attr_icon = self._icons.get(new_state)

    def _apply_and_save_state(self, new_state):
        changed = self._apply_state(new_state)
        if changed:
            self._apply_icon(new_state)
            self.async_write_ha_state()
        return changed

    def _force_update(self, event):
        new_state = self.calculate_current_state()
        _LOGGER.info(f"new_state for {self._attr_name}={new_state}")
        return self._apply_and_save_state(new_state)

    async def async_added_to_hass(self):
        @callback
        def dependent_entity_change(event):
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


class UserHomeAwaySensor(CalculatedSensor, SensorEntity):
    def __init__(
        self,
        name,
        icons,
        tracking_entity=None,
    ):
        super().__init__()

        self._attr_name = person_home_away_entity(name, without_domain=True)
        self._icons = icons
        self._tracking_entity = tracking_entity
        self._override_entity = person_override_home_away_entity(name)

        self._dependent_entities = [self._override_entity]
        if self._tracking_entity:
            self._dependent_entities.append(self._tracking_entity)

    def calculate_current_state(self):
        override = self.hass.states.get(self._override_entity)
        if override is not None and override.state != HOME_AWAY_STATE_AUTO:
            return override.state

        if self._tracking_entity:
            auto = self.hass.states.get(self._tracking_entity)
            if auto is not None:
                return auto.state

        return HOME_AWAY_STATE_UNKNOWN


class UserPresenceSensor(CalculatedSensor, SensorEntity):
    def __init__(
        self,
        name,
        state_if_unknown,
        icons,
        guest=False,
    ):
        super().__init__()
        self._attr_name = person_presence_entity(name, without_domain=True)
        self._icons = icons

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
                return PERSON_STATE_ABSENT

        home_away = self.hass.states.get(self._home_away_entity)
        if home_away is not None:
            if home_away.state == HOME_AWAY_STATE_NOT_HOME:
                return PERSON_STATE_ABSENT
            if home_away.state.lower() == HOME_AWAY_STATE_UNKNOWN:
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
        return set(value.split(GROUP_SEPARATOR))

    @classmethod
    def serialize(cls, states):
        return GROUP_SEPARATOR.join(sorted(set(states)))

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
            states.discard(PERSON_STATE_ABSENT)

        return self.serialize(states)


class LightProfileEntity(CalculatedSensor, SensorEntity):
    def __init__(
        self,
        binding_name,
        materialized_binding,
        profile_icons,
    ):
        super().__init__()
        self._attr_name = light_binding_profile_entity(
            binding_name, without_domain=True
        )

        self._icons = profile_icons

        self._rule_sets = materialized_binding[FIELD_LIGHT_PROFILE_RULE_SETS]
        self._dependent_entities = []
        for rule in self._rule_sets:
            self._dependent_entities.append(rule[FIELD_USER_OR_GROUP_ENTITY])

        self._default_profile = materialized_binding[FIELD_DEFAULT_PROFILE]

    def calculate_current_state(self):
        # For this entity we don't care if motion has occured or not. We are just
        # resolving the rules down to which profile would be currently used and
        # another bit of automation controls if that profile or the no_motion_profile
        # should be active
        #
        # Because we don't care about motion here we also don't look at the killswitches
        # which only effect if motion is/isn't honored

        for ruleset in self._rule_sets:
            user_or_group_state = self.hass.states.get(
                ruleset[FIELD_USER_OR_GROUP_ENTITY]
            )
            if user_or_group_state is None:
                continue
            states = GroupPresenceSensor.deserialize(user_or_group_state.state)

            for rule in ruleset[FIELD_RULES]:
                match_type = rule[FIELD_MATCH_TYPE]
                rule_states = set(rule[FIELD_STATES])

                if match_type == MATCH_TYPE_EXACT and states == rule_states:
                    return rule[FIELD_PROFILE]
                elif match_type == MATCH_TYPE_ANY:
                    if any(rule_state in states for rule_state in rule_states):
                        return rule[FIELD_PROFILE]
                elif match_type == MATCH_TYPE_ALL:
                    if all(rule_state in states for rule_state in rule_states):
                        return rule[FIELD_PROFILE]

        return self._default_profile


class LightMovementEntity(CalculatedSensor, SensorEntity):

    STATE_PRESENT = "present"
    STATE_COOLDOWN = "cooldown"
    STATE_NO_MOTION = "no_motion"

    def __init__(self, binding_name, materialized_binding):
        super().__init__()

        self._attr_name = light_movement_entity(binding_name, without_domain=True)

        self._no_motion_cb_cancel = None

        self._motion_entity = materialized_binding[FIELD_MOTION_SENSOR_ENTITY]
        self._no_motion_timeout = timedelta(
            seconds=materialized_binding[FIELD_NO_MOTION_WAIT]
        )

        self._dependent_entities = [
            self._motion_entity,
        ]

    async def async_added_to_hass(self):
        def on_remove():
            if self._no_motion_cb_cancel is not None:
                self._no_motion_cb_cancel()
                self._no_motion_cb_cancel = None

        self.async_on_remove(on_remove)
        return await super().async_added_to_hass()

    def _no_motion_callback(self, *args, **kwargs):
        _LOGGER.warning(f"No motion callback {self._attr_name}")
        self._apply_and_save_state(self.STATE_NO_MOTION)

    def _force_update(self, event):
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
            new_state = self.STATE_PRESENT
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
            new_state = self.STATE_COOLDOWN
        else:
            _LOGGER.warning(f"Unknown state for motion entity {motion_state}")
            return

        _LOGGER.info(f"new_state for {self._attr_name}={new_state}")
        return self._apply_and_save_state(new_state)


class LightAutomationEntity(CalculatedSensor, SensorEntity):
    def __init__(
        self,
        binding_name,
        materialized_binding,
        light_profiles,
        profile_icons,
    ):
        super().__init__()
        self._attr_name = light_automation_entity(binding_name, without_domain=True)

        self._rule_sets = materialized_binding[FIELD_LIGHT_PROFILE_RULE_SETS]
        self._icons = profile_icons

        self._no_motion_profile = materialized_binding[FIELD_NO_MOTION_PROFILE]

        self._global_killswitch_entity = killswitch_entity(MOTION_KILLSWITCH_GLOBAL)
        self._killswitch_entity = killswitch_entity(binding_name)
        self._light_profile_entity = light_binding_profile_entity(binding_name)
        self._movement_entity = light_movement_entity(binding_name)

        self._dependent_entities = [
            self._light_profile_entity,
            self._movement_entity,
        ]

        self._light_entity = materialized_binding[FIELD_LIGHTS]
        self._light_profiles = light_profiles

    def calculate_current_state(self):
        motion_state = self.hass.states.get(self._movement_entity)

        profile = None
        if motion_state is None:
            profile = None
        else:
            motion_state = motion_state.state
            if motion_state == LightMovementEntity.STATE_NO_MOTION:
                profile = self._no_motion_profile
            if motion_state in [
                LightMovementEntity.STATE_PRESENT,
                LightMovementEntity.STATE_COOLDOWN,
            ]:
                light_profile_state = self.hass.states.get(self._light_profile_entity)
                if light_profile_state is None:
                    profile = None
                else:
                    profile = light_profile_state.state

        return {
            "light_profile": profile,
            "motion_state": motion_state,
        }

    def _apply_icon(self, new_state):
        # we only care about what profile is being selected
        return super()._apply_icon(new_state["light_profile"])

    def _apply_state(self, new_state):
        light_profile_name = new_state["light_profile"]
        motion_state = new_state["motion_state"]
        change_light = True

        if light_profile_name is None:
            return False

        display_name = light_profile_name
        global_killswitch = self.hass.states.get(self._global_killswitch_entity)
        if global_killswitch is not None and global_killswitch.state == STATE_ON:
            _LOGGER.info(
                "refusing to update {self._attr_name} because of global killswitch"
            )
            change_light = False
            display_name = f"{light_profile_name}(killswitch)"

        killswitch = self.hass.states.get(self._killswitch_entity)
        if killswitch is not None and killswitch.state == STATE_ON:
            _LOGGER.info(
                "refusing to update {self._attr_name} because of local killswitch"
            )
            change_light = False
            display_name = f"{light_profile_name}(global_killswitch)"

        if motion_state == LightMovementEntity.STATE_COOLDOWN:
            display_name = f"{light_profile_name}(no_motion)"

        # This sets the user facing attribute but doesn't change the light
        super()._apply_state(display_name)

        light_state = self.hass.states.get(self._light_entity)
        if light_state is None:
            _LOGGER.warning(
                f"Requested to update light {self._light_entity} for automation "
                f"{self._attr_name} but that light appears to not exists"
            )
        elif change_light:
            light_profile = self._light_profiles[light_profile_name]

            service_data = {
                ATTR_ENTITY_ID: self._light_entity,
            }
            service = SERVICE_TURN_OFF
            if light_profile[FIELD_ENABLED]:
                service = SERVICE_TURN_ON
                light_profile_brightness = light_profile.get(FIELD_BRIGHTNESS_PCT, None)
                if light_profile_brightness is not None:
                    service_data[ATTR_BRIGHTNESS_PCT] = light_profile_brightness

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
