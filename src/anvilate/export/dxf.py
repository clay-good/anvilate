"""DXF export of 2D plate outlines with holes.

Turns the plan geometry a code-checked structural plate implies — a lifting lug,
a gusset, a base plate — into a DXF drawing a fabricator can cut from. The plate
is a closed rectangular outline; each hole is a circle. Dimensions are
:class:`~anvilate.units.Quantity` lengths, written to the DXF in millimetres.

Requires ``ezdxf`` (the ``export`` extra); importing this module without it raises
a clear :class:`ImportError`.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from ..units import Quantity

__all__ = ["Hole", "Slot", "export_plate_dxf"]

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
