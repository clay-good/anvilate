"""Draw any built solid: hidden-line views from the solid itself, as SVG.

The first renderer was written per pattern. It projected each pattern's known corners and
said of itself that it "refuses to masquerade as a general hidden-line renderer", which meant
every new part needed new drawing code. This module draws from the solid: the kernel's
hidden-line removal gives the visible and hidden edges exactly, the tessellated faces give a
shaded fill, and a pattern contributes nothing but its solid and its face tags.

What comes out is the small SVG vocabulary :mod:`anvilate.raster` reads (``rect``,
``polygon``, and ``path`` of ``M``/``L`` segments), so the SVG and the PNG are one drawing.
Text is drawn as strokes from a built-in font for the same reason: no font file, no
renderer-dependent metrics, the same pixels everywhere. It is a check picture, not a
manufacturing drawing, and a dimensioned view says so on its face.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from ._models import each_one

__all__ = [
    "ASSEMBLY_PALETTES",
    "ENVELOPE_PALETTE",
    "render_assembly",
    "VIEWS",
    "render_overview",
    "render_view",
]

VIEWS = ("iso", "front", "top", "right")

# Camera direction (from the part toward the eye) and the up vector, per view. Z is up, as
# in the STEP file; "front" looks along +Y, "right" along -X, "top" straight down.
_CAMERAS: Mapping[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {
    "iso": ((1.0, -1.0, 0.8), (0.0, 0.0, 1.0)),
    "front": ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
    "top": ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
    "right": ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
}

_INK = "#0f172a"
_HIDDEN = "#64748b"
_TONES = ("#93c5fd", "#bfdbfe", "#eff6ff")  # darkest to lightest face
_LIGHT = (0.35, -0.5, 0.8)
_CHORD_MM_FRACTION = 0.004  # curve discretisation, as a fraction of the part's size

Vec = tuple[float, float, float]
Point = tuple[float, float]


def _sub(a: Vec, b: Vec) -> Vec:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a: Vec, b: Vec) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec, b: Vec) -> Vec:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(a: Vec) -> Vec:
    size = math.sqrt(_dot(a, a)) or 1.0
    return (a[0] / size, a[1] / size, a[2] / size)


class _Camera:
    """An orthographic camera looking at the middle of the part."""

    def __init__(self, shape: Any, view: str) -> None:
        box = shape.bounding_box()
        self.centre: Vec = (
            (box.min.X + box.max.X) / 2,
            (box.min.Y + box.max.Y) / 2,
            (box.min.Z + box.max.Z) / 2,
        )
        self.size = max(box.size.X, box.size.Y, box.size.Z, 1e-9)
        toward_eye, up = _CAMERAS[view]
        self.toward_eye = _unit(toward_eye)
        self.right = _unit(_cross(up, self.toward_eye))
        self.up = _cross(self.toward_eye, self.right)
        distance = self.size * 10
        self.eye: Vec = (
            self.centre[0] + self.toward_eye[0] * distance,
            self.centre[1] + self.toward_eye[1] * distance,
            self.centre[2] + self.toward_eye[2] * distance,
        )
        self.declared_up = up

    def flat(self, point: Vec) -> Point:
        relative = _sub(point, self.centre)
        return (_dot(relative, self.right), _dot(relative, self.up))

    def depth(self, point: Vec) -> float:
        return _dot(_sub(point, self.centre), self.toward_eye)


def _edge_points(edge: Any, chord: float) -> list[Point]:
    """One projected edge as a polyline; a straight edge is its two ends."""
    if str(edge.geom_type).endswith("LINE"):
        ends = (edge.position_at(0), edge.position_at(1))
        return [(p.X, p.Y) for p in ends]
    steps = max(8, min(96, math.ceil(edge.length / chord)))
    return [(p.X, p.Y) for p in (edge.position_at(k / steps) for k in range(steps + 1))]


def _hidden_lines(shape: Any, camera: _Camera) -> tuple[list[list[Point]], list[list[Point]]]:
    visible, hidden = shape.project_to_viewport(
        camera.eye, viewport_up=camera.declared_up, look_at=camera.centre
    )
    chord = camera.size * _CHORD_MM_FRACTION
    return (
        [_edge_points(edge, chord) for edge in visible],
        [_edge_points(edge, chord) for edge in hidden],
    )


def _faces(
    shape: Any,
    tags: Mapping[str, Sequence[Any]],
    camera: _Camera,
    palettes: Mapping[str, tuple[str, str, str]] | None = None,
) -> list[tuple[float, str, str, list[Point]]]:
    """Front-facing triangles as (depth, tone, tag, points), farthest first.

    ``palettes`` gives a tag its own three tones, darkest to lightest, so the bodies of a
    combination can be told apart; a face with no palette takes the single part's.
    """
    tag_of = {id(face): tag for tag, faces in tags.items() for face in faces}
    by_hash = {hash(face): tag for tag, faces in tags.items() for face in faces}
    light = _unit(_LIGHT)
    drawn = []
    for face in shape.faces():
        tag = tag_of.get(id(face)) or by_hash.get(hash(face), "")
        points, triangles = face.tessellate(camera.size * 0.002, 0.3)
        vertices = [(p.X, p.Y, p.Z) for p in points]
        for a, b, c in triangles:
            normal = _unit(_cross(_sub(vertices[b], vertices[a]), _sub(vertices[c], vertices[a])))
            if _dot(normal, camera.toward_eye) <= 1e-9:
                continue  # facing away: a closed solid hides it behind a front face
            brightness = max(0.0, _dot(normal, light))
            tones = (palettes or {}).get(tag, _TONES)
            tone = tones[2] if brightness > 0.7 else tones[1] if brightness > 0.25 else tones[0]
            corners = [vertices[a], vertices[b], vertices[c]]
            depth = sum(camera.depth(p) for p in corners) / 3
            drawn.append((depth, tone, tag, [camera.flat(p) for p in corners]))
    drawn.sort(key=lambda item: item[0])
    return drawn


class _Sheet:
    """Model-space geometry fitted into a pixel rectangle, y flipped for the screen."""

    def __init__(self, points: Sequence[Point], x: float, y: float, w: float, h: float) -> None:
        xs = [p[0] for p in points] or [0.0]
        ys = [p[1] for p in points] or [0.0]
        self.min_x, self.max_y = min(xs), max(ys)
        span_x, span_y = max(xs) - min(xs), max(ys) - min(ys)
        self.scale = min(w / (span_x or 1e-9), h / (span_y or 1e-9))
        self.x = x + (w - span_x * self.scale) / 2
        self.y = y + (h - span_y * self.scale) / 2

    def at(self, point: Point) -> Point:
        return (
            self.x + (point[0] - self.min_x) * self.scale,
            self.y + (self.max_y - point[1]) * self.scale,
        )


def _polyline(points: Sequence[Point]) -> str:
    return "M " + " L ".join(f"{x:.2f} {y:.2f}" for x, y in points)


# --- a stroke font, so text is the same pixels in SVG and PNG --------------------------
#
# Each glyph is polylines on a 4-wide, 6-tall grid (y up). Enough for dimension values, part
# names, materials and verdicts; a character with no glyph is drawn as a small box rather
# than dropped, so a missing glyph is visible.
_GLYPHS: Mapping[str, tuple[tuple[tuple[float, float], ...], ...]] = {
    "0": (((1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5), (4, 1), (3, 0), (1, 0)),),
    "1": (((1, 5), (2, 6), (2, 0)), ((1, 0), (3, 0))),
    "2": (((0, 5), (1, 6), (3, 6), (4, 5), (4, 4), (0, 0), (4, 0)),),
    "3": (((0, 6), (4, 6), (2, 3.5), (4, 2), (4, 1), (3, 0), (1, 0), (0, 1)),),
    "4": (((3, 0), (3, 6), (0, 2), (4, 2)),),
    "5": (((4, 6), (0, 6), (0, 3.5), (3, 3.5), (4, 2.5), (4, 1), (3, 0), (0, 0)),),
    "6": (
        ((4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (3, 0), (4, 1), (4, 2), (3, 3), (0, 3)),
    ),
    "7": (((0, 6), (4, 6), (1.5, 0)),),
    "8": (
        (
            (1, 3),
            (0, 4),
            (0, 5),
            (1, 6),
            (3, 6),
            (4, 5),
            (4, 4),
            (3, 3),
            (1, 3),
            (0, 2),
            (0, 1),
            (1, 0),
            (3, 0),
            (4, 1),
            (4, 2),
            (3, 3),
        ),
    ),
    "9": (
        ((0, 1), (1, 0), (3, 0), (4, 1), (4, 5), (3, 6), (1, 6), (0, 5), (0, 4), (1, 3), (4, 3)),
    ),
    ".": (((1.6, 0), (2.4, 0), (2.4, 0.8), (1.6, 0.8), (1.6, 0)),),
    ",": (((2, 0.8), (2, 0), (1.2, -1)),),
    "-": (((0.5, 3), (3.5, 3)),),
    "+": (((0.5, 3), (3.5, 3)), ((2, 1.5), (2, 4.5))),
    "/": (((0, 0), (4, 6)),),
    ":": (((2, 1), (2, 1.6)), ((2, 3.6), (2, 4.2))),
    "(": (((3, 6), (1.5, 4.5), (1.5, 1.5), (3, 0)),),
    ")": (((1, 6), (2.5, 4.5), (2.5, 1.5), (1, 0)),),
    "_": (((0, 0), (4, 0)),),
    "x": (((0, 0), (4, 4)), ((0, 4), (4, 0))),
    "°": (((1, 4), (3, 4), (3, 6), (1, 6), (1, 4)),),
    "Ø": (((0, 0), (4, 0), (4, 6), (0, 6), (0, 0)), ((-0.5, -0.5), (4.5, 6.5))),
    "A": (((0, 0), (2, 6), (4, 0)), ((0.8, 2.4), (3.2, 2.4))),
    "B": (
        ((0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)),
        ((3, 3), (4, 2), (4, 1), (3, 0), (0, 0)),
    ),
    "C": (((4, 1), (3, 0), (1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5)),),
    "D": (((0, 0), (0, 6), (3, 6), (4, 5), (4, 1), (3, 0), (0, 0)),),
    "E": (((4, 0), (0, 0), (0, 6), (4, 6)), ((0, 3), (3, 3))),
    "F": (((0, 0), (0, 6), (4, 6)), ((0, 3), (3, 3))),
    "G": (((4, 5), (3, 6), (1, 6), (0, 5), (0, 1), (1, 0), (4, 0), (4, 3), (2, 3)),),
    "H": (((0, 0), (0, 6)), ((4, 0), (4, 6)), ((0, 3), (4, 3))),
    "I": (((1, 0), (3, 0)), ((2, 0), (2, 6)), ((1, 6), (3, 6))),
    "J": (((0, 1), (1, 0), (3, 0), (4, 1), (4, 6)),),
    "K": (((0, 0), (0, 6)), ((4, 6), (0, 2.5)), ((1.4, 3.7), (4, 0))),
    "L": (((0, 6), (0, 0), (4, 0)),),
    "M": (((0, 0), (0, 6), (2, 3), (4, 6), (4, 0)),),
    "N": (((0, 0), (0, 6), (4, 0), (4, 6)),),
    "O": (
        ((1.2, 0), (0, 1.2), (0, 4.8), (1.2, 6), (2.8, 6), (4, 4.8), (4, 1.2), (2.8, 0), (1.2, 0)),
    ),
    "P": (((0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)),),
    "Q": (
        ((1, 0), (0, 1), (0, 5), (1, 6), (3, 6), (4, 5), (4, 1), (3, 0), (1, 0)),
        ((2.5, 1.5), (4.3, -0.3)),
    ),
    "R": (((0, 0), (0, 6), (3, 6), (4, 5), (4, 4), (3, 3), (0, 3)), ((2, 3), (4, 0))),
    "S": (((4, 5), (3, 6), (1, 6), (0, 5), (0, 4), (4, 2), (4, 1), (3, 0), (1, 0), (0, 1)),),
    "T": (((0, 6), (4, 6)), ((2, 6), (2, 0))),
    "U": (((0, 6), (0, 1), (1, 0), (3, 0), (4, 1), (4, 6)),),
    "V": (((0, 6), (2, 0), (4, 6)),),
    "W": (((0, 6), (1, 0), (2, 3.5), (3, 0), (4, 6)),),
    "X": (((0, 0), (4, 6)), ((0, 6), (4, 0))),
    "Y": (((0, 6), (2, 3), (4, 6)), ((2, 3), (2, 0))),
    "Z": (((0, 6), (4, 6), (0, 0), (4, 0)),),
}


# How far a dimension line stands off the part, in pixels.
_DIMENSION_OFFSET = 26.0


def _text_width(text: str, height: float) -> float:
    """How wide ``text`` is drawn at ``height`` px."""
    unit = height / 6
    return len(text) * 5.6 * unit - 1.6 * unit


def _text(text: str, x: float, y: float, height: float, *, anchor: str = "start") -> str:
    """``text`` as one SVG path of strokes, its baseline at ``y``, ``height`` px tall."""
    unit = height / 6
    advance = 5.6 * unit
    width = _text_width(text, height)
    left = x - (width / 2 if anchor == "middle" else width if anchor == "end" else 0)
    segments = []
    for index, raw in enumerate(text):
        char = raw if raw in _GLYPHS else raw.upper()
        if char == " ":
            continue
        strokes = _GLYPHS.get(char, (((0, 0), (4, 0), (4, 6), (0, 6), (0, 0)),))
        for stroke in strokes:
            segments.append(
                _polyline(
                    [(left + index * advance + px * unit, y - py * unit) for px, py in stroke]
                )
            )
    return (
        f'<path d="{" ".join(segments)}" fill="none" stroke="{_INK}" '
        f'stroke-width="{max(1.0, height / 9):.2f}"/>'
    )


def _dimension(
    sheet: _Sheet, start: Point, end: Point, label: str, offset: float, height: float
) -> list[str]:
    """A dimension line between two model points, pushed ``offset`` px off the part."""
    (x0, y0), (x1, y1) = sheet.at(start), sheet.at(end)
    length = math.hypot(x1 - x0, y1 - y0) or 1.0
    nx, ny = -(y1 - y0) / length * offset, (x1 - x0) / length * offset
    a, b = (x0 + nx, y0 + ny), (x1 + nx, y1 + ny)
    tick = 4.0
    ux, uy = (x1 - x0) / length, (y1 - y0) / length

    def cross_tick(at: Point) -> str:
        return _polyline(
            [(at[0] - uy * tick, at[1] + ux * tick), (at[0] + uy * tick, at[1] - ux * tick)]
        )

    strokes = [
        _polyline([(x0, y0), (a[0] + nx * 0.2, a[1] + ny * 0.2)]),
        _polyline([(x1, y1), (b[0] + nx * 0.2, b[1] + ny * 0.2)]),
        _polyline([a, b]),
        cross_tick(a),
        cross_tick(b),
    ]
    parts = [f'<path d="{" ".join(strokes)}" fill="none" stroke="{_HIDDEN}"/>']
    mid = ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    if abs(ux) >= abs(uy):  # a horizontal run: the label sits beyond the line, off the part
        below = ny > 0
        parts.append(
            _text(label, mid[0], mid[1] + (height + 4 if below else -4), height, anchor="middle")
        )
    else:  # a vertical run: the label sits beside the line
        left = nx < 0
        parts.append(
            _text(label, mid[0] + (-6 if left else 6), mid[1] + height / 2, height,
                  anchor="end" if left else "start")
        )  # fmt: skip
    return parts


def _view_markup(
    shape: Any,
    tags: Mapping[str, Sequence[Any]],
    view: str,
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    dimensions: bool,
    unit: str = "mm",
    palettes: Mapping[str, tuple[str, str, str]] | None = None,
    marks: Sequence[tuple[str, str]] = (),
) -> list[str]:
    camera = _Camera(shape, view)
    visible, hidden = _hidden_lines(shape, camera)
    faces = _faces(shape, tags, camera, palettes)
    outline = [p for line in visible + hidden for p in line] + [p for f in faces for p in f[3]]
    margin = 0.2 if dimensions else 0.08
    left = right = w * margin
    if dimensions:
        xs, ys = [p[0] for p in outline], [p[1] for p in outline]
        factor = 1 / 25.4 if unit == "in" else 1.0
        height = max(9.0, min(13.0, w / 48))
        width_mm, height_mm = max(xs) - min(xs), max(ys) - min(ys)
        across, upward = f"{width_mm * factor:.4g} {unit}", f"{height_mm * factor:.4g} {unit}"
        # The upright dimension's label stands to the right of the part, so the part gives
        # up the room it needs: on a long thin part "200 MM" ran off the view as "200 M".
        right = max(right, _DIMENSION_OFFSET + 10 + _text_width(upward, height))
    sheet = _Sheet(outline, x + left, y + h * margin, w - left - right, h * (1 - 2 * margin))
    out = []
    for _depth, tone, tag, corners in faces:
        points = " ".join(f"{px:.2f},{py:.2f}" for px, py in (sheet.at(c) for c in corners))
        label = f' data-face="{tag}"' if tag else ""
        out.append(f'<polygon{label} points="{points}" fill="{tone}" stroke="{tone}"/>')
    if hidden:
        dashed = " ".join(_polyline([sheet.at(p) for p in line]) for line in hidden)
        out.append(
            f'<path data-edges="hidden" d="{dashed}" fill="none" stroke="{_HIDDEN}" '
            'stroke-dasharray="4 3"/>'
        )
    solid = " ".join(_polyline([sheet.at(p) for p in line]) for line in visible)
    out.append(
        f'<path data-edges="visible" d="{solid}" fill="none" stroke="{_INK}" stroke-width="1.5"/>'
    )
    if dimensions:
        out += _dimension(
            sheet, (min(xs), min(ys)), (max(xs), min(ys)), across, _DIMENSION_OFFSET, height
        )
        out += _dimension(
            sheet, (max(xs), min(ys)), (max(xs), max(ys)), upward, _DIMENSION_OFFSET, height
        )
    size = max(8.0, min(11.0, w / 40))
    drawn: list[Point] = []
    for label, tag in marks:
        # On the body's own visible surface: the middle of the largest of its triangles
        # that face the eye. The middle of a body's box is in the bore of a ring, and two
        # rings on one axis had their balloons in the same empty place.
        mine = [(depth, corners) for depth, _tone, face_tag, corners in faces if face_tag == tag]
        if not mine:
            continue
        # Among the quarter of them nearest the eye, so the choice is a face that is seen
        # and not a bolt's shank inside its hole.
        nearest, farthest = max(d for d, _c in mine), min(d for d, _c in mine)
        front = [c for d, c in mine if d >= nearest - 0.25 * (nearest - farthest)]
        widest = max(front, key=_triangle_area)
        centre = sheet.at(
            (sum(point[0] for point in widest) / 3, sum(point[1] for point in widest) / 3)
        )
        # Bodies stacked in one hole would have their balloons on top of each other, so a
        # balloon that lands on an earlier one steps to the right of it.
        while any(math.dist(centre, other) < size * 2.6 for other in drawn):
            centre = (centre[0] + size * 2.6, centre[1])
        drawn.append(centre)
        out += _balloon(label, centre, size)
    return out


def _triangle_area(corners: Sequence[Point]) -> float:
    (ax, ay), (bx, by), (cx, cy) = corners
    return abs((bx - ax) * (cy - ay) - (cx - ax) * (by - ay)) / 2


def _balloon(label: str, centre: Point, height: float) -> list[str]:
    """A numbered balloon: a white disc with a ring round it and the number inside."""
    radius = height * (0.95 if len(label) < 2 else 1.25)
    ring = [
        (
            centre[0] + radius * math.cos(2 * math.pi * step / 20),
            centre[1] + radius * math.sin(2 * math.pi * step / 20),
        )
        for step in range(21)
    ]
    points = " ".join(f"{x:.2f},{y:.2f}" for x, y in ring[:-1])
    return [
        f'<polygon data-balloon="{label}" points="{points}" fill="#ffffff" stroke="#ffffff"/>',
        f'<path d="{_polyline(ring)}" fill="none" stroke="{_INK}"/>',
        _text(label, centre[0], centre[1] + height * 0.42, height * 0.85, anchor="middle"),
    ]


def _document(width: int, height: int, label: str, body: Sequence[str]) -> bytes:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{label}">',
        f'<rect width="{width}" height="{height}" fill="#ffffff"/>',
        *body,
        "</svg>",
    ]
    return ("\n".join(lines) + "\n").encode("utf-8")


def _plain(text: str) -> str:
    return "".join(c if c.isalnum() or c in " .-_" else " " for c in text)


def render_view(
    shape: Any,
    tags: Mapping[str, Sequence[Any]],
    *,
    name: str,
    view: str,
    width_px: int,
    dimensions: bool = False,
    unit: str = "mm",
) -> tuple[bytes, int]:
    """One view of ``shape`` as SVG bytes, and its height in pixels.

    With ``dimensions`` the view carries the overall width and height of what it shows,
    measured from the projected solid, and a line saying it is a check picture.
    """
    height_px = max(64, round(width_px * 0.75))
    body = _view_markup(
        shape, tags, view, 0, 0, width_px, height_px, dimensions=dimensions, unit=unit
    )
    if dimensions:
        size = max(8.0, min(11.0, width_px / 60))
        body.append(_text("CHECK PICTURE - NOT A MANUFACTURING DRAWING", 8, height_px - 8, size))
    label = f"{_plain(name)} {view} viewport"
    return _document(width_px, height_px, label, body), height_px


def render_overview(
    shape: Any,
    tags: Mapping[str, Sequence[Any]],
    *,
    name: str,
    lines: Sequence[str],
    width_px: int,
    unit: str = "mm",
) -> tuple[bytes, int]:
    """The four views on one image with a title block: one picture that answers "what is it?".

    ``lines`` are the title block's rows after the name: overall size, material, verdict.
    """
    # One string is a sequence of characters, and would be drawn one letter to a row.
    lines = each_one(lines, str, named="lines")
    height_px = max(64, round(width_px * 0.75))
    header = max(40.0, height_px * 0.12)
    cell_w, cell_h = width_px / 2, (height_px - header) / 2
    title = max(11.0, min(18.0, width_px / 50))
    body = [_text(_plain(name).upper(), 12, header * 0.45, title)]
    small = title * 0.72
    body.append(_text("   ".join(_plain(line).upper() for line in lines), 12, header * 0.85, small))
    for index, view in enumerate(VIEWS):
        x, y = (index % 2) * cell_w, header + (index // 2) * cell_h
        body += _view_markup(
            shape, tags, view, x, y, cell_w, cell_h, dimensions=view != "iso", unit=unit
        )
        body.append(_text(view.upper(), x + 8, y + small + 4, small))
    body.append(
        f'<path d="{_polyline([(0, header), (width_px, header)])} '
        f"{_polyline([(cell_w, header), (cell_w, height_px)])} "
        f'{_polyline([(0, header + cell_h), (width_px, header + cell_h)])}" '
        f'fill="none" stroke="{_HIDDEN}"/>'
    )
    return _document(width_px, height_px, f"{_plain(name)} overview", body), height_px


#: Three tones for each body of a combination, darkest to lightest, in the order the bodies
#: are numbered. The middle tones step in lightness as well as hue, so two neighbouring
#: parts stay apart on a greyscale print; the numbered balloons are what identify a part.
ASSEMBLY_PALETTES: tuple[tuple[str, str, str], ...] = (
    ("#93c5fd", "#bfdbfe", "#eff6ff"),
    ("#d97706", "#f59e0b", "#fcd34d"),
    ("#10b981", "#34d399", "#a7f3d0"),
    ("#7c3aed", "#a78bfa", "#ddd6fe"),
    ("#e11d48", "#f43f5e", "#fda4af"),
    ("#155e75", "#0e7490", "#06b6d4"),
)
#: Hardware envelopes are drawn in grey: where a fastener goes, not a designed part.
ENVELOPE_PALETTE = ("#94a3b8", "#cbd5e1", "#f1f5f9")


def render_assembly(
    bodies: Sequence[tuple[str, Any, bool]],
    *,
    name: str,
    lines: Sequence[str],
    parts_list: Sequence[str],
    marks: Sequence[tuple[str, int]],
    width_px: int,
    unit: str = "mm",
) -> tuple[bytes, int]:
    """A combination on one image: four views, each body in its own tone, and a parts list.

    ``bodies`` are ``(label, solid, is_envelope)`` in the order they are numbered.
    ``marks`` put a numbered balloon on a body: ``(number, index into bodies)``.
    ``parts_list`` are the rows printed under the views, one per line of the bill of
    materials, so the numbers in the picture can be read off beside it.
    """
    from build123d import Compound

    lines = each_one(lines, str, named="lines")
    parts_list = each_one(parts_list, str, named="parts_list")
    shape = Compound(children=[solid for _label, solid, _envelope in bodies])
    tags: dict[str, list[Any]] = {}
    palettes: dict[str, tuple[str, str, str]] = {}
    designed = 0
    for index, (_label, solid, envelope) in enumerate(bodies):
        tags[str(index)] = list(solid.faces())
        if envelope:
            palettes[str(index)] = ENVELOPE_PALETTE
        else:
            palettes[str(index)] = ASSEMBLY_PALETTES[designed % len(ASSEMBLY_PALETTES)]
            designed += 1
    balloons = [(label, str(index)) for label, index in marks]
    views_px = max(64, round(width_px * 0.75))
    header = max(40.0, views_px * 0.12)
    cell_w, cell_h = width_px / 2, (views_px - header) / 2
    title = max(11.0, min(18.0, width_px / 50))
    small = title * 0.72
    row = small * 1.7
    height_px = round(views_px + row * (len(parts_list) + 1))
    body = [_text(_plain(name).upper(), 12, header * 0.45, title)]
    body.append(_text("   ".join(_plain(line).upper() for line in lines), 12, header * 0.85, small))
    for index, view in enumerate(VIEWS):
        x, y = (index % 2) * cell_w, header + (index // 2) * cell_h
        body += _view_markup(
            shape,
            tags,
            view,
            x,
            y,
            cell_w,
            cell_h,
            dimensions=view != "iso",
            unit=unit,
            palettes=palettes,
            marks=balloons if view == "iso" else (),
        )
        body.append(_text(view.upper(), x + 8, y + small + 4, small))
    body.append(
        f'<path d="{_polyline([(0, header), (width_px, header)])} '
        f"{_polyline([(cell_w, header), (cell_w, views_px)])} "
        f"{_polyline([(0, header + cell_h), (width_px, header + cell_h)])} "
        f'{_polyline([(0, views_px), (width_px, views_px)])}" '
        f'fill="none" stroke="{_HIDDEN}"/>'
    )
    for number, text in enumerate(parts_list):
        body.append(_text(_plain(text).upper(), 12, views_px + row * (number + 1), small))
    return _document(width_px, height_px, f"{_plain(name)} assembly", body), height_px
