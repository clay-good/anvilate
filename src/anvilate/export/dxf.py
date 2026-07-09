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

__all__ = ["Hole", "export_plate_dxf"]


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


def _mm(value: Quantity, name: str) -> float:
    if not value.has_dimension("[length]"):
        raise ValueError(f"{name} must be a [length] quantity; got {value.dimensionality}")
    return value.to("mm").magnitude


def export_plate_dxf(
    *,
    width: Quantity,
    height: Quantity,
    holes: list[Hole],
    path: str | Path,
) -> Path:
    """Write a rectangular plate outline with ``holes`` to a DXF file.

    The plate spans (0, 0) to (``width``, ``height``) as a closed polyline; each
    :class:`Hole` becomes a circle. All lengths are written in millimetres. Returns
    the path written. Raises :class:`ValueError` for a non-positive plate or a hole
    that falls outside it, and :class:`ImportError` if ezdxf is unavailable.
    """
    ezdxf = _require_ezdxf()

    w = _mm(width, "width")
    h = _mm(height, "height")
    if w <= 0 or h <= 0:
        raise ValueError(f"plate width and height must be positive; got {width} x {height}")

    doc = ezdxf.new()
    doc.units = ezdxf.units.MM
    msp = doc.modelspace()
    msp.add_lwpolyline([(0, 0), (w, 0), (w, h), (0, h)], close=True)

    for hole in holes:
        cx = _mm(hole.x, "hole x")
        cy = _mm(hole.y, "hole y")
        radius = _mm(hole.diameter, "hole diameter") / 2
        if not (0 <= cx - radius and cx + radius <= w and 0 <= cy - radius and cy + radius <= h):
            raise ValueError(
                f"hole at ({hole.x}, {hole.y}) d={hole.diameter} falls outside the "
                f"{width} x {height} plate"
            )
        msp.add_circle((cx, cy), radius)

    path = Path(path)
    doc.saveas(path)
    return path
