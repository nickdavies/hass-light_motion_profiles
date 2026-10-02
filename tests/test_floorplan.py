"""Tests for floorplan.py: reading rooms back out of homelab-data's plans."""

import pytest

from custom_components.light_motion_profiles.floorplan import (
    FloorplanError,
    Rect,
    cover,
    outline,
    parse,
)

# A 20 by 10 plan with a 2 unit margin: an L-shaped kitchen wrapped round a
# square pantry, and a hall whose wall to the kitchen is curved.
PLAN = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="-2 -2 24 14" width="480" height="280">
  <g id="outdoor"><path class="outdoor" d="M0,0 L1,0 L1,1 Z"/></g>
  <g id="rooms">
    <g id="room-kitchen">
      <path class="room" d="M0,0 L10,0 L10,10 L0,10 L0,5 L5,5 L5,0 Z"/>
      <text class="name" x="7.5" y="4">Kitchen</text>
      <text class="temp" id="temp-kitchen" x="7.5" y="5.3">--</text>
    </g>
    <g id="room-pantry">
      <path class="room" d="M0,0 L5,0 L5,5 L0,5 Z"/>
      <text class="small" x="2.5" y="2">Pantry</text>
      <text class="temp" id="temp-pantry" x="2.5" y="3.3">--</text>
    </g>
    <g id="room-hall">
      <path class="room" d="M10,0 L20,0 L20,10 L10,10 Q14,5 10,0 Z"/>
      <text class="name" x="16" y="5">Hall</text>
      <text class="temp" id="temp-hall" x="16" y="6.4">--</text>
    </g>
  </g>
  <g id="closets"><path class="room closet" d="M0,0 L1,0 L1,1 Z"/></g>
</svg>
"""


def _area(rects: list[Rect]) -> float:
    return sum(r.width * r.height for r in rects)


class TestOutline:
    def test_straight_walls_are_their_corners(self):
        polygon, corners = outline("M0,0 L4,0 L4,2 Z")
        assert polygon == corners == [(0, 0), (4, 0), (4, 2)]

    def test_a_curve_is_followed_not_drawn_to_its_control_point(self):
        polygon, _ = outline("M0,0 Q10,5 0,10 L-5,10 Z")
        assert (10.0, 5.0) not in polygon
        assert (5.0, 5.0) in polygon  # its middle
        assert polygon[-2] == (0.0, 10.0)

    @pytest.mark.parametrize("d", ["M0,0 A1,1 0 0 1 2,2 Z", "M0,0 L1", "M0,0 L1,1 Z"])
    def test_rejects_what_homelab_data_doesnt_draw(self, d):
        with pytest.raises(FloorplanError):
            outline(d)


class TestCover:
    def test_an_l_is_two_rectangles_exactly(self):
        polygon, corners = outline("M0,0 L10,0 L10,10 L0,10 L0,5 L5,5 L5,0 Z")
        assert cover(polygon, corners) == [
            ((5.0, 0.0), (10.0, 5.0)),
            ((0.0, 5.0), (10.0, 10.0)),
        ]

    def test_a_rectangle_is_itself(self):
        polygon, corners = outline("M1,1 L3,1 L3,4 L1,4 Z")
        assert cover(polygon, corners) == [((1.0, 1.0), (3.0, 4.0))]


class TestParse:
    def test_aspect_is_the_view_box(self):
        assert parse(PLAN).aspect == pytest.approx(24 / 14)

    def test_finds_every_room_and_only_rooms(self):
        assert list(parse(PLAN).rooms) == ["kitchen", "pantry", "hall"]

    def test_the_anchor_is_on_the_reading_in_percent(self):
        left, top = parse(PLAN).rooms["kitchen"].anchor
        assert left == pytest.approx((7.5 + 2) / 24 * 100)
        assert top == pytest.approx((5.3 + 0.1 + 2) / 14 * 100)

    def test_areas_cover_each_room_and_no_other(self):
        rooms = parse(PLAN).rooms
        assert _area(rooms["pantry"].areas) == pytest.approx(25 / (24 * 14) * 1e4)
        assert _area(rooms["kitchen"].areas) == pytest.approx(75 / (24 * 14) * 1e4)
        # About its true area: 100, less the curve's bulge, which reaches
        # halfway to its control point: 2/3 * 2 * 10.
        hall = _area(rooms["hall"].areas) / 1e4 * (24 * 14)
        assert hall == pytest.approx(100 - 40 / 3, abs=4)

        everything = [a for room in rooms.values() for a in room.areas]
        for i, a in enumerate(everything):
            for b in everything[i + 1 :]:
                apart_x = abs(a.left - b.left) * 2 >= a.width + b.width - 1e-9
                apart_y = abs(a.top - b.top) * 2 >= a.height + b.height - 1e-9
                assert apart_x or apart_y, f"{a} overlaps {b}"

    def test_a_room_without_its_reading_is_an_error(self):
        broken = PLAN.replace('id="temp-hall"', 'id="temp-other"')
        with pytest.raises(FloorplanError, match="hall"):
            parse(broken)

    @pytest.mark.parametrize(
        "svg",
        ["not a drawing", '<svg xmlns="http://www.w3.org/2000/svg"/>'],
    )
    def test_rejects_other_files(self, svg):
        with pytest.raises(FloorplanError):
            parse(svg)
