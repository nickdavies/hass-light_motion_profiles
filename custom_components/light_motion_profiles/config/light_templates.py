"""
This file contains all the possible templates. It doesn't include
any logic for detecting where the templates should be subsituted into
only the data under the `templates` key in the config
"""
from dataclasses import dataclass
from typing import Set, Dict, Self, List

from template import Template, TemplateList
from light_profiles import Match, LightRule, UserState


@dataclass
class TemplateMatchValue:
    value: str | List[str]


class TemplateMatch(Template):
    template_data = str | List[str]
    output_type = Match

    @classmethod
    def validate_inputs(cls, content: str | List[str], inputs: Set[str]):
        used = set()
        if isinstance(content, list):
            for value in content:
                used.add(cls._validate_value(value, inputs))
        else:
            used.add(cls._validate_value(content, inputs))
        used.discard(None)
        return used

    def materialize_unchecked(self, inputs: Dict[str, str]):
        if isinstance(self._content, list):
            out = [self._materialize_value(value, inputs) for value in self._content]
        else:
            out = self._materialize_value(self._content, inputs)
        return Match(out)

    @classmethod
    def from_yaml(cls, name, data, inputs: Set[str], allow_extra: bool) -> Self:
        return cls(name, data, inputs, allow_extra)


@dataclass
class TemplateUserStateValue:
    user: TemplateMatch
    state_any: TemplateMatch | None
    state_exact: TemplateMatch | None


class TemplateUserState(Template):
    template_data = TemplateUserStateValue
    output_type = UserState

    @classmethod
    def validate_inputs(cls, content: TemplateUserStateValue, inputs: Set[str]):
        """
        We need no extra validation here because we only have templates as field values
        which are already validated
        """
        used = set()
        used.update(content.user._inputs)
        if content.state_any:
            used.update(content.state_any._inputs)
        elif content.state_exact:
            used.update(content.state_exact._inputs)
        return used

    def materialize_unchecked(self, inputs: Dict[str, str]):
        return UserState(
            user=self._content.user.materialize(inputs),
            state_any=self._content.state_any.materialize(inputs)
            if self._content.state_any is not None
            else None,
            state_exact=self._content.state_exact.materialize(inputs)
            if self._content.state_exact is not None
            else None,
        )

    @classmethod
    def from_yaml(cls, name, data, inputs: Set[str], allow_extra: bool) -> Self:
        return cls(
            name=name,
            content=TemplateUserStateValue(
                user=TemplateMatch.from_yaml(
                    name + ".user",
                    data["user"],
                    inputs,
                    allow_extra,
                ),
                state_any=TemplateMatch.from_yaml(
                    name + ".state_any",
                    data["state_any"],
                    inputs,
                    allow_extra,
                )
                if "state_any" in data
                else None,
                state_exact=TemplateMatch.from_yaml(
                    name + ".state_exact",
                    data["state_exact"],
                    inputs,
                    allow_extra,
                )
                if "state_exact" in data
                else None,
            ),
            inputs=inputs,
            allow_extra=allow_extra,
        )


class TemplateUserStates(TemplateList):
    template_type = TemplateUserState

    @classmethod
    def from_yaml(cls, name, data, inputs, allow_extra: bool) -> Self:
        content = []
        for i, user_state in enumerate(data):
            if user_state == "*":
                content.append(
                    TemplateMatch.from_yaml(
                        name=name + f".{i}",
                        data=user_state,
                        inputs=inputs,
                        allow_extra=True,
                    )
                )
            else:
                content.append(
                    TemplateUserState.from_yaml(
                        name=name + f".{i}",
                        data=user_state,
                        inputs=inputs,
                        allow_extra=True,
                    )
                )
        return cls(
            name=name, content=content, inputs=set(inputs), allow_extra=allow_extra
        )


@dataclass
class TemplateLightRuleValue:
    state_name: TemplateMatch
    room_state: TemplateMatch
    occupancy: TemplateMatch
    user_state: TemplateUserStates | TemplateMatch
    light_profile: str


class TemplateLightRule(Template):
    template_data = TemplateLightRuleValue

    @classmethod
    def validate_inputs(cls, content: TemplateLightRuleValue, inputs: Set[str]):
        used = set()
        used.update(content.state_name._inputs)
        used.update(content.room_state._inputs)
        used.update(content.occupancy._inputs)
        used.update(content.user_state._inputs)
        used.add(cls._validate_value(content.light_profile, inputs))
        used.discard(None)
        return used

    def materialize_unchecked(self, inputs: Dict[str, str]) -> LightRule:
        return LightRule(
            state_name=self._content.state_name.materialize(inputs),
            room_state=self._content.room_state.materialize(inputs),
            occupancy=self._content.occupancy.materialize(inputs),
            user_state=self._content.user_state.materialize(inputs),
            light_profile=self._materialize_value(self._content.light_profile, inputs),
        )

    @classmethod
    def from_yaml(cls, name: str, data, inputs: Set[str], allow_extra: bool) -> Self:
        name = name + f".{data['state_name']}"
        return cls(
            name=name,
            content=TemplateLightRuleValue(
                state_name=TemplateMatch.from_yaml(
                    name + ".state_name",
                    data["state_name"],
                    inputs,
                    allow_extra,
                ),
                room_state=TemplateMatch.from_yaml(
                    name + ".room_state",
                    data["room_state"],
                    inputs,
                    allow_extra,
                ),
                occupancy=TemplateMatch.from_yaml(
                    name + ".occupancy",
                    data["occupancy"],
                    inputs,
                    allow_extra,
                ),
                user_state=TemplateUserStates.from_yaml(
                    name + ".user_state",
                    data["user_state"],
                    inputs,
                    allow_extra,
                ),
                light_profile=data["light_profile"],
            ),
            inputs=inputs,
            allow_extra=allow_extra,
        )


class TemplateLightConfigRules(TemplateList):
    template_type = TemplateLightRule

    @classmethod
    def from_yaml(cls, name, data) -> Self:
        if isinstance(data["inputs"], list):
            inputs = set(data["inputs"])
        else:
            inputs = {data["inputs"]}

        content = []
        for i, rule in enumerate(data["template"]):
            content.append(
                TemplateLightRule.from_yaml(
                    name=name + f".{i}",
                    data=rule,
                    inputs=inputs,
                    allow_extra=True,
                )
            )
        return cls(name=name, content=content, inputs=inputs, allow_extra=True)


@dataclass
class AllTemplates:
    light_config_rules: Dict[str, TemplateLightConfigRules]

    @classmethod
    def from_yaml(cls, data) -> Self:
        return cls(
            light_config_rules={
                name: TemplateLightConfigRules.from_yaml(name, template)
                for name, template in data["light_config_rules"].items()
            },
        )
