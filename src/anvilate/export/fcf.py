"""Feature control frame drawing geometry, from the semantic GD&T model.

The third consumer of :mod:`anvilate.gdt`. One declaration — a
:class:`~anvilate.gdt.FeatureControlFrame` — renders as text (``frame.render()``),
crosses into quality interchange (:func:`~anvilate.export.qif.qif_characteristic_mapping`),
and is drawn here as the boxed, compartmented frame a drawing carries.

**Every geometric symbol is drawn as geometry, not typeset as a character.** A ⌖ or an Ⓜ
written into a DXF as text renders correctly only where the viewer has a font carrying
the glyph — and where it does not, the callout silently loses its modifier or shows a
tofu box, which is the drawing saying something other than what the model declares.
Lines and arcs render the same everywhere. Only digits, the decimal point and datum
letters are left as text, and the character set is closed so that nothing else can reach
the layout allowance below.

**The symbol constructions are read out of a published symbol chart, not recalled.**
Every proportion below comes from the Genium *Drafting Manual* Section 6.1,
"Dimensioning and Tolerancing Symbols" (February 1997, based on ASME Y14.5M-1994), which
dimensions each symbol as a multiple of the predominant character height ``h``. Three
would have been wrong from memory: symmetry is three horizontal lines of 2h, 1.2h and 2h
at 0.5h spacing (not an equals sign), the cylindricity tangent lines stand at 60° rather
than vertical, and the runout arrowheads are 0.8h long by 0.6h wide on a 45° shaft.

Geometry is returned as primitives in millimetres with the frame's lower-left corner at
``origin``; :func:`~anvilate.export.dxf.export_feature_control_frame_dxf` is what writes
them to a file, and any other renderer can consume the same primitives.
"""

from __future__ import annotations

from math import cos, radians, sin, tan

from pydantic import BaseModel, ConfigDict

from ..gdt import (
    Characteristic,
    FeatureControlFrame,
    FrameModifier,
    MaterialCondition,
)
from ..units import Quantity

__all__ = [
    "DEFAULT_TEXT_HEIGHT",
    "Polyline",
    "Circle",
    "Arc",
    "Label",
    "FrameDrawing",
    "characteristic_symbol",
    "frame_drawing",
]


class Polyline(BaseModel):
    """An open or closed run of straight segments, in millimetres."""

    model_config = ConfigDict(frozen=True)

    points: tuple[tuple[float, float], ...]
    closed: bool = False


class Circle(BaseModel):
    """A full circle, in millimetres."""

    model_config = ConfigDict(frozen=True)

    center: tuple[float, float]
    radius: float


class Arc(BaseModel):
    """A counter-clockwise arc from ``start_angle`` to ``end_angle`` (degrees)."""

    model_config = ConfigDict(frozen=True)

    center: tuple[float, float]
    radius: float
    start_angle: float
    end_angle: float


class Label(BaseModel):
    """A text run, positioned by the centre of its bounding box."""

    model_config = ConfigDict(frozen=True)

    text: str
    center: tuple[float, float]
    height: float


Stroke = Polyline | Circle | Arc


class FrameDrawing(BaseModel):
    """A feature control frame as drawable primitives.

    ``strokes`` are the frame box, its compartment dividers and every geometric symbol;
    ``labels`` are the numeric value and the datum letters. ``compartment_edges`` are the
    x positions of the box's left edge, each divider and its right edge, so a caller can
    place a datum feature symbol or a leader against a known compartment.
    """

    model_config = ConfigDict(frozen=True)

    strokes: tuple[Stroke, ...]
    labels: tuple[Label, ...]
    origin: tuple[float, float]
    width: float
    height: float
    compartment_edges: tuple[float, ...]


# --- Symbol constructions, in units of the character height h -------------------------
#
# Each builder returns strokes in a local frame; `_centered` then shifts the whole symbol
# so its bounding box is centred on the origin. Centring generically rather than by hand
# per symbol is what keeps a symbol's proportions independent of where it was drawn.

_TAN_60 = tan(radians(60.0))
_TAN_30 = tan(radians(30.0))
_SIN_45 = sin(radians(45.0))
_COS_45 = cos(radians(45.0))


def _line(x1: float, y1: float, x2: float, y2: float) -> Polyline:
    return Polyline(points=((x1, y1), (x2, y2)))


def _straightness() -> list[Stroke]:
    # Figure 19: a straight line, 2h long.
    return [_line(-1.0, 0.0, 1.0, 0.0)]


def _flatness() -> list[Stroke]:
    # Figure 20: a parallelogram 1.5h wide and h tall, sides at 60°.
    run = 0.5 / _TAN_60  # horizontal run of each slanted side over the half height
    return [
        Polyline(
            points=(
                (-0.75, -0.5),
                (0.75 - 2 * run, -0.5),
                (0.75, 0.5),
                (-0.75 + 2 * run, 0.5),
            ),
            closed=True,
        )
    ]


def _circularity() -> list[Stroke]:
    # Figure 21: a circle 1.5h in diameter.
    return [Circle(center=(0.0, 0.0), radius=0.75)]


def _cylindricity() -> list[Stroke]:
    # Figure 22: a circle h in diameter with two lines tangent to it at 60°, the pair
    # standing 1.5h tall. The tangent point sits half a diameter out along the normal.
    radius = 0.5
    normal = (sin(radians(60.0)), -cos(radians(60.0)))
    tx, ty = radius * normal[0], radius * normal[1]
    strokes: list[Stroke] = [Circle(center=(0.0, 0.0), radius=radius)]
    for sign in (1.0, -1.0):
        px, py = sign * tx, sign * ty
        # Walk the tangent line to the symbol's full height, 0.75h either side of centre.
        x_low = px + (-0.75 - py) / _TAN_60
        x_high = px + (0.75 - py) / _TAN_60
        strokes.append(_line(x_low, -0.75, x_high, 0.75))
    return strokes


def _line_profile_arc() -> Arc:
    # Figure 29: an arc open at the bottom — 2h across and h tall, so a semicircle of
    # radius h whose diameter is the open side.
    return Arc(center=(0.0, -0.5), radius=1.0, start_angle=0.0, end_angle=180.0)


def _profile_of_a_line() -> list[Stroke]:
    return [_line_profile_arc()]


def _profile_of_a_surface() -> list[Stroke]:
    # Figure 30: the line-profile arc closed by a straight line across the bottom.
    return [_line_profile_arc(), _line(-1.0, -0.5, 1.0, -0.5)]


def _angularity() -> list[Stroke]:
    # Figure 25: two lines forming a 30° angle, the pair 1.5h tall.
    base = 1.5 / _TAN_30
    return [
        Polyline(points=((base, 0.75), (0.0, -0.75), (base, -0.75))),
    ]


def _perpendicularity() -> list[Stroke]:
    # Figure 24: a vertical line 1.5h tall standing on a horizontal line 2h long.
    return [_line(0.0, 0.75, 0.0, -0.75), _line(-1.0, -0.75, 1.0, -0.75)]


def _parallelism() -> list[Stroke]:
    # Figure 23: two parallel lines at 60°, 1.5h tall, 0.6h apart measured horizontally.
    run = 1.5 / _TAN_60
    return [
        _line(0.0, -0.75, run, 0.75),
        _line(0.6, -0.75, 0.6 + run, 0.75),
    ]


def _position() -> list[Stroke]:
    # Figure 26: a circle h in diameter with a horizontal and a vertical line 1.5h long
    # drawn through it.
    return [
        Circle(center=(0.0, 0.0), radius=0.5),
        _line(-0.75, 0.0, 0.75, 0.0),
        _line(0.0, -0.75, 0.0, 0.75),
    ]


def _concentricity() -> list[Stroke]:
    # Figure 27: two concentric circles, 1.5h and h in diameter.
    return [
        Circle(center=(0.0, 0.0), radius=0.75),
        Circle(center=(0.0, 0.0), radius=0.5),
    ]


def _symmetry() -> list[Stroke]:
    # Figure 28: three horizontal lines — 2h, 1.2h and 2h — spaced 0.5h apart. Not an
    # equals sign, and the middle line is the short one.
    return [
        _line(-1.0, 0.5, 1.0, 0.5),
        _line(-0.6, 0.0, 0.6, 0.0),
        _line(-1.0, -0.5, 1.0, -0.5),
    ]


def _runout_arrow(x_offset: float) -> list[Stroke]:
    """One 45° runout arrow, 1.5h tall, with a 0.8h × 0.6h head at the top."""
    length = 1.5 / _SIN_45
    tip = (x_offset + 0.5 * length * _COS_45, 0.75)
    tail = (x_offset - 0.5 * length * _COS_45, -0.75)
    back = (tip[0] - 0.8 * _COS_45, tip[1] - 0.8 * _SIN_45)
    perp = (-_SIN_45, _COS_45)
    corner_a = (back[0] + 0.3 * perp[0], back[1] + 0.3 * perp[1])
    corner_b = (back[0] - 0.3 * perp[0], back[1] - 0.3 * perp[1])
    return [
        Polyline(points=(tail, tip)),
        Polyline(points=(tip, corner_a, corner_b), closed=True),
    ]


def _circular_runout() -> list[Stroke]:
    # Figure 31: a single arrow. The head may be filled or open; it is drawn open, which
    # the standard permits and a stroke renderer can reproduce exactly.
    return _runout_arrow(0.0)


def _total_runout() -> list[Stroke]:
    # Figure 32: two arrows 1.1h apart, joined by a horizontal line at their tails.
    strokes = _runout_arrow(-0.55) + _runout_arrow(0.55)
    tail_y = -0.75
    strokes.append(
        _line(
            -0.55 - 0.5 * (1.5 / _SIN_45) * _COS_45,
            tail_y,
            0.55 - 0.5 * (1.5 / _SIN_45) * _COS_45,
            tail_y,
        )
    )
    return strokes


_SYMBOL_BUILDERS = {
    Characteristic.STRAIGHTNESS: _straightness,
    Characteristic.FLATNESS: _flatness,
    Characteristic.CIRCULARITY: _circularity,
    Characteristic.CYLINDRICITY: _cylindricity,
    Characteristic.PROFILE_OF_A_LINE: _profile_of_a_line,
    Characteristic.PROFILE_OF_A_SURFACE: _profile_of_a_surface,
    Characteristic.ANGULARITY: _angularity,
    Characteristic.PERPENDICULARITY: _perpendicularity,
    Characteristic.PARALLELISM: _parallelism,
    Characteristic.POSITION: _position,
    Characteristic.CONCENTRICITY: _concentricity,
    Characteristic.SYMMETRY: _symmetry,
    Characteristic.CIRCULAR_RUNOUT: _circular_runout,
    Characteristic.TOTAL_RUNOUT: _total_runout,
}


# --- Bounding boxes and placement -----------------------------------------------------

_QUADRANT_ANGLES = (0.0, 90.0, 180.0, 270.0)


def _arc_extreme_angles(start: float, end: float) -> list[float]:
    """The quadrant angles swept by an arc going counter-clockwise from ``start``."""
    sweep = (end - start) % 360.0
    hit = []
    for angle in _QUADRANT_ANGLES:
        if (angle - start) % 360.0 <= sweep:
            hit.append(angle)
    return hit


def _stroke_bbox(stroke: Stroke) -> tuple[float, float, float, float]:
    if isinstance(stroke, Polyline):
        xs = [p[0] for p in stroke.points]
        ys = [p[1] for p in stroke.points]
        return min(xs), min(ys), max(xs), max(ys)
    if isinstance(stroke, Circle):
        cx, cy = stroke.center
        r = stroke.radius
        return cx - r, cy - r, cx + r, cy + r
    cx, cy = stroke.center
    r = stroke.radius
    xs = [cx + r * cos(radians(stroke.start_angle)), cx + r * cos(radians(stroke.end_angle))]
    ys = [cy + r * sin(radians(stroke.start_angle)), cy + r * sin(radians(stroke.end_angle))]
    for angle in _arc_extreme_angles(stroke.start_angle, stroke.end_angle):
        xs.append(cx + r * cos(radians(angle)))
        ys.append(cy + r * sin(radians(angle)))
    return min(xs), min(ys), max(xs), max(ys)


def _label_bbox(label: Label) -> tuple[float, float, float, float]:
    half_w = _text_width(label.text, label.height) / 2
    half_h = label.height / 2
    return (
        label.center[0] - half_w,
        label.center[1] - half_h,
        label.center[0] + half_w,
        label.center[1] + half_h,
    )


def _bbox(strokes: list[Stroke], labels: list[Label]) -> tuple[float, float, float, float]:
    boxes = [_stroke_bbox(s) for s in strokes] + [_label_bbox(t) for t in labels]
    if not boxes:
        raise ValueError("a glyph with no geometry has no bounding box")
    return (
        min(b[0] for b in boxes),
        min(b[1] for b in boxes),
        max(b[2] for b in boxes),
        max(b[3] for b in boxes),
    )


def _place_stroke(stroke: Stroke, scale: float, dx: float, dy: float) -> Stroke:
    if isinstance(stroke, Polyline):
        return Polyline(
            points=tuple((p[0] * scale + dx, p[1] * scale + dy) for p in stroke.points),
            closed=stroke.closed,
        )
    if isinstance(stroke, Circle):
        return Circle(
            center=(stroke.center[0] * scale + dx, stroke.center[1] * scale + dy),
            radius=stroke.radius * scale,
        )
    return Arc(
        center=(stroke.center[0] * scale + dx, stroke.center[1] * scale + dy),
        radius=stroke.radius * scale,
        start_angle=stroke.start_angle,
        end_angle=stroke.end_angle,
    )


def _place_label(label: Label, scale: float, dx: float, dy: float) -> Label:
    return Label(
        text=label.text,
        center=(label.center[0] * scale + dx, label.center[1] * scale + dy),
        height=label.height * scale,
    )


class _Glyph(BaseModel):
    """A symbol in units of h, its bounding box centred on the origin."""

    model_config = ConfigDict(frozen=True)

    strokes: tuple[Stroke, ...]
    labels: tuple[Label, ...]
    width: float
    height: float


def _glyph(strokes: list[Stroke], labels: list[Label] | None = None) -> _Glyph:
    labels = labels or []
    x0, y0, x1, y1 = _bbox(strokes, labels)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return _Glyph(
        strokes=tuple(_place_stroke(s, 1.0, -cx, -cy) for s in strokes),
        labels=tuple(_place_label(t, 1.0, -cx, -cy) for t in labels),
        width=x1 - x0,
        height=y1 - y0,
    )


# --- Text: a closed character set, and a layout allowance that is not a measurement ----

# Only these characters ever reach a Label: the digits and decimal point of a tolerance
# converted to millimetres, and the upper-case letters of a datum reference or a circled
# modifier. The set is closed deliberately — the width below is an allowance rather than
# a measured advance, so anything outside the set is refused rather than laid out on an
# assumption that was never checked for it.
_PERMITTED_CHARACTERS = frozenset("0123456789.ABCDEFGHIJKLMNOPQRSTUVWXYZ")

# Width allowance per character, as a multiple of the text height. The DXF standard
# stroke font advances a digit or an upper-case letter at roughly two thirds of its
# height; 0.75 leaves room for that plus inter-character spacing. It is an allowance and
# not a measurement: a viewer substituting a wider font can still overrun, which is why
# every text run is centred in its compartment rather than left-aligned against a
# divider it could then cross.
_ADVANCE_PER_CHARACTER = 0.75


def _text_width(text: str, height: float) -> float:
    return len(text) * _ADVANCE_PER_CHARACTER * height


def _check_characters(text: str) -> str:
    bad = sorted(set(text) - _PERMITTED_CHARACTERS)
    if bad:
        raise ValueError(
            f"a feature control frame is drawn with digits, the decimal point and "
            f"upper-case datum letters only; {bad} cannot be laid out because the frame's "
            f"width allowance was never checked against them"
        )
    return text


# --- Modifier glyphs ------------------------------------------------------------------


def _circled_letter(letter: str) -> _Glyph:
    """Figures 33-39: a letter 0.8h tall inside a circle 1.5h in diameter."""
    return _glyph(
        [Circle(center=(0.0, 0.0), radius=0.75)],
        [Label(text=_check_characters(letter), center=(0.0, 0.0), height=0.8)],
    )


def _diameter_glyph() -> _Glyph:
    """Figure 2: a circle h in diameter crossed by a line at 60°, 1.5h tall overall.

    The 1.5h is the symbol's height, not the slash's length — the slash runs 1.5h/sin 60°
    so that it reaches 0.75h above and below the centre. Reading it as the length draws a
    Ø barely taller than its own circle.
    """
    half = 0.75 / sin(radians(60.0))
    return _glyph(
        [
            Circle(center=(0.0, 0.0), radius=0.5),
            _line(
                -half * cos(radians(60.0)),
                -half * sin(radians(60.0)),
                half * cos(radians(60.0)),
                half * sin(radians(60.0)),
            ),
        ]
    )


def _statistical_glyph() -> _Glyph:
    """Figure 37: ``ST`` inside an elongated hexagon 2.5h by 1.5h with 60° ends."""
    run = 0.75 / _TAN_60
    return _glyph(
        [
            Polyline(
                points=(
                    (-1.25, 0.0),
                    (-1.25 + run, 0.75),
                    (1.25 - run, 0.75),
                    (1.25, 0.0),
                    (1.25 - run, -0.75),
                    (-1.25 + run, -0.75),
                ),
                closed=True,
            )
        ],
        [Label(text=_check_characters("ST"), center=(0.0, 0.0), height=0.8)],
    )


_MATERIAL_CONDITION_LETTER = {
    MaterialCondition.MMC: "M",
    MaterialCondition.LMC: "L",
}

_FRAME_MODIFIER_LETTER = {
    FrameModifier.PROJECTED: "P",
    FrameModifier.FREE_STATE: "F",
    FrameModifier.TANGENT_PLANE: "T",
}


def characteristic_symbol(
    characteristic: Characteristic,
    *,
    height: Quantity,
    center: tuple[float, float] = (0.0, 0.0),
) -> tuple[Stroke, ...]:
    """The geometric characteristic symbol as strokes, ``height`` being the character
    height ``h`` the symbol chart proportions everything against.

    The returned geometry is in millimetres with its bounding box centred on ``center``.
    A symbol is never as tall or as wide as ``h``: the chart sizes each one in its own
    multiples of h (1.5h tall for most, 2h wide for straightness and symmetry), so the
    bounding box is what a caller should measure rather than assume.
    """
    h = _mm_height(height)
    glyph = _glyph(list(_SYMBOL_BUILDERS[characteristic]()))
    return tuple(_place_stroke(s, h, center[0], center[1]) for s in glyph.strokes)


def _mm_height(height: Quantity) -> float:
    if not height.has_dimension("[length]"):
        raise ValueError(f"the character height must be a [length] quantity; got {height}")
    h = height.to("mm").magnitude
    if not h > 0:
        raise ValueError(f"the character height must be positive; got {height}")
    return h


# --- Frame layout ---------------------------------------------------------------------

# A feature control frame stands two character heights tall (Figure 41), each compartment
# padded half a character height either side of its content, with items inside a
# compartment separated by 0.3h.
_FRAME_HEIGHT = 2.0
# ISO 3098's usual drawing character height, and the default h everything is sized from.
DEFAULT_TEXT_HEIGHT = Quantity(magnitude=3.5, unit="mm")
_PADDING = 0.5
_ITEM_GAP = 0.3


def _tolerance_text(frame: FeatureControlFrame) -> str:
    """The tolerance value in millimetres, as the drawing carries it.

    Converted rather than carried in the frame's own unit: the DXF is written as a
    millimetre document, and a frame declared in inches whose number crossed unchanged
    would read as a tolerance 25.4 times tighter than the one declared.
    """
    value = frame.tolerance.to("mm").magnitude
    text = f"{value:g}"
    if "e" in text or "E" in text:
        raise ValueError(
            f"{frame.tolerance} is {text} in millimetres, which a drawing cannot carry as "
            f"a number; a feature control frame is drawn with a decimal value"
        )
    return _check_characters(text)


def _value_items(frame: FeatureControlFrame) -> list[_Glyph | str]:
    """The tolerance compartment's contents, in the order Y14.5 reads them.

    The same order ``FeatureControlFrame.render()`` uses, so the drawn frame and the text
    frame cannot disagree about which modifier follows which.
    """
    items: list[_Glyph | str] = []
    if frame.zone_is_diametral:
        items.append(_diameter_glyph())
    items.append(_tolerance_text(frame))
    letter = _MATERIAL_CONDITION_LETTER.get(frame.material_condition)
    if letter is not None:
        items.append(_circled_letter(letter))
    for modifier in frame.modifiers:
        if modifier is FrameModifier.DIAMETER:
            continue
        if modifier is FrameModifier.STATISTICAL:
            items.append(_statistical_glyph())
        else:
            items.append(_circled_letter(_FRAME_MODIFIER_LETTER[modifier]))
    return items


def _datum_items(frame: FeatureControlFrame) -> list[list[_Glyph | str]]:
    compartments: list[list[_Glyph | str]] = []
    for datum in frame.datums:
        items: list[_Glyph | str] = [_check_characters(datum.letter)]
        letter = {"MMB": "M", "LMB": "L"}.get(datum.boundary.value)
        if letter is not None:
            items.append(_circled_letter(letter))
        compartments.append(items)
    return compartments


def _item_width(item: _Glyph | str) -> float:
    return item.width if isinstance(item, _Glyph) else _text_width(item, 1.0)


def _compartment_width(items: list[_Glyph | str]) -> float:
    content = sum(_item_width(i) for i in items) + _ITEM_GAP * (len(items) - 1)
    return content + 2 * _PADDING


def frame_drawing(
    frame: FeatureControlFrame,
    *,
    text_height: Quantity = DEFAULT_TEXT_HEIGHT,
    origin: tuple[float, float] = (0.0, 0.0),
) -> FrameDrawing:
    """One feature control frame as drawable primitives, in millimetres.

    ``text_height`` is the drawing's predominant character height ``h`` — 3.5 mm is the
    usual ISO 3098 height and the default here. The frame is 2h tall and starts at
    ``origin``, its lower-left corner, growing to the right.

    Every symbol is geometry and only the tolerance value and datum letters are text; the
    tolerance is converted to millimetres because the drawing is a millimetre document.
    """
    h = _mm_height(text_height)
    x0, y0 = origin
    height = _FRAME_HEIGHT * h
    mid_y = y0 + height / 2

    compartments: list[list[_Glyph | str]] = [
        [_glyph(list(_SYMBOL_BUILDERS[frame.characteristic]()))],
        _value_items(frame),
        *_datum_items(frame),
    ]

    strokes: list[Stroke] = []
    labels: list[Label] = []
    edges = [x0]
    cursor = x0
    for items in compartments:
        width = _compartment_width(items) * h
        cursor += width
        edges.append(cursor)
        # Centre the run of items in the compartment, so a text run that a substituted
        # font draws wider than the allowance overruns symmetrically rather than into a
        # divider.
        run = (_compartment_width(items) - 2 * _PADDING) * h
        item_x = cursor - width + (width - run) / 2
        for item in items:
            item_width = _item_width(item) * h
            center = (item_x + item_width / 2, mid_y)
            if isinstance(item, _Glyph):
                strokes.extend(_place_stroke(s, h, center[0], center[1]) for s in item.strokes)
                labels.extend(_place_label(t, h, center[0], center[1]) for t in item.labels)
            else:
                labels.append(Label(text=item, center=center, height=h))
            item_x += item_width + _ITEM_GAP * h

    total_width = edges[-1] - x0
    strokes.append(
        Polyline(
            points=(
                (x0, y0),
                (x0 + total_width, y0),
                (x0 + total_width, y0 + height),
                (x0, y0 + height),
            ),
            closed=True,
        )
    )
    for edge in edges[1:-1]:
        strokes.append(_line(edge, y0, edge, y0 + height))

    return FrameDrawing(
        strokes=tuple(strokes),
        labels=tuple(labels),
        origin=origin,
        width=total_width,
        height=height,
        compartment_edges=tuple(edges),
    )
