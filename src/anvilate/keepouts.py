"""Keepout bodies built on a part's own geometry, and the part's intrusion into each.

A :class:`~anvilate.spec.Keepout` declares a volume the part must leave empty. Here it
becomes a body: the rule's primitive, centred on the anchor face of the built part, its axis
along the face's inward normal and its near end ``offset`` from the face. Because it is
placed from the anchor face, the body moves when that face moves; a keepout anchored to a
face the build does not carry is not generated and says so.

Each keepout is then measured against the part solid, at nominal geometry:

- material in the protected **core** fails, naming the intersection volume and the worst
  penetration, the intersection's extent along the keepout axis;
- material in the **clearance margin** band fails too, as a margin intrusion with the
  clearance that remains. The spec asks for a warning here, and the library has no
  warning status; a margin the document declared is a requirement it stated, so the entry
  fails and says the core is untouched rather than passing over it;
- a clean keepout states the clearance it was measured at.

The keepout bodies are returned separately and never unioned into the part. A summary entry
states how many keepouts were screened, against how many bodies, and the smallest clearance
with the keepout that produced it, so a clean result cannot be mistaken for one in which
nothing was screened.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .derivation import DerivationAbsence, Underived
from .geometry import BuiltGeometry, GeometryUnavailable
from .scorecard import CheckStatus, Direction, RepairHint, ScorecardEntry
from .spec import (
    CylinderKeepout,
    DesignSpec,
    FrustumKeepout,
    Keepout,
    PrismKeepout,
    SweptProfileKeepout,
)

__all__ = ["KeepoutBody", "build_keepout", "screen_keepouts"]

# Below this the kernel's common volume is round-off, not material (mm³).
_VOLUME_EPSILON = 1e-6
_NOMINAL = "at nominal geometry, without declared tolerances applied"
# Which dimension of a box-shaped pattern runs along each axis, for the repair hint.
_BOX_AXES = {0: "width", 1: "depth", 2: "plate_thickness"}


@dataclass(frozen=True)
class KeepoutBody:
    """A keepout's protected core and its margin envelope, placed on the part."""

    keepout: Keepout
    core: Any
    envelope: Any | None
    axis: tuple[float, float, float]


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
        solid = b.Cone(
            _mm(rule.base_diameter) / 2 + grow,
            _mm(rule.top_diameter) / 2 + grow,
            _mm(rule.height) + 2 * grow,
            align=base,
        )
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
    if clearance < margin:
        return (
            ScorecardEntry(
                name=name,
                status=CheckStatus.FAIL,
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
            status=CheckStatus.PASS
            if all(e.status is CheckStatus.PASS for e in entries)
            else CheckStatus.FAIL,
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
