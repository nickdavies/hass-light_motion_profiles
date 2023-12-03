from typing import TypeVar, Generic, Dict, Set, Tuple, List

V = TypeVar("V")
T = TypeVar("T")


class InvalidTemplateError(Exception):
    pass


class UnusedInputError(InvalidTemplateError):
    pass


class UnknownInputError(InvalidTemplateError):
    pass


class Template(Generic[V]):
    def __init__(
        self, name: str, content: V, inputs: Set[str], allow_extra: bool = False
    ):
        self.name = name
        try:
            used_inputs, self._content = self.validate_inputs(content, inputs)
        except InvalidTemplateError as e:
            raise InvalidTemplateError(f"Invalid template {name}") from e

        unused_inputs = inputs - used_inputs
        if unused_inputs and not allow_extra:
            raise UnusedInputError(
                f"Invalid template {name}: unused inputs '{','.join(unused_inputs)}'"
            )
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

    @classmethod
    def _materialize_value(cls, template_value: str, inputs: Dict[str, str]) -> str:
        for field, value in inputs.items():
            if template_value == f"{{{field}}}":
                return value
        raise InvalidTemplateError(
            f"Unable to materialize field '{value}' with: '{inputs}'"
        )

    @classmethod
    def validate_inputs(cls, content: V, inputs: Set[str]) -> Tuple[Set[str], V]:
        raise NotImplementedError

    def materialize(self, inputs: Dict[str, str]) -> V:
        missing = self._inputs - set(inputs)
        if missing:
            raise InvalidTemplateError(
                f"Invalid materialization for template {self.name}: "
                f"missing '{','.join(missing)}'"
            )
        return self.materialize_unchecked(inputs)

    def materialize_unchecked(self, inputs: Dict[str, str]) -> T:
        raise NotImplementedError


class TemplateList(Template):
    template_type: T

    def __init__(self, name: str, content: List[V], inputs: Set[str]):
        templated = []
        for i, template in enumerate(content):
            templated.append(
                self.template_type(name + f".{i}", template, inputs, allow_extra=True)
            )
        super().__init__(name, templated, inputs)

    @classmethod
    def validate_inputs(cls, content: List[T], inputs):
        used = set()
        for template in content:
            used.update(template._inputs)

        return (used, content)

    def materialize_unchecked(self, inputs: Dict[str, str]):
        return [t.materialize_unchecked(inputs) for t in self._content]
