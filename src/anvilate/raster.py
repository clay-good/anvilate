"""Rasterize the viewport SVG this package writes into a PNG, with the standard library only.

An MCP client hands a tool's image to the model, and the model reads PNG, JPEG, GIF and WebP:
an SVG viewport reached the agent as an attachment it could not look at, so it could not see
the part it had just built. This module draws the small, fixed vocabulary `render_viewport`
emits (``rect``, ``polygon``, ``line``, ``circle``, ``ellipse``, and ``path`` made of ``M``,
``L``, ``A`` and ``Z``) and refuses anything else rather than drawing a guess. Edges are
smoothed by drawing at twice the size and averaging. The output is deterministic: the same
SVG gives the same bytes, so the viewport's SHA-256 still identifies the drawing.

It is not a general SVG renderer, and is not offered as one: it is the other half of the
renderer in `geometry`, and the tests hold the two together.
"""

from __future__ import annotations

import math
import re
import struct
import zlib
from xml.etree import ElementTree

from .refusal import RefusalError, Remedy

__all__ = ["RasterError", "svg_to_png"]


class RasterError(RefusalError, ValueError):
    """An SVG this rasterizer does not draw: anything but the viewport vocabulary."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            remedies=(
                Remedy(
                    action="render",
                    subject="the viewport with format svg",
                    source="anvilate.geometry.render_viewport, whose SVG this module rasterizes",
                ),
            ),
        )


_SCALE = 2  # supersampling factor
_CURVE_SEGMENTS = 96
_SVG = "{http://www.w3.org/2000/svg}"
_DRAWN = {"rect", "polygon", "line", "circle", "ellipse", "path"}
_NUMBER = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")

Point = tuple[float, float]


def _colour(value: str | None) -> tuple[int, int, int] | None:
    if value is None or value == "none":
        return None
    if re.fullmatch(r"#[0-9a-fA-F]{6}", value):
        return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)
    raise RasterError(f"the viewport rasterizer reads #rrggbb colours only; got {value!r}")


class _Canvas:
    def __init__(self, width: int, height: int) -> None:
        self.width, self.height = width * _SCALE, height * _SCALE
        self.rows = [bytearray(b"\xff" * (self.width * 3)) for _ in range(self.height)]

    def fill(self, points: list[Point], colour: tuple[int, int, int]) -> None:
        """Even-odd scanline fill of one closed polygon, in output pixel coordinates."""
        scaled = [(x * _SCALE, y * _SCALE) for x, y in points]
        ys = [y for _, y in scaled]
        top = max(0, math.floor(min(ys)))
        bottom = min(self.height - 1, math.ceil(max(ys)))
        pixel = bytes(colour)
        # Each edge that can cross a row centre, as (lowest y, highest y, x0, y0, dx, dy).
        # A level edge crosses none. The crossing is evaluated exactly as x0 + (c - y0) *
        # dx / dy, never through a precomputed slope: the picture is held to its bytes.
        edges = [
            (min(y0, y1), max(y0, y1), x0, y0, x1 - x0, y1 - y0)
            for (x0, y0), (x1, y1) in zip(scaled, scaled[1:] + scaled[:1], strict=True)
            if y0 != y1
        ]
        width, rows, ceil = self.width, self.rows, math.ceil
        for row in range(top, bottom + 1):
            centre = row + 0.5
            crossings = [
                x0 + (centre - y0) * dx / dy
                for low, high, x0, y0, dx, dy in edges
                if low <= centre < high
            ]
            if len(crossings) == 2:  # a convex polygon: nearly every fill a drawing makes
                left, right = crossings
                if left > right:
                    left, right = right, left
                start, stop = max(0, ceil(left - 0.5)), min(width, ceil(right - 0.5))
                if stop > start:
                    rows[row][start * 3 : stop * 3] = pixel * (stop - start)
                continue
            crossings.sort()
            line = rows[row]
            for left, right in zip(crossings[::2], crossings[1::2], strict=False):
                start = max(0, ceil(left - 0.5))
                stop = min(width, ceil(right - 0.5))
                if stop > start:
                    line[start * 3 : stop * 3] = pixel * (stop - start)

    def _square(self, x: float, y: float, half: float, colour: tuple[int, int, int]) -> None:
        """The square ``fill`` draws about one point, without the polygon machinery.

        Half the fills in a drawing are these joints. Its two upright edges cross every row
        centre between its top and bottom at their own x, so the run is the same on each.
        """
        left, right = (x - half) * _SCALE, (x + half) * _SCALE
        high, low = (y - half) * _SCALE, (y + half) * _SCALE
        start, stop = max(0, math.ceil(left - 0.5)), min(self.width, math.ceil(right - 0.5))
        if stop <= start:
            return
        run = bytes(colour) * (stop - start)
        for row in range(max(0, math.floor(high)), min(self.height - 1, math.ceil(low)) + 1):
            if high <= row + 0.5 < low:
                self.rows[row][start * 3 : stop * 3] = run

    def stroke(
        self, points: list[Point], colour: tuple[int, int, int], width: float, *, closed: bool
    ) -> None:
        """Each segment as a filled quadrilateral, with a square at every joint."""
        half = max(width, 0.75) / 2
        path = points + points[:1] if closed else points
        for (x0, y0), (x1, y1) in zip(path, path[1:], strict=False):
            length = math.hypot(x1 - x0, y1 - y0)
            if length == 0:
                continue
            nx, ny = -(y1 - y0) / length * half, (x1 - x0) / length * half
            self.fill(
                [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)],
                colour,
            )
        for x, y in path:
            self._square(x, y, half, colour)

    def png(self) -> bytes:
        """Average each 2x2 block into one pixel and encode as an 8-bit RGB PNG."""
        width, height = self.width // _SCALE, self.height // _SCALE
        raw = bytearray()
        blank, white = bytearray(b"\xff" * (self.width * 3)), b"\xff" * (width * 3)
        for row in range(height):
            upper, lower = self.rows[row * 2], self.rows[row * 2 + 1]
            raw.append(0)  # filter: none
            if upper == blank and lower == blank:  # most of a drawing is paper
                raw += white
                continue
            out = bytearray(width * 3)
            for channel in range(3):
                # The four samples under one output pixel sit 0, 3 bytes along each row.
                out[channel::3] = bytes(
                    (a + b + c + d + 2) >> 2
                    for a, b, c, d in zip(
                        upper[channel::6],
                        upper[channel + 3 :: 6],
                        lower[channel::6],
                        lower[channel + 3 :: 6],
                        strict=True,
                    )
                )
            raw += out

        def chunk(kind: bytes, body: bytes) -> bytes:
            return (
                struct.pack(">I", len(body))
                + kind
                + body
                + struct.pack(">I", zlib.crc32(kind + body))
            )

        header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
        return (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", header)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b"")
        )


def _ellipse(cx: float, cy: float, rx: float, ry: float) -> list[Point]:
    return [
        (
            cx + rx * math.cos(2 * math.pi * k / _CURVE_SEGMENTS),
            cy + ry * math.sin(2 * math.pi * k / _CURVE_SEGMENTS),
        )
        for k in range(_CURVE_SEGMENTS)
    ]


def _arc(
    start: Point, rx: float, ry: float, rotation: float, large: bool, sweep: bool, end: Point
) -> list[Point]:
    """Points along an SVG elliptical arc (SVG 1.1 implementation notes, F.6.5), excluding start."""
    (x1, y1), (x2, y2) = start, end
    if rx == 0 or ry == 0 or start == end:
        return [end]
    phi = math.radians(rotation)
    cos_phi, sin_phi = math.cos(phi), math.sin(phi)
    dx, dy = (x1 - x2) / 2, (y1 - y2) / 2
    xp, yp = cos_phi * dx + sin_phi * dy, -sin_phi * dx + cos_phi * dy
    rx, ry = abs(rx), abs(ry)
    grow = (xp / rx) ** 2 + (yp / ry) ** 2
    if grow > 1:
        rx, ry = rx * math.sqrt(grow), ry * math.sqrt(grow)
    numerator = rx * rx * ry * ry - rx * rx * yp * yp - ry * ry * xp * xp
    factor = math.sqrt(max(0.0, numerator / (rx * rx * yp * yp + ry * ry * xp * xp)))
    if large == sweep:
        factor = -factor
    cxp, cyp = factor * rx * yp / ry, -factor * ry * xp / rx
    cx = cos_phi * cxp - sin_phi * cyp + (x1 + x2) / 2
    cy = sin_phi * cxp + cos_phi * cyp + (y1 + y2) / 2

    def angle(ux: float, uy: float) -> float:
        return math.atan2(uy, ux)

    theta = angle((xp - cxp) / rx, (yp - cyp) / ry)
    delta = angle((-xp - cxp) / rx, (-yp - cyp) / ry) - theta
    if sweep and delta < 0:
        delta += 2 * math.pi
    elif not sweep and delta > 0:
        delta -= 2 * math.pi
    steps = max(4, math.ceil(abs(delta) / (2 * math.pi) * _CURVE_SEGMENTS))
    points = []
    for k in range(1, steps + 1):
        t = theta + delta * k / steps
        x, y = rx * math.cos(t), ry * math.sin(t)
        points.append((cos_phi * x - sin_phi * y + cx, sin_phi * x + cos_phi * y + cy))
    return points


def _path(d: str) -> list[tuple[list[Point], bool]]:
    """Each subpath of an absolute M/L/H/V/A/Z path, and whether it is closed."""
    if re.search(r"[^MLHVAZ\s\d.,eE+-]", d):
        raise RasterError(
            f"the viewport rasterizer reads absolute M, L, H, V, A and Z only; got {d!r}"
        )
    tokens = re.findall(r"[MLHVAZ]|" + _NUMBER.pattern, d)
    subpaths: list[tuple[list[Point], bool]] = []
    points: list[Point] = []
    index = 0
    while index < len(tokens):
        command = tokens[index]
        index += 1
        if command == "M":
            if len(points) > 1:
                subpaths.append((points, False))
            points = [(float(tokens[index]), float(tokens[index + 1]))]
            index += 2
        elif command == "L":
            points.append((float(tokens[index]), float(tokens[index + 1])))
            index += 2
        elif command == "H":
            points.append((float(tokens[index]), points[-1][1]))
            index += 1
        elif command == "V":
            points.append((points[-1][0], float(tokens[index])))
            index += 1
        elif command == "A":
            rx, ry, rotation, large, sweep, x, y = (
                float(token) for token in tokens[index : index + 7]
            )
            points += _arc(points[-1], rx, ry, rotation, bool(large), bool(sweep), (x, y))
            index += 7
        elif command == "Z":
            subpaths.append((points, True))
            points = []
        else:
            raise RasterError(f"the viewport rasterizer met a stray number in {d!r}")
    if len(points) > 1:
        subpaths.append((points, False))
    return subpaths


def _dashes(points: list[Point], pattern: list[float]) -> list[list[Point]]:
    """The drawn pieces of a polyline under an SVG dash pattern (on, off, on, ...)."""
    pieces: list[list[Point]] = []
    phase, remaining, drawing = 0, pattern[0], True
    current: list[Point] = [points[0]]
    for (x0, y0), (x1, y1) in zip(points, points[1:], strict=False):
        length = math.hypot(x1 - x0, y1 - y0)
        travelled = 0.0
        while length - travelled > remaining:
            travelled += remaining
            point = (x0 + (x1 - x0) * travelled / length, y0 + (y1 - y0) * travelled / length)
            if drawing:
                pieces.append([*current, point])
            current = [point]
            drawing = not drawing
            phase = (phase + 1) % len(pattern)
            remaining = pattern[phase]
        remaining -= length - travelled
        current.append((x1, y1))
    if drawing and len(current) > 1:
        pieces.append(current)
    return pieces


def _number(element: ElementTree.Element, name: str) -> float:
    return float(element.get(name, "0"))


def svg_to_png(svg: bytes) -> bytes:
    """The PNG of one viewport SVG written by :func:`anvilate.geometry.render_viewport`."""
    root = ElementTree.fromstring(svg)
    width, height = int(float(root.get("width", "0"))), int(float(root.get("height", "0")))
    if width <= 0 or height <= 0:
        raise RasterError("the viewport SVG states no positive width and height")
    canvas = _Canvas(width, height)
    for element in root:
        tag = element.tag.removeprefix(_SVG)
        if tag not in _DRAWN:
            raise RasterError(f"the viewport rasterizer does not draw <{tag}>")
        if tag == "rect":
            x, y = _number(element, "x"), _number(element, "y")
            right, bottom = x + _number(element, "width"), y + _number(element, "height")
            shapes = [([(x, y), (right, y), (right, bottom), (x, bottom)], True)]
        elif tag == "polygon":
            values = [float(v) for v in _NUMBER.findall(element.get("points", ""))]
            shapes = [(list(zip(values[::2], values[1::2], strict=True)), True)]
        elif tag == "line":
            ends = [(_number(element, "x1"), _number(element, "y1"))]
            ends.append((_number(element, "x2"), _number(element, "y2")))
            shapes = [(ends, False)]
        elif tag in ("circle", "ellipse"):
            rx = _number(element, "r" if tag == "circle" else "rx")
            ry = _number(element, "r" if tag == "circle" else "ry")
            shapes = [(_ellipse(_number(element, "cx"), _number(element, "cy"), rx, ry), True)]
        else:
            shapes = _path(element.get("d", ""))
        fill = _colour(element.get("fill")) if tag != "line" else None
        stroke = _colour(element.get("stroke"))
        width = float(element.get("stroke-width", "1"))
        dash = [float(v) for v in _NUMBER.findall(element.get("stroke-dasharray", ""))]
        if dash and (len(dash) % 2 or any(v <= 0 for v in dash)):
            raise RasterError(
                f"the viewport rasterizer reads even, positive dash arrays; got {dash}"
            )
        for points, closed in shapes:
            if fill is not None and closed:
                canvas.fill(points, fill)
            if stroke is None:
                continue
            if not dash:
                canvas.stroke(points, stroke, width, closed=closed)
                continue
            # A dashed edge is a hidden one; drawn solid it would read as visible.
            for piece in _dashes(points + points[:1] if closed else points, dash):
                canvas.stroke(piece, stroke, width, closed=False)
    return canvas.png()
