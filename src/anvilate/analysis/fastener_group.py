"""T1 fastener groups: in-plane load shared by stiffness, then each fastener's interaction.

A bolt pattern carries an in-plane shear and a twisting moment through its fasteners. The
Astronautic Structures Manual (NASA TM X-73305, Vol. I, §B1.1.1) states the accepted
practice: friction between the plates is ignored; a load through the centroid of the
pattern is shared equally by equal fasteners and in proportion to their section areas
otherwise; and a load whose line misses the centroid must have its eccentricity taken
into account. Where the fasteners' shear stiffnesses are known and differ, they are the
better weights, and a declared stiffness replaces the area.

With weights w_i and positions r_i measured from the weighted centroid, a rigid plate
moved by the load gives each fastener

    direct     F_i = V · w_i / Σw
    torsional  F_i = M · w_i · (−y_i, x_i) / Σ w_i·r_i²

where M is the moment about the centroid, the applied moment plus the eccentricity of V.
A tension through the pattern's centroid is shared by the same weights. A moment about an
in-plane axis (prying, out-of-plane bending) is not distributed here.

Each fastener is then checked at the ultimate condition by NASA-STD-5020B's combined
shear and tension criteria (§4.4.4), without the bending term:

    full-diameter body in the shear plane   (P_s/P_s-allow)^2.5 + (P_t/P_t-allow)^1.5 ≤ 1   (Eq. 20)
    threads in the shear plane              (P_s/P_s-allow)^1.2 + (P_t/P_t-allow)^2   ≤ 1   (Eq. 22)

The bending term may be left out where the shear is not carried across a gap or a
non-load-carrying spacer (§4.4.4); where it is, these indices are unconservative and the
result says the bending term was not included. Preload is left out, as §4.4.4 allows at
ultimate. Where a fastener declares a pull-through allowable, its tension is held to it.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import StrEnum
from math import hypot, pi

from pydantic import BaseModel, ConfigDict, model_validator

from .._models import Named, RevalidatedModel, each_one
from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

__all__ = [
    "ShearPlane",
    "GroupFastener",
    "FastenerLoad",
    "FastenerGroupResult",
    "fastener_group_loads",
]

_PATTERN_SOURCE = "the fastener pattern's drawing: positions, diameters and stiffnesses"
_ALLOWABLE_SOURCE = "the fastener's procurement specification allowables"
_LOAD_SOURCE = "the ultimate design loads on the pattern"
_EXPONENTS = {"body": (2.5, 1.5, "Eq. 20"), "threads": (1.2, 2.0, "Eq. 22")}


class _FastenerGroupInputError(RefusalError, ValueError):
    """A fastener-group input that cannot be used without correction."""


def _refusal(message: str, *, subject: str, source: str) -> _FastenerGroupInputError:
    return _FastenerGroupInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


def _magnitude(value: Quantity, unit: str, name: str, source: str, *, positive: bool) -> float:
    if not isinstance(value, Quantity):
        raise _refusal(f"{name} must be a quantity in {unit}; got {value!r}", subject=name,
                       source=source)  # fmt: skip
    try:
        magnitude = value.to(unit).magnitude
    except Exception as error:
        raise _refusal(f"{name} is {value}, which is not convertible to {unit}", subject=name,
                       source=source) from error  # fmt: skip
    magnitude = require_finite(magnitude, name=name)
    if positive and magnitude <= 0:
        raise _refusal(f"{name} must be positive; got {value}", subject=name, source=source)
    return magnitude


class ShearPlane(StrEnum):
    """What the shear plane cuts, which sets the NASA-STD-5020B interaction exponents."""

    BODY = "body"
    THREADS = "threads"


class GroupFastener(RevalidatedModel):
    """One fastener of a pattern, its position and its ultimate allowables (NASA-STD-5020B).

    ``stiffness`` is its shear stiffness, from test or a cited formula; left out, the
    fastener is weighted by its shank area, as NASA TM X-73305 §B1.1.1(2) does.
    """

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    name: Named
    x: Quantity
    y: Quantity
    diameter: Quantity
    shear_allowable: Quantity
    tension_allowable: Quantity
    shear_plane: ShearPlane
    stiffness: Quantity | None = None
    pull_through_allowable: Quantity | None = None

    @model_validator(mode="after")
    def _a_fastener(self) -> GroupFastener:
        _magnitude(self.x, "mm", "x", _PATTERN_SOURCE, positive=False)
        _magnitude(self.y, "mm", "y", _PATTERN_SOURCE, positive=False)
        _magnitude(self.diameter, "mm", "diameter", _PATTERN_SOURCE, positive=True)
        _magnitude(self.shear_allowable, "N", "shear_allowable", _ALLOWABLE_SOURCE, positive=True)
        _magnitude(self.tension_allowable, "N", "tension_allowable", _ALLOWABLE_SOURCE,
                   positive=True)  # fmt: skip
        if self.stiffness is not None:
            _magnitude(self.stiffness, "N/mm", "stiffness", _PATTERN_SOURCE, positive=True)
        if self.pull_through_allowable is not None:
            _magnitude(self.pull_through_allowable, "N", "pull_through_allowable",
                       _ALLOWABLE_SOURCE, positive=True)  # fmt: skip
        return self

    def _weight(self, *, by_stiffness: bool) -> float:
        if by_stiffness:
            return float(self.stiffness.to("N/mm").magnitude)  # type: ignore[union-attr]
        d = float(self.diameter.to("mm").magnitude)
        return pi * d * d / 4


class FastenerLoad(RevalidatedModel):
    """One fastener's share and its NASA-STD-5020B interaction index (≤ 1 passes).

    Forces in N. ``pull_through_ratio`` is tension over the pull-through allowable, or
    ``None`` where none was declared.
    """

    model_config = ConfigDict(frozen=True)

    name: Named
    shear_x: float
    shear_y: float
    shear: float
    tension: float
    interaction: float
    equation: str
    pull_through_ratio: float | None


class FastenerGroupResult(BaseModel):
    """Every fastener's load and interaction, the governing one, and how it was shared.

    ``weighted_by`` is "stiffness" or "shank area" (NASA TM X-73305 §B1.1.1);
    ``centroid`` is the weighted centroid in mm. The bending term of NASA-STD-5020B
    Eqs. 20 and 22 is not included, and the result says so.
    """

    model_config = ConfigDict(frozen=True)

    fasteners: tuple[FastenerLoad, ...]
    governing: str
    governing_index: float
    centroid: tuple[float, float]
    weighted_by: str
    bending_term_included: bool = False

    def __str__(self) -> str:
        worst = next(f for f in self.fasteners if f.name == self.governing)
        return (
            f"fastener {self.governing} governs: interaction {self.governing_index:.3f} "
            f"({worst.equation}, without the bending term) at {worst.shear:.4g} N shear and "
            f"{worst.tension:.4g} N tension; shared by {self.weighted_by} (NASA-STD-5020B)"
        )


def fastener_group_loads(
    fasteners: Sequence[GroupFastener],
    *,
    shear_x: Quantity,
    shear_y: Quantity,
    moment: Quantity,
    load_x: Quantity,
    load_y: Quantity,
    tension: Quantity,
) -> FastenerGroupResult:
    """Share ultimate loads over a pattern and check each fastener (NASA-STD-5020B §4.4.4).

    ``shear_x`` and ``shear_y`` act at the point (``load_x``, ``load_y``), and ``moment``
    is an applied moment about the out-of-plane axis, counter-clockwise positive;
    ``tension`` is the total through the pattern's centroid. Either every fastener declares
    a stiffness or none does: weights of two kinds cannot be compared.
    """
    group = each_one(fasteners, GroupFastener, named="fasteners")
    if not group:
        raise _refusal("a pattern has at least one fastener", subject="fasteners",
                       source=_PATTERN_SOURCE)  # fmt: skip
    names = [f.name for f in group]
    if len(set(names)) != len(names):
        raise _refusal(f"fastener names {names} repeat; each is reported by its name",
                       subject="fasteners", source=_PATTERN_SOURCE)  # fmt: skip
    declared = [f.stiffness is not None for f in group]
    if any(declared) and not all(declared):
        raise _refusal(
            "some fasteners declare a stiffness and some do not; shank areas and "
            "stiffnesses cannot weight one pattern, so declare `stiffness` on every one",
            subject="fasteners",
            source=_PATTERN_SOURCE,
        )
    by_stiffness = all(declared)
    vx = _magnitude(shear_x, "N", "shear_x", _LOAD_SOURCE, positive=False)
    vy = _magnitude(shear_y, "N", "shear_y", _LOAD_SOURCE, positive=False)
    m0 = _magnitude(moment, "N*mm", "moment", _LOAD_SOURCE, positive=False)
    px = _magnitude(load_x, "mm", "load_x", _LOAD_SOURCE, positive=False)
    py = _magnitude(load_y, "mm", "load_y", _LOAD_SOURCE, positive=False)
    pt = _magnitude(tension, "N", "tension", _LOAD_SOURCE, positive=False)
    if pt < 0:
        raise _refusal(
            "tension is the pull on the pattern, zero or positive; a compressive load bears "
            "on the plates",
            subject="tension",
            source=_LOAD_SOURCE,
        )
    w = [f._weight(by_stiffness=by_stiffness) for f in group]
    xs = [float(f.x.to("mm").magnitude) for f in group]
    ys = [float(f.y.to("mm").magnitude) for f in group]
    total = sum(w)
    cx = sum(wi * x for wi, x in zip(w, xs, strict=True)) / total
    cy = sum(wi * y for wi, y in zip(w, ys, strict=True)) / total
    polar = sum(wi * ((x - cx) ** 2 + (y - cy) ** 2) for wi, x, y in zip(w, xs, ys, strict=True))
    m = m0 + (px - cx) * vy - (py - cy) * vx
    if m != 0 and polar == 0:
        raise _refusal(
            "the pattern has a twisting moment and no lever arm to resist it: every fastener "
            "sits at the centroid",
            subject="fasteners",
            source=_PATTERN_SOURCE,
        )
    loads = []
    for f, wi, x, y in zip(group, w, xs, ys, strict=True):
        fx = vx * wi / total - (m * wi * (y - cy) / polar if m else 0.0)
        fy = vy * wi / total + (m * wi * (x - cx) / polar if m else 0.0)
        shear = hypot(fx, fy)
        tension_i = pt * wi / total
        a, b, eq = _EXPONENTS[f.shear_plane.value]
        index = (shear / f.shear_allowable.to("N").magnitude) ** a + (
            tension_i / f.tension_allowable.to("N").magnitude
        ) ** b
        pull = (
            None
            if f.pull_through_allowable is None
            else tension_i / f.pull_through_allowable.to("N").magnitude
        )
        loads.append(
            FastenerLoad(name=f.name, shear_x=fx, shear_y=fy, shear=shear, tension=tension_i,
                         interaction=float(index), equation=eq, pull_through_ratio=pull)
        )  # fmt: skip
    worst = max(loads, key=lambda load: load.interaction)
    return FastenerGroupResult(
        fasteners=tuple(loads),
        governing=worst.name,
        governing_index=worst.interaction,
        centroid=(cx, cy),
        weighted_by="stiffness" if by_stiffness else "shank area",
    )
