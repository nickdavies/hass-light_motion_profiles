from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Set, Mapping

from ..config.validators import InvalidConfigError
from ..config.light_profiles import Match as RawMatch, UserState as RawUserState


class MatchError(Exception):
    pass


class MatchSingle(ABC):
    @abstractmethod
    def match(self, target_value: str) -> bool:
        pass

    @classmethod
    def from_raw(cls, m: RawMatch) -> "MatchSingle":
        if isinstance(m.value, list):
            return MatchSingleAny(m.value)
        elif m.value == "*":
            return MatchSingleWildcard()
        else:
            return MatchSingleExplicit(m.value)


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
    @abstractmethod
    def match(self, all_users_states: Mapping[str, str | Set[str]]) -> bool:
        pass

    @classmethod
    def from_raw(cls, config: RawUserState) -> "MatchUser":
        multi: MatchMulti
        if config.state_any is not None:
            multi = MatchMultiAny(MatchSingle.from_raw(config.state_any))
        elif config.state_all is not None:
            multi = MatchMultiAll(MatchSingle.from_raw(config.state_all))
        elif config.state_exact is not None:
            multi = MatchMultiExact(MatchSingle.from_raw(config.state_exact))

        return MatchUserSingle(
            user=config.user,
            match_multi=multi,
        )


@dataclass
class MatchUserSingle(MatchUser):
    user: str
    match_multi: MatchMulti

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

    def __init__(
        self,
        room_state: RawMatch,
        occupancy: RawMatch,
        user_state: List[RawUserState] | RawMatch,
    ) -> None:
        self.room_state = MatchSingle.from_raw(room_state)
        self.occupancy = MatchSingle.from_raw(occupancy)

        if isinstance(user_state, RawMatch):
            m = MatchSingle.from_raw(user_state)
            if not isinstance(m, MatchSingleWildcard):
                raise InvalidConfigError(
                    "Using a single value for user state is only allowed to "
                    f"contain '*' not '{user_state.value}'"
                )
            self.user_state = [MatchUserWildcard()]
        else:
            self.user_state = [MatchUser.from_raw(us) for us in user_state]

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
