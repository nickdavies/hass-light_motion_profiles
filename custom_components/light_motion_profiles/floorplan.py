"""Where each room sits on a floor plan from homelab-data.

homelab-data draws each floor of the house as `floorplan_<floor>.svg`, which
homelab serves from Home Assistant's www/floorplan/. Each room in it is a
`<g id="room-<area id>">` holding its outline, a `<path class="room">`, and a
`<text id="temp-<area id>">` placeholder for a reading under its name. This
reads those back, as percentages of the drawing, for a dashboard to place
things over the plan.

The outlines are straight lines (`M`, `L`, `Z`) and quadratic curves (`Q`), in
absolute coordinates, which is all homelab-data draws.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass

SVG = "{http://www.w3.org/2000/svg}"
ROOM_PREFIX = "room-"
READING_PREFIX = "temp-"

# Points each curve is followed through when deciding what is inside a room.
CURVE_STEPS = 8

# How far below a reading's baseline a room's anchor is, in plan units (feet).
# An icon there covers the reading's placeholder, and at phone sizes clears the
# room's name above it.
ANCHOR_BELOW_READING = 0.1

Point = tuple[float, float]


@dataclass(frozen=True)
class Rect:
    """A rectangle by its centre and size, in percent of the plan's width
    (`left`, `width`) and height (`top`, `height`)."""

    left: float
    top: float
    width: float
    height: float


@dataclass(frozen=True)
class PlanRoom:
    # Where something about the room goes, over its reading's placeholder under
    # its name, in percent of the plan.
    anchor: tuple[float, float]
    # Rectangles that together cover the room and nothing else.
    areas: list[Rect]


@dataclass(frozen=True)
class Floorplan:
    # The plan's width over its height.
    aspect: float
    rooms: dict[str, PlanRoom]


class FloorplanError(Exception):
    pass


_TOKEN = re.compile(r"[MLQZ]|-?\d+(?:\.\d+)?")


def outline(d: str) -> tuple[list[Point], list[Point]]:
    """A path's outline as a polygon, and the corners it was drawn through.

    Curves are followed in `CURVE_STEPS` straight pieces, each a polygon point;
    the corners are the points the path itself names (its curves' ends, and the
    points along them, but not their control points).
    """
    tokens = _TOKEN.findall(d)
    polygon: list[Point] = []
    corners: list[Point] = []
    i = 0

    def point() -> Point:
        nonlocal i
        try:
            p = (float(tokens[i]), float(tokens[i + 1]))
        except (IndexError, ValueError) as e:
            raise FloorplanError(f"Can't read the outline {d!r}") from e
        i += 2
        return p

    while i < len(tokens):
        command = tokens[i]
        i += 1
        if command in ("M", "L"):
            p = point()
            polygon.append(p)
            corners.append(p)
        elif command == "Q":
            if not polygon:
                raise FloorplanError(f"The outline {d!r} starts with a curve")
            (x0, y0), (cx, cy), (x1, y1) = polygon[-1], point(), point()
            for step in range(1, CURVE_STEPS + 1):
                t = step / CURVE_STEPS
                p = (
                    (1 - t) ** 2 * x0 + 2 * (1 - t) * t * cx + t**2 * x1,
                    (1 - t) ** 2 * y0 + 2 * (1 - t) * t * cy + t**2 * y1,
                )
                polygon.append(p)
                corners.append(p)
        elif command == "Z":
            pass
        else:
            raise FloorplanError(f"Can't read {command!r} in the outline {d!r}")
    if len(polygon) < 3:
        raise FloorplanError(f"The outline {d!r} has no inside")
    return polygon, corners


def inside(polygon: list[Point], x: float, y: float) -> bool:
    """Whether a point is inside a polygon, by counting edges crossed."""
    crossed = False
    for (x0, y0), (x1, y1) in zip(polygon, polygon[1:] + polygon[:1]):
        if (y0 > y) != (y1 > y) and x < x0 + (y - y0) * (x1 - x0) / (y1 - y0):
            crossed = not crossed
    return crossed


def cover(polygon: list[Point], corners: list[Point]) -> list[tuple[Point, Point]]:
    """Rectangles, as (top left, bottom right), that cover a polygon.

    The polygon is cut into a grid along every corner's x and y, and each cell
    whose middle is inside it is kept. Given every room's corners, rooms cut on
    the same grid, so no cell, and so no rectangle, is in two rooms. Cells are then joined into runs across
    each row, and runs into rectangles down the rows they share. An outline of
    straight walls is covered exactly; a curve or a slanted wall is followed to
    the nearest cell.
    """
    xs = sorted({round(x, 4) for x, _ in corners})
    ys = sorted({round(y, 4) for _, y in corners})

    open_rects: dict[tuple[float, float], float] = {}
    rects: list[tuple[Point, Point]] = []
    for top, bottom in zip(ys, ys[1:]):
        middle = (top + bottom) / 2
        runs: list[tuple[float, float]] = []
        for left, right in zip(xs, xs[1:]):
            if not inside(polygon, (left + right) / 2, middle):
                continue
            if runs and runs[-1][1] == left:
                runs[-1] = (runs[-1][0], right)
            else:
                runs.append((left, right))
        for run in set(open_rects) - set(runs):
            rects.append(((run[0], open_rects.pop(run)), (run[1], top)))
        for run in runs:
            open_rects.setdefault(run, top)
    for run, top in open_rects.items():
        rects.append(((run[0], top), (run[1], ys[-1])))
    return sorted(rects, key=lambda r: (r[0][1], r[0][0]))


def parse(svg: str) -> Floorplan:
    """The rooms on a plan, by area id."""
    try:
        root = ET.fromstring(svg)
    except ET.ParseError as e:
        raise FloorplanError(f"Not a drawing: {e}") from e
    try:
        min_x, min_y, width, height = (
            float(v) for v in root.attrib["viewBox"].replace(",", " ").split()
        )
    except (KeyError, ValueError) as e:
        raise FloorplanError("The drawing has no usable viewBox") from e

    def x(value: float) -> float:
        return (value - min_x) / width * 100

    def y(value: float) -> float:
        return (value - min_y) / height * 100

    outlines: dict[str, tuple[tuple[list[Point], list[Point]], Point]] = {}
    for group in root.iter(f"{SVG}g"):
        group_id = group.get("id", "")
        if not group_id.startswith(ROOM_PREFIX):
            continue
        area_id = group_id.removeprefix(ROOM_PREFIX)
        shape = next(
            (
                p
                for p in group.iter(f"{SVG}path")
                if "room" in p.get("class", "").split()
            ),
            None,
        )
        reading = next(
            (
                t
                for t in group.iter(f"{SVG}text")
                if t.get("id") == READING_PREFIX + area_id
            ),
            None,
        )
        if shape is None or reading is None:
            raise FloorplanError(f"Room {area_id!r} has no outline or no reading")

        outlines[area_id] = (
            outline(shape.get("d", "")),
            (float(reading.get("x", 0)), float(reading.get("y", 0))),
        )

    corners = [c for (_, room_corners), _ in outlines.values() for c in room_corners]
    rooms = {}
    for area_id, ((polygon, _), (reading_x, reading_y)) in outlines.items():
        areas = [
            Rect(
                left=x((x0 + x1) / 2),
                top=y((y0 + y1) / 2),
                width=(x1 - x0) / width * 100,
                height=(y1 - y0) / height * 100,
            )
            for (x0, y0), (x1, y1) in cover(polygon, corners)
        ]
        anchor = (x(reading_x), y(reading_y + ANCHOR_BELOW_READING))
        rooms[area_id] = PlanRoom(anchor, areas)
    return Floorplan(aspect=width / height, rooms=rooms)
