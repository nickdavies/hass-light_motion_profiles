"""
This file contains all the possible templates. It doesn't include
any logic for detecting where the templates should be subsituted into
only the data under the `templates` key in the config
"""
from dataclasses import dataclass
from typing import Set, Mapping, List, Any

import voluptuous as vol
from homeassistant.helpers import config_validation as cv

from .template import Template, TemplateList
from .light_profiles import Match, LightRule, UserState


class NoSuchTemplateError(Exception):
    pass


class TemplateMatch(Template[str | Set[str], Match]):
    @classmethod
    def validate_inputs(cls, content: str | Set[str], inputs: Set[str]) -> Set[str]:
        assert isinstance(content, str) or isinstance(content, set)
        used = set()
        if isinstance(content, set):
            for value in content:
                new = cls._validate_value(value, inputs)
                if new is not None:
                    used.add(new)
        else:
            new = cls._validate_value(content, inputs)
            if new is not None:
                used.add(new)
        return used

    def materialize_unchecked(self, inputs: Mapping[str, str]) -> Match:
        if isinstance(self._content, set):
            return Match(
                {self._materialize_value(value, inputs) for value in self._content}
            )
        else:
            return Match(self._materialize_value(self._content, inputs))

    @classmethod
    def from_yaml(
        cls, name: str, data: str | Set[str], inputs: Set[str], allow_extra: bool
    ) -> "TemplateMatch":
        return cls(name, data, inputs, allow_extra)


@dataclass
class TemplateUserStateValue:
    user: str
    state_any: TemplateMatch | None
    state_all: TemplateMatch | None
    state_exact: TemplateMatch | None


class TemplateUserState(Template[TemplateUserStateValue, UserState]):
    @classmethod
    def validate_inputs(
        cls, content: TemplateUserStateValue, inputs: Set[str]
    ) -> Set[str]:
        """
        We need no extra validation here because we only have templates as field values
        which are already validated
        """
        used = set()
        new = cls._validate_value(content.user, inputs)
        if new is not None:
            used.add(new)
        if content.state_any:
            used.update(content.state_any._inputs)
        elif content.state_all:
            used.update(content.state_all._inputs)
        elif content.state_exact:
            used.update(content.state_exact._inputs)
        return used

    def materialize_unchecked(self, inputs: Mapping[str, str]) -> UserState:
        return UserState(
            user=self._materialize_value(self._content.user, inputs),
            state_any=self._content.state_any.materialize(inputs)
            if self._content.state_any is not None
            else None,
            state_all=self._content.state_all.materialize(inputs)
            if self._content.state_all is not None
            else None,
            state_exact=self._content.state_exact.materialize(inputs)
            if self._content.state_exact is not None
            else None,
        )

    @classmethod
    def from_yaml(
        cls, name: str, data: Mapping[str, Any], inputs: Set[str], allow_extra: bool
    ) -> "TemplateUserState":
        return cls(
            name=name,
            content=TemplateUserStateValue(
                user=data[UserState.FIELD_USER],
                state_any=TemplateMatch.from_yaml(
                    name + "." + UserState.FIELD_STATE_ANY,
                    data[UserState.FIELD_STATE_ANY],
                    inputs,
                    allow_extra,
                )
                if UserState.FIELD_STATE_ANY in data
                else None,
                state_all=TemplateMatch.from_yaml(
                    name + "." + UserState.FIELD_STATE_ALL,
                    data[UserState.FIELD_STATE_ALL],
                    inputs,
                    allow_extra,
                )
                if UserState.FIELD_STATE_ALL in data
                else None,
                state_exact=TemplateMatch.from_yaml(
                    name + "." + UserState.FIELD_STATE_EXACT,
                    data[UserState.FIELD_STATE_EXACT],
                    inputs,
                    allow_extra,
                )
                if UserState.FIELD_STATE_EXACT in data
                else None,
            ),
            inputs=inputs,
            allow_extra=allow_extra,
        )


class TemplateUserStates(TemplateList[TemplateUserStateValue, UserState]):
    @classmethod
    def from_yaml(
        cls,
        name: str,
        data: List[Mapping[str, Any]],
        inputs: Set[str],
        allow_extra: bool,
    ) -> "TemplateUserStates":
        content: List[Template[TemplateUserStateValue, UserState]] = []
        for i, user_state in enumerate(data):
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
    state_name: str
    room_state: TemplateMatch
    occupancy: TemplateMatch
    user_state: TemplateUserStates | TemplateMatch
    light_profile: str


class TemplateLightRule(Template[TemplateLightRuleValue, LightRule]):
    @classmethod
    def validate_inputs(
        cls, content: TemplateLightRuleValue, inputs: Set[str]
    ) -> Set[str]:
        used = set()
        new = cls._validate_value(content.state_name, inputs)
        if new is not None:
            used.add(new)

        used.update(content.room_state._inputs)
        used.update(content.occupancy._inputs)
        used.update(content.user_state._inputs)

        new = cls._validate_value(content.light_profile, inputs)
        if new is not None:
            used.add(new)
        return used

    def materialize_unchecked(self, inputs: Mapping[str, str]) -> LightRule:
        return LightRule(
            state_name=self._materialize_value(self._content.state_name, inputs),
            room_state=self._content.room_state.materialize(inputs),
            occupancy=self._content.occupancy.materialize(inputs),
            user_state=self._content.user_state.materialize(inputs),
            light_profile=self._materialize_value(self._content.light_profile, inputs),
        )

    @classmethod
    def from_yaml(
        cls, name: str, data: Mapping[str, Any], inputs: Set[str], allow_extra: bool
    ) -> "TemplateLightRule":
        name = name + f".{data[LightRule.FIELD_STATE_NAME]}"

        user_state: TemplateUserStates | TemplateMatch
        if isinstance(data[LightRule.FIELD_USER_STATE], str):
            user_state = TemplateMatch.from_yaml(
                name=name + "." + LightRule.FIELD_USER_STATE,
                data=data[LightRule.FIELD_USER_STATE],
                inputs=inputs,
                allow_extra=True,
            )
        else:
            user_state = TemplateUserStates.from_yaml(
                name=name + "." + LightRule.FIELD_USER_STATE,
                data=data[LightRule.FIELD_USER_STATE],
                inputs=inputs,
                allow_extra=allow_extra,
            )

        return cls(
            name=name,
            content=TemplateLightRuleValue(
                state_name=data[LightRule.FIELD_STATE_NAME],
                room_state=TemplateMatch.from_yaml(
                    name + "." + LightRule.FIELD_ROOM_STATE,
                    data[LightRule.FIELD_ROOM_STATE],
                    inputs,
                    allow_extra,
                ),
                occupancy=TemplateMatch.from_yaml(
                    name + "." + LightRule.FIELD_OCCUPANCY,
                    data[LightRule.FIELD_OCCUPANCY],
                    inputs,
                    allow_extra,
                ),
                user_state=user_state,
                light_profile=data[LightRule.FIELD_LIGHT_PROFILE],
            ),
            inputs=inputs,
            allow_extra=allow_extra,
        )

    @classmethod
    def vol(cls) -> vol.Schema:
        return LightRule.vol()


class TemplateLightConfigRules(TemplateList[TemplateLightRuleValue, LightRule]):
    FIELD_INPUTS = "inputs"
    FIELD_TEMPLATE = "template"

    @classmethod
    def from_yaml(
        cls, name: str, data: Mapping[str, Any]
    ) -> "TemplateLightConfigRules":
        if isinstance(data[cls.FIELD_INPUTS], list):
            inputs = set(data[cls.FIELD_INPUTS])
        else:
            inputs = {data[cls.FIELD_INPUTS]}

        content: List[Template[TemplateLightRuleValue, LightRule]] = []
        for i, rule in enumerate(data[cls.FIELD_TEMPLATE]):
            content.append(
                TemplateLightRule.from_yaml(
                    name=name + f".{i}",
                    data=rule,
                    inputs=inputs,
                    allow_extra=True,
                )
            )
        return cls(name=name, content=content, inputs=inputs, allow_extra=True)

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(cls.FIELD_INPUTS): [cv.string],
                vol.Required(cls.FIELD_TEMPLATE): [TemplateLightRule.vol()],
            }
        )


@dataclass
class AllTemplates:
    FIELD_LIGHT_CONFIG_RULES = "light_config_rules"

    light_config_rules: Mapping[str, TemplateLightConfigRules]

    @classmethod
    def from_yaml(cls, data: Mapping[str, Any]) -> "AllTemplates":
        return cls(
            light_config_rules={
                name: TemplateLightConfigRules.from_yaml(name, template)
                for name, template in data.get(cls.FIELD_LIGHT_CONFIG_RULES, {}).items()
            },
        )

    def materialize_light_config_template(
        self, name: str, inputs: Mapping[str, str]
    ) -> List[LightRule]:
        template = self.light_config_rules.get(name)
        if template is None:
            raise NoSuchTemplateError(
                f"light config template '{name}' doesn't exist possible templates are: "
                f"{', '.join(self.light_config_rules)}"
            )
        return template.materialize(inputs)

    @classmethod
    def vol(cls) -> vol.Schema:
        return vol.Schema(
            {
                vol.Optional(cls.FIELD_LIGHT_CONFIG_RULES): {
                    cv.string: TemplateLightConfigRules.vol()
                }
            }
        )
