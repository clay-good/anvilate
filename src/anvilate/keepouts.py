"""Keepout bodies built on a part's own geometry, and the part's intrusion into each.

A :class:`~anvilate.spec.Keepout` declares a volume the part must leave empty. Here it
becomes a body: the rule's primitive, centred on the anchor face of the built part, its axis
along the face's inward normal and its near end ``offset`` from the face. Because it is
placed from the anchor face, the body moves when that face moves; a keepout anchored to a
face the build does not carry is not generated and says so.

Each keepout is then measured against the part solid, at nominal geometry:

- material in the protected **core** fails, naming the intersection volume and the worst
  penetration, the intersection's extent along the keepout axis;
- material in the **clearance margin** band is a warning: the core is clear and the entry
  says so with the clearance that remains, and a card holding one does not pass;
- a clean keepout states the clearance it was measured at.

The keepout bodies are returned separately and never unioned into the part. A summary entry
states how many keepouts were screened, against how many bodies, and the smallest clearance
with the keepout that produced it, so a clean result cannot be mistaken for one in which
nothing was screened.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .derivation import DerivationAbsence, Underived
from .export.dxf import _atomic_path
from .export.gate import ExportAuthorization
from .geometry import BuiltGeometry, GeometryUnavailable
from .scorecard import CheckStatus, Direction, RepairHint, Scorecard, ScorecardEntry
from .spec import (
    CylinderKeepout,
    DesignSpec,
    FrustumKeepout,
    Keepout,
    PrismKeepout,
    SweptProfileKeepout,
)

__all__ = [
    "KeepoutArchetype",
    "KEEPOUT_ARCHETYPES",
    "KeepoutBody",
    "build_keepout",
    "screen_keepouts",
    "keepout_label",
    "write_keepout_step",
]

# Below this the kernel's common volume is round-off, not material (mm³).
_VOLUME_EPSILON = 1e-6
# Below this a distance is round-off (mm): a nanometre, far under any clearance a drawing
# states.
_DISTANCE_EPSILON = 1e-6
_NOMINAL = "at nominal geometry, without declared tolerances applied"
# Which dimension of a box-shaped pattern runs along each axis, for the repair hint.
_BOX_AXES = {0: "width", 1: "depth", 2: "plate_thickness"}


@dataclass(frozen=True)
class KeepoutArchetype:
    """One keepout rule as a pattern in the library, answering its contribution contract.

    The contract every pattern ships under: a parametric implementation (``pattern``, built
    by :func:`build_keepout`), semantic tags (the keepout's own tag, carried by its body),
    declared parameter bounds (``bounds``, enforced when the document is read), a DFM
    profile (``dfm``: none, because a keepout is never made), analytical check bindings
    (``checked_by``), and golden-file tests, which ``tests/test_keepout_geometry.py`` holds
    at five or more per archetype.
    """

    rule: str
    pattern: str
    parameters: tuple[str, ...]
    bounds: str
    dfm: str = "none: a keepout is a protected volume and is never manufactured"
    checked_by: str = "anvilate.keepouts.screen_keepouts"


#: The generated keepout rules. An imported body is not among them: it is read from a file
#: another tool made, not built from parameters here.
KEEPOUT_ARCHETYPES: dict[str, KeepoutArchetype] = {
    archetype.rule: archetype
    for archetype in (
        KeepoutArchetype(
            rule="prism",
            pattern="keepout_prism/1",
            parameters=("width", "depth", "height"),
            bounds="every extent greater than zero",
        ),
        KeepoutArchetype(
            rule="cylinder",
            pattern="keepout_cylinder/1",
            parameters=("diameter", "height"),
            bounds="diameter and height greater than zero",
        ),
        KeepoutArchetype(
            rule="frustum",
            pattern="keepout_frustum/1",
            parameters=("base_diameter", "top_diameter", "height"),
            bounds="base diameter and height greater than zero; top diameter zero or more",
        ),
        KeepoutArchetype(
            rule="swept_profile",
            pattern="keepout_swept_profile/1",
            parameters=("profile_width", "profile_height", "path_length"),
            bounds="every extent greater than zero",
        ),
    )
}


@dataclass(frozen=True)
class KeepoutBody:
    """A keepout's protected core and its margin envelope, placed on the part."""

    keepout: Keepout
    core: Any
    envelope: Any | None
    axis: tuple[float, float, float]

    @property
    def pattern(self) -> str:
        """The archetype this body was built from, as the part's own pattern is named."""
        return KEEPOUT_ARCHETYPES[self.keepout.rule.rule].pattern


def _kernel() -> Any:
    try:
        import build123d
    except ImportError as failure:  # pragma: no cover - exercised without the geometry extra
        raise GeometryUnavailable(
            "keepout bodies need the optional dependency; install anvilate[geometry]"
        ) from failure
    return build123d


def _mm(value: Any) -> float:
    return float(value.to("mm").magnitude)


def _primitive(b: Any, keepout: Keepout, grow: float) -> Any | None:
    """The rule's body along +Z from z = -grow, grown by ``grow`` on every side."""
    rule, base = keepout.rule, (b.Align.CENTER, b.Align.CENTER, b.Align.MIN)
    if isinstance(rule, PrismKeepout):
        solid = b.Box(
            _mm(rule.width) + 2 * grow,
            _mm(rule.depth) + 2 * grow,
            _mm(rule.height) + 2 * grow,
            align=base,
        )
    elif isinstance(rule, SweptProfileKeepout):
        solid = b.Box(
            _mm(rule.profile_width) + 2 * grow,
            _mm(rule.profile_height) + 2 * grow,
            _mm(rule.path_length) + 2 * grow,
            align=base,
        )
    elif isinstance(rule, CylinderKeepout):
        solid = b.Cylinder(_mm(rule.diameter) / 2 + grow, _mm(rule.height) + 2 * grow, align=base)
    elif isinstance(rule, FrustumKeepout):
        bottom, top = _mm(rule.base_diameter) / 2 + grow, _mm(rule.top_diameter) / 2 + grow
        height = _mm(rule.height) + 2 * grow
        # A frustum whose two ends are equal is a cylinder, and the kernel refuses to build
        # it as a cone ("cone with two identic radii") with an exception of its own.
        if abs(bottom - top) <= 1e-9 * max(bottom, 1.0):
            solid = b.Cylinder(bottom, height, align=base)
        else:
            solid = b.Cone(bottom, top, height, align=base)
    else:
        return None  # an imported body is a file this module does not read
    return b.Pos(0, 0, -grow) * solid


def build_keepout(keepout: Keepout, part: BuiltGeometry) -> KeepoutBody | None:
    """``keepout`` as a body on ``part``, or ``None`` when it cannot be generated here.

    ``None`` when the anchor is not a face the build tags, or the rule is an imported body.
    """
    b = _kernel()
    faces = part.faces.get(str(keepout.anchor))
    if not faces:
        return None
    face = faces[0]
    center = face.center()
    inward = -face.normal_at(center)
    plane = b.Plane(origin=center + inward * _mm(keepout.offset), z_dir=inward)
    core = _primitive(b, keepout, 0.0)
    if core is None:
        return None
    margin = _mm(keepout.clearance_margin)
    envelope = _primitive(b, keepout, margin) if margin > 0 else None
    return KeepoutBody(
        keepout=keepout,
        core=plane.location * core,
        envelope=None if envelope is None else plane.location * envelope,
        axis=(inward.X, inward.Y, inward.Z),
    )


def _extent_along(shape: Any, axis: tuple[float, float, float]) -> float:
    along = [sum(c * a for c, a in zip(tuple(v), axis, strict=True)) for v in shape.vertices()]
    return max(along) - min(along) if along else 0.0


def _repair(part: BuiltGeometry, axis: tuple[float, float, float], depth: float, margin: float):
    """Shrink the part dimension running along the keepout axis, for a box pattern."""
    index = max(range(3), key=lambda i: abs(axis[i]))
    parameter = _BOX_AXES.get(index)
    if parameter is None or parameter not in part.dimensions_mm:
        return None
    target = part.dimensions_mm[parameter] - depth - margin
    if target <= 0:
        return RepairHint(parameter=parameter, direction=Direction.DECREASE)
    return RepairHint.solved(
        parameter,
        direction=Direction.DECREASE,
        value=target,
        unit="mm",
        provenance="keepout penetration and margin, measured along its axis",
    )


def _entry(keepout: Keepout, part: BuiltGeometry, body: KeepoutBody | None) -> tuple:
    name = f"keepout {keepout.tag}"
    about = f"'{keepout.tag}' ({keepout.reason})"
    if body is None:
        why = (
            "its rule is an imported body, whose file this build does not read"
            if keepout.rule.rule == "imported_body"
            else f"its anchor '{keepout.anchor}' is not a face this build tags; it tags "
            f"{sorted(part.faces)}"
        )
        return (
            ScorecardEntry(
                name=name,
                status=CheckStatus.NOT_EVALUATED,
                detail=f"keepout {about} was not generated: {why}",
            ),
            None,
        )
    solid = part.shape
    core = solid & body.core
    volume = float(core.volume) if core is not None else 0.0
    margin = _mm(keepout.clearance_margin)
    reason = Underived(
        kind=DerivationAbsence.NUMERIC_RESULT,
        reason="exact B-Rep common volume and minimum distance between the part and the body",
    )
    if volume > _VOLUME_EPSILON:
        depth = _extent_along(core, body.axis)
        return (
            ScorecardEntry(
                name=name,
                status=CheckStatus.FAIL,
                detail=(
                    f"{part.name} intrudes on keepout {about}: {volume:.3g} mm³ in the protected "
                    f"core, {depth:.3g} mm deep along its axis, {_NOMINAL}"
                ),
                underived=reason,
                repair_hint=_repair(part, body.axis, depth, margin),
            ),
            0.0,
        )
    clearance = float(solid.distance_to(body.core))
    # The kernel's distance between touching bodies is round-off, not a gap.
    if clearance < _DISTANCE_EPSILON:
        clearance = 0.0
    if clearance < margin:
        return (
            ScorecardEntry(
                name=name,
                status=CheckStatus.WARNING,
                detail=(
                    f"{part.name} stops {clearance:.3g} mm from keepout {about}, inside its "
                    f"{margin:g} mm clearance margin; the core is clear, {_NOMINAL}"
                ),
                underived=reason,
                repair_hint=_repair(part, body.axis, 0.0, margin - clearance),
            ),
            clearance,
        )
    return (
        ScorecardEntry(
            name=name,
            status=CheckStatus.PASS,
            detail=(
                f"{part.name} clears keepout {about} by {clearance:.3g} mm, outside its "
                f"{margin:g} mm margin, {_NOMINAL}"
            ),
            underived=reason,
        ),
        clearance,
    )


def screen_keepouts(
    spec: DesignSpec, part: BuiltGeometry
) -> tuple[tuple[ScorecardEntry, ...], tuple[KeepoutBody, ...]]:
    """Each declared keepout measured against ``part``, a summary, and the bodies built.

    The bodies come back beside the part and are never unioned into it. A spec declaring
    no keepouts returns nothing: there is no claim to check.
    """
    if not spec.keepouts:
        return (), ()
    entries, bodies, clearances = [], [], []
    for keepout in spec.keepouts:
        body = build_keepout(keepout, part)
        entry, clearance = _entry(keepout, part, body)
        entries.append(entry)
        if body is not None:
            bodies.append(body)
        if clearance is not None:
            clearances.append((clearance, str(keepout.tag)))
    if clearances:
        smallest, tag = min(clearances)
        summary = ScorecardEntry(
            name="keepout intrusion",
            status=Scorecard(entries=tuple(entries)).status,
            detail=(
                f"{len(bodies)} of {len(spec.keepouts)} keepouts screened against 1 body "
                f"({part.name}); smallest clearance {smallest:.3g} mm, at keepout '{tag}', "
                f"{_NOMINAL}"
            ),
            underived=Underived(
                kind=DerivationAbsence.NUMERIC_RESULT,
                reason="the governing value of the per-keepout measurements above",
            ),
        )
    else:
        summary = ScorecardEntry(
            name="keepout intrusion",
            status=CheckStatus.NOT_EVALUATED,
            detail=(
                f"0 of {len(spec.keepouts)} declared keepouts were generated, so nothing was "
                "screened; this is not a clean result"
            ),
        )
    return (summary, *entries), tuple(bodies)


def keepout_label(keepout: Keepout) -> str:
    """The name a keepout body carries in every export: its tag, that it is not to be made,
    and why it is protected."""
    return f"KEEPOUT {keepout.tag} (non-manufacturing): {keepout.reason}"


def write_keepout_step(
    bodies: tuple[KeepoutBody, ...], path: Path, *, authorization: ExportAuthorization
) -> Path:
    """Write the keepout bodies to their own STEP file, each named as non-manufacturing.

    A separate file rather than extra bodies in the part's: the machinable solid's STEP is
    unchanged by any keepout, so a CAM tool reading it cannot machine a protected volume,
    and a reader of this file sees each body's tag and reason as its product name. The
    header carries the export authorization and a fixed date, as the part's STEP does, so
    the same bodies write the same bytes.
    """
    if not bodies:
        raise ValueError("there are no keepout bodies to write; screen_keepouts built none")
    b = _kernel()
    from .geometry import _GVP_RECOMMENDED_PRACTICE, _step_string

    solids = []
    for body in bodies:
        solid = body.core
        solid.label = keepout_label(body.keepout)
        solids.append(solid)
    compound = b.Compound(children=solids)
    compound.label = "keepouts (non-manufacturing)"
    with _atomic_path(path) as partial:
        b.export_step(compound, str(partial))
        try:
            text = partial.read_text(encoding="utf-8")
        except UnicodeDecodeError as failure:
            raise ValueError("the STEP writer produced a file that is not UTF-8") from failure
        descriptions = [
            "keepout bodies: protected volumes, not part geometry",
            _GVP_RECOMMENDED_PRACTICE,
            *(f"{key}={value}" for key, value in authorization.metadata()),
        ]
        header = (
            "FILE_DESCRIPTION(("
            + ",".join(f"'{_step_string(value)}'" for value in descriptions)
            + "),'2;1');"
        )
        text, described = re.subn(r"FILE_DESCRIPTION\(.*?\);", header, text, count=1)
        text, named = re.subn(
            r"FILE_NAME\('[^']*','[^']*',",
            lambda _match: "FILE_NAME('keepouts','2000-01-01T00:00:00',",
            text,
            count=1,
        )
        if described != 1 or named != 1:
            raise ValueError("the STEP writer produced an unrecognized header")
        # The writer numbers assembly usages from a counter that lives for the process, so
        # a second export of the same bodies came out with different ids. Renumbered in
        # file order, the same bodies write the same bytes.
        occurrences = iter(range(1, 1_000_000))
        text = re.sub(
            r"NEXT_ASSEMBLY_USAGE_OCCURRENCE\('\d+'",
            lambda _match: f"NEXT_ASSEMBLY_USAGE_OCCURRENCE('{next(occurrences)}'",
            text,
        )
        partial.write_text(text, encoding="utf-8")
    return path
