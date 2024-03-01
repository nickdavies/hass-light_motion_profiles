from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Set, Mapping


class MatchError(Exception):
    pass


class MatchSingle(ABC):
    @abstractmethod
    def match(self, target_value: str) -> bool:
        pass


class MatchSingleExplicit(MatchSingle):
    def __init__(self, value: str):
        self.value = value

    def match(self, target_value: str) -> bool:
        return self.value == target_value


class MatchSingleWildcard(MatchSingle):
    def match(self, target_value: str) -> bool:
        return True


class MatchSingleAny(MatchSingle):
    def __init__(self, value: List[str]):
        self.value = set(value)

    def match(self, target_value: str) -> bool:
        return target_value in self.value


class MatchMulti(ABC):
    def __init__(self, match: MatchSingle):
        self._match = match

    @abstractmethod
    def match(self, target_values: str | Set[str]) -> bool:
        pass


class MatchMultiAny(MatchMulti):
    def match(self, target_values: str | Set[str]) -> bool:
        if isinstance(target_values, str):
            return self._match.match(target_values)
        else:
            return any(self._match.match(v) for v in target_values)


class MatchMultiAll(MatchMulti):
    def match(self, target_values: str | Set[str]) -> bool:
        if isinstance(target_values, str):
            return self._match.match(target_values)
        else:
            return all(self._match.match(v) for v in target_values)


class MatchMultiExact(MatchMulti):
    def match(self, target_values: str | Set[str]) -> bool:
        # Wildcards are never exact matches
        if isinstance(self._match, MatchSingleWildcard):
            return False

        if isinstance(target_values, str):
            target_values = {target_values}

        if isinstance(self._match, MatchSingleAny):
            options = self._match.value
        elif isinstance(self._match, MatchSingleExplicit):
            options = {self._match.value}
        else:
            raise NotImplementedError(
                f"Unknown type of match found '{type(self._match).__name__}'"
            )

        return options == target_values


@dataclass
class MatchUser(ABC):
    user: str
    match_multi: MatchMulti

    @abstractmethod
    def match(self, all_users_states: Mapping[str, str | Set[str]]) -> bool:
        pass


class MatchUserSingle(MatchUser):
    def match(self, all_users_states: Mapping[str, str | Set[str]]) -> bool:
        user_state = all_users_states.get(self.user)
        if user_state is None:
            raise MatchError(f"Did not receive user state for user {self.user}")
        return self.match_multi.match(user_state)


class MatchUserWildcard(MatchUser):
    def __init__(self) -> None:
        pass

    def match(self, all_users_states: Mapping[str, str | Set[str]]) -> bool:
        return True


@dataclass
class RuleMatch:
    room_state: MatchSingle
    occupancy: MatchSingle
    user_state: List[MatchUser]

    def match(
        self,
        room_state: str,
        occupancy_state: str,
        user_state: Mapping[str, str | Set[str]],
    ) -> bool:
        if not self.room_state.match(room_state):
            return False

        if not self.occupancy.match(occupancy_state):
            return False

        return any(s.match(user_state) for s in self.user_state)
