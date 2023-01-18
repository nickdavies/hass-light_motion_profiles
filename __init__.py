import voluptuous as vol

DOMAIN = "light_motion_profiles"


USER_SCHEMA = vol.Schema(
    vol.Any(
        None,
        {
            vol.Optional("guest", default=False): bool,
            vol.Optional("icons"): vol.Schema({vol.Extra: str}),
            vol.Optional("tracking_entity"): str,
        },
    )
)

# For now we have no metadata about groups but we will define
# them as dicts still so we can add some later if we need to
GROUP_SCHEMA = vol.Schema(
    vol.Any(
        None,
        {
            vol.Extra: vol.Any(None, vol.Schema({})),
        },
    )
)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            vol.Any(
                None,
                {
                    vol.Optional("users"): {vol.Extra: USER_SCHEMA},
                    vol.Optional("groups"): {vol.Extra: GROUP_SCHEMA},
                },
            )
        )
    }
)


if __name__ == "__main__":
    import sys

    import yaml

    with open(sys.argv[1], "r") as f:
        config = yaml.safe_load(f)

    print(config)
    print(CONFIG_SCHEMA(config))
