"""One vocabulary of holes, slots and edge treatments, shared by every drawable pattern.

A bracket, a flange and a lug all need the same hole. Built inside each pattern it would be
three holes with three sets of bugs and three vocabularies for measuring them. Here a cut is
declared once (:func:`through_hole`, :func:`blind_hole`, :func:`counterbore`,
:func:`countersink`, :func:`slot`, and the :func:`rectangular_pattern` and
:func:`bolt_circle` that place several), applied to a planar *host* by :func:`apply`, and
comes back as a tagged :class:`Feature` a caller can measure by name.

A cut that cannot be made in its host is refused, naming the cut, the host and the
shortfall: a hole bigger than the face it is in, one that breaks out through an edge, two
that overlap, a blind hole deeper than the material. A tapped hole is a hole that carries its
thread designation as data. Thread helices are never modelled.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from .geometry import GeometryError

__all__ = [
    "Cut",
    "Feature",
    "Host",
    "apply",
    "blind_hole",
    "bolt_circle",
    "counterbore",
    "countersink",
    "rectangular_pattern",
    "round_corners",
    "slot",
    "through_hole",
]

Vec = tuple[float, float, float]

_KINDS = ("through_hole", "blind_hole", "counterbore", "countersink", "slot")


def _refuse(message: str, *, subject: str) -> GeometryError:
    return GeometryError(
        message,
        action="replace",
        subject=subject,
        source="a feature that fits inside the face it is cut into, clear of its edges",
    )


@dataclass(frozen=True)
class Host:
    """The planar slab a feature is cut into: a face, its frame, its extent and its depth.

    ``origin`` is the centre of the entry face, ``u`` and ``v`` the in-plane unit axes,
    and ``normal`` the outward unit normal: features are cut inward, along ``-normal``.
    ``width`` runs along ``u`` and ``height`` along ``v``; a round host states ``radius``
    instead, and features must then fit inside that circle.
    """

    name: str
    origin: Vec
    u: Vec
    v: Vec
    normal: Vec
    thickness: float
    width: float | None = None
    height: float | None = None
    radius: float | None = None


@dataclass(frozen=True)
class Cut:
    """One declared cut, in the host's own (u, v) coordinates from its centre."""

    tag: str
    kind: str
    u: float
    v: float
    diameter: float
    depth: float | None = None
    extra: Mapping[str, float] = field(default_factory=dict)
    thread: str | None = None

    @property
    def radius(self) -> float:
        """Half the cut's width on the face: its widest round, or half a slot's width."""
        return (
            max(
                self.diameter,
                self.extra.get("counterbore_diameter", 0.0),
                self.extra.get("head_diameter", 0.0),
            )
            / 2
        )

    @property
    def spine(self) -> tuple[tuple[float, float], tuple[float, float]]:
        """The segment the cut's footprint is swept along: a point for a round cut.

        A footprint is every point within :attr:`radius` of this segment, which is a circle
        for a hole and a round-ended slot for a slot. Edge distance and overlap are measured
        on that shape, not on a circle around it: a slot lying along a plate's edge is as
        close to the edge as its width, not its length.
        """
        if self.kind != "slot":
            return (self.u, self.v), (self.u, self.v)
        half = (self.extra["length"] - self.diameter) / 2
        angle = math.radians(self.extra["angle_deg"])
        du, dv = half * math.cos(angle), half * math.sin(angle)
        return (self.u - du, self.v - dv), (self.u + du, self.v + dv)


@dataclass(frozen=True)
class Feature:
    """A cut as built: its tag, kind and size, and where it is in the part's coordinates."""

    tag: str
    kind: str
    diameter_mm: float
    depth_mm: float
    position_mm: Vec
    axis: Vec
    extra: Mapping[str, float] = field(default_factory=dict)
    thread: str | None = None

    def measure(self, quantity: str) -> float:
        """One number about this feature: diameter, depth, x, y, z, or a named extra."""
        values = {
            "diameter": self.diameter_mm,
            "depth": self.depth_mm,
            "x": self.position_mm[0],
            "y": self.position_mm[1],
            "z": self.position_mm[2],
            **self.extra,
        }
        if quantity not in values:
            raise GeometryError(
                f"feature {self.tag!r} has no {quantity!r}; it has {sorted(values)}",
                action="select",
                subject=f"the feature quantity {quantity!r}",
                source=f"what the {self.kind} {self.tag!r} can be measured by",
            )
        return float(values[quantity])


def _positive(value: float, what: str, tag: str) -> float:
    if not (isinstance(value, int | float) and math.isfinite(value) and value > 0):
        raise _refuse(
            f"{tag}: {what} must be a positive length in mm; got {value}",
            subject=f"the {what} of {tag}",
        )
    return float(value)


def through_hole(
    tag: str, u: float, v: float, diameter: float, *, thread: str | None = None
) -> Cut:
    """A round hole through the whole host. ``thread`` marks it tapped, as data."""
    return Cut(tag, "through_hole", u, v, _positive(diameter, "diameter", tag), thread=thread)


def blind_hole(
    tag: str, u: float, v: float, diameter: float, depth: float, *, thread: str | None = None
) -> Cut:
    """A round hole ``depth`` deep that stops inside the host."""
    return Cut(
        tag,
        "blind_hole",
        u,
        v,
        _positive(diameter, "diameter", tag),
        _positive(depth, "depth", tag),
        thread=thread,
    )


def counterbore(
    tag: str,
    u: float,
    v: float,
    diameter: float,
    counterbore_diameter: float,
    counterbore_depth: float,
) -> Cut:
    """A through hole with a wider flat-bottomed recess for a screw head."""
    diameter = _positive(diameter, "diameter", tag)
    wide = _positive(counterbore_diameter, "counterbore diameter", tag)
    if wide <= diameter:
        raise _refuse(
            f"{tag}: the counterbore ({wide:g} mm) must be wider than its hole ({diameter:g} mm)",
            subject=f"the counterbore diameter of {tag}",
        )
    extra = {
        "counterbore_diameter": wide,
        "counterbore_depth": _positive(counterbore_depth, "counterbore depth", tag),
    }
    return Cut(tag, "counterbore", u, v, diameter, extra=MappingProxyType(extra))


def countersink(
    tag: str,
    u: float,
    v: float,
    diameter: float,
    head_diameter: float,
    *,
    angle_deg: float = 90.0,
) -> Cut:
    """A through hole with a conical recess, ``angle_deg`` being the cone's included angle."""
    diameter = _positive(diameter, "diameter", tag)
    head = _positive(head_diameter, "head diameter", tag)
    if head <= diameter:
        raise _refuse(
            f"{tag}: the countersink ({head:g} mm) must be wider than its hole ({diameter:g} mm)",
            subject=f"the head diameter of {tag}",
        )
    if not 60.0 <= angle_deg <= 120.0:
        raise _refuse(
            f"{tag}: a countersink's included angle is from 60 to 120 degrees; got {angle_deg:g}",
            subject=f"the countersink angle of {tag}",
        )
    extra = {"head_diameter": head, "angle_deg": float(angle_deg)}
    return Cut(tag, "countersink", u, v, diameter, extra=MappingProxyType(extra))


def slot(
    tag: str, u: float, v: float, length: float, width: float, *, angle_deg: float = 0.0
) -> Cut:
    """A round-ended through slot: ``length`` overall, ``width`` across, turned by ``angle_deg``."""
    width = _positive(width, "width", tag)
    length = _positive(length, "length", tag)
    if length <= width:
        raise _refuse(
            f"{tag}: a slot's length ({length:g} mm) must exceed its width ({width:g} mm); "
            "equal lengths are a round hole",
            subject=f"the length of {tag}",
        )
    extra = {"length": length, "angle_deg": float(angle_deg)}
    return Cut(tag, "slot", u, v, width, extra=MappingProxyType(extra))


def rectangular_pattern(
    tag: str,
    *,
    count_u: int,
    count_v: int,
    pitch_u: float,
    pitch_v: float,
    diameter: float,
    centre: tuple[float, float] = (0.0, 0.0),
    thread: str | None = None,
) -> tuple[Cut, ...]:
    """``count_u`` by ``count_v`` through holes on a grid centred at ``centre``."""
    if not (isinstance(count_u, int) and isinstance(count_v, int) and count_u >= 1 <= count_v):
        raise _refuse(
            f"{tag}: a rectangular pattern needs whole counts of at least 1; got "
            f"{count_u} by {count_v}",
            subject=f"the counts of {tag}",
        )
    if count_u * count_v > 400:
        raise _refuse(
            f"{tag}: {count_u * count_v} holes is past the 400 a pattern may hold",
            subject=f"the counts of {tag}",
        )
    if count_u > 1:
        _positive(pitch_u, "pitch along u", tag)
    if count_v > 1:
        _positive(pitch_v, "pitch along v", tag)
    cuts = []
    for i in range(count_u):
        for j in range(count_v):
            u = centre[0] + (i - (count_u - 1) / 2) * pitch_u
            v = centre[1] + (j - (count_v - 1) / 2) * pitch_v
            cuts.append(through_hole(f"{tag}_{i + 1}_{j + 1}", u, v, diameter, thread=thread))
    return tuple(cuts)


def bolt_circle(
    tag: str,
    *,
    count: int,
    circle_diameter: float,
    diameter: float,
    start_angle_deg: float = 0.0,
    centre: tuple[float, float] = (0.0, 0.0),
    thread: str | None = None,
) -> tuple[Cut, ...]:
    """``count`` equally spaced through holes on a circle of ``circle_diameter``."""
    if not (isinstance(count, int) and 2 <= count <= 72):
        raise _refuse(
            f"{tag}: a bolt circle holds from 2 to 72 holes; got {count}",
            subject=f"the count of {tag}",
        )
    radius = _positive(circle_diameter, "circle diameter", tag) / 2
    cuts = []
    for index in range(count):
        angle = math.radians(start_angle_deg) + 2 * math.pi * index / count
        cuts.append(
            through_hole(
                f"{tag}_{index + 1}",
                centre[0] + radius * math.cos(angle),
                centre[1] + radius * math.sin(angle),
                diameter,
                thread=thread,
            )
        )
    return tuple(cuts)


Point2 = tuple[float, float]


def _to_segment(point: Point2, segment: tuple[Point2, Point2]) -> float:
    (ax, ay), (bx, by) = segment
    dx, dy = bx - ax, by - ay
    span = dx * dx + dy * dy
    t = (
        0.0
        if span == 0
        else max(0.0, min(1.0, ((point[0] - ax) * dx + (point[1] - ay) * dy) / span))
    )
    return math.hypot(point[0] - (ax + t * dx), point[1] - (ay + t * dy))


def _crossing(first: tuple[Point2, Point2], second: tuple[Point2, Point2]) -> bool:
    def side(a: Point2, b: Point2, c: Point2) -> float:
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    (a, b), (c, d) = first, second
    return side(a, b, c) * side(a, b, d) < 0 and side(c, d, a) * side(c, d, b) < 0


def _between(first: tuple[Point2, Point2], second: tuple[Point2, Point2]) -> float:
    """The least distance between two segments (either may be a single point)."""
    if _crossing(first, second):
        return 0.0
    return min(
        _to_segment(first[0], second),
        _to_segment(first[1], second),
        _to_segment(second[0], first),
        _to_segment(second[1], first),
    )


def _fits(host: Host, cuts: Sequence[Cut]) -> None:
    """Refuse the first cut that cannot be made in ``host``, saying by how much."""
    tags = [cut.tag for cut in cuts]
    repeated = sorted({tag for tag in tags if tags.count(tag) > 1})
    if repeated:
        raise _refuse(
            f"{host.name}: these feature tags are used twice: {repeated}",
            subject=f"the feature tags of {host.name}",
        )
    for cut in cuts:
        ends = cut.spine
        if host.radius is not None:
            edge = host.radius - max(math.hypot(u, v) for u, v in ends) - cut.radius
        else:
            assert host.width is not None and host.height is not None
            edge = (
                min(min(host.width / 2 - abs(u), host.height / 2 - abs(v)) for u, v in ends)
                - cut.radius
            )
        if edge <= 1e-9:
            raise _refuse(
                f"{cut.tag} does not fit in {host.name}: its edge would be "
                f"{max(0.0, -edge):g} mm outside the face",
                subject=f"the position or size of {cut.tag}",
            )
        depths = [cut.depth or 0.0, cut.extra.get("counterbore_depth", 0.0)]
        if cut.kind == "countersink":
            half = math.radians(cut.extra["angle_deg"]) / 2
            depths.append((cut.extra["head_diameter"] - cut.diameter) / 2 / math.tan(half))
        if max(depths) >= host.thickness:
            raise _refuse(
                f"{cut.tag} is {max(depths):g} mm deep and {host.name} is "
                f"{host.thickness:g} mm thick; a recess must stop inside the material",
                subject=f"the depth of {cut.tag}",
            )
    for index, first in enumerate(cuts):
        for second in cuts[index + 1 :]:
            gap = _between(first.spine, second.spine) - first.radius - second.radius
            if gap <= 1e-9:
                raise _refuse(
                    f"{first.tag} and {second.tag} overlap by {max(0.0, -gap):g} mm in {host.name}",
                    subject=f"the positions of {first.tag} and {second.tag}",
                )


def _point(host: Host, u: float, v: float) -> Vec:
    return (
        host.origin[0] + host.u[0] * u + host.v[0] * v,
        host.origin[1] + host.u[1] * u + host.v[1] * v,
        host.origin[2] + host.u[2] * u + host.v[2] * v,
    )


def apply(shape: Any, host: Host, cuts: Sequence[Cut]) -> tuple[Any, tuple[Feature, ...]]:
    """Cut every feature into ``shape`` through ``host``, returning the solid and the features.

    All cuts are checked against the host and each other before any is made, so a refusal
    leaves nothing half-built.
    """
    from build123d import Align, Box, Cone, Cylinder, Plane, Pos, Rot

    cuts = tuple(cuts)
    for cut in cuts:
        if cut.kind not in _KINDS:
            raise _refuse(f"{cut.tag}: unknown feature kind {cut.kind!r}", subject=cut.tag)
    _fits(host, cuts)
    plane = Plane(origin=host.origin, x_dir=host.u, z_dir=host.normal)
    centred_top = (Align.CENTER, Align.CENTER, Align.MAX)
    through = host.thickness + 2.0
    features = []
    for cut in cuts:
        place = plane.location * Pos(cut.u, cut.v, 0)
        if cut.kind == "slot":
            straight = cut.extra["length"] - cut.diameter
            tool = Box(straight, cut.diameter, through, align=centred_top)
            for end in (-straight / 2, straight / 2):
                tool = tool + Pos(end, 0, 0) * Cylinder(
                    cut.diameter / 2, through, align=centred_top
                )
            tool = Pos(0, 0, 1.0) * Rot(0, 0, cut.extra["angle_deg"]) * tool
            depth = host.thickness
        elif cut.kind == "blind_hole":
            assert cut.depth is not None
            tool = Cylinder(cut.diameter / 2, cut.depth, align=centred_top)
            depth = cut.depth
        else:
            tool = Pos(0, 0, 1.0) * Cylinder(cut.diameter / 2, through, align=centred_top)
            depth = host.thickness
            if cut.kind == "counterbore":
                tool = tool + Pos(0, 0, 1.0) * Cylinder(
                    cut.extra["counterbore_diameter"] / 2,
                    cut.extra["counterbore_depth"] + 1.0,
                    align=centred_top,
                )
            elif cut.kind == "countersink":
                half = math.radians(cut.extra["angle_deg"]) / 2
                rise = (cut.extra["head_diameter"] - cut.diameter) / 2 / math.tan(half)
                tool = tool + Cone(
                    cut.diameter / 2, cut.extra["head_diameter"] / 2, rise, align=centred_top
                )
        shape = shape - place * tool
        features.append(
            Feature(
                tag=cut.tag,
                kind=cut.kind,
                diameter_mm=cut.diameter,
                depth_mm=depth,
                position_mm=_point(host, cut.u, cut.v),
                axis=host.normal,
                extra=cut.extra,
                thread=cut.thread,
            )
        )
    return shape, tuple(features)


def round_corners(shape: Any, radius: float, *, along: Vec = (0.0, 0.0, 1.0)) -> Any:
    """Fillet the edges of ``shape`` that run parallel to ``along`` (a plate's corners)."""
    from build123d import Axis, fillet

    _positive(radius, "corner radius", "the corner fillet")
    axis = Axis((0, 0, 0), along)
    edges = shape.edges().filter_by(axis)
    if not edges:
        raise _refuse(
            "the corner fillet found no edges along the stated direction",
            subject="the corner radius",
        )
    try:
        return fillet(edges, radius)
    except Exception as failure:  # noqa: BLE001 - the kernel refuses an oversize fillet its own way
        raise _refuse(
            f"a {radius:g} mm corner radius does not fit this part's edges",
            subject="the corner radius",
        ) from failure
