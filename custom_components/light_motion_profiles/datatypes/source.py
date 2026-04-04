from typing import Any, List


class DataSource:
    value: Any
    entity_id: str | None

    def __init__(self, value: Any = None, entity_id: str | None = None):
        self.value = value
        self.entity_id = entity_id

    def resolve(self, hass: Any) -> Any:
        """Resolve the value, reading from an entity if configured.

        Returns the entity's state if entity_id is set and the entity is
        available, otherwise falls back to the static value.
        """
        if self.entity_id is not None:
            state = hass.states.get(self.entity_id)
            if state is not None and state.state not in ("unknown", "unavailable"):
                return state.state
        return self.value

    def get_entity_ids(self) -> List[str]:
        """Return entity IDs that this DataSource depends on."""
        if self.entity_id is not None:
            return [self.entity_id]
        return []


class TriggerSource:
    value: str
