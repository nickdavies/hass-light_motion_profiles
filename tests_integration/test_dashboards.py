"""The debug dashboards, built with lovelace_codegen.

Every other test leaves `debug_dashboard` unset, so this is what shows that the
dashboards still register and render against the installed lovelace_codegen.
"""

import copy
from typing import Any

import pytest
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import area_registry as ar
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


async def _setup_dashboards(
    hass: HomeAssistant, areas: dict[str, str] | None = None
) -> HomeAssistant:
    """Set the component up with the debug dashboards on, and `areas` (light
    config name to area id) as the light configs' `area:` keys."""
    config = copy.deepcopy(TEST_CONFIG)
    config[DOMAIN]["settings"]["debug_dashboard"] = {}
    for light, area in (areas or {}).items():
        config[DOMAIN]["light_configs"][light]["area"] = area

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


@pytest.fixture
async def with_dashboards(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
) -> HomeAssistant:
    return await _setup_dashboards(hass)


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


async def _views(hass: HomeAssistant) -> dict[str, Any]:
    return {v["path"]: v for v in (await _debug(hass))["views"]}


def _cards(view: dict[str, Any]) -> list[Any]:
    return view["cards"][0]["cards"]


@pytest.fixture
async def with_rooms(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
) -> HomeAssistant:
    """simple_room is in "Living"; bedside_lamp in "Bedroom", which has no icon."""
    areas = ar.async_get(hass)
    living = areas.async_create("Living", icon="mdi:sofa")
    bedroom = areas.async_create("Bedroom")
    return await _setup_dashboards(
        hass, {"simple_room": living.id, "bedside_lamp": bedroom.id}
    )


async def test_debug_has_people_groups_then_rooms(with_rooms: HomeAssistant) -> None:
    main = (await _debug(with_rooms))["views"][0]
    grids = _cards(main)

    assert main["path"] == "main"
    assert [g["title"] for g in grids] == ["People", "Groups", "Rooms"]
    assert {g["columns"] for g in grids} == {4}
    assert [t["entity"] for t in grids[0]["cards"]] == [
        USER_A_PRESENCE,
        USER_B_PRESENCE,
    ]
    assert [t["entity"] for t in grids[1]["cards"]] == [GROUP_PRESENCE]


async def test_rooms_come_from_areas_sorted_by_name(with_rooms: HomeAssistant) -> None:
    rooms = _cards((await _debug(with_rooms))["views"][0])[2]["cards"]

    assert [(r["type"], r["name"], r["icon"]) for r in rooms] == [
        ("button", "Bedroom", "mdi:texture-box"),
        ("button", "Living", "mdi:sofa"),
    ]
    assert [r["tap_action"]["navigation_path"] for r in rooms] == [
        "/lovelace-debug/room-bedroom",
        "/lovelace-debug/room-living",
    ]


async def test_a_config_with_no_area_is_unassigned(
    with_dashboards: HomeAssistant,
) -> None:
    rooms = _cards((await _debug(with_dashboards))["views"][0])[2]["cards"]

    assert [r["name"] for r in rooms] == ["Unassigned"]
    tiles = _cards((await _views(with_dashboards))["room-unassigned"])[0]["cards"]
    assert [t["entity"] for t in tiles] == [SIMPLE_ROOM_AUTOMATION, BEDSIDE_AUTOMATION]


async def test_an_area_that_doesnt_exist_still_gets_a_room(
    hass: HomeAssistant, light_service_calls: list[ServiceCall]
) -> None:
    await _setup_dashboards(hass, {"simple_room": "attic"})

    rooms = _cards((await _debug(hass))["views"][0])[2]["cards"]

    assert [(r["name"], r["icon"]) for r in rooms] == [
        ("Attic", "mdi:alert-circle-outline"),
        ("Unassigned", "mdi:help-box-outline"),
    ]


async def test_a_room_has_config_tiles_then_a_profile_row_each(
    with_rooms: HomeAssistant,
) -> None:
    room = (await _views(with_rooms))["room-living"]
    tiles, profiles = _cards(room)

    assert room["title"] == "Living"
    assert [t["entity"] for t in tiles["cards"]] == [SIMPLE_ROOM_AUTOMATION]
    assert tiles["cards"][0]["tap_action"]["navigation_path"] == (
        "/lovelace-debug/light-simple_room"
    )
    assert profiles["title"] == "Profiles"
    assert _entity_ids(profiles) == [SIMPLE_ROOM_AUTOMATION]


async def test_every_link_leads_to_a_subview_that_leads_back(
    with_rooms: HomeAssistant,
) -> None:
    views = await _views(with_rooms)

    def links(view: dict[str, Any]) -> list[str]:
        return [
            card["tap_action"]["navigation_path"]
            for grid in _cards(view)
            if grid["type"] == "grid"
            for card in grid["cards"]
        ]

    main_links = links(views["main"])
    room_links = [
        link
        for path in views
        if path.startswith("room-")
        for link in links(views[path])
    ]
    subviews = {f"/lovelace-debug/{path}" for path in views if path != "main"}
    assert sorted(main_links + room_links) == sorted(subviews)

    for path, view in views.items():
        if path == "main":
            continue
        assert view["subview"] is True
        if path.startswith("light-"):
            room = "room-living" if path == "light-simple_room" else "room-bedroom"
            assert view["back_path"] == f"/lovelace-debug/{room}"
        else:
            assert view["back_path"] == "/lovelace-debug/main"


async def test_the_subviews_are_made_of_the_fragments(
    with_rooms: HomeAssistant,
) -> None:
    views = await _views(with_rooms)
    hass = with_rooms

    assert _cards(views["user-user_a"]) == [_render(hass, "user", user="user_a")]
    assert _cards(views["group-everyone"]) == [
        _render(hass, "group", group="everyone"),
        _render(hass, "user", user="user_a"),
        _render(hass, "user", user="user_b"),
    ]
    assert _cards(views["light-simple_room"]) == [
        _render(hass, "light_config", light="simple_room"),
        _render(hass, "manual_lights", light="simple_room"),
    ]
