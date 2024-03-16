import itertools
from dataclasses import dataclass
from typing import Iterator, Set, Mapping, List, Dict

from .datatypes import Config, LightGroup, UsersGroups, User, Group


class Wildcard:
    pass


@dataclass
class Options:
    options: Set[str]


@dataclass
class MatchResult:
    occupancy: str | Wildcard | Options
    room: str | Wildcard | Options
    user_state: Mapping[str, str | Set[str] | Wildcard | Options]
    rule_name: str | None

    def to_tabulate(self) -> Dict[str, str]:
        out = {
            "room_state": str(self.room),
            "occupancy": str(self.occupancy),
        }
        for user, raw_value in sorted(self.user_state.items()):
            if isinstance(raw_value, str):
                value = raw_value
            elif isinstance(raw_value, set):
                value = ",".join(raw_value)
            elif isinstance(raw_value, Wildcard):
                value = "*"
            elif isinstance(raw_value, Options):
                value = "|".join(raw_value.options)
            else:
                raise ValueError(f"Got unexpected raw_value: '{raw_value}'")
            out[f"user: {user}"] = value
        out["rule_name"] = self.rule_name if self.rule_name else "UNASSIGNED!"
        return out


@dataclass
class UserCombinator:
    # A list of all users/groups
    users_groups: UsersGroups

    # All the possible states a single user can be in
    single_person_states: Set[str]

    absent_state: str

    def combinations_for_people(
        self, people_map: Mapping[str, User]
    ) -> Iterator[Dict[str, str | Set[str]]]:
        all_states = self.single_person_states | {self.absent_state}
        people = list(people_map)
        for options in itertools.product(all_states, repeat=len(people)):
            yield dict(zip(people, options))

    def resolve_groups(self, target: Group, states: Dict[str, str | Set[str]]) -> None:
        member_states = []
        for member in target.members:
            if member in self.users_groups.groups:
                self.resolve_groups(self.users_groups.groups[member], states)
            member_states.append(states[member])

        new_group_states = Group.resolve_group_states(
            iter(member_states), self.absent_state
        )
        states[target.name] = new_group_states

    def combinations_for_target(
        self, target: User | Group
    ) -> Iterator[Mapping[str, str | Set[str]]]:
        # First we fetch all the people involved here recursively which may
        # just be 1 person
        all_users = self.users_groups.members(target.name)

        # Now for every combination of states those people could be in we resolve
        # the groups
        for combination in self.combinations_for_people(all_users):
            if isinstance(target, Group):
                self.resolve_groups(target, combination)
            yield combination


def calculate_key(values: Mapping[str, str | Set[str]]) -> str:
    out = []
    for user, value in values.items():
        if isinstance(value, set):
            out.append(",".join(sorted(value)))
        else:
            out.append(value)
    return ":".join(out)


def gen_light_group_matches(
    group: LightGroup,
    config: Config,
) -> Iterator[MatchResult]:
    room_states = sorted(list(config.settings.room.valid_room_states))
    occupancy_states = sorted(config.settings.room.occupancy_states.all_states())
    users_groups = config.users_groups

    target = users_groups.get(group.user)
    rule_users = list(sorted(group.get_rule_users()))

    combinator = UserCombinator(
        users_groups=config.users_groups,
        single_person_states=set(config.settings.users_groups.valid_person_states),
        absent_state=config.settings.users_groups.absent_state,
    )

    seen = set()
    for user_state in combinator.combinations_for_target(target):
        filtered_user_state = {k: v for k, v in user_state.items() if k in rule_users}
        key = calculate_key(filtered_user_state)
        if key in seen:
            continue
        seen.add(key)
        for room_state in room_states:
            for occupancy_state in occupancy_states:
                matched = None
                for rule in group.rules:
                    if rule.rule_match.match(
                        room_state, occupancy_state, filtered_user_state
                    ):
                        matched = rule.state_name
                        break
                yield MatchResult(
                    room=room_state,
                    occupancy=occupancy_state,
                    user_state=filtered_user_state,
                    rule_name=matched,
                )


def build_ranges(config: Config) -> Mapping[str, List[MatchResult]]:
    out = {}
    for name, group in config.lights.items():
        out[name] = list(
            gen_light_group_matches(
                group,
                config,
            )
        )
    return out
