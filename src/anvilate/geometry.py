"""Deterministic B-Rep geometry built from audited Design Spec patterns.

The geometry layer does not execute arbitrary generated Python.  A Design Spec selects a
named pattern, and that pattern reads only the dimensions it declares.  The first shipped
pattern is ``base_plate``: a rectangular solid centered on the XY origin with its bottom
face at Z=0.

``build123d`` is an optional dependency.  Importing :mod:`anvilate.geometry` remains cheap;
the dependency is required only when a solid is built or written.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Any, Literal

from pydantic import Field

from ._models import FrozenMap, Named, RevalidatedModel
from .packs.structural import BasePlate
from .spec import DesignSpec

__all__ = [
    "BASE_PLATE_PATTERN",
    "BuiltGeometry",
    "GeometryError",
    "GeometrySummary",
    "GeometryUnavailable",
    "UnsupportedGeometry",
    "build_base_plate",
    "build_spec",
    "write_step",
]

BASE_PLATE_PATTERN = "base_plate/1"


class GeometryError(ValueError):
    """A spec cannot produce valid geometry."""


class GeometryUnavailable(GeometryError):
    """The optional geometry runtime is not installed."""


class UnsupportedGeometry(GeometryError):
    """No audited geometry pattern exists for the requested element type."""


class GeometrySummary(RevalidatedModel):
    """The serializable identity and kernel checks for one built solid."""

    name: Named
    pattern: Literal["base_plate/1"]
    valid: Literal[True]
    volume_mm3: Annotated[float, Field(alias="volumeMm3", gt=0)]
    dimensions_mm: FrozenMap[str, Annotated[float, Field(gt=0)]] = Field(
        alias="dimensionsMm",
        json_schema_extra={
            "additionalProperties": {"type": "number", "exclusiveMinimum": 0}
        },
    )
    face_tags: tuple[Named, ...] = Field(alias="faceTags", min_length=1)


@dataclass(frozen=True)
class BuiltGeometry:
    """One valid solid and the stable semantic names attached to its faces."""

    name: str
    pattern: str
    shape: Any
    faces: Mapping[str, tuple[Any, ...]]
    dimensions_mm: Mapping[str, float]

    @property
    def volume_mm3(self) -> float:
        """The kernel-computed solid volume in cubic millimeters."""
        return float(self.shape.volume)

    @property
    def is_valid(self) -> bool:
        """Whether the kernel reports one positive-volume valid solid."""
        return bool(self.shape.is_valid and len(self.shape.solids()) == 1 and self.volume_mm3 > 0)

    @property
    def signature(self) -> tuple[str, tuple[tuple[str, float], ...], tuple[str, ...]]:
        """A deterministic identity for regeneration checks, independent of STEP headers."""
        return (self.pattern, tuple(sorted(self.dimensions_mm.items())), tuple(sorted(self.faces)))

    def summary(self) -> GeometrySummary:
        """Return the standalone document published by the CLI and MCP surfaces."""
        return GeometrySummary(
            name=self.name,
            pattern=self.pattern,
            valid=True,
            volumeMm3=self.volume_mm3,
            dimensionsMm=dict(self.dimensions_mm),
            faceTags=tuple(sorted(self.faces)),
        )


def _kernel():
    try:
        from build123d import Align, Box, export_step
    except ImportError as failure:  # pragma: no cover - exercised without the geometry extra
        raise GeometryUnavailable(
            "3D geometry needs the optional dependency; install anvilate[geometry]"
        ) from failure
    return Align, Box, export_step


def _positive_mm(value: Any, field: str) -> float:
    magnitude = float(value.to("mm").magnitude)
    if magnitude <= 0:
        raise GeometryError(f"base_plate {field} must be greater than zero; got {magnitude:g} mm")
    return magnitude


def _tag_box_faces(shape: Any) -> Mapping[str, tuple[Any, ...]]:
    """Name a box's faces from outward normals rather than kernel enumeration order."""
    directions = {
        (1, 0, 0): "east",
        (-1, 0, 0): "west",
        (0, 1, 0): "north",
        (0, -1, 0): "south",
        (0, 0, 1): "top",
        (0, 0, -1): "bottom",
    }
    tagged: dict[str, tuple[Any, ...]] = {}
    for face in shape.faces():
        normal = face.normal_at()
        key = (
            int(round(normal.X)),
            int(round(normal.Y)),
            int(round(normal.Z)),
        )
        try:
            name = directions[key]
        except KeyError as failure:  # pragma: no cover - a box primitive cannot produce this
            raise GeometryError(
                f"base_plate produced a face with unexpected normal {key}"
            ) from failure
        tagged[name] = (face,)
    if set(tagged) != set(directions.values()):  # pragma: no cover - kernel corruption guard
        raise GeometryError(f"base_plate face tagging incomplete: got {sorted(tagged)}")
    return MappingProxyType(tagged)


def build_base_plate(plate: BasePlate) -> BuiltGeometry:
    """Build the audited rectangular base-plate pattern from declared dimensions."""
    if plate.plate_thickness is None:
        raise GeometryError("base_plate geometry needs element_params.plate_thickness")
    width = _positive_mm(plate.width, "width")
    depth = _positive_mm(plate.depth, "depth")
    thickness = _positive_mm(plate.plate_thickness, "plate_thickness")
    Align, Box, _export_step = _kernel()
    shape = Box(
        width,
        depth,
        thickness,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )
    built = BuiltGeometry(
        name=str(plate.name),
        pattern=BASE_PLATE_PATTERN,
        shape=shape,
        faces=_tag_box_faces(shape),
        dimensions_mm=MappingProxyType(
            {"width": width, "depth": depth, "plate_thickness": thickness}
        ),
    )
    if not built.is_valid:  # pragma: no cover - Box with guarded dimensions is valid
        raise GeometryError("base_plate pattern did not produce one valid positive-volume solid")
    return built


def build_spec(spec: DesignSpec) -> BuiltGeometry:
    """Build the audited geometry pattern selected by a Design Spec."""
    if spec.element_type != "base_plate":
        tag = spec.element_type or "<undeclared>"
        raise UnsupportedGeometry(
            f"no audited geometry pattern is registered for element_type {tag!r}; "
            "supported: base_plate"
        )
    try:
        plate = BasePlate(**dict(spec.element_params))
    except ValueError as failure:
        raise GeometryError(f"invalid base_plate element_params: {failure}") from failure
    return build_base_plate(plate)


def write_step(built: BuiltGeometry, path: Path) -> Path:
    """Write one built solid as STEP and return the output path."""
    if not built.is_valid:
        raise GeometryError("refusing to write invalid geometry")
    _Align, _Box, export_step = _kernel()
    export_step(built.shape, path)
    return path
