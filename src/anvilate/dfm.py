"""Geometric DFM rules: the built solid read the way a shop quoting it would.

A part can pass every strength check and still come back from the shop with a list: an
inside corner sharper than any end mill, a hole twelve diameters deep, a flange hole too
close to a bend to form, a molded wall with no draft, an overhang a printer cannot build
without support. None of these needs a solver. Each is a measurement of the built solid
against a threshold in a **process profile**.

Every threshold says where it came from. The bundled ones are **practice defaults**,
labelled as such on every finding: common shop figures, not a standard's clause. A shop
replaces any of them with its own number and its source (:meth:`ProcessProfile.override`),
and the finding then names that source. A licensed handbook's thresholds are never
bundled; a user enters them with their citation.

What is measured, on the solid itself:

- **Internal corner radius** (CNC milling): every concave fillet about the tool axis, and
  every sharp concave straight edge along it (radius 0), found by probing beside the edge:
  for an edge between faces with outward normals n₁ and n₂, the point m + ε(n₁ − n₂) is
  inside the material only when the edge is concave. A corner across the tool axis, where
  a wall meets the floor a flat end mill cuts, takes no cutter radius and is not judged.
- **Hole depth ratio** (CNC milling): each drilled feature's depth over its diameter.
- **Bend radius and hole-to-bend, hole-to-edge distances** (sheet metal): from the
  developed flat profile, in thicknesses.
- **Draft** (injection molding): every face's angle to the pull direction; a planar face
  or a cylinder about the pull axis with less than the profile's draft is reported.
- **Overhang** (additive): every down-facing planar face's angle above horizontal against
  the build direction, skipping faces on the build plate. Curved down-facing faces are
  not measured, and the report says so.

Findings are :class:`~anvilate.scorecard.ScorecardEntry` objects, one per rule, naming
the faces or features at fault and the measured value against the limit; a bend also
names the inside radius that meets it. They are manufacturability findings: they sit
beside the physics verdicts and change none of them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import acos, asin, degrees, hypot, sqrt
from typing import Any

from pydantic import ConfigDict

from ._models import Named, Provenance, StatableModel
from .derivation import DerivationAbsence, Underived
from .geometry import BuiltGeometry
from .refusal import RefusalError, Remedy
from .scorecard import (
    CheckStatus,
    Comparison,
    LimitSense,
    ScorecardEntry,
)
from .units import Quantity, require_finite

__all__ = [
    "DfmProcess",
    "DfmThreshold",
    "ProcessProfile",
    "default_profile",
    "screen_dfm",
]

_PRACTICE = "practice default (a common shop figure, not a standard's clause)"
_PROFILE_SOURCE = "the shop's process profile, with its source"
#: The declared dimensions that are walls, for the uniformity rule.
_WALL_KEYS = frozenset({"wall", "floor", "thickness", "lid_thickness", "rib", "boss_wall"})
#: The catalogued failure mode every DFM entry answers (anvilate.failure_modes).
_ADDRESSES = ("a feature the shop cannot make as drawn",)


class _DfmInputError(RefusalError, ValueError):
    """A DFM input that cannot be used without correction."""


def _refusal(message: str, *, subject: str, source: str = _PROFILE_SOURCE) -> _DfmInputError:
    return _DfmInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


class DfmProcess(StrEnum):
    """The processes a profile describes."""

    CNC_MILLING = "cnc_milling"
    SHEET_METAL = "sheet_metal"
    INJECTION_MOLDING = "injection_molding"
    DIE_CASTING = "die_casting"
    ADDITIVE = "additive"


# rule: (unit, the sense that passes, what it is) — one meaning per rule, whatever process.
_RULES: dict[str, tuple[str, LimitSense, str]] = {
    "internal_radius_min": (
        "mm",
        LimitSense.AT_LEAST,
        "the smallest inside corner radius the shop's tools cut",
    ),
    "hole_depth_ratio_max": (
        "dimensionless",
        LimitSense.AT_MOST,
        "the deepest hole, in diameters, the shop drills",
    ),
    "bend_radius_ratio_min": (
        "dimensionless",
        LimitSense.AT_LEAST,
        "the smallest inside bend radius, in thicknesses",
    ),
    "hole_to_bend_min": (
        "dimensionless",
        LimitSense.AT_LEAST,
        "a hole's edge to a bend line, in thicknesses",
    ),
    "hole_to_edge_min": (
        "dimensionless",
        LimitSense.AT_LEAST,
        "a hole's edge to the blank's edge, in thicknesses",
    ),
    "flange_length_min": (
        "dimensionless",
        LimitSense.AT_LEAST,
        "the shortest flange the brake forms, in thicknesses",
    ),
    "draft_min": ("degree", LimitSense.AT_LEAST, "the least draft on a face along the pull"),
    "wall_ratio_max": (
        "dimensionless",
        LimitSense.AT_MOST,
        "the thickest declared wall over the thinnest, for even filling",
    ),
    "overhang_min": (
        "degree",
        LimitSense.AT_LEAST,
        "the least angle above horizontal a down-facing face builds unsupported",
    ),
}

# (process, rule): the bundled practice default.
_DEFAULTS: dict[tuple[DfmProcess, str], float] = {
    (DfmProcess.CNC_MILLING, "internal_radius_min"): 1.0,
    (DfmProcess.CNC_MILLING, "hole_depth_ratio_max"): 10.0,
    (DfmProcess.SHEET_METAL, "bend_radius_ratio_min"): 1.0,
    (DfmProcess.SHEET_METAL, "hole_to_bend_min"): 2.5,
    (DfmProcess.SHEET_METAL, "hole_to_edge_min"): 2.0,
    (DfmProcess.SHEET_METAL, "flange_length_min"): 4.0,
    (DfmProcess.INJECTION_MOLDING, "draft_min"): 1.0,
    (DfmProcess.INJECTION_MOLDING, "wall_ratio_max"): 2.0,
    (DfmProcess.DIE_CASTING, "draft_min"): 1.0,
    (DfmProcess.DIE_CASTING, "wall_ratio_max"): 2.0,
    (DfmProcess.ADDITIVE, "overhang_min"): 45.0,
}  # fmt: skip


class DfmThreshold(StatableModel):
    """One rule's limit in a process profile, and where it came from."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule: Named
    value: float
    unit: Named
    source: Provenance
    practice_default: bool


class ProcessProfile(StatableModel):
    """A process's DFM thresholds; practice defaults until a shop overrides them with a source."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    process: DfmProcess
    thresholds: tuple[DfmThreshold, ...]

    def threshold(self, rule: str) -> DfmThreshold:
        """The threshold for ``rule``, refusing one this profile does not hold."""
        for t in self.thresholds:
            if t.rule == rule:
                return t
        raise _refusal(f"profile for {self.process.value} has no rule '{rule}'; it holds "
                       f"{[t.rule for t in self.thresholds]}", subject="rule")  # fmt: skip

    def override(self, rule: str, value: float, *, source: str) -> ProcessProfile:
        """This profile with ``rule`` set to the shop's ``value``, citing ``source``."""
        current = self.threshold(rule)
        v = require_finite(value, name="value")
        if v < 0:
            raise _refusal(f"a threshold is zero or positive; got {v}", subject="value")
        if not isinstance(source, str) or not source.strip():
            raise _refusal("an override names its source: the shop standard or the "
                           "machine's documented capability", subject="source")  # fmt: skip
        replaced = DfmThreshold(rule=rule, value=v, unit=current.unit, source=source,
                                practice_default=False)  # fmt: skip
        return self.model_copy(
            update={"thresholds": tuple(replaced if t.rule == rule else t for t in self.thresholds)}
        )


def default_profile(process: DfmProcess) -> ProcessProfile:
    """The bundled practice defaults for ``process``, each labelled as one."""
    if not isinstance(process, DfmProcess):
        raise _refusal(f"process must be a DfmProcess; got {process!r}", subject="process")
    return ProcessProfile(
        process=process,
        thresholds=tuple(
            DfmThreshold(
                rule=rule,
                value=value,
                unit=_RULES[rule][0],
                source=_PRACTICE,
                practice_default=True,
            )
            for (p, rule), value in _DEFAULTS.items()
            if p is process
        ),
    )


# --- measuring the solid -------------------------------------------------------------------


@dataclass(frozen=True)
class _Item:
    where: str
    value: float


def _unit(v: Any) -> tuple[float, float, float]:
    x, y, z = float(v.X), float(v.Y), float(v.Z)
    n = sqrt(x * x + y * y + z * z) or 1.0
    return x / n, y / n, z / n


def _point(v: Any) -> tuple[float, float, float]:
    return float(v.X), float(v.Y), float(v.Z)


def _dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _face_tag(built: BuiltGeometry, face: Any) -> str:
    for tag, faces in built.faces.items():
        if any(face.is_same(f) for f in faces):
            return tag
    return "untagged face"


def _internal_radii(built: BuiltGeometry, tool: tuple[float, float, float]) -> list[_Item]:
    from build123d import Vector

    from .context import _solid_facts

    items = [
        _Item(f"concave fillet about {tuple(round(a, 3) for a in c.axis)} at "
              f"{tuple(round(p, 1) for p in c.position_mm)}", c.diameter_mm / 2)
        for c in _solid_facts(built.shape).cylinders
        if c.kind == "fillet" and abs(_dot(c.axis, tool)) > 0.999
    ]  # fmt: skip
    shape = built.shape
    for edge in shape.edges():
        if edge.geom_type.name != "LINE":
            continue
        # Only a corner along the tool axis takes the cutter's radius: a flat end mill
        # leaves a sharp corner where a wall meets the floor it cuts.
        if abs(_dot(_unit(edge.tangent_at(0.5)), tool)) < 0.999:
            continue
        faces = [f for f in shape.faces() if any(edge.is_same(e) for e in f.edges())]
        if len(faces) != 2 or any(f.geom_type.name != "PLANE" for f in faces):
            continue
        mid = edge.position_at(0.5)
        n1, n2 = (_unit(f.normal_at(mid)) for f in faces)
        if abs(_dot(n1, n2)) > 0.999:
            continue
        eps = 0.05
        probe = Vector(*(m + eps * (a - b) for m, a, b in zip(tuple(mid), n1, n2, strict=True)))
        if shape.is_inside(probe):
            items.append(_Item(f"sharp internal edge at {tuple(round(float(c), 1) for c in mid)}",
                               0.0))  # fmt: skip
    return items


def _segment_distance(
    p: tuple[float, float], a: tuple[float, float], b: tuple[float, float]
) -> float:
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / length2))
    return hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def _vector(direction: tuple[float, float, float] | None, name: str) -> tuple[float, float, float]:
    if direction is None:
        raise _refusal(
            f"this process needs a {name}: the cutter's axis, the mold's pull, or the build "
            "direction, as the setup fixes it",
            subject=name,
            source="the tooling or build setup",
        )
    x, y, z = (require_finite(c, name=name) for c in direction)
    n = sqrt(x * x + y * y + z * z)
    if n == 0:
        raise _refusal(
            f"{name} is the zero vector", subject=name, source="the tooling or build setup"
        )
    return x / n, y / n, z / n


# --- the rules -----------------------------------------------------------------------------


def _entry(
    built: BuiltGeometry,
    rule: str,
    threshold: DfmThreshold,
    items: list[_Item],
    *,
    label: str,
    note: str = "",
) -> ScorecardEntry:
    unit, sense, meaning = _RULES[rule]
    basis = "a practice default" if threshold.practice_default else threshold.source
    reason = Underived(
        kind=DerivationAbsence.NUMERIC_RESULT,
        reason=f"measured on the built solid of {built.pattern}: {meaning}",
    )
    name = f"DFM {rule.replace('_', ' ')}: {built.name}"
    if not items:
        return ScorecardEntry(name=name, status=CheckStatus.PASS, underived=reason,
                              detail=f"no {label} to judge on {built.name}{note}")  # fmt: skip
    worst = (min if sense is LimitSense.AT_LEAST else max)(items, key=lambda i: i.value)
    failing = [
        i
        for i in items
        if (
            i.value < threshold.value if sense is LimitSense.AT_LEAST else i.value > threshold.value
        )
    ]
    comparison = Comparison(
        measured=Quantity(magnitude=worst.value, unit=unit),
        limit=Quantity(magnitude=threshold.value, unit=unit),
        sense=sense,
        measured_label=f"worst {label}",
        # The source is free text and may carry a unit of its own ("30 mm V-die"), so it
        # stays in the detail; the label says only what kind of limit it is.
        limit_label="limit (a practice default)"
        if threshold.practice_default
        else "limit (the shop's override)",
    )
    suffix = {"mm": " mm", "degree": "°"}.get(unit, "")
    where = "; ".join(f"{i.where} ({i.value:.3g}{suffix})" for i in failing[:5])
    more = f" and {len(failing) - 5} more" if len(failing) > 5 else ""
    detail = (
        f"{len(failing)} of {len(items)} {label} beyond the limit of "
        f"{threshold.value:g}{suffix} ({basis}): {where}{more}{note}"
        if failing
        else f"all {len(items)} {label} within {threshold.value:g}{suffix} ({basis}){note}"
    )
    return ScorecardEntry(
        name=name,
        status=CheckStatus.FAIL if failing else CheckStatus.PASS,
        detail=detail,
        comparison=comparison,
        underived=reason,
    )


def screen_dfm(
    built: BuiltGeometry,
    profile: ProcessProfile,
    *,
    pull_direction: tuple[float, float, float] | None = None,
    build_direction: tuple[float, float, float] | None = None,
    tool_direction: tuple[float, float, float] | None = None,
) -> tuple[ScorecardEntry, ...]:
    """The DFM findings for a built part under ``profile``, one entry per rule.

    ``tool_direction`` (CNC milling), ``pull_direction`` (injection molding) and
    ``build_direction`` (additive) are the axis the cutter turns about, the direction the
    tool opens, and the direction the part grows; each process refuses a call without the
    one it needs.
    """
    entries = _findings(
        built,
        profile,
        pull_direction=pull_direction,
        build_direction=build_direction,
        tool_direction=tool_direction,
    )
    # Every DFM entry answers the one catalogued manufacturability mode.
    return tuple(entry.model_copy(update={"addresses": _ADDRESSES}) for entry in entries)


def _findings(
    built: BuiltGeometry,
    profile: ProcessProfile,
    *,
    pull_direction: tuple[float, float, float] | None,
    build_direction: tuple[float, float, float] | None,
    tool_direction: tuple[float, float, float] | None,
) -> tuple[ScorecardEntry, ...]:
    if not isinstance(built, BuiltGeometry):
        raise _refusal("built must be a BuiltGeometry from the geometry layer", subject="built",
                       source="geometry.build_spec")  # fmt: skip
    if not isinstance(profile, ProcessProfile):
        raise _refusal("profile must be a ProcessProfile", subject="profile")
    dims = built.dimensions_mm
    process = profile.process
    if process is DfmProcess.CNC_MILLING:
        tool = _vector(tool_direction, "tool_direction")
        radius = profile.threshold("internal_radius_min")
        depth = profile.threshold("hole_depth_ratio_max")
        holes = [
            _Item(f"{f.tag} ({f.kind}, Ø{f.diameter_mm:g} × {f.depth_mm:g} mm)",
                  f.depth_mm / f.diameter_mm)
            for f in built.features
            if f.kind in {"through_hole", "blind_hole", "counterbore", "countersink"}
        ]  # fmt: skip
        return (
            _entry(built, "internal_radius_min", radius, _internal_radii(built, tool),
                   label="internal corner radii"),
            _entry(built, "hole_depth_ratio_max", depth, holes,
                   label="hole depth-to-diameter ratios"),
        )  # fmt: skip
    if process is DfmProcess.SHEET_METAL:
        profile_flat = built.profile
        t = dims.get("thickness")
        if profile_flat is None or not profile_flat.bends or t is None:
            raise _refusal(f"{built.name} is not a formed sheet-metal part: it has no developed "
                           "profile with bend lines and a thickness", subject="built",
                           source="a sheet-metal pattern")  # fmt: skip
        bend = profile.threshold("bend_radius_ratio_min")
        to_bend = profile.threshold("hole_to_bend_min")
        to_edge = profile.threshold("hole_to_edge_min")
        ratio = dims.get("inside_radius", 0.0) / t
        radius_items = [_Item("every bend (inside radius over thickness)", ratio)]
        bend_items, edge_items = [], []
        outline = [(x, y) for x, y, _ in profile_flat.outline]
        edges = list(zip(outline, outline[1:] + outline[:1], strict=False))
        for x, y, d in profile_flat.circles:
            gap = min(_segment_distance((x, y), a, b) for a, b in profile_flat.bends) - d / 2
            bend_items.append(_Item(f"hole Ø{d:g} at ({x:g}, {y:g}) to its nearest bend", gap / t))
            if edges:
                edge = min(_segment_distance((x, y), a, b) for a, b in edges) - d / 2
                edge_items.append(_Item(f"hole Ø{d:g} at ({x:g}, {y:g}) to the blank's edge",
                                        edge / t))  # fmt: skip
        target = bend.value * t
        flange_items = [
            _Item(f"{key} {value:g} mm", value / t)
            for key, value in sorted(dims.items())
            if key.startswith("flange_")
        ]
        return (
            _entry(built, "bend_radius_ratio_min", bend, radius_items,
                   label="bend radius ratios",
                   note=f"; an inside_radius of {target:g} mm meets the limit"),
            _entry(built, "hole_to_bend_min", to_bend, bend_items,
                   label="hole-to-bend distances over thickness"),
            _entry(built, "hole_to_edge_min", to_edge, edge_items,
                   label="hole-to-edge distances over thickness",
                   note="; arcs in the outline are measured as their chords"),
            _entry(built, "flange_length_min", profile.threshold("flange_length_min"),
                   flange_items, label="flange lengths over thickness"),
        )  # fmt: skip
    if process in (DfmProcess.INJECTION_MOLDING, DfmProcess.DIE_CASTING):
        pull = _vector(pull_direction, "pull_direction")
        draft = profile.threshold("draft_min")
        items = []
        for face in built.shape.faces():
            kind = face.geom_type.name
            if kind == "PLANE":
                n = _unit(face.normal_at(face.center()))
                along = abs(_dot(n, pull))
                if along > 0.999:
                    continue  # faces across the pull part the mold, they need no draft
                angle = degrees(asin(min(1.0, along)))
            elif kind == "CYLINDER":
                axis = (
                    _unit(face.axis_of_rotation.direction)
                    if hasattr(face, "axis_of_rotation")
                    else None
                )
                if axis is None or abs(_dot(axis, pull)) < 0.999:
                    continue
                angle = 0.0
            else:
                continue
            items.append(_Item(_face_tag(built, face), angle))
        walls = {k: v for k, v in dims.items() if k in _WALL_KEYS}
        ratio_items = (
            [
                _Item(
                    f"thickest over thinnest of {sorted(walls)}",
                    max(walls.values()) / min(walls.values()),
                )
            ]
            if len(walls) >= 2
            else []
        )
        return (
            _entry(built, "draft_min", draft, items, label="face drafts",
                   note="; curved faces other than cylinders about the pull are not measured"),
            _entry(built, "wall_ratio_max", profile.threshold("wall_ratio_max"), ratio_items,
                   label="wall thickness ratios",
                   note="; walls are read from the part's declared dimensions"),
        )  # fmt: skip
    up = _vector(build_direction, "build_direction")
    overhang = profile.threshold("overhang_min")
    heights = [_dot(_point(v), up) for v in built.shape.vertices()]
    floor = min(heights) if heights else 0.0
    items = []
    for face in built.shape.faces():
        if face.geom_type.name != "PLANE":
            continue
        n = _unit(face.normal_at(face.center()))
        downward = -_dot(n, up)
        if downward <= 1e-9:
            continue
        lowest = min(_dot(_point(v), up) for v in face.vertices())
        highest = max(_dot(_point(v), up) for v in face.vertices())
        if highest - floor < 1e-6 and lowest - floor < 1e-6:
            continue  # on the build plate
        # The angle between the face's normal and straight down IS the face's angle above
        # horizontal: a face looking straight down is horizontal, 0°; a vertical wall is 90°.
        above_horizontal = degrees(acos(min(1.0, downward)))
        items.append(_Item(_face_tag(built, face), above_horizontal))
    return (
        _entry(built, "overhang_min", overhang, items, label="down-facing face angles",
               note="; curved down-facing faces are not measured"),
    )  # fmt: skip
