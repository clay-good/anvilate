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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from html import escape
from itertools import combinations
from math import isfinite, pi, sqrt
from pathlib import Path
from threading import Lock
from types import MappingProxyType
from typing import Annotated, Any, Literal

from pydantic import Field, FiniteFloat, model_validator

from ._models import FrozenMap, Named, Provenance, StatableModel
from .derivation import DerivationAbsence, Underived
from .export.gate import ExportAuthorization
from .packs.industrial import CoverPlate
from .packs.machinery import TransmissionShaft
from .packs.structural import BasePlate
from .packs.timber import TimberBeam
from .scorecard import CheckStatus, Scorecard, ScorecardEntry
from .spec import CircularLocator, DesignSpec, HolePattern, InterfaceContract, InterfaceFrame
from .units import Quantity

__all__ = [
    "BASE_PLATE_PATTERN",
    "COVER_PLATE_PATTERN",
    "TRANSMISSION_SHAFT_PATTERN",
    "TIMBER_BEAM_PATTERN",
    "BuiltGeometry",
    "GeometryError",
    "GeometrySummary",
    "GeometryMeasurement",
    "GeometryUnavailable",
    "ConfirmedStepInterface",
    "ConfirmedPlanarContact",
    "PlanarContactAreaCheck",
    "ConfirmedCylindricalMate",
    "CylindricalMateEngagementCheck",
    "ConfirmedPlanarGap",
    "PlanarGapClearanceCheck",
    "CylindricalMateFitCheck",
    "FitFeatureCheck",
    "CircularFeatureCandidate",
    "CylindricalMatingCandidate",
    "HolePatternCandidate",
    "PlanarInterfaceCandidate",
    "PlanarContactCandidate",
    "PlanarGapCandidate",
    "SolidInterferenceCandidate",
    "RenderedViewport",
    "StepValidationProperties",
    "StepInterfaceCandidates",
    "StepSolidCandidate",
    "UnsupportedGeometry",
    "ViewportImage",
    "build_base_plate",
    "build_cover_plate",
    "build_transmission_shaft",
    "build_timber_beam",
    "build_spec",
    "confirm_step_interface",
    "confirm_planar_contact",
    "check_planar_contact_area",
    "confirm_cylindrical_mate",
    "check_cylindrical_mate_engagement",
    "confirm_planar_gap",
    "check_planar_gap_clearance",
    "check_cylindrical_mate_fit",
    "detect_step_interfaces",
    "measure_geometry",
    "render_viewport",
    "read_step_validation_properties",
    "verify_step_integrity",
    "write_step",
    "render_3mf",
]

BASE_PLATE_PATTERN = "base_plate/1"
COVER_PLATE_PATTERN = "cover_plate/1"
TRANSMISSION_SHAFT_PATTERN = "transmission_shaft/1"
TIMBER_BEAM_PATTERN = "timber_beam/1"
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


class PlanarContactCandidate(StatableModel):
    """One exact coplanar overlap between opposing faces on different imported solids."""

    id: Named
    first_solid_id: Named
    first_face_candidate_id: Named
    second_solid_id: Named
    second_face_candidate_id: Named
    overlap_area_mm2: Annotated[FiniteFloat, Field(gt=0)]

    @model_validator(mode="after")
    def _joins_two_different_solids(self) -> PlanarContactCandidate:
        if self.first_solid_id == self.second_solid_id:
            raise ValueError("a planar contact candidate must join two different solids")
        return self


class PlanarGapCandidate(StatableModel):
    """One projected overlap between separated opposing faces on different solids."""

    id: Named
    first_solid_id: Named
    first_face_candidate_id: Named
    second_solid_id: Named
    second_face_candidate_id: Named
    separation_mm: Annotated[FiniteFloat, Field(gt=0)]
    overlap_area_mm2: Annotated[FiniteFloat, Field(gt=0)]
    direction: tuple[FiniteFloat, FiniteFloat, FiniteFloat]

    @model_validator(mode="after")
    def _is_one_directed_pair(self) -> PlanarGapCandidate:
        if self.first_solid_id == self.second_solid_id:
            raise ValueError("a planar gap candidate must join two different solids")
        direction_length = sqrt(sum(component**2 for component in self.direction))
        if abs(direction_length - 1) > 1e-9:
            raise ValueError("planar gap direction must be a unit vector")
        return self


class SolidInterferenceCandidate(StatableModel):
    """One positive-volume B-Rep intersection between different imported solids."""

    id: Named
    first_solid_id: Named
    second_solid_id: Named
    overlap_volume_mm3: Annotated[FiniteFloat, Field(gt=0)]
    center_mm: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    bounds_min_mm: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    bounds_max_mm: tuple[FiniteFloat, FiniteFloat, FiniteFloat]

    @model_validator(mode="after")
    def _is_one_bounded_pair(self) -> SolidInterferenceCandidate:
        if self.first_solid_id == self.second_solid_id:
            raise ValueError("a solid interference must join two different solids")
        if any(
            low > high for low, high in zip(self.bounds_min_mm, self.bounds_max_mm, strict=True)
        ):
            raise ValueError("interference bounds minimum must not exceed its maximum")
        if any(
            center < low or center > high
            for center, low, high in zip(
                self.center_mm, self.bounds_min_mm, self.bounds_max_mm, strict=True
            )
        ):
            raise ValueError("interference bounds must contain its center")
        return self


class CylindricalMatingCandidate(StatableModel):
    """One coaxial bore/shaft pair measured between different imported solids."""

    id: Named
    bore_solid_id: Named
    bore_surface_id: Named
    shaft_solid_id: Named
    shaft_surface_id: Named
    bore_diameter_mm: Annotated[FiniteFloat, Field(gt=0)]
    shaft_diameter_mm: Annotated[FiniteFloat, Field(gt=0)]
    diametral_clearance_mm: FiniteFloat
    axial_engagement_mm: Annotated[FiniteFloat, Field(gt=0)]
    axis_origin_mm: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    axis_direction: tuple[FiniteFloat, FiniteFloat, FiniteFloat]

    @model_validator(mode="after")
    def _is_one_consistent_pair(self) -> CylindricalMatingCandidate:
        if self.bore_solid_id == self.shaft_solid_id:
            raise ValueError("a cylindrical mating candidate must join two different solids")
        expected = self.bore_diameter_mm - self.shaft_diameter_mm
        if abs(self.diametral_clearance_mm - expected) > 1e-9:
            raise ValueError("diametral clearance must equal bore diameter minus shaft diameter")
        axis_length = sqrt(sum(component**2 for component in self.axis_direction))
        if abs(axis_length - 1) > 1e-9:
            raise ValueError("cylindrical mating axis_direction must be a unit vector")
        return self


class StepSolidCandidate(StatableModel):
    """One imported solid identified by deterministic measured geometry."""

    id: Named
    volume_mm3: Annotated[FiniteFloat, Field(gt=0)]
    center_mm: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    bounds_min_mm: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    bounds_max_mm: tuple[FiniteFloat, FiniteFloat, FiniteFloat]

    @model_validator(mode="after")
    def _bounds_contain_the_center(self) -> StepSolidCandidate:
        if any(
            low > high for low, high in zip(self.bounds_min_mm, self.bounds_max_mm, strict=True)
        ):
            raise ValueError("solid bounds minimum must not exceed its maximum")
        if any(
            center < low or center > high
            for center, low, high in zip(
                self.center_mm, self.bounds_min_mm, self.bounds_max_mm, strict=True
            )
        ):
            raise ValueError("solid bounds must contain its center")
        return self


class StepInterfaceCandidates(StatableModel):
    """Deterministic interface candidates measured from one imported STEP part."""

    source_name: Named
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    solids: tuple[StepSolidCandidate, ...] = ()
    planar_faces: tuple[PlanarInterfaceCandidate, ...]
    planar_contacts: tuple[PlanarContactCandidate, ...] = ()
    planar_gaps: tuple[PlanarGapCandidate, ...] = ()
    cylindrical_mates: tuple[CylindricalMatingCandidate, ...] = ()
    solid_interferences: tuple[SolidInterferenceCandidate, ...] = ()
    interference_scorecard: Scorecard | None = None
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


class ConfirmedPlanarContact(StatableModel):
    """One exact planar contact candidate accepted by a named person."""

    source_name: Named
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    contact_candidate_id: Named
    name: Named
    first_solid_id: Named
    first_face_candidate_id: Named
    second_solid_id: Named
    second_face_candidate_id: Named
    overlap_area_mm2: Annotated[FiniteFloat, Field(gt=0)]
    confirmed_by: Named


class PlanarContactAreaCheck(StatableModel):
    """A confirmed planar contact checked against one cited minimum overlap area."""

    confirmed_contact: ConfirmedPlanarContact
    minimum_overlap_area_mm2: Annotated[FiniteFloat, Field(ge=0)]
    margin_above_minimum_mm2: FiniteFloat
    status: Literal["pass", "fail"]
    reference: Provenance

    @model_validator(mode="after")
    def _matches_its_minimum(self) -> PlanarContactAreaCheck:
        expected_margin = self.confirmed_contact.overlap_area_mm2 - self.minimum_overlap_area_mm2
        if abs(self.margin_above_minimum_mm2 - expected_margin) > 1e-9:
            raise ValueError("contact-area margin must match the measured overlap")
        expected_status = "pass" if expected_margin >= 0 else "fail"
        if self.status != expected_status:
            raise ValueError("contact-area status must match the measured overlap and minimum")
        return self


class ConfirmedPlanarGap(StatableModel):
    """One planar gap candidate accepted by a named person."""

    source_name: Named
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    gap_candidate_id: Named
    name: Named
    first_solid_id: Named
    first_face_candidate_id: Named
    second_solid_id: Named
    second_face_candidate_id: Named
    separation_mm: Annotated[FiniteFloat, Field(gt=0)]
    overlap_area_mm2: Annotated[FiniteFloat, Field(gt=0)]
    direction: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    confirmed_by: Named

    @model_validator(mode="after")
    def _preserves_one_directed_pair(self) -> ConfirmedPlanarGap:
        if self.first_solid_id == self.second_solid_id:
            raise ValueError("a confirmed planar gap must join two different solids")
        direction_length = sqrt(sum(component**2 for component in self.direction))
        if abs(direction_length - 1) > 1e-9:
            raise ValueError("confirmed planar gap direction must be a unit vector")
        return self


class PlanarGapClearanceCheck(StatableModel):
    """A confirmed planar gap checked against one cited clearance band."""

    confirmed_gap: ConfirmedPlanarGap
    minimum_gap_mm: Annotated[FiniteFloat, Field(ge=0)]
    maximum_gap_mm: Annotated[FiniteFloat, Field(ge=0)]
    margin_above_minimum_mm: FiniteFloat
    margin_below_maximum_mm: FiniteFloat
    status: Literal["pass", "fail"]
    reference: Provenance

    @model_validator(mode="after")
    def _matches_its_band(self) -> PlanarGapClearanceCheck:
        if self.minimum_gap_mm > self.maximum_gap_mm:
            raise ValueError("minimum gap must not exceed maximum gap")
        separation = self.confirmed_gap.separation_mm
        expected_lower = separation - self.minimum_gap_mm
        expected_upper = self.maximum_gap_mm - separation
        if abs(self.margin_above_minimum_mm - expected_lower) > 1e-9:
            raise ValueError("minimum-gap margin must match the measured separation")
        if abs(self.margin_below_maximum_mm - expected_upper) > 1e-9:
            raise ValueError("maximum-gap margin must match the measured separation")
        expected_status = "pass" if expected_lower >= 0 and expected_upper >= 0 else "fail"
        if self.status != expected_status:
            raise ValueError("gap-check status must match the measured separation and band")
        return self


class ConfirmedCylindricalMate(StatableModel):
    """One cylindrical mating candidate accepted by a named person."""

    source_name: Named
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    mate_candidate_id: Named
    name: Named
    bore_solid_id: Named
    bore_surface_id: Named
    shaft_solid_id: Named
    shaft_surface_id: Named
    bore_diameter_mm: Annotated[FiniteFloat, Field(gt=0)]
    shaft_diameter_mm: Annotated[FiniteFloat, Field(gt=0)]
    diametral_clearance_mm: FiniteFloat
    axial_engagement_mm: Annotated[FiniteFloat, Field(gt=0)]
    axis_origin_mm: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    axis_direction: tuple[FiniteFloat, FiniteFloat, FiniteFloat]
    confirmed_by: Named

    @model_validator(mode="after")
    def _preserves_consistent_geometry(self) -> ConfirmedCylindricalMate:
        if self.bore_solid_id == self.shaft_solid_id:
            raise ValueError("a confirmed cylindrical mate must join two different solids")
        expected = self.bore_diameter_mm - self.shaft_diameter_mm
        if abs(self.diametral_clearance_mm - expected) > 1e-9:
            raise ValueError("diametral clearance must equal bore diameter minus shaft diameter")
        axis_length = sqrt(sum(component**2 for component in self.axis_direction))
        if abs(axis_length - 1) > 1e-9:
            raise ValueError("confirmed cylindrical mate axis_direction must be a unit vector")
        return self


class CylindricalMateEngagementCheck(StatableModel):
    """A confirmed cylindrical mate checked against one cited minimum engagement."""

    confirmed_mate: ConfirmedCylindricalMate
    minimum_axial_engagement_mm: Annotated[FiniteFloat, Field(ge=0)]
    margin_above_minimum_mm: FiniteFloat
    status: Literal["pass", "fail"]
    reference: Provenance

    @model_validator(mode="after")
    def _matches_its_minimum(self) -> CylindricalMateEngagementCheck:
        expected_margin = self.confirmed_mate.axial_engagement_mm - self.minimum_axial_engagement_mm
        if abs(self.margin_above_minimum_mm - expected_margin) > 1e-9:
            raise ValueError("engagement margin must match the measured axial engagement")
        expected_status = "pass" if expected_margin >= 0 else "fail"
        if self.status != expected_status:
            raise ValueError("engagement status must match the measured engagement and minimum")
        return self


class FitFeatureCheck(StatableModel):
    """One measured diameter checked against an explicit ISO 286 zone."""

    designation: Named
    measured_diameter_mm: Annotated[FiniteFloat, Field(gt=0)]
    minimum_diameter_mm: Annotated[FiniteFloat, Field(gt=0)]
    maximum_diameter_mm: Annotated[FiniteFloat, Field(gt=0)]
    within_zone: bool

    @model_validator(mode="after")
    def _matches_its_limits(self) -> FitFeatureCheck:
        if self.minimum_diameter_mm > self.maximum_diameter_mm:
            raise ValueError("fit feature minimum diameter must not exceed its maximum")
        expected = self.minimum_diameter_mm <= self.measured_diameter_mm <= self.maximum_diameter_mm
        if self.within_zone is not expected:
            raise ValueError("within_zone must match the measured diameter and limits")
        return self


class CylindricalMateFitCheck(StatableModel):
    """A confirmed cylindrical mate checked against a caller-supplied ISO 286 fit."""

    confirmed_mate: ConfirmedCylindricalMate
    basic_size_mm: Annotated[FiniteFloat, Field(gt=0)]
    fit_designation: Named
    fit_kind: Literal["clearance", "transition", "interference"]
    minimum_design_clearance_mm: FiniteFloat
    maximum_design_clearance_mm: FiniteFloat
    hole: FitFeatureCheck
    shaft: FitFeatureCheck
    measured_clearance_within_design_range: bool
    status: Literal["pass", "fail"]
    reference: Provenance

    @model_validator(mode="after")
    def _matches_its_checks(self) -> CylindricalMateFitCheck:
        if self.minimum_design_clearance_mm > self.maximum_design_clearance_mm:
            raise ValueError("minimum design clearance must not exceed maximum design clearance")
        measured = self.confirmed_mate.diametral_clearance_mm
        clearance_ok = (
            self.minimum_design_clearance_mm <= measured <= self.maximum_design_clearance_mm
        )
        if self.measured_clearance_within_design_range is not clearance_ok:
            raise ValueError("measured clearance result must match the design clearance range")
        expected_status = "pass" if self.hole.within_zone and self.shaft.within_zone else "fail"
        if self.status != expected_status:
            raise ValueError("fit-check status must match the hole and shaft checks")
        return self


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


@dataclass(frozen=True)
class _CylindricalSurface:
    id: str
    solid_id: str
    inward: bool
    radius: float
    axis_origin: _Point3D
    axis_direction: _Point3D
    start: float
    end: float


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


def _canonical_axis(position: _Point3D, direction: _Point3D) -> tuple[_Point3D, _Point3D]:
    """A direction-independent identity for one infinite axis line."""
    unit = _normalized(direction)
    first = next(component for component in unit if abs(component) > 1e-12)
    if first < 0:
        unit = (-unit[0], -unit[1], -unit[2])
    origin = _point_along(position, unit, -_dot(position, unit))
    return _rounded_point(origin), _rounded_point(unit)


def _solid_measurements(solid: Any) -> tuple[float, _Point3D, _Point3D, _Point3D]:
    bounds = solid.bounding_box()
    return (
        round(float(solid.volume), 9),
        _rounded_point(_coordinates(solid.center())),
        _rounded_point(_coordinates(bounds.min)),
        _rounded_point(_coordinates(bounds.max)),
    )


def _interference_scorecard(
    candidates: tuple[SolidInterferenceCandidate, ...], *, pair_count: int
) -> Scorecard:
    if candidates:
        entries = tuple(
            ScorecardEntry(
                name=f"solid interference {candidate.first_solid_id}/{candidate.second_solid_id}",
                status=CheckStatus.FAIL,
                detail=(
                    f"positive common volume {candidate.overlap_volume_mm3:g} mm³ between "
                    f"{candidate.first_solid_id} and {candidate.second_solid_id}"
                ),
                reference="assembly-robotics: Assembly-level validation",
                underived=Underived(
                    kind=DerivationAbsence.NUMERIC_RESULT,
                    reason="the verdict comes from an exact B-Rep common-volume operation",
                ),
            )
            for candidate in candidates
        )
    else:
        entries = (
            ScorecardEntry(
                name="solid interference",
                status=CheckStatus.PASS,
                detail=f"0 positive-volume intersections across {pair_count} solid pairs",
                reference="assembly-robotics: Assembly-level validation",
                underived=Underived(
                    kind=DerivationAbsence.NUMERIC_RESULT,
                    reason="the verdict comes from exact B-Rep common-volume operations",
                ),
            ),
        )
    return Scorecard(entries=entries)


def _read_step_geometry(path: Path) -> Any:
    """The geometry a STEP file carries, read without its assembly and product structure.

    build123d's ``import_step`` walks the file's XCAF document to name each part, and on
    NIST's CTC 02 AP242 test model (a valid file the CAx-IF uses) reading a label name
    segfaulted the process: exit 139, no exception to catch, and whatever called the reader
    (the CLI, or an MCP server serving other requests) gone with it. Nothing here uses those
    names, so the file is read by OCCT's plain ``STEPControl_Reader``, which transfers the
    geometry and never touches the label tree. It also leaves each face with one placement,
    which is what assigning a face to the solid that owns it needs.
    """
    from build123d import Compound
    from OCP.BRep import BRep_Builder  # type: ignore[import-untyped]
    from OCP.IFSelect import IFSelect_RetDone  # type: ignore[import-untyped]
    from OCP.STEPControl import STEPControl_Reader  # type: ignore[import-untyped]
    from OCP.TopAbs import TopAbs_COMPOUND  # type: ignore[import-untyped]
    from OCP.TopoDS import TopoDS_Compound  # type: ignore[import-untyped]

    reader = STEPControl_Reader()
    if reader.ReadFile(str(path)) != IFSelect_RetDone:
        raise GeometryError(f"could not import STEP file {path}: the reader rejected it")
    if reader.TransferRoots() < 1:
        raise GeometryError(f"could not import STEP file {path}: it transfers no shape")
    shape = reader.OneShape()
    if shape.ShapeType() == TopAbs_COMPOUND:
        return Compound(shape)
    # A file holding one solid transfers as a bare TopoDS_Solid, and build123d's Compound
    # over one reports a volume of 0. It has to be a real compound around it.
    compound = TopoDS_Compound()
    builder = BRep_Builder()
    builder.MakeCompound(compound)
    builder.Add(compound, shape)
    return Compound(compound)


def detect_step_interfaces(path: Path) -> StepInterfaceCandidates:
    """Detect planar faces and regular equal-diameter through-hole patterns in STEP.

    The result is a set of candidates, not an accepted interface contract. The caller must
    choose a face and pattern before putting either into a Design Spec. Detection relies on
    imported B-Rep topology and measured geometry only; STEP mate semantics and entity order
    are ignored.
    """
    try:
        from build123d import Location
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
                shape = _read_step_geometry(path)
            finally:
                for printer in printers:
                    messenger.AddPrinter(printer)
    except GeometryError:
        raise  # already says which file and why
    except Exception as failure:
        raise GeometryError(f"could not import STEP file {path}: {failure}") from failure
    solids = list(shape.solids())
    if (
        not shape.is_valid
        or not solids
        or any(not solid.is_valid or solid.volume <= 0 for solid in solids)
    ):
        unusable = sum(1 for solid in solids if not solid.is_valid or solid.volume <= 0)
        raise GeometryError(
            "STEP interface detection needs valid positive-volume solids; the file has "
            f"{len(solids)} solid(s), {unusable} of them invalid or empty"
            + ("" if shape.is_valid else ", and its shape as a whole is not valid")
            + ". A file carrying only tessellated or surface geometry has no solid to read"
        )
    records = []
    for solid in solids:
        volume, center, minimum, maximum = _solid_measurements(solid)
        signature = {
            "volume": volume,
            "center": center,
            "minimum": minimum,
            "maximum": maximum,
        }
        records.append((_candidate_id("solid", signature), solid, volume, center, minimum, maximum))
    if len({record[0] for record in records}) != len(solids):
        raise GeometryError(
            "STEP interface detection cannot distinguish coincident solids with identical "
            "measured geometry"
        )
    solid_ids = {
        solid_id: solid for solid_id, solid, _volume, _center, _minimum, _maximum in records
    }
    solid_candidates = tuple(
        sorted(
            (
                StepSolidCandidate(
                    id=solid_id,
                    volume_mm3=volume,
                    center_mm=center,
                    bounds_min_mm=minimum,
                    bounds_max_mm=maximum,
                )
                for solid_id, _solid, volume, center, minimum, maximum in records
            ),
            key=lambda candidate: candidate.id,
        )
    )
    solid_interferences: list[SolidInterferenceCandidate] = []
    for (first_solid_id, first_solid), (second_solid_id, second_solid) in combinations(
        sorted(solid_ids.items()), 2
    ):
        try:
            overlap = first_solid & second_solid
        except Exception as failure:
            raise GeometryError(
                f"could not measure solid interference between {first_solid_id} and "
                f"{second_solid_id}: {failure}"
            ) from failure
        if overlap is None or float(overlap.volume) <= 1e-9:
            continue
        volume, center, minimum, maximum = _solid_measurements(overlap)
        signature = {
            "first_solid": first_solid_id,
            "second_solid": second_solid_id,
            "volume": volume,
            "center": center,
            "minimum": minimum,
            "maximum": maximum,
        }
        solid_interferences.append(
            SolidInterferenceCandidate(
                id=_candidate_id("interference", signature),
                first_solid_id=first_solid_id,
                second_solid_id=second_solid_id,
                overlap_volume_mm3=volume,
                center_mm=center,
                bounds_min_mm=minimum,
                bounds_max_mm=maximum,
            )
        )
    pair_count = len(solids) * (len(solids) - 1) // 2
    interference_scorecard = _interference_scorecard(
        tuple(solid_interferences), pair_count=pair_count
    )

    # Faces of the solids only. An AP242 file with PMI may carry supplemental geometry, such
    # as a datum or section plane, as a loose shell beside the part. Six of NIST's seventeen
    # AP242 test models do, and every planar face used to be taken from the whole shape, so
    # one such plane, owned by no solid, refused the entire file. It is not a surface of the
    # part, so it is set aside and the result says how many were.
    part_faces = [face for solid in solids for face in solid.faces()]
    loose_faces = len(shape.faces()) - len(part_faces)
    planar = [face for face in part_faces if face.geom_type.name == "PLANE"]
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

    cylindrical_surfaces: list[_CylindricalSurface] = []
    for cylinder in (face for face in part_faces if face.geom_type.name == "CYLINDER"):
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
        if len(solids) > 1 and len(circular_edges) >= 2:
            containing = [
                solid_id
                for solid_id, solid in solid_ids.items()
                if any(face.is_same(cylinder) for face in solid.faces())
            ]
            if len(containing) != 1:
                raise GeometryError(
                    "a cylindrical face could not be assigned to one imported solid"
                )
            axis_origin, axis_direction = _canonical_axis(axis_point, direction)
            positions = sorted(
                _dot(_coordinates(edge.center()), axis_direction) for edge in circular_edges
            )
            start, end = round(positions[0], 9), round(positions[-1], 9)
            if end - start > 1e-9:
                surface_signature = {
                    "solid": containing[0],
                    "kind": "bore" if inward else "shaft",
                    "radius": round(float(radius), 9),
                    "axis_origin": axis_origin,
                    "axis_direction": axis_direction,
                    "start": start,
                    "end": end,
                }
                cylindrical_surfaces.append(
                    _CylindricalSurface(
                        id=_candidate_id("cylinder", surface_signature),
                        solid_id=containing[0],
                        inward=inward,
                        radius=round(float(radius), 9),
                        axis_origin=axis_origin,
                        axis_direction=axis_direction,
                        start=start,
                        end=end,
                    )
                )
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

    candidates: list[PlanarInterfaceCandidate] = []
    plane_candidates: list[tuple[_DetectedPlane, PlanarInterfaceCandidate]] = []
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
            # A pitch circle inside the fit tolerance is holes stacked on one centre, not a
            # pattern. `<= 0` let NIST's STC 08 through with a radius of about 1e-12 mm, which
            # rounded to a pitch diameter of 0.0 and failed the candidate's `> 0` rule as an
            # internal error (exit 5) instead of being passed over.
            if (
                pitch_radius <= fit_tolerance
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
        candidate = PlanarInterfaceCandidate.model_validate(candidate_data)
        candidates.append(candidate)
        plane_candidates.append((plane, candidate))
    candidates.sort(
        key=lambda candidate: (
            candidate.normal,
            candidate.center_mm,
            candidate.area_mm2,
            candidate.id,
        )
    )
    contacts: list[PlanarContactCandidate] = []
    gaps: list[PlanarGapCandidate] = []
    if len(solids) > 1:
        for (first_plane, first_candidate), (
            second_plane,
            second_candidate,
        ) in combinations(plane_candidates, 2):
            if (
                first_candidate.solid_id is None
                or second_candidate.solid_id is None
                or first_candidate.solid_id == second_candidate.solid_id
                or _dot(first_candidate.normal, second_candidate.normal) > -0.999999
            ):
                continue
            signed_separation = _dot(
                _subtract(second_plane.center, first_plane.center), first_plane.normal
            )
            separation = abs(signed_separation)
            if separation > 1e-6 and signed_separation < 0:
                continue
            endpoints = sorted(
                (
                    (first_candidate.solid_id, first_candidate.id),
                    (second_candidate.solid_id, second_candidate.id),
                )
            )
            try:
                aligned_second = second_plane.face
                if separation > 1e-6:
                    translation = tuple(
                        -signed_separation * component for component in first_plane.normal
                    )
                    aligned_second = second_plane.face.moved(Location(translation))
                overlap = first_plane.face & aligned_second
            except Exception as failure:
                raise GeometryError(
                    f"could not measure planar overlap between {endpoints[0][1]} and "
                    f"{endpoints[1][1]}: {failure}"
                ) from failure
            if overlap is None:
                continue
            overlap_area = round(float(overlap.area), 9)
            if overlap_area <= 1e-9:
                continue
            signature = {
                "first_solid": endpoints[0][0],
                "first_face": endpoints[0][1],
                "second_solid": endpoints[1][0],
                "second_face": endpoints[1][1],
                "overlap_area": overlap_area,
            }
            if separation <= 1e-6:
                contacts.append(
                    PlanarContactCandidate(
                        id=_candidate_id("contact", signature),
                        first_solid_id=endpoints[0][0],
                        first_face_candidate_id=endpoints[0][1],
                        second_solid_id=endpoints[1][0],
                        second_face_candidate_id=endpoints[1][1],
                        overlap_area_mm2=overlap_area,
                    )
                )
                continue
            direction = (
                first_candidate.normal
                if endpoints[0] == (first_candidate.solid_id, first_candidate.id)
                else second_candidate.normal
            )
            gap_signature = {
                **signature,
                "separation": round(separation, 9),
                "direction": direction,
            }
            gaps.append(
                PlanarGapCandidate(
                    id=_candidate_id("planar-gap", gap_signature),
                    first_solid_id=endpoints[0][0],
                    first_face_candidate_id=endpoints[0][1],
                    second_solid_id=endpoints[1][0],
                    second_face_candidate_id=endpoints[1][1],
                    separation_mm=round(separation, 9),
                    overlap_area_mm2=overlap_area,
                    direction=direction,
                )
            )
    cylindrical_mates: list[CylindricalMatingCandidate] = []
    bores = [surface for surface in cylindrical_surfaces if surface.inward]
    shafts = [surface for surface in cylindrical_surfaces if not surface.inward]
    for bore in bores:
        for shaft in shafts:
            if bore.solid_id == shaft.solid_id:
                continue
            if _dot(bore.axis_direction, shaft.axis_direction) < 0.999999:
                continue
            axis_offset = _subtract(bore.axis_origin, shaft.axis_origin)
            if sqrt(_dot(axis_offset, axis_offset)) > 1e-6:
                continue
            engagement = round(min(bore.end, shaft.end) - max(bore.start, shaft.start), 9)
            if engagement <= 1e-9:
                continue
            bore_diameter = round(2 * bore.radius, 9)
            shaft_diameter = round(2 * shaft.radius, 9)
            clearance = round(bore_diameter - shaft_diameter, 9)
            signature = {
                "bore_solid": bore.solid_id,
                "bore_surface": bore.id,
                "shaft_solid": shaft.solid_id,
                "shaft_surface": shaft.id,
                "bore_diameter": bore_diameter,
                "shaft_diameter": shaft_diameter,
                "clearance": clearance,
                "engagement": engagement,
                "axis_origin": bore.axis_origin,
                "axis_direction": bore.axis_direction,
            }
            cylindrical_mates.append(
                CylindricalMatingCandidate(
                    id=_candidate_id("cylindrical-mate", signature),
                    bore_solid_id=bore.solid_id,
                    bore_surface_id=bore.id,
                    shaft_solid_id=shaft.solid_id,
                    shaft_surface_id=shaft.id,
                    bore_diameter_mm=bore_diameter,
                    shaft_diameter_mm=shaft_diameter,
                    diametral_clearance_mm=clearance,
                    axial_engagement_mm=engagement,
                    axis_origin_mm=bore.axis_origin,
                    axis_direction=bore.axis_direction,
                )
            )
    warnings = [
        "candidates are measured suggestions only; confirm one before creating an "
        "interface contract",
        "this detector does not yet classify nested blind steps or nonconcentric locators",
    ]
    if loose_faces > 0:
        warnings.append(
            f"{loose_faces} face(s) belong to no solid (supplemental geometry, such as a datum "
            "or section plane) and were not considered as interfaces"
        )
    if len(solids) > 1:
        warnings.append(
            "planar contacts report exact coplanar overlap only; they do not prove intended mating"
        )
        warnings.append(
            "planar gaps report projected overlap and separation only; they do not judge clearance"
        )
        warnings.append(
            "cylindrical mates report measured signed clearance only; they do not judge fit"
        )
        warnings.append("positive common solid volume is a failed assembly interference check")
    result_data: dict[str, Any] = {
        "source_name": path.name,
        "source_sha256": sha256(source_bytes).hexdigest(),
        "planar_faces": tuple(candidates),
        "warnings": tuple(warnings),
    }
    if len(solids) > 1:
        contacts.sort(key=lambda contact: contact.id)
        gaps.sort(key=lambda gap: gap.id)
        cylindrical_mates.sort(key=lambda mate: mate.id)
        solid_interferences.sort(key=lambda candidate: candidate.id)
        result_data["solids"] = solid_candidates
        result_data["planar_contacts"] = tuple(contacts)
        result_data["planar_gaps"] = tuple(gaps)
        result_data["cylindrical_mates"] = tuple(cylindrical_mates)
        result_data["solid_interferences"] = tuple(solid_interferences)
        result_data["interference_scorecard"] = interference_scorecard
    return StepInterfaceCandidates.model_validate(result_data)


def confirm_planar_contact(
    candidates: StepInterfaceCandidates,
    *,
    contact_id: str,
    name: str,
    confirmed_by: str,
) -> ConfirmedPlanarContact:
    """Accept one exact measured planar contact without inventing interface geometry."""
    confirmer = confirmed_by.strip()
    if not confirmer:
        raise GeometryError("accepting a contact candidate names the person confirming it")
    contact_name = name.strip()
    if not contact_name:
        raise GeometryError("an accepted planar contact has a non-blank name")
    matches = [contact for contact in candidates.planar_contacts if contact.id == contact_id]
    if len(matches) != 1:
        available = ", ".join(contact.id for contact in candidates.planar_contacts) or "none"
        raise GeometryError(
            f"contact candidate {contact_id!r} was not found exactly once; available: {available}"
        )
    contact = matches[0]
    return ConfirmedPlanarContact(
        source_name=candidates.source_name,
        source_sha256=candidates.source_sha256,
        contact_candidate_id=contact.id,
        name=contact_name,
        first_solid_id=contact.first_solid_id,
        first_face_candidate_id=contact.first_face_candidate_id,
        second_solid_id=contact.second_solid_id,
        second_face_candidate_id=contact.second_face_candidate_id,
        overlap_area_mm2=contact.overlap_area_mm2,
        confirmed_by=confirmer,
    )


def check_planar_contact_area(
    confirmed: ConfirmedPlanarContact,
    *,
    minimum_overlap_area: Quantity,
    reference: str,
) -> PlanarContactAreaCheck:
    """Check a confirmed contact against one caller-supplied, cited minimum area."""
    if not minimum_overlap_area.has_dimension("[length]**2"):
        raise GeometryError(
            "minimum contact area must be an area; got "
            f"{minimum_overlap_area.dimensionality} ({minimum_overlap_area})"
        )
    minimum_mm2 = minimum_overlap_area.to("mm^2").magnitude
    if minimum_mm2 < 0:
        raise GeometryError("minimum contact area must not be negative")
    margin = round(confirmed.overlap_area_mm2 - minimum_mm2, 9)
    return PlanarContactAreaCheck(
        confirmed_contact=confirmed,
        minimum_overlap_area_mm2=round(minimum_mm2, 9),
        margin_above_minimum_mm2=margin,
        status="pass" if margin >= 0 else "fail",
        reference=reference,
    )


def confirm_cylindrical_mate(
    candidates: StepInterfaceCandidates,
    *,
    mate_id: str,
    name: str,
    confirmed_by: str,
) -> ConfirmedCylindricalMate:
    """Accept one exact cylindrical mate without judging its fit."""
    confirmer = confirmed_by.strip()
    if not confirmer:
        raise GeometryError("accepting a cylindrical mate names the person confirming it")
    mate_name = name.strip()
    if not mate_name:
        raise GeometryError("an accepted cylindrical mate has a non-blank name")
    matches = [mate for mate in candidates.cylindrical_mates if mate.id == mate_id]
    if len(matches) != 1:
        available = ", ".join(mate.id for mate in candidates.cylindrical_mates) or "none"
        raise GeometryError(
            f"cylindrical mate {mate_id!r} was not found exactly once; available: {available}"
        )
    mate = matches[0]
    return ConfirmedCylindricalMate(
        source_name=candidates.source_name,
        source_sha256=candidates.source_sha256,
        mate_candidate_id=mate.id,
        name=mate_name,
        bore_solid_id=mate.bore_solid_id,
        bore_surface_id=mate.bore_surface_id,
        shaft_solid_id=mate.shaft_solid_id,
        shaft_surface_id=mate.shaft_surface_id,
        bore_diameter_mm=mate.bore_diameter_mm,
        shaft_diameter_mm=mate.shaft_diameter_mm,
        diametral_clearance_mm=mate.diametral_clearance_mm,
        axial_engagement_mm=mate.axial_engagement_mm,
        axis_origin_mm=mate.axis_origin_mm,
        axis_direction=mate.axis_direction,
        confirmed_by=confirmer,
    )


def confirm_planar_gap(
    candidates: StepInterfaceCandidates,
    *,
    gap_id: str,
    name: str,
    confirmed_by: str,
) -> ConfirmedPlanarGap:
    """Accept one exact planar gap without inventing an allowable clearance."""
    confirmer = confirmed_by.strip()
    if not confirmer:
        raise GeometryError("accepting a planar gap names the person confirming it")
    gap_name = name.strip()
    if not gap_name:
        raise GeometryError("an accepted planar gap has a non-blank name")
    matches = [gap for gap in candidates.planar_gaps if gap.id == gap_id]
    if len(matches) != 1:
        available = ", ".join(gap.id for gap in candidates.planar_gaps) or "none"
        raise GeometryError(
            f"planar gap {gap_id!r} was not found exactly once; available: {available}"
        )
    gap = matches[0]
    return ConfirmedPlanarGap(
        source_name=candidates.source_name,
        source_sha256=candidates.source_sha256,
        gap_candidate_id=gap.id,
        name=gap_name,
        first_solid_id=gap.first_solid_id,
        first_face_candidate_id=gap.first_face_candidate_id,
        second_solid_id=gap.second_solid_id,
        second_face_candidate_id=gap.second_face_candidate_id,
        separation_mm=gap.separation_mm,
        overlap_area_mm2=gap.overlap_area_mm2,
        direction=gap.direction,
        confirmed_by=confirmer,
    )


def check_planar_gap_clearance(
    confirmed: ConfirmedPlanarGap,
    *,
    minimum_gap: Quantity,
    maximum_gap: Quantity,
    reference: str,
) -> PlanarGapClearanceCheck:
    """Check a confirmed gap against caller-supplied, cited clearance limits."""
    for label, bound in (("minimum gap", minimum_gap), ("maximum gap", maximum_gap)):
        if not bound.has_dimension("[length]"):
            raise GeometryError(f"{label} must be a length; got {bound.dimensionality} ({bound})")
    minimum_mm = minimum_gap.to("mm").magnitude
    maximum_mm = maximum_gap.to("mm").magnitude
    if minimum_mm < 0 or maximum_mm < 0:
        raise GeometryError("planar gap limits must not be negative")
    if minimum_mm > maximum_mm:
        raise GeometryError("minimum gap must not exceed maximum gap")
    lower_margin = round(confirmed.separation_mm - minimum_mm, 9)
    upper_margin = round(maximum_mm - confirmed.separation_mm, 9)
    return PlanarGapClearanceCheck(
        confirmed_gap=confirmed,
        minimum_gap_mm=round(minimum_mm, 9),
        maximum_gap_mm=round(maximum_mm, 9),
        margin_above_minimum_mm=lower_margin,
        margin_below_maximum_mm=upper_margin,
        status="pass" if lower_margin >= 0 and upper_margin >= 0 else "fail",
        reference=reference,
    )


def check_cylindrical_mate_engagement(
    confirmed: ConfirmedCylindricalMate,
    *,
    minimum_engagement: Quantity,
    reference: str,
) -> CylindricalMateEngagementCheck:
    """Check a confirmed cylindrical mate against one cited minimum engagement."""
    if not minimum_engagement.has_dimension("[length]"):
        raise GeometryError(
            "minimum axial engagement must be a length; got "
            f"{minimum_engagement.dimensionality} ({minimum_engagement})"
        )
    minimum_mm = minimum_engagement.to("mm").magnitude
    if minimum_mm < 0:
        raise GeometryError("minimum axial engagement must not be negative")
    margin = round(confirmed.axial_engagement_mm - minimum_mm, 9)
    return CylindricalMateEngagementCheck(
        confirmed_mate=confirmed,
        minimum_axial_engagement_mm=round(minimum_mm, 9),
        margin_above_minimum_mm=margin,
        status="pass" if margin >= 0 else "fail",
        reference=reference,
    )


def check_cylindrical_mate_fit(
    confirmed: ConfirmedCylindricalMate,
    *,
    basic_size: Quantity,
    designation: str,
) -> CylindricalMateFitCheck:
    """Check confirmed measured diameters against one explicit ISO 286 fit."""
    from .tolerance.iso286 import fit

    resolved = fit(designation, basic_size)
    basic_size_mm = basic_size.to("mm").magnitude
    hole_min = resolved.hole.min_size.to("mm").magnitude
    hole_max = resolved.hole.max_size.to("mm").magnitude
    shaft_min = resolved.shaft.min_size.to("mm").magnitude
    shaft_max = resolved.shaft.max_size.to("mm").magnitude
    measured_clearance = confirmed.diametral_clearance_mm
    design_min = resolved.min_clearance.to("mm").magnitude
    design_max = resolved.max_clearance.to("mm").magnitude
    hole_ok = hole_min <= confirmed.bore_diameter_mm <= hole_max
    shaft_ok = shaft_min <= confirmed.shaft_diameter_mm <= shaft_max
    return CylindricalMateFitCheck(
        confirmed_mate=confirmed,
        basic_size_mm=basic_size_mm,
        fit_designation=resolved.designation,
        fit_kind=resolved.kind,
        minimum_design_clearance_mm=design_min,
        maximum_design_clearance_mm=design_max,
        hole=FitFeatureCheck(
            designation=resolved.hole.designation,
            measured_diameter_mm=confirmed.bore_diameter_mm,
            minimum_diameter_mm=hole_min,
            maximum_diameter_mm=hole_max,
            within_zone=hole_ok,
        ),
        shaft=FitFeatureCheck(
            designation=resolved.shaft.designation,
            measured_diameter_mm=confirmed.shaft_diameter_mm,
            minimum_diameter_mm=shaft_min,
            maximum_diameter_mm=shaft_max,
            within_zone=shaft_ok,
        ),
        measured_clearance_within_design_range=design_min <= measured_clearance <= design_max,
        status="pass" if hole_ok and shaft_ok else "fail",
        reference=resolved.source,
    )


def _assembly_interface_scorecard(
    candidates: StepInterfaceCandidates,
    *,
    contact_check: PlanarContactAreaCheck | None = None,
    engagement_check: CylindricalMateEngagementCheck | None = None,
    fit_check: CylindricalMateFitCheck | None = None,
    gap_check: PlanarGapClearanceCheck | None = None,
) -> Scorecard:
    """Roll assembly interference and requested interface checks into one verdict."""
    replacements: dict[str, ScorecardEntry] = {}
    if (
        fit_check is not None
        and fit_check.status == "pass"
        and fit_check.fit_kind == "interference"
        and fit_check.measured_clearance_within_design_range
        and fit_check.confirmed_mate.diametral_clearance_mm < 0
    ):
        mate = fit_check.confirmed_mate
        pair = {mate.bore_solid_id, mate.shaft_solid_id}
        matching = [
            candidate
            for candidate in candidates.solid_interferences
            if {candidate.first_solid_id, candidate.second_solid_id} == pair
        ]
        expected_overlap = (
            pi
            / 4
            * (mate.shaft_diameter_mm**2 - mate.bore_diameter_mm**2)
            * mate.axial_engagement_mm
        )
        if len(matching) == 1 and matching[0].overlap_volume_mm3 <= expected_overlap + max(
            1e-6, expected_overlap * 1e-6
        ):
            interference = matching[0]
            original_name = (
                f"solid interference {interference.first_solid_id}/{interference.second_solid_id}"
            )
            replacements[original_name] = ScorecardEntry(
                name=f"declared cylindrical interference {mate.name}",
                status=CheckStatus.PASS,
                detail=(
                    f"common volume {interference.overlap_volume_mm3:g} mm³ is fully explained "
                    f"by {expected_overlap:g} mm³ of measured {fit_check.fit_designation} "
                    "cylindrical engagement"
                ),
                reference=(
                    "assembly-robotics: Assembly-level validation; ISO 286-1:2010, "
                    "standard tolerance grades and fundamental deviations"
                ),
                underived=Underived(
                    kind=DerivationAbsence.NUMERIC_RESULT,
                    reason=(
                        "the verdict compares exact common volume with the annular volume "
                        "of the confirmed cylindrical engagement"
                    ),
                ),
            )
    entries = [
        replacements.get(entry.name, entry)
        for entry in (
            ()
            if candidates.interference_scorecard is None
            else candidates.interference_scorecard.entries
        )
    ]
    if contact_check is not None:
        entries.append(
            ScorecardEntry(
                name=f"planar contact area {contact_check.confirmed_contact.name}",
                status=CheckStatus.PASS if contact_check.status == "pass" else CheckStatus.FAIL,
                detail=(
                    f"measured {contact_check.confirmed_contact.overlap_area_mm2:g} mm² "
                    f"against minimum {contact_check.minimum_overlap_area_mm2:g} mm²"
                ),
                reference=contact_check.reference,
                underived=Underived(
                    kind=DerivationAbsence.NUMERIC_RESULT,
                    reason="the verdict compares a B-Rep overlap area with the cited minimum",
                ),
            )
        )
    if engagement_check is not None:
        entries.append(
            ScorecardEntry(
                name=f"cylindrical mate engagement {engagement_check.confirmed_mate.name}",
                status=(
                    CheckStatus.PASS if engagement_check.status == "pass" else CheckStatus.FAIL
                ),
                detail=(
                    f"measured {engagement_check.confirmed_mate.axial_engagement_mm:g} mm "
                    f"against minimum {engagement_check.minimum_axial_engagement_mm:g} mm"
                ),
                reference=engagement_check.reference,
                underived=Underived(
                    kind=DerivationAbsence.NUMERIC_RESULT,
                    reason="the verdict compares B-Rep axial engagement with the cited minimum",
                ),
            )
        )
    if fit_check is not None:
        for label, feature in (("hole", fit_check.hole), ("shaft", fit_check.shaft)):
            entries.append(
                ScorecardEntry(
                    name=f"cylindrical mate {label} within {feature.designation}",
                    status=CheckStatus.PASS if feature.within_zone else CheckStatus.FAIL,
                    detail=(
                        f"measured {feature.measured_diameter_mm:g} mm against "
                        f"{feature.minimum_diameter_mm:g}–{feature.maximum_diameter_mm:g} mm"
                    ),
                    reference=(
                        "ISO 286-1:2010, standard tolerance grades and fundamental deviations"
                    ),
                    underived=Underived(
                        kind=DerivationAbsence.NUMERIC_RESULT,
                        reason="the verdict compares a B-Rep diameter with resolved ISO 286 limits",
                    ),
                )
            )
    if gap_check is not None:
        entries.append(
            ScorecardEntry(
                name=f"planar gap {gap_check.confirmed_gap.name}",
                status=CheckStatus.PASS if gap_check.status == "pass" else CheckStatus.FAIL,
                detail=(
                    f"measured {gap_check.confirmed_gap.separation_mm:g} mm against "
                    f"{gap_check.minimum_gap_mm:g}–{gap_check.maximum_gap_mm:g} mm"
                ),
                reference=gap_check.reference,
                underived=Underived(
                    kind=DerivationAbsence.NUMERIC_RESULT,
                    reason="the verdict compares a B-Rep separation with the cited limits",
                ),
            )
        )
    return Scorecard(entries=tuple(entries))


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


def build_timber_beam(beam: TimberBeam) -> BuiltGeometry:
    """Build an audited timber beam: a box of its dressed width and depth over its span.

    The solid is the member between its supports, ``span`` long, with ``depth`` vertical:
    the ends that sit on the bearings are not modelled, because the element declares a
    bearing length and not how far the member runs past it. The faces are named as the
    base plate's are, so the top face is the one the load bears on.
    """
    width = _positive_mm(beam.width, "width", element="timber_beam")
    depth = _positive_mm(beam.depth, "depth", element="timber_beam")
    span = _positive_mm(beam.span, "span", element="timber_beam")
    Align, Box, _Cylinder, _export_step = _kernel()
    shape = Box(width, span, depth, align=(Align.CENTER, Align.CENTER, Align.MIN))
    built = BuiltGeometry(
        name=str(beam.name),
        pattern=TIMBER_BEAM_PATTERN,
        shape=shape,
        faces=_tag_box_faces(shape),
        dimensions_mm=MappingProxyType({"width": width, "span": span, "depth": depth}),
    )
    if not built.is_valid:  # pragma: no cover - guarded Box dimensions are valid
        raise GeometryError("timber_beam pattern did not produce one valid positive-volume solid")
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
        if spec.element_type == "timber_beam":
            return build_timber_beam(TimberBeam(**dict(spec.element_params)))
    except ValueError as failure:
        raise GeometryError(f"invalid {spec.element_type} element_params: {failure}") from failure
    tag = spec.element_type or "<undeclared>"
    raise UnsupportedGeometry(
        f"no audited geometry pattern is registered for element_type {tag!r}; "
        "supported: base_plate, cover_plate, transmission_shaft, timber_beam"
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
        TIMBER_BEAM_PATTERN,
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


def _semantic_pmi(
    document: Any, shape_tool: Any, label: Any, built: BuiltGeometry, tolerances
) -> None:
    """Attach each declared geometric tolerance to the faces its tag names, as AP242 PMI.

    Datums are lettered A, B, C in the order their tags first appear. OCCT's STEP writer
    states every tolerance measure in metres and does not convert the value it is given, so
    a 0.05 mm flatness passed as 0.05 was written as 0.05 m, a zone a thousand times too
    wide. The value is converted here, and the test reads the unit back out of the file.
    """
    from OCP.TCollection import TCollection_HAsciiString  # type: ignore[import-untyped]
    from OCP.TDF import TDF_LabelSequence  # type: ignore[import-untyped]
    from OCP.XCAFDimTolObjects import (  # type: ignore[import-untyped]
        XCAFDimTolObjects_DatumObject,
        XCAFDimTolObjects_GeomToleranceObject,
        XCAFDimTolObjects_GeomToleranceType,
        XCAFDimTolObjects_GeomToleranceTypeValue,
    )
    from OCP.XCAFDoc import (  # type: ignore[import-untyped]
        XCAFDoc_Datum,
        XCAFDoc_DocumentTool,
        XCAFDoc_GeomTolerance,
    )

    kinds = {
        "flatness": "Flatness",
        "straightness": "Straightness",
        "circularity": "CircularityOrRoundness",
        "cylindricity": "Cylindricity",
        "perpendicularity": "Perpendicularity",
        "parallelism": "Parallelism",
        "angularity": "Angularity",
        "position": "Position",
        "circular_runout": "CircularRunout",
        "total_runout": "TotalRunout",
    }
    dim_tol = XCAFDoc_DocumentTool.DimTolTool_s(document.Main())

    def faces(tag: str) -> Any:
        if tag not in built.faces:
            raise GeometryError(
                f"a geometric tolerance names '{tag}', which the {built.pattern} solid does not "
                f"tag; it tags {sorted(built.faces)}"
            )
        sequence = TDF_LabelSequence()
        for face in built.faces[tag]:
            sequence.Append(shape_tool.AddSubShape(label, face.wrapped))
        return sequence

    letters: dict[str, str] = {}
    for tolerance in tolerances:
        for tag in tolerance.datums:
            letters.setdefault(tag, "ABCDEFGHJKLMNPRSTUVWXYZ"[len(letters)])
    for tolerance in tolerances:
        characteristic = str(getattr(tolerance.characteristic, "value", tolerance.characteristic))
        tolerance_label = dim_tol.AddGeomTolerance()
        definition = XCAFDimTolObjects_GeomToleranceObject()
        definition.SetType(
            getattr(
                XCAFDimTolObjects_GeomToleranceType,
                f"XCAFDimTolObjects_GeomToleranceType_{kinds[characteristic]}",
            )
        )
        definition.SetValue(tolerance.tolerance.to("m").magnitude)  # see the docstring
        if tolerance.diametral:
            definition.SetTypeOfValue(
                XCAFDimTolObjects_GeomToleranceTypeValue.XCAFDimTolObjects_GeomToleranceTypeValue_Diameter
            )
        XCAFDoc_GeomTolerance.Set_s(tolerance_label).SetObject(definition)
        dim_tol.SetGeomTolerance(faces(tolerance.feature), tolerance_label)
        for position, tag in enumerate(tolerance.datums, start=1):
            datum_label = dim_tol.AddDatum()
            datum = XCAFDimTolObjects_DatumObject()
            datum.SetName(TCollection_HAsciiString(letters[tag]))
            datum.SetPosition(position)
            XCAFDoc_Datum.Set_s(datum_label).SetObject(datum)
            dim_tol.SetDatum(faces(tag), datum_label)
            dim_tol.SetDatumToGeomTol(datum_label, tolerance_label)


def _write_step_shape(
    built: BuiltGeometry,
    path: Path,
    *,
    schema: Literal["ap242", "ap214"],
    tolerances: Sequence[Any] = (),
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
        if tolerances:
            _semantic_pmi(document, shape_tool, label, built, tolerances)

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
            writer.SetDimTolMode(bool(tolerances))
            if not writer.Transfer(document, STEPControl_StepModelType.STEPControl_AsIs):
                raise GeometryError("STEP writer could not transfer the built solid")
            if writer.Write(str(path)) != IFSelect_ReturnStatus.IFSelect_RetDone:
                raise GeometryError("STEP writer could not write the built solid")
        except BaseException:
            # BaseException, not Exception: a Ctrl-C mid-write is a KeyboardInterrupt, and
            # it used to leave a truncated STEP file at the path a finished one belongs at.
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
        from build123d import CenterOf
    except ImportError as failure:  # pragma: no cover - guarded by the geometry extra
        raise GeometryUnavailable(
            "STEP validation needs the optional dependency; install anvilate[geometry]"
        ) from failure
    expected = read_step_validation_properties(path)
    received = _read_step_geometry(path)
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
    tolerances: Sequence[Any] = (),
) -> Path:
    """Write one authorized solid as deterministic, watermarked STEP and return its path.

    ``tolerances`` are a Design Spec's ``geometric_tolerances``, written as AP242 semantic
    PMI on the faces their tags name: the same model the drawing frame and the QIF
    characteristic render from, so a tightened tolerance reaches all three. AP214 has no
    semantic PMI, so tolerances with ``schema="ap214"`` are refused rather than dropped.
    """
    if not built.is_valid:
        raise GeometryError("refusing to write invalid geometry")
    if tolerances and schema != "ap242":
        raise GeometryError(
            "semantic PMI is an AP242 construct and AP214 cannot carry it; write AP242, or "
            "write AP214 without the tolerances"
        )
    if schema not in {"ap242", "ap214"}:
        raise GeometryError(f"unsupported STEP schema {schema!r}; choose ap242 or ap214")
    _write_step_shape(built, path, schema=schema, tolerances=tuple(tolerances))
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


def render_3mf(
    built: BuiltGeometry, *, authorization: ExportAuthorization, tolerance_mm: float = 0.01
) -> bytes:
    """One authorized solid as the bytes of a 3MF file, tessellated to ``tolerance_mm``.

    The kernel meshes each face on its own, so a vertex on an edge two faces share arrives
    once per face. Vertices with identical coordinates are welded into one before the mesh is
    handed to :func:`~anvilate.export.threemf.render_mesh_3mf`, whose closed-and-oriented
    check then holds the kernel's triangulation to what a printer needs. The mesh is also
    held to the solid: its signed volume must be positive, which is outward-facing triangles,
    and within 1% of the solid's own volume. A tessellation that loses a feature is refused
    rather than written.
    """
    from .export.threemf import render_mesh_3mf

    if not built.is_valid:
        raise GeometryError("refusing to write invalid geometry")
    if isinstance(tolerance_mm, bool) or not isinstance(tolerance_mm, int | float):
        raise GeometryError(f"tolerance_mm must be a number of millimetres; got {tolerance_mm!r}")
    if not 0 < tolerance_mm <= 1.0:
        raise GeometryError(f"tolerance_mm must lie in (0, 1] mm; got {tolerance_mm!r}")
    raw_vertices, raw_triangles = built.shape.tessellate(tolerance_mm, 0.1)
    welded: dict[tuple[float, float, float], int] = {}
    remap: list[int] = []
    for vertex in raw_vertices:
        key = (float(vertex.X), float(vertex.Y), float(vertex.Z))
        remap.append(welded.setdefault(key, len(welded)))
    vertices = list(welded)
    triangles = [(remap[a], remap[b], remap[c]) for a, b, c in raw_triangles]
    signed = 0.0
    for a, b, c in triangles:
        (ax, ay, az), (bx, by, bz), (cx, cy, cz) = vertices[a], vertices[b], vertices[c]
        signed += (
            ax * (by * cz - bz * cy) - ay * (bx * cz - bz * cx) + az * (bx * cy - by * cx)
        ) / 6
    solid = built.volume_mm3
    if signed <= 0 or abs(signed - solid) > 0.01 * solid:
        raise GeometryError(
            f"the tessellation encloses {signed:.6g} mm^3 and the solid {solid:.6g} mm^3; a "
            "mesh that does not hold the solid's volume, facing outward, is not the part"
        )
    return render_mesh_3mf(
        vertices=vertices, triangles=triangles, name=built.name, authorization=authorization
    )
