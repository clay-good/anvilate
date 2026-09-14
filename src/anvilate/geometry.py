"""Deterministic B-Rep geometry built from audited Design Spec patterns.

The geometry layer does not execute arbitrary generated Python.  A Design Spec selects a
named pattern, and that pattern reads only the dimensions it declares.  The shipped
patterns are plates and a solid round transmission shaft, each centered on the XY origin
with its bottom face or drive end at Z=0.

``build123d`` is an optional dependency.  Importing :mod:`anvilate.geometry` remains cheap;
the dependency is required only when a solid is built or written.
"""

from __future__ import annotations

import base64
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from html import escape
from math import isfinite, sqrt
from pathlib import Path
from threading import Lock
from types import MappingProxyType
from typing import Annotated, Any, Literal

from pydantic import Field, FiniteFloat, model_validator

from ._models import FrozenMap, Named, StatableModel
from .export.gate import ExportAuthorization
from .packs.industrial import CoverPlate
from .packs.machinery import TransmissionShaft
from .packs.structural import BasePlate
from .spec import CircularLocator, DesignSpec, HolePattern, InterfaceContract, InterfaceFrame
from .units import Quantity

__all__ = [
    "BASE_PLATE_PATTERN",
    "COVER_PLATE_PATTERN",
    "TRANSMISSION_SHAFT_PATTERN",
    "BuiltGeometry",
    "GeometryError",
    "GeometrySummary",
    "GeometryMeasurement",
    "GeometryUnavailable",
    "ConfirmedStepInterface",
    "CircularFeatureCandidate",
    "HolePatternCandidate",
    "PlanarInterfaceCandidate",
    "RenderedViewport",
    "StepValidationProperties",
    "StepInterfaceCandidates",
    "UnsupportedGeometry",
    "ViewportImage",
    "build_base_plate",
    "build_cover_plate",
    "build_transmission_shaft",
    "build_spec",
    "confirm_step_interface",
    "detect_step_interfaces",
    "measure_geometry",
    "render_viewport",
    "read_step_validation_properties",
    "verify_step_integrity",
    "write_step",
]

BASE_PLATE_PATTERN = "base_plate/1"
COVER_PLATE_PATTERN = "cover_plate/1"
TRANSMISSION_SHAFT_PATTERN = "transmission_shaft/1"
_COUNT_UNIT = "count"
_AP242_SCHEMA = "AP242_MANAGED_MODEL_BASED_3D_ENGINEERING_MIM_LF"
_AP214_SCHEMA = "AUTOMOTIVE_DESIGN { 1 0 10303 214 1 1 1 1 }"
_GVP_RECOMMENDED_PRACTICE = (
    "CAx-IF Rec.Pracs.---Geometric and Assembly Validation Properties---4.6---2023-04-21"
)
_STEP_IO_LOCK = Lock()


class GeometryError(ValueError):
    """A spec cannot produce valid geometry."""


class GeometryUnavailable(GeometryError):
    """The optional geometry runtime is not installed."""


class UnsupportedGeometry(GeometryError):
    """No audited geometry pattern exists for the requested element type."""


class GeometrySummary(StatableModel):
    """The serializable identity and kernel checks for one built solid."""

    name: Named
    pattern: Literal["base_plate/1", "cover_plate/1", "transmission_shaft/1"]
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


@dataclass(frozen=True)
class StepValidationProperties:
    """Part-level geometric validation properties read from a STEP exchange file."""

    volume_mm3: float
    surface_area_mm2: float
    centroid_mm: tuple[float, float, float]


class HolePatternCandidate(StatableModel):
    """One equal-diameter through-hole pattern measured on a planar STEP face."""

    id: Named
    hole_count: Annotated[int, Field(ge=2)]
    hole_diameter_mm: Annotated[FiniteFloat, Field(gt=0)]
    pitch_diameter_mm: Annotated[FiniteFloat, Field(gt=0)]
    center_mm: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    hole_centers_mm: tuple[tuple[FiniteFloat, FiniteFloat, FiniteFloat], ...] = Field(min_length=2)

    @model_validator(mode="after")
    def _count_matches_centers(self) -> HolePatternCandidate:
        if self.hole_count != len(self.hole_centers_mm):
            raise ValueError(
                f"hole_count is {self.hole_count}, but "
                f"{len(self.hole_centers_mm)} centers are listed"
            )
        return self


class CircularFeatureCandidate(StatableModel):
    """One concentric bore, boss, or counterbore that can locate a mating interface."""

    id: Named
    kind: Literal["bore", "boss", "counterbore"]
    diameter_mm: Annotated[FiniteFloat, Field(gt=0)]
    axial_extent_mm: Annotated[FiniteFloat, Field(gt=0)]
    through_diameter_mm: Annotated[FiniteFloat, Field(gt=0)] | None = None
    center_mm: tuple[FiniteFloat, FiniteFloat, FiniteFloat]

    @model_validator(mode="after")
    def _counterbore_has_its_through_diameter(self) -> CircularFeatureCandidate:
        if (self.kind == "counterbore") != (self.through_diameter_mm is not None):
            raise ValueError("only a counterbore candidate carries through_diameter_mm")
        if self.through_diameter_mm is not None and self.through_diameter_mm >= self.diameter_mm:
            raise ValueError("a counterbore through diameter must be smaller than its recess")
        return self


class PlanarInterfaceCandidate(StatableModel):
    """One planar mating-face candidate and any through-hole patterns it carries."""

    id: Named
    solid_id: Named | None = None
    area_mm2: Annotated[FiniteFloat, Field(gt=0)]
    center_mm: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    normal: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    hole_patterns: tuple[HolePatternCandidate, ...] = ()
    locating_features: tuple[CircularFeatureCandidate, ...] = ()


class StepInterfaceCandidates(StatableModel):
    """Deterministic interface candidates measured from one imported STEP part."""

    source_name: Named
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    planar_faces: tuple[PlanarInterfaceCandidate, ...]
    warnings: tuple[str, ...] = ()


class ConfirmedStepInterface(StatableModel):
    """A measured STEP candidate accepted by a named person as an interface contract."""

    source_name: Named
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    face_candidate_id: Named
    pattern_candidate_id: Named
    solid_id: Named | None = None
    confirmed_by: Named
    contract: InterfaceContract


_Point3D = tuple[float, float, float]


@dataclass
class _DetectedPlane:
    face: Any
    area: float
    center: _Point3D
    normal: _Point3D
    holes: list[tuple[float, _Point3D]]
    circular_features: list[
        tuple[Literal["bore", "boss", "counterbore"], float, float, _Point3D, float | None]
    ]


def _coordinates(vector: Any) -> _Point3D:
    """One kernel vector as stable plain coordinates."""
    return (float(vector.X), float(vector.Y), float(vector.Z))


def _dot(left: _Point3D, right: _Point3D) -> float:
    return sum(a * b for a, b in zip(left, right, strict=True))


def _cross(left: _Point3D, right: _Point3D) -> _Point3D:
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _normalized(vector: _Point3D) -> _Point3D:
    magnitude = sqrt(_dot(vector, vector))
    return (vector[0] / magnitude, vector[1] / magnitude, vector[2] / magnitude)


def _interface_basis(normal: _Point3D) -> tuple[_Point3D, _Point3D, _Point3D]:
    """A deterministic right-handed in-plane basis from one face normal."""
    unit_normal = _normalized(normal)
    reference = (1.0, 0.0, 0.0) if abs(unit_normal[0]) < 0.9 else (0.0, 1.0, 0.0)
    projection = _dot(reference, unit_normal)
    projected = (
        reference[0] - projection * unit_normal[0],
        reference[1] - projection * unit_normal[1],
        reference[2] - projection * unit_normal[2],
    )
    x_axis = _normalized(projected)
    y_axis = _normalized(_cross(unit_normal, x_axis))
    return (_rounded_point(x_axis), _rounded_point(y_axis), _rounded_point(unit_normal))


def _counterbore_through_radius(
    shape: Any,
    recess: Any,
    shoulder: Any,
    axis_point: _Point3D,
    direction: _Point3D,
    recess_radius: float,
) -> float | None:
    """The one smaller coaxial inward cylinder continuing through the opposite face."""
    matches = []
    for cylinder in (face for face in shape.faces() if face.geom_type.name == "CYLINDER"):
        if cylinder.is_same(recess) or cylinder.radius is None or cylinder.radius >= recess_radius:
            continue
        other_axis = cylinder.axis_of_rotation
        if other_axis is None:
            continue
        other_direction = _coordinates(other_axis.direction)
        if abs(_dot(direction, other_direction)) < 0.999999:
            continue
        offset = _subtract(_coordinates(other_axis.position), axis_point)
        if sqrt(_dot(_cross(offset, direction), _cross(offset, direction))) > 0.01:
            continue
        surface_point = _coordinates(cylinder.center())
        along = _dot(_subtract(surface_point, _coordinates(other_axis.position)), other_direction)
        axial_point = _point_along(_coordinates(other_axis.position), other_direction, along)
        radial = _subtract(surface_point, axial_point)
        if _dot(radial, _coordinates(cylinder.normal_at())) >= 0:
            continue
        circular_edges = [edge for edge in cylinder.edges() if edge.geom_type.name == "CIRCLE"]
        if not any(
            shoulder_edge.is_same(cylinder_edge)
            for shoulder_edge in shoulder.edges()
            for cylinder_edge in circular_edges
        ):
            continue
        attached = [
            plane
            for plane in shape.faces()
            if plane.geom_type.name == "PLANE"
            and any(
                plane_edge.is_same(cylinder_edge)
                for plane_edge in plane.edges()
                for cylinder_edge in circular_edges
            )
        ]
        if len(attached) != 2 or not any(plane.is_same(shoulder) for plane in attached):
            continue
        opposite = next(plane for plane in attached if not plane.is_same(shoulder))
        if _dot(_coordinates(shoulder.normal_at()), _coordinates(opposite.normal_at())) > -0.999999:
            continue
        matches.append(float(cylinder.radius))
    return matches[0] if len(matches) == 1 else None


def _candidate_id(prefix: str, values: object) -> str:
    payload = json.dumps(values, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{prefix}-{sha256(payload).hexdigest()[:12]}"


def _rounded_point(point: _Point3D) -> _Point3D:
    def clean(value: float) -> float:
        return 0.0 if abs(value) < 0.0000000005 else round(value, 9)

    return (clean(point[0]), clean(point[1]), clean(point[2]))


def _subtract(left: _Point3D, right: _Point3D) -> _Point3D:
    return (left[0] - right[0], left[1] - right[1], left[2] - right[2])


def _point_along(origin: _Point3D, direction: _Point3D, distance: float) -> _Point3D:
    return (
        origin[0] + distance * direction[0],
        origin[1] + distance * direction[1],
        origin[2] + distance * direction[2],
    )


def _solid_signature(solid: Any) -> dict[str, object]:
    bounds = solid.bounding_box()
    return {
        "volume": round(float(solid.volume), 9),
        "center": _rounded_point(_coordinates(solid.center())),
        "minimum": _rounded_point(_coordinates(bounds.min)),
        "maximum": _rounded_point(_coordinates(bounds.max)),
    }


def detect_step_interfaces(path: Path) -> StepInterfaceCandidates:
    """Detect planar faces and regular equal-diameter through-hole patterns in STEP.

    The result is a set of candidates, not an accepted interface contract. The caller must
    choose a face and pattern before putting either into a Design Spec. Detection relies on
    imported B-Rep topology and measured geometry only; STEP mate semantics and entity order
    are ignored.
    """
    try:
        from build123d import import_step
        from OCP.Message import Message  # type: ignore[import-untyped]
    except ImportError as failure:  # pragma: no cover - guarded by the geometry extra
        raise GeometryUnavailable(
            "STEP interface detection needs the optional dependency; install anvilate[geometry]"
        ) from failure
    try:
        source_bytes = path.read_bytes()
    except OSError as failure:
        raise GeometryError(f"could not read STEP file {path}: {failure}") from failure
    if not source_bytes.lstrip().startswith(b"ISO-10303-21;"):
        raise GeometryError(f"could not import STEP file {path}: missing ISO-10303-21 header")
    try:
        # OCCT writes parser diagnostics through process-global printers, bypassing the
        # caller's stdout stream. Remove them only while this locked import runs so JSON
        # output remains JSON even for a malformed exchange file, then restore them.
        with _STEP_IO_LOCK:
            messenger = Message.DefaultMessenger_s()
            printers = list(messenger.Printers())
            for printer in printers:
                messenger.RemovePrinter(printer)
            try:
                shape = import_step(path)
            finally:
                for printer in printers:
                    messenger.AddPrinter(printer)
    except Exception as failure:
        raise GeometryError(f"could not import STEP file {path}: {failure}") from failure
    solids = list(shape.solids())
    if (
        not shape.is_valid
        or not solids
        or any(not solid.is_valid or solid.volume <= 0 for solid in solids)
    ):
        raise GeometryError(
            f"STEP interface detection needs valid positive-volume solids; found {len(solids)}"
        )
    signatures = [_solid_signature(solid) for solid in solids]
    if len({_candidate_id("solid", signature) for signature in signatures}) != len(solids):
        raise GeometryError(
            "STEP interface detection cannot distinguish coincident solids with identical "
            "measured geometry"
        )
    solid_ids = {
        _candidate_id("solid", signature): solid
        for signature, solid in zip(signatures, solids, strict=True)
    }

    planar = [face for face in shape.faces() if face.geom_type.name == "PLANE"]
    planes = [
        _DetectedPlane(
            face=face,
            area=float(face.area),
            center=_coordinates(face.center()),
            normal=_coordinates(face.normal_at()),
            holes=[],
            circular_features=[],
        )
        for face in planar
    ]

    for cylinder in (face for face in shape.faces() if face.geom_type.name == "CYLINDER"):
        axis = cylinder.axis_of_rotation
        radius = cylinder.radius
        if axis is None or radius is None:  # pragma: no cover - a cylindrical face has both
            continue
        direction = _coordinates(axis.direction)
        axis_point = _coordinates(axis.position)
        surface_point = _coordinates(cylinder.center())
        along = _dot(_subtract(surface_point, axis_point), direction)
        axial_point = _point_along(axis_point, direction, along)
        radial = _subtract(surface_point, axial_point)
        inward = _dot(radial, _coordinates(cylinder.normal_at())) < 0
        circular_edges = [edge for edge in cylinder.edges() if edge.geom_type.name == "CIRCLE"]
        attached = []
        for index, plane in enumerate(planes):
            if any(
                plane_edge.is_same(cylinder_edge)
                for plane_edge in plane.face.edges()
                for cylinder_edge in circular_edges
            ):
                attached.append(index)
        if len(attached) != 2:
            continue
        first, second = (planes[index] for index in attached)
        if abs(_dot(direction, first.normal)) < 0.999999:
            continue
        extent = abs(_dot(_subtract(second.center, first.center), direction))
        if extent <= 0:
            continue
        if inward and _dot(first.normal, second.normal) < -0.999999:
            for index in attached:
                plane = planes[index]
                denominator = _dot(direction, plane.normal)
                distance = _dot(_subtract(plane.center, axis_point), plane.normal) / denominator
                center = _rounded_point(_point_along(axis_point, direction, distance))
                plane.holes.append((float(radius), center))
                plane.circular_features.append(("bore", float(radius), extent, center, None))
        elif inward and _dot(first.normal, second.normal) > 0.999999:
            mouth = max((first, second), key=lambda plane: _dot(plane.center, plane.normal))
            floor = first if mouth is second else second
            floor_circles = [edge for edge in floor.face.edges() if edge.geom_type.name == "CIRCLE"]
            denominator = _dot(direction, mouth.normal)
            distance = _dot(_subtract(mouth.center, axis_point), mouth.normal) / denominator
            center = _rounded_point(_point_along(axis_point, direction, distance))
            if len(floor_circles) == 1:
                mouth.circular_features.append(("bore", float(radius), extent, center, None))
            else:
                through_radius = _counterbore_through_radius(
                    shape, cylinder, floor.face, axis_point, direction, float(radius)
                )
                if through_radius is not None:
                    mouth.circular_features.append(
                        ("counterbore", float(radius), extent, center, through_radius)
                    )
        elif not inward and _dot(first.normal, second.normal) > 0.999999:
            base = min((first, second), key=lambda plane: _dot(plane.center, plane.normal))
            denominator = _dot(direction, base.normal)
            distance = _dot(_subtract(base.center, axis_point), base.normal) / denominator
            center = _rounded_point(_point_along(axis_point, direction, distance))
            base.circular_features.append(("boss", float(radius), extent, center, None))

    candidates = []
    for plane in planes:
        containing = [
            solid_id
            for solid_id, solid in solid_ids.items()
            if any(face.is_same(plane.face) for face in solid.faces())
        ]
        if len(containing) != 1:
            raise GeometryError("a planar face could not be assigned to exactly one imported solid")
        solid_id = containing[0] if len(solids) > 1 else None
        center = _rounded_point(plane.center)
        normal = _rounded_point(plane.normal)
        face_signature = {"area": round(plane.area, 9), "center": center, "normal": normal}
        if solid_id is not None:
            face_signature["solid"] = solid_id
        face_id = _candidate_id("plane", face_signature)
        groups: dict[float, list[tuple[float, float, float]]] = {}
        for radius, hole_center in plane.holes:
            groups.setdefault(round(radius, 6), []).append(hole_center)
        patterns = []
        for radius, hole_centers in sorted(groups.items()):
            if len(hole_centers) < 2:
                continue
            ordered_centers = tuple(sorted(hole_centers))
            pattern_center = (
                sum(point[0] for point in ordered_centers) / len(ordered_centers),
                sum(point[1] for point in ordered_centers) / len(ordered_centers),
                sum(point[2] for point in ordered_centers) / len(ordered_centers),
            )
            pitch_radii = [
                sqrt(
                    (point[0] - pattern_center[0]) ** 2
                    + (point[1] - pattern_center[1]) ** 2
                    + (point[2] - pattern_center[2]) ** 2
                )
                for point in ordered_centers
            ]
            pitch_radius = sum(pitch_radii) / len(pitch_radii)
            fit_tolerance = max(0.01, pitch_radius * 1e-4)
            if (
                pitch_radius <= 0
                or max(abs(value - pitch_radius) for value in pitch_radii) > fit_tolerance
            ):
                continue
            pattern_signature = {
                "face": face_id,
                "hole_diameter": round(2 * radius, 9),
                "pitch_diameter": round(2 * pitch_radius, 9),
                "center": _rounded_point(pattern_center),
                "holes": ordered_centers,
            }
            patterns.append(
                HolePatternCandidate(
                    id=_candidate_id("pattern", pattern_signature),
                    hole_count=len(ordered_centers),
                    hole_diameter_mm=2 * radius,
                    pitch_diameter_mm=round(2 * pitch_radius, 9),
                    center_mm=_rounded_point(pattern_center),
                    hole_centers_mm=ordered_centers,
                )
            )
        locating_features = []
        for kind, radius, extent, feature_center, through_radius in plane.circular_features:
            if not any(
                sqrt(
                    sum(
                        (a - b) ** 2 for a, b in zip(feature_center, pattern.center_mm, strict=True)
                    )
                )
                <= max(0.01, pattern.pitch_diameter_mm * 1e-4)
                for pattern in patterns
            ):
                continue
            signature = {
                "face": face_id,
                "kind": kind,
                "diameter": round(2 * radius, 9),
                "axial_extent": round(extent, 9),
                "through_diameter": (
                    None if through_radius is None else round(2 * through_radius, 9)
                ),
                "center": feature_center,
            }
            locating_features.append(
                CircularFeatureCandidate(
                    id=_candidate_id("locator", signature),
                    kind=kind,
                    diameter_mm=round(2 * radius, 9),
                    axial_extent_mm=round(extent, 9),
                    through_diameter_mm=(
                        None if through_radius is None else round(2 * through_radius, 9)
                    ),
                    center_mm=feature_center,
                )
            )
        candidate_data = {
            "id": face_id,
            "area_mm2": round(plane.area, 9),
            "center_mm": center,
            "normal": normal,
            "hole_patterns": tuple(sorted(patterns, key=lambda pattern: pattern.id)),
            "locating_features": tuple(sorted(locating_features, key=lambda feature: feature.id)),
        }
        if solid_id is not None:
            candidate_data["solid_id"] = solid_id
        candidates.append(PlanarInterfaceCandidate.model_validate(candidate_data))
    candidates.sort(
        key=lambda candidate: (
            candidate.normal,
            candidate.center_mm,
            candidate.area_mm2,
            candidate.id,
        )
    )
    return StepInterfaceCandidates(
        source_name=path.name,
        source_sha256=sha256(source_bytes).hexdigest(),
        planar_faces=tuple(candidates),
        warnings=(
            "candidates are measured suggestions only; confirm one before creating an "
            "interface contract",
            "this detector does not yet classify nested blind steps or nonconcentric locators",
        ),
    )


def confirm_step_interface(
    candidates: StepInterfaceCandidates,
    *,
    pattern_id: str,
    name: str,
    mating_plane: str,
    confirmed_by: str,
    locating_feature_id: str | None = None,
) -> ConfirmedStepInterface:
    """Accept one measured hole pattern as a downstream interface contract.

    This function does not infer a choice or a semantic tag. The caller supplies the exact
    deterministic candidate ID, the contract identity, and the person who reviewed the
    measured proposal.
    """
    confirmer = confirmed_by.strip()
    if not confirmer:
        raise GeometryError("accepting an interface candidate names the person confirming it")
    if not name.strip():
        raise GeometryError("an accepted interface contract has a non-blank name")
    if not mating_plane.strip():
        raise GeometryError("an accepted interface names its semantic mating-plane tag")

    matches = [
        (face, pattern)
        for face in candidates.planar_faces
        for pattern in face.hole_patterns
        if pattern.id == pattern_id
    ]
    if len(matches) != 1:
        available = sorted(
            pattern.id for face in candidates.planar_faces for pattern in face.hole_patterns
        )
        choices = ", ".join(available) if available else "none"
        raise GeometryError(
            f"pattern candidate {pattern_id!r} was not found exactly once; available: {choices}"
        )
    face, pattern = matches[0]
    locator = None
    if locating_feature_id is not None:
        locator_matches = [
            feature for feature in face.locating_features if feature.id == locating_feature_id
        ]
        if len(locator_matches) != 1:
            locator_choices = ", ".join(feature.id for feature in face.locating_features) or "none"
            raise GeometryError(
                f"locating feature {locating_feature_id!r} was not found on {face.id}; "
                f"available: {locator_choices}"
            )
        locator = locator_matches[0]
    x_axis, y_axis, normal = _interface_basis(face.normal)
    hole_centers = tuple(
        (
            Quantity(
                magnitude=round(_dot(_subtract(center, pattern.center_mm), x_axis), 9), unit="mm"
            ),
            Quantity(
                magnitude=round(_dot(_subtract(center, pattern.center_mm), y_axis), 9), unit="mm"
            ),
        )
        for center in pattern.hole_centers_mm
    )
    try:
        confirmed_data = {
            "source_name": candidates.source_name,
            "source_sha256": candidates.source_sha256,
            "face_candidate_id": face.id,
            "pattern_candidate_id": pattern.id,
            "confirmed_by": confirmer,
            "contract": InterfaceContract(
                name=name.strip(),
                mating_plane=mating_plane.strip(),
                pattern=HolePattern(
                    diameter=Quantity(magnitude=pattern.pitch_diameter_mm, unit="mm"),
                    hole_count=pattern.hole_count,
                    hole_size=Quantity(magnitude=pattern.hole_diameter_mm, unit="mm"),
                    hole_centers=hole_centers,
                ),
                frame=InterfaceFrame(
                    origin=(
                        Quantity(magnitude=pattern.center_mm[0], unit="mm"),
                        Quantity(magnitude=pattern.center_mm[1], unit="mm"),
                        Quantity(magnitude=pattern.center_mm[2], unit="mm"),
                    ),
                    x_axis=x_axis,
                    y_axis=y_axis,
                    normal=normal,
                ),
                locator=(
                    None
                    if locator is None
                    else CircularLocator(
                        kind=locator.kind,
                        diameter=Quantity(magnitude=locator.diameter_mm, unit="mm"),
                        axial_extent=Quantity(magnitude=locator.axial_extent_mm, unit="mm"),
                        through_diameter=(
                            None
                            if locator.through_diameter_mm is None
                            else Quantity(magnitude=locator.through_diameter_mm, unit="mm")
                        ),
                    )
                ),
            ),
        }
        if face.solid_id is not None:
            confirmed_data["solid_id"] = face.solid_id
        return ConfirmedStepInterface.model_validate(confirmed_data)
    except ValueError as failure:
        raise GeometryError(
            f"could not create the confirmed interface contract: {failure}"
        ) from failure


def _kernel():
    try:
        from build123d import Align, Box, Cylinder, export_step
    except ImportError as failure:  # pragma: no cover - exercised without the geometry extra
        raise GeometryUnavailable(
            "3D geometry needs the optional dependency; install anvilate[geometry]"
        ) from failure
    return Align, Box, Cylinder, export_step


def _positive_mm(value: Any, field: str, *, element: str = "base_plate") -> float:
    try:
        magnitude = float(value.to("mm").magnitude)
    except (TypeError, ValueError) as failure:
        raise GeometryError(f"{element} {field} must be a length; got {value}") from failure
    if magnitude <= 0:
        raise GeometryError(f"{element} {field} must be greater than zero; got {magnitude:g} mm")
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
    Align, Box, _Cylinder, _export_step = _kernel()
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


def _tag_round_faces(shape: Any, *, has_bore: bool) -> Mapping[str, tuple[Any, ...]]:
    """Tag an extruded disk or annulus by surface kind and outward orientation."""
    tagged: dict[str, tuple[Any, ...]] = {}
    curved = []
    for face in shape.faces():
        if face.geom_type.name == "PLANE":
            tag = "top" if face.normal_at().Z > 0 else "bottom"
            tagged[tag] = (face,)
        elif face.geom_type.name == "CYLINDER":
            curved.append(face)
    curved.sort(key=lambda face: face.area, reverse=True)
    if curved:
        tagged["perimeter"] = (curved[0],)
    if has_bore and len(curved) == 2:
        tagged["bore"] = (curved[1],)
    expected = {"bottom", "perimeter", "top"} | ({"bore"} if has_bore else set())
    if set(tagged) != expected:  # pragma: no cover - primitive topology corruption guard
        raise GeometryError(f"cover_plate face tagging incomplete: got {sorted(tagged)}")
    return MappingProxyType(tagged)


def build_cover_plate(plate: CoverPlate) -> BuiltGeometry:
    """Build an audited rectangular, circular, or annular cover-plate solid."""
    thickness = _positive_mm(plate.thickness, "thickness", element="cover_plate")
    Align, Box, Cylinder, _export_step = _kernel()
    if plate.diameter is None:
        width = _positive_mm(plate.width, "width", element="cover_plate")
        length = _positive_mm(plate.length, "length", element="cover_plate")
        shape = Box(
            width,
            length,
            thickness,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )
        faces = _tag_box_faces(shape)
        dimensions = {"width": width, "length": length, "thickness": thickness}
    else:
        diameter = _positive_mm(plate.diameter, "diameter", element="cover_plate")
        shape = Cylinder(
            diameter / 2,
            thickness,
            align=(Align.CENTER, Align.CENTER, Align.MIN),
        )
        dimensions = {"diameter": diameter, "thickness": thickness}
        if plate.hole_diameter is not None:
            hole = _positive_mm(plate.hole_diameter, "hole_diameter", element="cover_plate")
            if hole >= diameter:
                raise GeometryError(
                    "cover_plate hole_diameter must be below diameter; "
                    f"got {hole:g} mm and {diameter:g} mm"
                )
            shape = shape - Cylinder(
                hole / 2,
                thickness,
                align=(Align.CENTER, Align.CENTER, Align.MIN),
            )
            dimensions["hole_diameter"] = hole
        faces = _tag_round_faces(shape, has_bore=plate.hole_diameter is not None)
    built = BuiltGeometry(
        name=str(plate.name),
        pattern=COVER_PLATE_PATTERN,
        shape=shape,
        faces=faces,
        dimensions_mm=MappingProxyType(dimensions),
    )
    if not built.is_valid:  # pragma: no cover - guarded primitives are valid
        raise GeometryError("cover_plate pattern did not produce one valid positive-volume solid")
    return built


def _tag_shaft_faces(shape: Any) -> Mapping[str, tuple[Any, ...]]:
    """Tag the two shaft ends and its outside surface without topology indices."""
    tagged: dict[str, tuple[Any, ...]] = {}
    for face in shape.faces():
        if face.geom_type.name == "PLANE":
            tag = "driven_end" if face.normal_at().Z > 0 else "drive_end"
        elif face.geom_type.name == "CYLINDER":
            tag = "outside_surface"
        else:  # pragma: no cover - a cylinder primitive cannot produce another surface
            raise GeometryError(
                f"transmission_shaft produced an unexpected {face.geom_type.name} face"
            )
        tagged[tag] = (face,)
    expected = {"drive_end", "driven_end", "outside_surface"}
    if set(tagged) != expected:  # pragma: no cover - primitive topology corruption guard
        raise GeometryError(f"transmission_shaft face tagging incomplete: got {sorted(tagged)}")
    return MappingProxyType(tagged)


def build_transmission_shaft(
    shaft: TransmissionShaft, *, name: str = "transmission-shaft"
) -> BuiltGeometry:
    """Build an audited prismatic solid-round shaft from its declared diameter and length."""
    if shaft.length is None:
        raise GeometryError("transmission_shaft geometry needs element_params.length")
    diameter = _positive_mm(shaft.diameter, "diameter", element="transmission_shaft")
    length = _positive_mm(shaft.length, "length", element="transmission_shaft")
    Align, _Box, Cylinder, _export_step = _kernel()
    shape = Cylinder(
        diameter / 2,
        length,
        align=(Align.CENTER, Align.CENTER, Align.MIN),
    )
    built = BuiltGeometry(
        name=name,
        pattern=TRANSMISSION_SHAFT_PATTERN,
        shape=shape,
        faces=_tag_shaft_faces(shape),
        dimensions_mm=MappingProxyType({"diameter": diameter, "length": length}),
    )
    if not built.is_valid:  # pragma: no cover - guarded Cylinder dimensions are valid
        raise GeometryError(
            "transmission_shaft pattern did not produce one valid positive-volume solid"
        )
    return built


def build_spec(spec: DesignSpec) -> BuiltGeometry:
    """Build the audited geometry pattern selected by a Design Spec."""
    try:
        if spec.element_type == "base_plate":
            return build_base_plate(BasePlate(**dict(spec.element_params)))
        if spec.element_type == "cover_plate":
            return build_cover_plate(CoverPlate(**dict(spec.element_params)))
        if spec.element_type == "transmission_shaft":
            return build_transmission_shaft(
                TransmissionShaft(**dict(spec.element_params)), name=str(spec.name)
            )
    except ValueError as failure:
        raise GeometryError(f"invalid {spec.element_type} element_params: {failure}") from failure
    tag = spec.element_type or "<undeclared>"
    raise UnsupportedGeometry(
        f"no audited geometry pattern is registered for element_type {tag!r}; "
        "supported: base_plate, cover_plate, transmission_shaft"
    )


def _render_round_geometry(
    built: BuiltGeometry,
    *,
    view: Literal["iso", "front", "top", "right"],
    width_px: int,
) -> RenderedViewport:
    """Render a Z-axis disk, annulus, or shaft with exact SVG curves."""
    height_px = max(64, round(width_px * 0.75))
    cx, cy = width_px / 2, height_px / 2
    diameter = built.dimensions_mm["diameter"]
    is_shaft = built.pattern == TRANSMISSION_SHAFT_PATTERN
    axial_size = built.dimensions_mm["length" if is_shaft else "thickness"]
    bottom_tag = "drive_end" if is_shaft else "bottom"
    top_tag = "driven_end" if is_shaft else "top"
    perimeter_tag = "outside_surface" if is_shaft else "perimeter"
    radius = min(width_px, height_px) * 0.42
    wall = max(3.0, radius * axial_size / diameter)
    if is_shaft and view != "top":
        # A plate is normally much wider than it is thick, while a shaft is normally the
        # opposite. Scaling both from the radius made a 600 x 55 mm shaft thousands of
        # pixels tall and clipped both ends outside a 600 px viewport. Fit the full axial
        # extent for the shaft views, including the projected end ellipse in isometric.
        projected_length = axial_size + (diameter * 0.42 if view == "iso" else 0)
        scale = min(width_px * 0.84 / diameter, height_px * 0.84 / projected_length)
        radius = diameter * scale / 2
        wall = axial_size * scale
    bore_radius = radius * built.dimensions_mm.get("hole_diameter", 0) / diameter
    if view == "top":
        body = [
            f'<circle data-face="{bottom_tag}" cx="{cx:.3f}" cy="{cy:.3f}" r="{radius:.3f}" '
            'fill="#dbeafe" stroke="#0f172a" stroke-width="1.5"/>',
            f'<circle data-face="{top_tag}" cx="{cx:.3f}" cy="{cy:.3f}" r="{radius:.3f}" '
            'fill="#eff6ff" stroke="#0f172a" stroke-width="1.5"/>',
            f'<circle data-face="{perimeter_tag}" cx="{cx:.3f}" cy="{cy:.3f}" r="{radius:.3f}" '
            'fill="none" stroke="#0f172a" stroke-width="2"/>',
        ]
        if bore_radius:
            body.append(
                f'<circle data-face="bore" cx="{cx:.3f}" cy="{cy:.3f}" '
                f'r="{bore_radius:.3f}" fill="#ffffff" stroke="#0f172a" stroke-width="1.5"/>'
            )
    elif view == "iso":
        ry = radius * 0.42
        top_y = cy - wall / 2
        bottom_y = cy + wall / 2
        body = [
            f'<ellipse data-face="{bottom_tag}" cx="{cx:.3f}" cy="{bottom_y:.3f}" '
            f'rx="{radius:.3f}" ry="{ry:.3f}" fill="#bfdbfe" stroke="#0f172a"/>',
            f'<path data-face="{perimeter_tag}" d="M {cx - radius:.3f} {top_y:.3f} '
            f"L {cx - radius:.3f} {bottom_y:.3f} A {radius:.3f} {ry:.3f} 0 0 0 "
            f'{cx + radius:.3f} {bottom_y:.3f} L {cx + radius:.3f} {top_y:.3f} Z" '
            'fill="#93c5fd" stroke="#0f172a" stroke-width="1.5"/>',
            f'<ellipse data-face="{top_tag}" cx="{cx:.3f}" cy="{top_y:.3f}" '
            f'rx="{radius:.3f}" ry="{ry:.3f}" fill="#eff6ff" stroke="#0f172a"/>',
        ]
        if bore_radius:
            body.append(
                f'<ellipse data-face="bore" cx="{cx:.3f}" cy="{top_y:.3f}" '
                f'rx="{bore_radius:.3f}" ry="{bore_radius * 0.42:.3f}" '
                'fill="#ffffff" stroke="#0f172a" stroke-width="1.5"/>'
            )
    else:
        left, top = cx - radius, cy - wall / 2
        body = [
            f'<line data-face="{bottom_tag}" x1="{left:.3f}" y1="{top + wall:.3f}" '
            f'x2="{left + 2 * radius:.3f}" y2="{top + wall:.3f}" stroke="#0f172a"/>',
            f'<rect data-face="{perimeter_tag}" x="{left:.3f}" y="{top:.3f}" '
            f'width="{2 * radius:.3f}" height="{wall:.3f}" fill="#bfdbfe" '
            'stroke="#0f172a" stroke-width="1.5"/>',
            f'<line data-face="{top_tag}" x1="{left:.3f}" y1="{top:.3f}" '
            f'x2="{left + 2 * radius:.3f}" y2="{top:.3f}" stroke="#0f172a"/>',
        ]
        if bore_radius:
            body.append(
                f'<path data-face="bore" d="M {cx - bore_radius:.3f} {top:.3f} '
                f'V {top + wall:.3f} M {cx + bore_radius:.3f} {top:.3f} V {top + wall:.3f}" '
                'fill="none" stroke="#475569" stroke-dasharray="4 3"/>'
            )
    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_px}" height="{height_px}" '
        f'viewBox="0 0 {width_px} {height_px}" role="img" '
        f'aria-label="{escape(built.name)} {view} viewport">\n'
        f'<rect width="{width_px}" height="{height_px}" fill="#ffffff"/>\n'
        + "\n".join(body)
        + "\n</svg>\n"
    ).encode("utf-8")
    return RenderedViewport(view=view, width_px=width_px, height_px=height_px, data=svg)


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
    if built.pattern not in {
        BASE_PLATE_PATTERN,
        COVER_PLATE_PATTERN,
        TRANSMISSION_SHAFT_PATTERN,
    }:
        raise UnsupportedGeometry(f"viewport rendering has no projector for {built.pattern!r}")
    if not 64 <= width_px <= 4096:
        raise GeometryError(f"viewport width_px must be from 64 through 4096; got {width_px}")
    if view not in {"iso", "front", "top", "right"}:
        raise GeometryError(f"unknown viewport {view!r}; choose iso, front, top, or right")
    if "diameter" in built.dimensions_mm:
        return _render_round_geometry(built, view=view, width_px=width_px)
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
        "length": (
            float(bounds.size.Z if built.pattern == TRANSMISSION_SHAFT_PATTERN else bounds.size.Y),
            "drive-to-driven extent"
            if built.pattern == TRANSMISSION_SHAFT_PATTERN
            else "north-south extent",
        ),
        "plate_thickness": (float(bounds.size.Z), "bottom-top extent"),
        "thickness": (float(bounds.size.Z), "bottom-top extent"),
        "diameter": (float(max(bounds.size.X, bounds.size.Y)), "outside diameter"),
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
    if query == "hole_diameter" and (faces := built.faces.get("bore")):
        thickness = float(bounds.size.Z)
        diameter = sum(face.area for face in faces) / (3.141592653589793 * thickness)
        return GeometryMeasurement(
            query=query,
            value=float(diameter),
            unit="mm",
            feature="bore",
        )
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
    supported = "volume, a declared dimension, face_count, hole_diameter, or area:<semantic-face>"
    raise GeometryError(f"unsupported geometry query {query!r}; choose {supported}")


def _step_string(value: str) -> str:
    """Escape one ISO 10303 string literal payload."""
    return value.replace("'", "''")


def _write_step_shape(
    built: BuiltGeometry,
    path: Path,
    *,
    schema: Literal["ap242", "ap214"],
) -> None:
    """Write STEP with CAx-IF part-level properties and contain global settings."""
    try:
        from build123d import CenterOf
        from OCP.gp import gp_Pnt  # type: ignore[import-untyped]
        from OCP.IFSelect import IFSelect_ReturnStatus  # type: ignore[import-untyped]
        from OCP.Interface import Interface_Static  # type: ignore[import-untyped]
        from OCP.Message import Message, Message_Gravity  # type: ignore[import-untyped]
        from OCP.STEPCAFControl import (  # type: ignore[import-untyped]
            STEPCAFControl_Controller,
            STEPCAFControl_Writer,
        )
        from OCP.STEPControl import (  # type: ignore[import-untyped]
            STEPControl_Controller,
            STEPControl_StepModelType,
        )
        from OCP.TCollection import TCollection_ExtendedString  # type: ignore[import-untyped]
        from OCP.TDataStd import TDataStd_Name  # type: ignore[import-untyped]
        from OCP.TDocStd import TDocStd_Document  # type: ignore[import-untyped]
        from OCP.XCAFApp import XCAFApp_Application  # type: ignore[import-untyped]
        from OCP.XCAFDoc import (  # type: ignore[import-untyped]
            XCAFDoc_Area,
            XCAFDoc_Centroid,
            XCAFDoc_DocumentTool,
            XCAFDoc_Volume,
        )
        from OCP.XSControl import XSControl_WorkSession  # type: ignore[import-untyped]
    except ImportError as failure:  # pragma: no cover - guarded by the geometry extra
        raise GeometryUnavailable(
            "3D geometry needs the optional dependency; install anvilate[geometry]"
        ) from failure

    with _STEP_IO_LOCK:
        document = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
        application = XCAFApp_Application.GetApplication_s()
        application.NewDocument(TCollection_ExtendedString("MDTV-XCAF"), document)
        application.InitDocument(document)
        XCAFDoc_DocumentTool.SetLengthUnit_s(document, 0.001)
        shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
        label = shape_tool.AddShape(built.shape.wrapped, False)
        TDataStd_Name.Set_s(label, TCollection_ExtendedString(built.name))
        centroid = built.shape.center(CenterOf.MASS)
        coordinates = tuple(0.0 if abs(value) < 1e-12 else float(value) for value in centroid)
        XCAFDoc_Volume.Set_s(label, built.volume_mm3)
        XCAFDoc_Area.Set_s(label, float(built.shape.area))
        XCAFDoc_Centroid.Set_s(label, gp_Pnt(*coordinates))

        STEPCAFControl_Controller.Init_s()
        STEPControl_Controller.Init_s()
        previous_schema = Interface_Static.CVal_s("write.step.schema")
        try:
            setting = "AP242DIS" if schema == "ap242" else "AP214IS"
            if not Interface_Static.SetCVal_s("write.step.schema", setting):
                raise GeometryError(f"the installed geometry kernel cannot select {schema.upper()}")
            messenger = Message.DefaultMessenger_s()
            for printer in messenger.Printers():
                printer.SetTraceLevel(Message_Gravity.Message_Fail)
            writer = STEPCAFControl_Writer(XSControl_WorkSession(), False)
            writer.SetNameMode(True)
            writer.SetPropsMode(True)
            if not writer.Transfer(document, STEPControl_StepModelType.STEPControl_AsIs):
                raise GeometryError("STEP writer could not transfer the built solid")
            if writer.Write(str(path)) != IFSelect_ReturnStatus.IFSelect_RetDone:
                raise GeometryError("STEP writer could not write the built solid")
        except Exception:
            path.unlink(missing_ok=True)
            raise
        finally:
            Interface_Static.SetCVal_s("write.step.schema", previous_schema)


def read_step_validation_properties(path: Path) -> StepValidationProperties:
    """Read the 3 CAx-IF part-level validation properties from one STEP part."""
    try:
        from OCP.IFSelect import IFSelect_ReturnStatus  # type: ignore[import-untyped]
        from OCP.STEPCAFControl import STEPCAFControl_Reader  # type: ignore[import-untyped]
        from OCP.TCollection import TCollection_ExtendedString  # type: ignore[import-untyped]
        from OCP.TDF import TDF_LabelSequence  # type: ignore[import-untyped]
        from OCP.TDocStd import TDocStd_Document  # type: ignore[import-untyped]
        from OCP.XCAFApp import XCAFApp_Application  # type: ignore[import-untyped]
        from OCP.XCAFDoc import (  # type: ignore[import-untyped]
            XCAFDoc_Area,
            XCAFDoc_Centroid,
            XCAFDoc_DocumentTool,
            XCAFDoc_Volume,
        )
    except ImportError as failure:  # pragma: no cover - guarded by the geometry extra
        raise GeometryUnavailable(
            "STEP validation needs the optional dependency; install anvilate[geometry]"
        ) from failure

    with _STEP_IO_LOCK:
        reader = STEPCAFControl_Reader()
        reader.SetPropsMode(True)
        if reader.ReadFile(str(path)) != IFSelect_ReturnStatus.IFSelect_RetDone:
            raise GeometryError(f"could not read STEP file {path}")
        document = TDocStd_Document(TCollection_ExtendedString("XmlOcaf"))
        application = XCAFApp_Application.GetApplication_s()
        application.NewDocument(TCollection_ExtendedString("MDTV-XCAF"), document)
        application.InitDocument(document)
        if not reader.Transfer(document):
            raise GeometryError(f"could not transfer STEP file {path}")
        labels = TDF_LabelSequence()
        XCAFDoc_DocumentTool.ShapeTool_s(document.Main()).GetFreeShapes(labels)
        if labels.Length() != 1:
            raise GeometryError(
                f"STEP integrity verification needs one part; found {labels.Length()}"
            )
        label = labels.Value(1)
        area = XCAFDoc_Area()
        volume = XCAFDoc_Volume()
        centroid = XCAFDoc_Centroid()
        missing = [
            name
            for name, attribute_type, attribute in (
                ("surface area", XCAFDoc_Area, area),
                ("volume", XCAFDoc_Volume, volume),
                ("centroid", XCAFDoc_Centroid, centroid),
            )
            if not label.FindAttribute(attribute_type.GetID_s(), attribute)
        ]
        if missing:
            raise GeometryError("STEP is missing validation properties: " + ", ".join(missing))
        point = centroid.Get()
        properties = StepValidationProperties(
            volume_mm3=float(volume.Get()),
            surface_area_mm2=float(area.Get()),
            centroid_mm=(float(point.X()), float(point.Y()), float(point.Z())),
        )
        values = (
            properties.volume_mm3,
            properties.surface_area_mm2,
            *properties.centroid_mm,
        )
        if not all(isfinite(value) for value in values):
            raise GeometryError("STEP validation properties must all be finite")
        if properties.volume_mm3 <= 0 or properties.surface_area_mm2 <= 0:
            raise GeometryError("STEP volume and surface-area properties must be positive")
        return properties


def verify_step_integrity(path: Path) -> StepValidationProperties:
    """Verify imported geometry against CAx-IF v4.6 industry example thresholds."""
    try:
        from build123d import CenterOf, import_step
    except ImportError as failure:  # pragma: no cover - guarded by the geometry extra
        raise GeometryUnavailable(
            "STEP validation needs the optional dependency; install anvilate[geometry]"
        ) from failure
    expected = read_step_validation_properties(path)
    received = import_step(path)
    if not received.is_valid or len(received.solids()) != 1:
        raise GeometryError("received STEP geometry is not one valid solid")
    volume_deviation = abs(float(received.volume) - expected.volume_mm3) / expected.volume_mm3
    area_deviation = (
        abs(float(received.area) - expected.surface_area_mm2) / expected.surface_area_mm2
    )
    center = received.center(CenterOf.MASS)
    centroid_deviation = sqrt(
        sum(
            (actual - stated) ** 2
            for actual, stated in zip(center, expected.centroid_mm, strict=True)
        )
    )
    size = received.bounding_box().size
    centroid_limit = 0.02 + (0.001 * sqrt(size.X**2 + size.Y**2 + size.Z**2))
    failures = []
    if volume_deviation >= 0.005:
        failures.append(f"volume differs by {volume_deviation:.3%}")
    if area_deviation >= 0.005:
        failures.append(f"surface area differs by {area_deviation:.3%}")
    if centroid_deviation >= centroid_limit:
        failures.append(
            f"centroid differs by {centroid_deviation:g} mm (limit {centroid_limit:g} mm)"
        )
    if failures:
        raise GeometryError("STEP geometric validation failed: " + "; ".join(failures))
    return expected


def write_step(
    built: BuiltGeometry,
    path: Path,
    *,
    authorization: ExportAuthorization,
    schema: Literal["ap242", "ap214"] = "ap242",
) -> Path:
    """Write one authorized solid as deterministic, watermarked STEP and return its path."""
    if not built.is_valid:
        raise GeometryError("refusing to write invalid geometry")
    if schema not in {"ap242", "ap214"}:
        raise GeometryError(f"unsupported STEP schema {schema!r}; choose ap242 or ap214")
    _write_step_shape(built, path, schema=schema)
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as failure:
        path.unlink(missing_ok=True)
        raise GeometryError(
            "STEP writer produced a non-UTF-8 file; refusing to release it"
        ) from failure
    expected_schema = _AP242_SCHEMA if schema == "ap242" else _AP214_SCHEMA
    if expected_schema not in text:
        path.unlink(missing_ok=True)
        raise GeometryError(f"STEP writer did not declare {schema.upper()}; refusing to release it")
    descriptions = [
        "Open CASCADE Model",
        _GVP_RECOMMENDED_PRACTICE,
        *(f"{key}={value}" for key, value in authorization.metadata()),
    ]
    product_name = _step_string(built.name)
    text, products_changed = re.subn(
        r"PRODUCT\('(?:[^']|'')*'\s*,\s*'(?:[^']|'')*'\s*,",
        lambda _match: f"PRODUCT('{product_name}','{product_name}',",
        text,
        count=1,
    )
    header = (
        "FILE_DESCRIPTION(("
        + ",".join(f"'{_step_string(value)}'" for value in descriptions)
        + "),'2;1');"
    )
    text, descriptions_changed = re.subn(r"FILE_DESCRIPTION\(.*?\);", header, text, count=1)
    filename = f"FILE_NAME('{_step_string(built.name)}','2000-01-01T00:00:00',"
    text, filename_changed = re.subn(
        r"FILE_NAME\('[^']*','[^']*',", lambda _match: filename, text, count=1
    )
    if products_changed != 1 or descriptions_changed != 1 or filename_changed != 1:
        path.unlink(missing_ok=True)
        raise GeometryError(
            "STEP writer produced an unrecognized header; refusing an unstamped file"
        )
    path.write_text(text, encoding="utf-8")
    try:
        verify_step_integrity(path)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    return path
