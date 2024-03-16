import logging
import argparse

from custom_components.light_motion_profiles import (
    build_domains,
)
from custom_components.light_motion_profiles.config import (
    RawConfig,
)
from custom_components.light_motion_profiles.datatypes import (
    Config,
)
from custom_components.light_motion_profiles.exhaustive import (
    gen_light_group_matches,
)

LOGGER = logging.getLogger(__name__)


def build_argparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file")
    parser.add_argument("light_group")
    parser.add_argument("--no-compress", action="store_true")

    return parser


if __name__ == "__main__":
    import os.path
    import yaml
    import tabulate
    import voluptuous as vol

    parser = build_argparse()
    args = parser.parse_args()

    full_path = os.path.expandvars(os.path.expanduser(args.config_file))
    with open(full_path) as f:
        data = yaml.safe_load(f)

    data = vol.All(
        RawConfig.vol(),
        RawConfig.validate_config,
    )(data)

    raw_config = RawConfig.from_yaml(data)
    domains = build_domains()
    config = Config(raw_config, domains)

    light_group = config.lights[args.light_group]
    results = list(gen_light_group_matches(light_group, config))
    results.sort(key=lambda r: (r.room, r.occupancy))

    table = tabulate.tabulate((r.to_tabulate() for r in results), headers="keys")
    print(table)
