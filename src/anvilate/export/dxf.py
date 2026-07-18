"""DXF export of 2D plate outlines with holes.

Turns the plan geometry a code-checked structural plate implies — a lifting lug,
a gusset, a base plate — into a DXF drawing a fabricator can cut from. The plate
is a closed rectangular outline; each hole is a circle. Dimensions are
:class:`~anvilate.units.Quantity` lengths, written to the DXF in millimetres.

Requires ``ezdxf`` (the ``export`` extra); importing this module without it raises
a clear :class:`ImportError`.
"""

from __future__ import annotations

from math import cos, pi, radians, sin
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = [
    "Hole",
    "Slot",
    "bolt_circle_holes",
    "linear_hole_pattern",
    "grid_hole_pattern",
    "plate_cut_length",
    "plate_mass",
    "export_plate_dxf",
]

# A fabrication DXF separates the outer profile cut from the interior hole pierces
# onto named layers so a CNC controller (plasma/laser/waterjet) can order and lead
# them in differently. Distinct ACI colours make the two legible in any viewer.
_OUTLINE_LAYER = "OUTLINE"
_HOLE_LAYER = "HOLES"
# An optional part mark (name, material) goes on its own TEXT layer, below the
# plate, so a fabricator can identify the cut without it being mistaken for cut
# geometry. Text height is a fixed fraction of the plate height.
_TEXT_LAYER = "TEXT"
_LABEL_HEIGHT_FRACTION = 0.06


def _require_ezdxf():
    try:
        import ezdxf
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            "DXF export needs ezdxf; install the export extra: pip install 'anvilate[export]'"
        ) from exc
    return ezdxf


class Hole(BaseModel):
    """A circular hole in a plate: its centre (x, y) and diameter."""

    model_config = ConfigDict(frozen=True)

    x: Quantity
    y: Quantity
    diameter: Quantity


class Slot(BaseModel):
    """A slotted (obround) hole: its centre (x, y), overall ``length``, ``width``,
    and orientation. ``length`` is the overall dimension along the slot axis
    (end-cap to end-cap), ``width`` the across-axis dimension (the end-cap
    diameter). ``vertical`` runs the slot along Y instead of X."""

    model_config = ConfigDict(frozen=True)

    x: Quantity
    y: Quantity
    length: Quantity
    width: Quantity
    vertical: bool = False


def _mm(value: Quantity, name: str) -> float:
    if not value.has_dimension("[length]"):
        raise ValueError(f"{name} must be a [length] quantity; got {value.dimensionality}")
    return value.to("mm").magnitude


def bolt_circle_holes(
    *,
    center_x: Quantity,
    center_y: Quantity,
    bolt_circle_diameter: Quantity,
    hole_diameter: Quantity,
    count: int,
    start_angle: float = 0.0,
) -> list[Hole]:
    """Generate ``count`` equally-spaced :class:`Hole` centres on a bolt circle.

    The standard flange / hub / bearing-cap pattern: ``count`` holes of
    ``hole_diameter`` spaced evenly around a circle of ``bolt_circle_diameter`` centred
    on (``center_x``, ``center_y``), the first at ``start_angle`` degrees from the
    positive X axis and the rest following counter-clockwise. Feed the returned list
    straight to :func:`export_plate_dxf` as its ``holes``. ``count`` must be at least 1
    and the diameters positive. Returns the holes in angular order.
    """
    if count < 1:
        raise ValueError(f"count must be at least 1; got {count}")
    cx = _mm(center_x, "center_x")
    cy = _mm(center_y, "center_y")
    bcd = _mm(bolt_circle_diameter, "bolt_circle_diameter")
    if bcd <= 0:
        raise ValueError(f"bolt_circle_diameter must be positive; got {bolt_circle_diameter}")
    if _mm(hole_diameter, "hole_diameter") <= 0:
        raise ValueError(f"hole_diameter must be positive; got {hole_diameter}")
    pitch_radius = bcd / 2.0
    holes: list[Hole] = []
    for i in range(count):
        angle = radians(start_angle + 360.0 * i / count)
        holes.append(
            Hole(
                x=Quantity(magnitude=cx + pitch_radius * cos(angle), unit="mm"),
                y=Quantity(magnitude=cy + pitch_radius * sin(angle), unit="mm"),
                diameter=hole_diameter,
            )
        )
    return holes


def linear_hole_pattern(
    *,
    start_x: Quantity,
    start_y: Quantity,
    hole_diameter: Quantity,
    count: int,
    pitch: Quantity,
    angle: float = 0.0,
) -> list[Hole]:
    """Generate ``count`` :class:`Hole` centres in a straight row at a fixed ``pitch``.

    The holes march from (``start_x``, ``start_y``) along a line at ``angle`` degrees
    from the positive X axis, spaced ``pitch`` apart (centre to centre) — a bolt row,
    a louvre line, a rack of mounting holes. ``count`` must be at least 1, the diameter
    and pitch positive. Returns the holes in order from the start point.
    """
    if count < 1:
        raise ValueError(f"count must be at least 1; got {count}")
    sx = _mm(start_x, "start_x")
    sy = _mm(start_y, "start_y")
    step = _mm(pitch, "pitch")
    if step <= 0:
        raise ValueError(f"pitch must be positive; got {pitch}")
    if _mm(hole_diameter, "hole_diameter") <= 0:
        raise ValueError(f"hole_diameter must be positive; got {hole_diameter}")
    theta = radians(angle)
    dx, dy = step * cos(theta), step * sin(theta)
    return [
        Hole(
            x=Quantity(magnitude=sx + i * dx, unit="mm"),
            y=Quantity(magnitude=sy + i * dy, unit="mm"),
            diameter=hole_diameter,
        )
        for i in range(count)
    ]


def grid_hole_pattern(
    *,
    origin_x: Quantity,
    origin_y: Quantity,
    hole_diameter: Quantity,
    columns: int,
    rows: int,
    x_pitch: Quantity,
    y_pitch: Quantity,
) -> list[Hole]:
    """Generate a rectangular ``columns`` × ``rows`` grid of :class:`Hole` centres.

    The holes fill a rectangular array from (``origin_x``, ``origin_y``), stepping
    ``x_pitch`` across each row and ``y_pitch`` up between rows — a perforated plate, a
    breadboard, a bolt field. ``columns`` and ``rows`` must be at least 1, the diameter
    and pitches positive. Returns the holes row by row (bottom row first, left to right).
    """
    if columns < 1 or rows < 1:
        raise ValueError(f"columns and rows must be at least 1; got {columns} x {rows}")
    ox = _mm(origin_x, "origin_x")
    oy = _mm(origin_y, "origin_y")
    xp = _mm(x_pitch, "x_pitch")
    yp = _mm(y_pitch, "y_pitch")
    if xp <= 0 or yp <= 0:
        raise ValueError(f"x_pitch and y_pitch must be positive; got {x_pitch}, {y_pitch}")
    if _mm(hole_diameter, "hole_diameter") <= 0:
        raise ValueError(f"hole_diameter must be positive; got {hole_diameter}")
    return [
        Hole(
            x=Quantity(magnitude=ox + col * xp, unit="mm"),
            y=Quantity(magnitude=oy + row * yp, unit="mm"),
            diameter=hole_diameter,
        )
        for row in range(rows)
        for col in range(columns)
    ]


def plate_cut_length(
    *,
    width: Quantity,
    height: Quantity,
    holes: list[Hole] | None = None,
    slots: list[Slot] | None = None,
) -> Quantity:
    """The total cut length of a rectangular plate: outline plus every hole and slot.

    The distance a plasma, laser, or waterjet head travels to cut the part — the
    rectangular outline perimeter 2·(``width`` + ``height``), plus π·d for each
    :class:`Hole`, plus the obround perimeter 2·(L − w) + π·w for each :class:`Slot`
    (two straight sides and two semicircular caps). Multiply by the machine's cut rate
    to estimate cut time and cost. ``width`` and ``height`` must be positive. Returns
    the total cut length in mm.
    """
    w = _mm(width, "width")
    h = _mm(height, "height")
    if w <= 0 or h <= 0:
        raise ValueError(f"plate width and height must be positive; got {width} x {height}")
    total = 2.0 * (w + h)
    for i, hole in enumerate(holes or []):
        total += pi * _mm(hole.diameter, f"holes[{i}].diameter")
    for i, slot in enumerate(slots or []):
        slot_length = _mm(slot.length, f"slots[{i}].length")
        slot_width = _mm(slot.width, f"slots[{i}].width")
        total += 2.0 * (slot_length - slot_width) + pi * slot_width
    return Quantity(magnitude=total, unit="mm")


def plate_mass(
    *,
    width: Quantity,
    height: Quantity,
    thickness: Quantity,
    density: Quantity,
    holes: list[Hole] | None = None,
    slots: list[Slot] | None = None,
) -> Quantity:
    """The finished mass of a rectangular plate, net of its holes and slots.

    The material actually left after cutting: the gross rectangle ``width`` × ``height``
    less the area of each :class:`Hole` (π·d²/4) and each :class:`Slot` (the obround area
    (L − w)·w + π·w²/4), times ``thickness`` and ``density`` — the number for a weight or
    material-cost estimate. All the plate dimensions and ``density`` must be positive, and
    the cut-outs must not remove more than the whole plate. Returns the mass in kg.
    """
    w = _mm(width, "width")
    h = _mm(height, "height")
    t = _mm(thickness, "thickness")
    if w <= 0 or h <= 0 or t <= 0:
        raise ValueError("plate width, height, and thickness must be positive")
    if not density.has_dimension("[mass] / [length]**3"):
        raise ValueError(f"density must be a mass/volume quantity; got {density.dimensionality}")
    net_area = w * h
    for i, hole in enumerate(holes or []):
        d = _mm(hole.diameter, f"holes[{i}].diameter")
        net_area -= pi * d**2 / 4.0
    for i, slot in enumerate(slots or []):
        slot_length = _mm(slot.length, f"slots[{i}].length")
        slot_width = _mm(slot.width, f"slots[{i}].width")
        net_area -= (slot_length - slot_width) * slot_width + pi * slot_width**2 / 4.0
    if net_area <= 0:
        raise ValueError("holes and slots remove the whole plate; net area is not positive")
    volume_m3 = net_area * t * 1e-9  # mm^3 -> m^3
    mass_kg = volume_m3 * density.to("kg/m**3").magnitude
    return Quantity(magnitude=mass_kg, unit="kg")


def _slot_vertices(
    cx: float, cy: float, length: float, width: float, vertical: bool
) -> list[tuple[float, float, float]]:
    """Obround corner vertices as (x, y, bulge) — two straight sides and two
    semicircular end caps (bulge 1). ``length`` is the overall axis dimension,
    ``width`` the end-cap diameter; ``vertical`` runs the axis along Y."""
    radius = width / 2
    straight = (length - width) / 2  # centre-to-centre of the two end caps, halved
    if vertical:
        return [
            (cx - radius, cy - straight, 0),
            (cx + radius, cy - straight, 1),
            (cx + radius, cy + straight, 0),
            (cx - radius, cy + straight, 1),
        ]
    return [
        (cx - straight, cy - radius, 0),
        (cx + straight, cy - radius, 1),
        (cx + straight, cy + radius, 0),
        (cx - straight, cy + radius, 1),
    ]


def export_plate_dxf(
    *,
    width: Quantity,
    height: Quantity,
    holes: list[Hole],
    path: str | Path,
    slots: list[Slot] | None = None,
    label: str | None = None,
) -> Path:
    """Write a rectangular plate outline with ``holes`` and ``slots`` to a DXF file.

    The plate spans (0, 0) to (``width``, ``height``) as a closed polyline; each
    :class:`Hole` becomes a circle and each :class:`Slot` an obround polyline, both
    on the ``HOLES`` layer. An optional ``label`` (e.g. a part mark and material) is
    written as text just below the plate on a separate ``TEXT`` layer. All lengths
    are written in millimetres. Returns the path written. Raises :class:`ValueError`
    for a non-positive plate or a feature that falls outside it, and
    :class:`ImportError` if ezdxf is unavailable.
    """
    ezdxf = _require_ezdxf()
    from ezdxf.enums import TextEntityAlignment

    w = _mm(width, "width")
    h = _mm(height, "height")
    if w <= 0 or h <= 0:
        raise ValueError(f"plate width and height must be positive; got {width} x {height}")

    doc = ezdxf.new()
    doc.units = ezdxf.units.MM
    doc.layers.add(_OUTLINE_LAYER, color=7)  # white/black — the profile cut
    doc.layers.add(_HOLE_LAYER, color=1)  # red — the interior pierces
    msp = doc.modelspace()
    msp.add_lwpolyline(
        [(0, 0), (w, 0), (w, h), (0, h)], close=True, dxfattribs={"layer": _OUTLINE_LAYER}
    )

    if label:
        doc.layers.add(_TEXT_LAYER, color=7)
        text_height = h * _LABEL_HEIGHT_FRACTION
        text = msp.add_text(label, height=text_height, dxfattribs={"layer": _TEXT_LAYER})
        text.set_placement((0, -1.5 * text_height), align=TextEntityAlignment.LEFT)

    for hole in holes:
        cx = _mm(hole.x, "hole x")
        cy = _mm(hole.y, "hole y")
        radius = _mm(hole.diameter, "hole diameter") / 2
        if not (0 <= cx - radius and cx + radius <= w and 0 <= cy - radius and cy + radius <= h):
            raise ValueError(
                f"hole at ({hole.x}, {hole.y}) d={hole.diameter} falls outside the "
                f"{width} x {height} plate"
            )
        msp.add_circle((cx, cy), radius, dxfattribs={"layer": _HOLE_LAYER})

    for slot in slots or []:
        cx = _mm(slot.x, "slot x")
        cy = _mm(slot.y, "slot y")
        length = _mm(slot.length, "slot length")
        slot_width = _mm(slot.width, "slot width")
        if slot_width <= 0 or length <= slot_width:
            raise ValueError(
                f"slot at ({slot.x}, {slot.y}) needs length > width > 0; "
                f"got length={slot.length}, width={slot.width}"
            )
        half_len = length / 2
        half_wid = slot_width / 2
        ax = half_wid if slot.vertical else half_len  # half extent along X
        ay = half_len if slot.vertical else half_wid  # half extent along Y
        if not (0 <= cx - ax and cx + ax <= w and 0 <= cy - ay and cy + ay <= h):
            raise ValueError(
                f"slot at ({slot.x}, {slot.y}) {slot.length}x{slot.width} falls outside "
                f"the {width} x {height} plate"
            )
        msp.add_lwpolyline(
            _slot_vertices(cx, cy, length, slot_width, slot.vertical),
            format="xyb",
            close=True,
            dxfattribs={"layer": _HOLE_LAYER},
        )

    path = Path(path)
    doc.saveas(path)
    return path
