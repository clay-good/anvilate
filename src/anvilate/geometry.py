"""Deterministic B-Rep geometry built from audited Design Spec patterns.

The geometry layer does not execute arbitrary generated Python.  A Design Spec selects a
named pattern, and that pattern reads only the dimensions it declares.  The first shipped
pattern is ``base_plate``: a rectangular solid centered on the XY origin with its bottom
face at Z=0.

``build123d`` is an optional dependency.  Importing :mod:`anvilate.geometry` remains cheap;
the dependency is required only when a solid is built or written.
"""

from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from html import escape
from math import sqrt
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Any, Literal

from pydantic import Field, model_validator

from ._models import FrozenMap, Named, StatableModel
from .packs.structural import BasePlate
from .spec import DesignSpec

__all__ = [
    "BASE_PLATE_PATTERN",
    "BuiltGeometry",
    "GeometryError",
    "GeometrySummary",
    "GeometryMeasurement",
    "GeometryUnavailable",
    "RenderedViewport",
    "UnsupportedGeometry",
    "ViewportImage",
    "build_base_plate",
    "build_spec",
    "measure_geometry",
    "render_viewport",
    "write_step",
]

BASE_PLATE_PATTERN = "base_plate/1"
_COUNT_UNIT = "count"


class GeometryError(ValueError):
    """A spec cannot produce valid geometry."""


class GeometryUnavailable(GeometryError):
    """The optional geometry runtime is not installed."""


class UnsupportedGeometry(GeometryError):
    """No audited geometry pattern exists for the requested element type."""


class GeometrySummary(StatableModel):
    """The serializable identity and kernel checks for one built solid."""

    name: Named
    pattern: Literal["base_plate/1"]
    valid: Literal[True]
    volume_mm3: Annotated[float, Field(alias="volumeMm3", gt=0)]
    dimensions_mm: FrozenMap[str, Annotated[float, Field(gt=0)]] = Field(
        alias="dimensionsMm",
        json_schema_extra={"additionalProperties": {"type": "number", "exclusiveMinimum": 0}},
    )
    face_tags: tuple[Named, ...] = Field(alias="faceTags", min_length=1)


class GeometryMeasurement(StatableModel):
    """One value read from built geometry rather than repeated from its spec."""

    query: Named
    value: Annotated[float, Field(gt=0)]
    unit: Literal["count", "mm", "mm^2", "mm^3"]
    feature: Named


class ViewportImage(StatableModel):
    """The portable image document returned beside an MCP image attachment."""

    view: Literal["iso", "front", "top", "right"]
    width_px: Annotated[int, Field(ge=64, le=4096)]
    height_px: Annotated[int, Field(ge=64, le=3072)]
    mime_type: Literal["image/svg+xml"]
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    image: Annotated[str, Field(min_length=1)]

    @model_validator(mode="after")
    def _payload_matches_its_digest(self) -> ViewportImage:
        try:
            data = base64.b64decode(self.image, validate=True)
        except ValueError as failure:
            raise ValueError("image must be valid base64") from failure
        actual = sha256(data).hexdigest()
        if actual != self.sha256:
            raise ValueError(f"sha256 does not match image bytes: computed {actual}")
        return self


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


@dataclass(frozen=True)
class RenderedViewport:
    """A deterministic SVG rendering and the metadata needed to attach it over MCP."""

    view: Literal["iso", "front", "top", "right"]
    width_px: int
    height_px: int
    data: bytes

    @property
    def mime_type(self) -> str:
        """The media type of :attr:`data`."""
        return "image/svg+xml"

    @property
    def sha256(self) -> str:
        """The lowercase SHA-256 digest of the exact SVG bytes."""
        return sha256(self.data).hexdigest()

    def document(self) -> ViewportImage:
        """Return the schema-backed, base64-encoded wire document."""
        return ViewportImage(
            view=self.view,
            width_px=self.width_px,
            height_px=self.height_px,
            mime_type=self.mime_type,
            sha256=self.sha256,
            image=base64.b64encode(self.data).decode("ascii"),
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


def render_viewport(
    built: BuiltGeometry,
    *,
    view: Literal["iso", "front", "top", "right"] = "iso",
    width_px: int = 800,
) -> RenderedViewport:
    """Render a deterministic vector viewport of one valid solid.

    The projection uses only the built solid's bounding vertices. That is exact for the
    current rectangular base-plate pattern and deliberately refuses to masquerade as a
    general hidden-line renderer for patterns that have not shipped.
    """
    if built.pattern != BASE_PLATE_PATTERN:
        raise UnsupportedGeometry(f"viewport rendering has no projector for {built.pattern!r}")
    if not 64 <= width_px <= 4096:
        raise GeometryError(f"viewport width_px must be from 64 through 4096; got {width_px}")
    if view not in {"iso", "front", "top", "right"}:
        raise GeometryError(f"unknown viewport {view!r}; choose iso, front, top, or right")
    height_px = max(64, round(width_px * 0.75))
    bounds = built.shape.bounding_box()
    x0, y0, z0 = bounds.min.X, bounds.min.Y, bounds.min.Z
    x1, y1, z1 = bounds.max.X, bounds.max.Y, bounds.max.Z
    vertices = (
        (x0, y0, z0),
        (x1, y0, z0),
        (x1, y1, z0),
        (x0, y1, z0),
        (x0, y0, z1),
        (x1, y0, z1),
        (x1, y1, z1),
        (x0, y1, z1),
    )
    root2 = sqrt(2)
    projectors = {
        "top": lambda x, y, z: (x, y, z),
        "front": lambda x, y, z: (x, z, -y),
        "right": lambda x, y, z: (y, z, x),
        "iso": lambda x, y, z: ((x + y) / root2, z + (y - x) / root2, x - y + z),
    }
    projected = tuple(projectors[view](*vertex) for vertex in vertices)
    low_x = min(point[0] for point in projected)
    high_x = max(point[0] for point in projected)
    low_y = min(point[1] for point in projected)
    high_y = max(point[1] for point in projected)
    margin = width_px * 0.08
    span_x = max(high_x - low_x, 1e-9)
    span_y = max(high_y - low_y, 1e-9)
    scale = min((width_px - 2 * margin) / span_x, (height_px - 2 * margin) / span_y)
    offset_x = (width_px - span_x * scale) / 2
    offset_y = (height_px - span_y * scale) / 2

    def screen(point: tuple[float, float, float]) -> tuple[float, float]:
        return (
            offset_x + (point[0] - low_x) * scale,
            height_px - offset_y - (point[1] - low_y) * scale,
        )

    faces = (
        ("bottom", (0, 1, 2, 3), "#cbd5e1"),
        ("south", (0, 1, 5, 4), "#bfdbfe"),
        ("east", (1, 2, 6, 5), "#93c5fd"),
        ("north", (2, 3, 7, 6), "#dbeafe"),
        ("west", (3, 0, 4, 7), "#e2e8f0"),
        ("top", (4, 5, 6, 7), "#eff6ff"),
    )
    ordered = sorted(
        faces,
        key=lambda face: sum(projected[index][2] for index in face[1]) / len(face[1]),
    )
    polygons = []
    for tag, indices, fill in ordered:
        points = " ".join(
            f"{screen(projected[index])[0]:.3f},{screen(projected[index])[1]:.3f}"
            for index in indices
        )
        polygons.append(
            f'<polygon data-face="{escape(tag)}" points="{points}" fill="{fill}" '
            'stroke="#0f172a" stroke-width="1.5" stroke-linejoin="round"/>'
        )
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px}" height="{height_px}" '
        f'viewBox="0 0 {width_px} {height_px}" role="img" '
        f'aria-label="{escape(built.name)} {view} viewport">\n'
        f'<rect width="{width_px}" height="{height_px}" fill="#ffffff"/>\n'
        + "\n".join(polygons)
        + "\n</svg>\n"
    ).encode("utf-8")
    return RenderedViewport(view=view, width_px=width_px, height_px=height_px, data=svg)


def measure_geometry(built: BuiltGeometry, query: str) -> GeometryMeasurement:
    """Measure one supported property directly from the regenerated B-Rep."""
    bounds = built.shape.bounding_box()
    dimensions = {
        "width": (float(bounds.size.X), "east-west extent"),
        "depth": (float(bounds.size.Y), "north-south extent"),
        "plate_thickness": (float(bounds.size.Z), "bottom-top extent"),
    }
    if query == "volume":
        return GeometryMeasurement(
            query=query, value=built.volume_mm3, unit="mm^3", feature="solid"
        )
    if query == "face_count":
        return GeometryMeasurement(
            query=query,
            value=float(sum(len(faces) for faces in built.faces.values())),
            unit=_COUNT_UNIT,
            feature="semantic faces",
        )
    if query in dimensions:
        value, feature = dimensions[query]
        return GeometryMeasurement(query=query, value=value, unit="mm", feature=feature)
    if query.startswith("area:"):
        tag = query.removeprefix("area:")
        faces = built.faces.get(tag)
        if faces:
            return GeometryMeasurement(
                query=query,
                value=float(sum(face.area for face in faces)),
                unit="mm^2",
                feature=tag,
            )
    supported = "volume, width, depth, plate_thickness, face_count, or area:<semantic-face>"
    raise GeometryError(f"unsupported geometry query {query!r}; choose {supported}")


def write_step(built: BuiltGeometry, path: Path) -> Path:
    """Write one built solid as STEP and return the output path."""
    if not built.is_valid:
        raise GeometryError("refusing to write invalid geometry")
    _Align, _Box, export_step = _kernel()
    export_step(built.shape, path)
    return path
