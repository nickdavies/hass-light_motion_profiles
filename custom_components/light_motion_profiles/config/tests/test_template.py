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
        return {used}, content

    def materialize_unchecked(self, inputs):
        return self._materialize_value(self._content, inputs)


class ExampleTemplateList(TemplateList):
    template_type = ExampleTemplate


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
        example = ExampleTemplateList(
            "example list template",
            [
                "{test}",
                "{test}",
                "{bar}",
            ],
            {"test", "bar"},
        )

        self.assertEqual(
            example.materialize({"test": "foo", "bar": "yay"}), ["foo", "foo", "yay"]
        )
        self.assertEqual(
            example.materialize({"test": "foo", "bar": "yay", "extra": "ok"}),
            ["foo", "foo", "yay"],
        )

        with self.assertRaises(UnusedInputError):
            ExampleTemplateList(
                "invalid example_template list",
                [
                    "{test}",
                    "{test}",
                    "{bar}",
                ],
                {"test", "bar", "extra"},
            )


if __name__ == "__main__":
    unittest.main()
