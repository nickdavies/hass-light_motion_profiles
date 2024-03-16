import unittest

from template import (
    Template,
    TemplateList,
    InvalidTemplateError,
    UnusedInputError,
    UnknownInputError,
)


class ExampleTemplate(Template):
    @classmethod
    def validate_inputs(cls, content, inputs):
        used = cls._validate_value(content, inputs)
        return {used}

    def materialize_unchecked(self, inputs):
        return self._materialize_value(self._content, inputs)


class ExampleTemplateList(TemplateList):
    pass


class TestTemplate(unittest.TestCase):
    def test_basic(self):
        example = ExampleTemplate("example_template", "{test}", {"test"})
        self.assertEqual(example.materialize({"test": "foo"}), "foo")
        self.assertEqual(example.materialize({"test": "foo", "extra": "ok"}), "foo")

        with self.assertRaises(InvalidTemplateError):
            ExampleTemplate("example_template", "{test}", {"bar"})

        with self.assertRaises(InvalidTemplateError):
            ExampleTemplate("example_template", "{test}", {"test", "extra"})

        with self.assertRaises(UnusedInputError):
            ExampleTemplate("example_template", "test", {"test"})

        with self.assertRaises(UnknownInputError):
            ExampleTemplate._validate_value("{test}", {"bar"})

        with self.assertRaises(InvalidTemplateError):
            example.materialize({})

        with self.assertRaises(InvalidTemplateError):
            example.materialize({"bar": "not ok"})

        e2 = ExampleTemplate(
            "example_template", "{test}", {"test", "extra"}, allow_extra=True
        )
        self.assertEqual(e2.materialize({"test": "foo"}), "foo")
        self.assertEqual(e2.materialize({"test": "foo", "extra": "ok"}), "foo")
        self.assertEqual(
            e2.materialize({"test": "foo", "extra": "ok", "unknown_extra": "also ok"}),
            "foo",
        )

    def test_list(self):
        inputs = {"test", "bar"}
        example = ExampleTemplateList(
            "invalid example_template list",
            [
                ExampleTemplate("test1", "{test}", inputs, allow_extra=True),
                ExampleTemplate("test2", "{test}", {"test"}),
                ExampleTemplate("test3", "{bar}", inputs, allow_extra=True),
            ],
            inputs,
        )

        self.assertEqual(
            example.materialize({"test": "foo", "bar": "yay"}), ["foo", "foo", "yay"]
        )
        self.assertEqual(
            example.materialize({"test": "foo", "bar": "yay", "extra": "ok"}),
            ["foo", "foo", "yay"],
        )

        with self.assertRaises(UnusedInputError):
            inputs = {"test", "bar", "extra"}
            ExampleTemplateList(
                "invalid example_template list",
                [
                    ExampleTemplate("test1", "{test}", inputs, allow_extra=True),
                    ExampleTemplate("test2", "{test}", inputs, allow_extra=True),
                    ExampleTemplate("test3", "{bar}", inputs, allow_extra=True),
                ],
                inputs,
            )


if __name__ == "__main__":
    unittest.main()
