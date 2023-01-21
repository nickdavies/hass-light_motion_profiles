PERSON_HOME_AWAY_DOMAIN = "sensor"
PERSON_OVERRIDE_HOME_AWAY_DOMAIN = "select"
PERSON_PRESENCE_DOMAIN = "sensor"
GROUP_PRESENCE_DOMAIN = "sensor"
PERSON_STATE_DOMAIN = "select"
EXISTS_ENTITY_DOMAIN = "switch"
KILLSWITCH_ENTITY_DOMAIN = "switch"


def _build(suffix, domain, without_domain):
    if without_domain:
        return suffix
    return f"{domain}.{suffix}"


def person_home_away_entity(name, without_domain=False):
    """
    This is the entity for the final calculated home/away it is the
    combination of the automatic home/away and manual override
    """
    return _build(f"person_{name}", PERSON_HOME_AWAY_DOMAIN, without_domain)


def person_override_home_away_entity(name, without_domain=False):
    """
    This is the entity for manually overwriting a users home/away status
    """
    return _build(
        f"{name}_status_override", PERSON_OVERRIDE_HOME_AWAY_DOMAIN, without_domain
    )


def person_state_entity(name, without_domain=False):
    """
    This is the entity that holds the state of a user
    """
    return _build(f"person_{name}_awake_state", PERSON_STATE_DOMAIN, without_domain)


def person_presence_entity(name, without_domain=False):
    """
    This is the entity for the final calculated presence of a person
    """
    return _build(f"person_presence_{name}", PERSON_PRESENCE_DOMAIN, without_domain)


def group_presence_entity(name, without_domain=False):
    """
    This is the entity for the final calculated presence of a person
    """
    return _build(f"group_presence_{name}", GROUP_PRESENCE_DOMAIN, without_domain)


def person_exists_entity(name, without_domain=False):
    return _build(f"person_{name}_exists", EXISTS_ENTITY_DOMAIN, without_domain)


def killswitch_entity(name, without_domain=False):
    return _build(f"killswitch_motion_{name}", KILLSWITCH_ENTITY_DOMAIN, without_domain)
