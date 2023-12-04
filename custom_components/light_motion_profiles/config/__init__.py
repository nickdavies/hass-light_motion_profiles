import logging

from light_profiles import WholeConfig
from light_templates import AllTemplates

LOGGER = logging.getLogger(__name__)


def load_config(raw_config):
    templates = AllTemplates.from_yaml(data["templates"])
    rules = templates.light_config_rules["default_rules"].materialize(
        {"users": "everyone"}
    )
    for rule in rules:
        print(rule)


if __name__ == "__main__":
    import sys
    import yaml

    with open(sys.argv[1]) as f:
        data = yaml.safe_load(f)

    templated_config = load_config(data)
