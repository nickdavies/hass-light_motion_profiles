import logging
import argparse

# Home Assistant makes `import voluptuous` mean probatio when it is imported.
# The component imports voluptuous before anything imports Home Assistant, so
# this does the same first; otherwise it would load the real voluptuous and
# Home Assistant would shadow it halfway through.
from probatio.compat import install_as_voluptuous

install_as_voluptuous()

from custom_components.light_motion_profiles import (  # noqa: E402
    build_domains,
)
from custom_components.light_motion_profiles.config import (  # noqa: E402
    RawConfig,
)
from custom_components.light_motion_profiles.datatypes import (  # noqa: E402
    Config,
)
from custom_components.light_motion_profiles.exhaustive import (  # noqa: E402
    gen_light_group_matches,
)

LOGGER = logging.getLogger(__name__)


def build_argparse() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("config_file")

    subparsers = parser.add_subparsers(dest="command", required=True)

    single_parser = subparsers.add_parser(
        "single", help="Show the truth table for a single light rule"
    )
    single_parser.add_argument("light_group")

    subparsers.add_parser(
        "unassigned", help="Search all light groups for any unassigned states"
    )

    return parser


def cmd_single(args, config: Config):
    light_group = config.lights[args.light_group]
    results = list(gen_light_group_matches(light_group, config))
    results.sort(key=lambda r: (r.room, r.occupancy))

    table = tabulate.tabulate((r.to_tabulate() for r in results), headers="keys")
    print(table)


def cmd_unassigned(args, config: Config):
    unassigned = []
    for lg_name, light_group in config.lights.items():
        for result in gen_light_group_matches(light_group, config):
            if result.rule_name is None:
                unassigned.append((lg_name, result))

    if unassigned:
        unassigned.sort(key=lambda r: (r[0], r[1].room, r[1].occupancy))
        out = []
        for lg, result in unassigned:
            row = {"light_group": lg}
            row.update(result.to_tabulate())
            del row["rule_name"]
            out.append(row)

        print(tabulate.tabulate(out, headers="keys"))


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

    if args.command == "single":
        cmd_single(args, config)
    elif args.command == "unassigned":
        cmd_unassigned(args, config)
