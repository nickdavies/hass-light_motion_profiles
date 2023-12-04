from typing import TypeVar, Generic, Dict, Set, List

V = TypeVar("V")
T = TypeVar("T")


class InvalidTemplateError(Exception):
    pass


class UnusedInputError(InvalidTemplateError):
    pass


class UnknownInputError(InvalidTemplateError):
    pass


class Template(Generic[T, V]):
    def __init__(
        self, name: str, content: T, inputs: Set[str], allow_extra: bool = False
    ):
        self.name = name
        try:
            used_inputs = self.validate_inputs(content, inputs)
        except InvalidTemplateError as e:
            raise InvalidTemplateError(f"Invalid template {name}") from e

        unused_inputs = inputs - used_inputs
        if unused_inputs and not allow_extra:
            raise UnusedInputError(
                f"Invalid template {name}: unused inputs '{','.join(unused_inputs)}'"
            )
        self._content = content
        self._inputs = used_inputs

    @classmethod
    def _validate_value(cls, value: str, inputs: Set[str]) -> str | None:
        if value[0] == "{" and value[-1] == "}":
            key = value[1:-1]
            if key not in inputs:
                raise UnknownInputError(
                    f"Found invalid template value '{value}' available: "
                    f"""'{", ".join(inputs)}'"""
                )
            return key
        return None

    def _materialize_value(self, template_value: str, inputs: Dict[str, str]) -> str:
        if template_value[0] == "{" and template_value[-1] == "}":
            key = template_value[1:-1]
            if key not in inputs:
                raise InvalidTemplateError(
                    f"Unable to materialize '{self.name}' "
                    f"value='{template_value}' with: '{inputs}'"
                )
            return inputs[key]
        return template_value

    @classmethod
    def validate_inputs(cls, content: T, inputs: Set[str]) -> Set[str]:
        raise NotImplementedError

    def materialize(self, inputs: Dict[str, str]) -> V:
        missing = self._inputs - set(inputs)
        if missing:
            raise InvalidTemplateError(
                f"Invalid materialization for template {self.name}: "
                f"missing '{','.join(missing)}'"
            )
        return self.materialize_unchecked(inputs)

    def materialize_unchecked(self, inputs: Dict[str, str]) -> V:
        raise NotImplementedError


class TemplateList(Template):
    @classmethod
    def validate_inputs(cls, content: List[Template], inputs):
        used = set()
        for template in content:
            used.update(template._inputs)
        return used

    def materialize_unchecked(self, inputs: Dict[str, str]) -> List[V]:
        return [t.materialize_unchecked(inputs) for t in self._content]
