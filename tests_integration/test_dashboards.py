"""The debug dashboards, built with lovelace_codegen.

Every other test leaves `debug_dashboard` unset, so this is what shows that the
dashboards still register and render against the installed lovelace_codegen.
"""

import copy
from typing import Any

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.loader import DATA_CUSTOM_COMPONENTS
from homeassistant.setup import async_setup_component

from .conftest import (
    BEDSIDE_AUTOMATION,
    BEDSIDE_LIGHT,
    BEDSIDE_MOTION,
    DOMAIN,
    GROUP_PRESENCE,
    PERSON_USER_A,
    SIMPLE_ROOM_AUTOMATION,
    SIMPLE_ROOM_LIGHT,
    SIMPLE_ROOM_MOTION,
    TEST_CONFIG,
    USER_A_PRESENCE,
    USER_B_PRESENCE,
    _ensure_custom_components_path,
)


def _entity_ids(node: Any) -> list[str]:
    """Every entity id anywhere in a rendered card tree."""
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "entity" and isinstance(value, str):
                found.append(value)
            else:
                found.extend(_entity_ids(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_entity_ids(item))
    return found


@pytest.fixture
async def with_dashboards(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
) -> HomeAssistant:
    config = copy.deepcopy(TEST_CONFIG)
    config[DOMAIN]["settings"]["debug_dashboard"] = {}

    # The entities the config names but other integrations own.
    for entity_id in (PERSON_USER_A, SIMPLE_ROOM_MOTION, BEDSIDE_MOTION):
        hass.states.async_set(entity_id, "on")
    for entity_id in (SIMPLE_ROOM_LIGHT, BEDSIDE_LIGHT):
        hass.states.async_set(entity_id, "off")

    hass.data.pop(DATA_CUSTOM_COMPONENTS, None)
    _ensure_custom_components_path()

    assert await async_setup_component(hass, DOMAIN, config), "setup failed"
    await hass.async_block_till_done()
    return hass


@pytest.mark.parametrize(
    "url_path", ["presence-debug", "motion-debug", "lovelace-debug"]
)
async def test_the_dashboard_registers_and_renders(
    with_dashboards: HomeAssistant, url_path: str
) -> None:
    dashboard = with_dashboards.data["lovelace"].dashboards[url_path]
    config = await dashboard.async_load(False)

    assert config["views"], "rendered no views"
    assert _entity_ids(config), "rendered no entities"


async def test_every_entity_on_the_dashboards_exists(
    with_dashboards: HomeAssistant,
) -> None:
    """A card naming an entity the component never created renders as a blank
    row nobody notices."""
    missing = set()
    for url_path in ("presence-debug", "motion-debug", "lovelace-debug"):
        dashboard = with_dashboards.data["lovelace"].dashboards[url_path]
        for entity_id in _entity_ids(await dashboard.async_load(False)):
            if with_dashboards.states.get(entity_id) is None:
                missing.add(entity_id)

    assert not missing


# --- Fragments ---
#
# Registered whether or not the debug dashboards are on, so these use the plain
# `integration` fixture. The dashboards are built from the same functions, so
# each fragment should appear, card for card, on the dashboard it came from.


def _registry(hass: HomeAssistant) -> Any:
    from custom_components.lovelace_codegen.fragments import DATA_FRAGMENTS

    return hass.data[DATA_FRAGMENTS]


def _render(hass: HomeAssistant, name: str, **params: str) -> Any:
    return _registry(hass).get(DOMAIN, name).render(params)


def _all_fragment_renders(hass: HomeAssistant) -> list[Any]:
    lights = TEST_CONFIG[DOMAIN]["light_configs"]
    users = TEST_CONFIG[DOMAIN]["users"]
    return [
        _render(hass, "users_groups"),
        _render(hass, "presence_outputs"),
        _render(hass, "killswitches"),
        _render(hass, "light_automation_states"),
        _render(hass, "motion_inputs"),
        *(_render(hass, "user", user=user) for user in users),
        *(_render(hass, "light_config", light=light) for light in lights),
        *(_render(hass, "manual_lights", light=light) for light in lights),
        *(_render(hass, "group", group=g) for g in TEST_CONFIG[DOMAIN]["groups"]),
    ]


async def test_fragments_are_registered_without_the_dashboards(
    integration: HomeAssistant,
) -> None:
    assert _registry(integration).names(DOMAIN) == [
        "group",
        "killswitches",
        "light_automation_states",
        "light_config",
        "manual_lights",
        "motion_inputs",
        "presence_outputs",
        "user",
        "users_groups",
    ]


async def test_every_entity_in_every_fragment_exists(
    integration: HomeAssistant,
) -> None:
    missing = {
        entity_id
        for card in _all_fragment_renders(integration)
        for entity_id in _entity_ids(card)
        if integration.states.get(entity_id) is None
    }
    assert not missing


async def test_the_dashboards_are_made_of_the_fragments(
    with_dashboards: HomeAssistant,
) -> None:
    dashboards = with_dashboards.data["lovelace"].dashboards
    presence = (await dashboards["presence-debug"].async_load(False))["views"][0]
    motion = (await dashboards["motion-debug"].async_load(False))["views"][0]
    presence_cards = presence["cards"][0]["cards"]
    motion_cards = motion["cards"][0]["cards"]

    users = TEST_CONFIG[DOMAIN]["users"]
    lights = TEST_CONFIG[DOMAIN]["light_configs"]
    assert presence_cards == [
        _render(with_dashboards, "users_groups"),
        _render(with_dashboards, "presence_outputs"),
        {
            "type": "vertical-stack",
            "cards": [_render(with_dashboards, "user", user=u) for u in users],
        },
    ]
    assert motion_cards == [
        _render(with_dashboards, "killswitches"),
        {
            "type": "vertical-stack",
            "cards": [
                _render(with_dashboards, "light_automation_states"),
                *(_render(with_dashboards, "light_config", light=x) for x in lights),
            ],
        },
        _render(with_dashboards, "motion_inputs"),
    ]


@pytest.mark.parametrize(
    ("name", "params"),
    [
        ("user", {"user": "nobody"}),
        ("user", {}),
        ("light_config", {"light": "attic"}),
        ("manual_lights", {"light": "attic"}),
        ("group", {"group": "nobody"}),
        ("killswitches", {"light": "simple_room"}),
    ],
)
async def test_fragments_reject_bad_params(
    integration: HomeAssistant, name: str, params: dict[str, str]
) -> None:
    import voluptuous as vol

    with pytest.raises(vol.Invalid):
        _render(integration, name, **params)


async def test_a_fragment_over_the_websocket(
    integration: HomeAssistant, hass_ws_client: Any
) -> None:
    client = await hass_ws_client(integration)
    await client.send_json_auto_id(
        {
            "type": "lovelace_codegen/fragment",
            "source": DOMAIN,
            "name": "light_config",
            "params": {"light": "bedside_lamp"},
        }
    )
    msg = await client.receive_json()

    assert msg["success"], msg
    assert msg["result"]["title"] == "bedside_lamp"
    assert BEDSIDE_LIGHT in _entity_ids(msg["result"])


async def test_group_lists_its_members_in_user_order(
    integration: HomeAssistant,
) -> None:
    card = _render(integration, "group", group="everyone")

    assert card["title"] == "Everyone"
    assert _entity_ids(card) == [GROUP_PRESENCE, USER_A_PRESENCE, USER_B_PRESENCE]


async def test_manual_lights_lists_a_group_light_then_its_members(
    integration: HomeAssistant,
) -> None:
    integration.states.async_set(
        SIMPLE_ROOM_LIGHT,
        "on",
        {"entity_id": ["light.simple_room_a", "light.simple_room_b"]},
    )

    card = _render(integration, "manual_lights", light="simple_room")

    assert _entity_ids(card) == [
        SIMPLE_ROOM_LIGHT,
        "light.simple_room_a",
        "light.simple_room_b",
    ]


async def test_manual_lights_on_a_single_light(integration: HomeAssistant) -> None:
    assert _entity_ids(_render(integration, "manual_lights", light="bedside_lamp")) == [
        BEDSIDE_LIGHT
    ]


# --- The merged Debug dashboard ---


async def _debug(hass: HomeAssistant) -> dict[str, Any]:
    dashboard = hass.data["lovelace"].dashboards["lovelace-debug"]
    return await dashboard.async_load(False)


async def test_debug_has_a_grid_of_tiles_for_each_kind(
    with_dashboards: HomeAssistant,
) -> None:
    main = (await _debug(with_dashboards))["views"][0]
    grids = main["cards"][0]["cards"]

    assert main["path"] == "main"
    assert [g["title"] for g in grids] == ["People", "Groups", "Lights"]
    assert {g["columns"] for g in grids} == {4}
    assert [t["entity"] for t in grids[0]["cards"]] == [
        USER_A_PRESENCE,
        USER_B_PRESENCE,
    ]
    assert [t["entity"] for t in grids[1]["cards"]] == [GROUP_PRESENCE]
    assert [t["entity"] for t in grids[2]["cards"]] == [
        SIMPLE_ROOM_AUTOMATION,
        BEDSIDE_AUTOMATION,
    ]


async def test_every_tile_opens_a_subview_that_leads_back(
    with_dashboards: HomeAssistant,
) -> None:
    views = (await _debug(with_dashboards))["views"]
    subviews = {f"/lovelace-debug/{v['path']}": v for v in views[1:]}

    targets = [
        tile["tap_action"]["navigation_path"]
        for grid in views[0]["cards"][0]["cards"]
        for tile in grid["cards"]
    ]
    assert sorted(targets) == sorted(subviews)
    for view in subviews.values():
        assert view["subview"] is True
        assert view["back_path"] == "/lovelace-debug/main"


async def test_the_subviews_are_made_of_the_fragments(
    with_dashboards: HomeAssistant,
) -> None:
    views = {v["path"]: v for v in (await _debug(with_dashboards))["views"]}

    def cards(path: str) -> list[Any]:
        return views[path]["cards"][0]["cards"]

    hass = with_dashboards
    assert cards("user-user_a") == [_render(hass, "user", user="user_a")]
    assert cards("group-everyone") == [
        _render(hass, "group", group="everyone"),
        _render(hass, "user", user="user_a"),
        _render(hass, "user", user="user_b"),
    ]
    assert cards("light-simple_room") == [
        _render(hass, "light_config", light="simple_room"),
        _render(hass, "manual_lights", light="simple_room"),
    ]
