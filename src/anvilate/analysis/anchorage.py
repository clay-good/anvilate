"""Anchor forces under a base moment: which bolt goes into tension, and how much.

A machine, a skid, a rack or a guardrail post is bolted to a slab, and the question the
anchors answer is not "is it heavy enough" but "which one lifts first". A lateral force
acting above the base makes an overturning moment; the weight resists it; whatever is
left over is carried in tension by the anchors furthest from the edge the thing wants to
tip about, and in shear by all of them.

**This module produces a demand, not a capacity.** It takes the lateral force as
declared — seismic, wind, a machine's own dynamic force, the 200 lbf a guardrail clause
applies at a top rail — and returns what each anchor is asked to carry. What an anchor
can *take* is a concrete or steel capacity from a code, with its own edition and factors,
and is not here.

Sources: Drake and Elkin, "Beam-Column Base Plate Design — LRFD Method", AISC Engineering
Journal, First Quarter 1999, pp. 29-38, whose Equations 16 and 17 take moments about the
anchor tension force and whose two statements about the rod group are the ones this
module keeps: **"all the base plate anchor rods are considered effective in sharing the
shear load"**, and **"all of the base plate anchor rods are not considered effective in
sharing the tension load"** — only those on the tension side of the bearing are.

The model, stated because every term of the answer depends on it:

- **The base is rigid and the anchors are not.** Load divides by geometry, not stiffness,
  which is the assumption every hand calculation of this makes.
- **Anchors take tension only**, and the anchors downwind of the tipping axis take none.
- **The compression resultant is taken at the leeward anchor row.** This is where the
  module simplifies the AISC paper: Drake and Elkin solve a quadratic (their Equation 20)
  for the bearing length Y from the concrete's bearing stress and the plate's width, and
  put the resultant at the centroid of that bearing area. Doing so needs a concrete
  strength and a plate size, which an anchor pattern alone does not state. Taking the
  resultant at the leeward anchors instead needs neither, and is **conservative**: the
  real bearing centroid is further out, which is a longer lever arm and less tension.
- **Tension divides by lever arm** — the elastic distribution a rigid base gives. With
  one row of anchors in tension this is the paper's own `T_u / #r`; with more rows it is
  what distinguishes the near row from the far one.
- **Shear divides equally among every anchor**, as the paper states.
- **Friction is not relied on.** A slab-to-base friction coefficient would reduce the
  shear on every anchor and is forbidden by most anchorage provisions under seismic load;
  this never applies one, so the shear reported is the whole of it.

What it refuses: fewer than two anchors, anchors that are all on one line parallel to the
load (nothing resists the moment), and a lateral force with no direction.
"""

from __future__ import annotations

from math import cos, hypot, isfinite, pi, sin

from pydantic import ConfigDict, model_validator

from .._models import Named, Provenance, StatableModel, each_one
from ..refusal import RefusalError, Remedy
from ..units import Quantity, render

__all__ = [
    "ANCHORAGE_METHOD",
    "AnchorPosition",
    "AnchorDemand",
    "AnchorageDemand",
    "anchor_pattern_demand",
    "DIRECTION_SWEEP_STEPS",
    "governing_anchor_direction",
]

#: What the answer is a result of. The force that went in and the capacity it is checked
#: against carry their own citations; this names the statics between them.
ANCHORAGE_METHOD = (
    "rigid-base statics after Drake and Elkin, AISC Engineering Journal 1Q 1999: anchors "
    "in tension only, compression resultant taken at the leeward anchor row rather than "
    "at the bearing centroid, shear divided equally over every anchor, no friction relied on"
)

_ANCHORAGE_SOURCE = "the equipment drawing: its anchor pattern, mass and centre of gravity"
_FORCE_SOURCE = "the declared lateral force and the height it acts at"


class _AnchorageInputError(RefusalError, ValueError):
    """An anchorage input that cannot be used without correction."""


def _refuse(message: str, *, subject: str, source: str = _ANCHORAGE_SOURCE):
    return _AnchorageInputError(
        message, remedies=(Remedy(action="replace", subject=subject, source=source),)
    )


def _check(value: Quantity, expected: str, name: str) -> None:
    """``value`` is a finite quantity of ``expected``, or a refusal naming the parameter."""
    if not isinstance(value, Quantity):
        raise _refuse(f"{name} must be a {expected} quantity; got {value!r}", subject=name)
    if not value.has_dimension(expected):
        raise _refuse(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
        )
    if not isfinite(value.magnitude):
        raise _refuse(f"{name} must be finite; got {value}", subject=name)


class AnchorPosition(StatableModel):
    """One anchor, where it is in the base's own plan coordinates."""

    model_config = ConfigDict(frozen=True)

    states_requirements = True

    tag: Named
    x: Quantity
    y: Quantity

    @model_validator(mode="after")
    def _is_a_point(self) -> AnchorPosition:
        for value, axis in ((self.x, "x"), (self.y, "y")):
            _check(value, "[length]", f"anchor {self.tag} {axis}")
        return self

    @property
    def mm(self) -> tuple[float, float]:
        """The anchor's plan position in millimetres."""
        return (self.x.to("mm").magnitude, self.y.to("mm").magnitude)

    def __str__(self) -> str:
        return f"{self.tag} at ({self.x}, {self.y})"


class AnchorDemand(StatableModel):
    """What one anchor is asked to carry, and how far it is from the tipping axis."""

    model_config = ConfigDict(frozen=True)

    states_requirements = True

    tag: Named
    tension: Quantity
    shear: Quantity
    lever_mm: float

    def __str__(self) -> str:
        return (
            f"{self.tag}: {render(self.tension, pretty=True)} tension, "
            f"{render(self.shear, pretty=True)} shear"
        )


class AnchorageDemand(StatableModel):
    """The whole pattern's answer: the moment, what resists it, and each anchor's share."""

    model_config = ConfigDict(frozen=True)

    states_requirements = True

    anchors: tuple[AnchorDemand, ...]
    overturning: Quantity
    resisting: Quantity
    stability_ratio: float
    sliding: Quantity
    method: Provenance = ANCHORAGE_METHOD

    @property
    def governing(self) -> AnchorDemand:
        """The anchor carrying the most tension, which is the one a capacity is checked at."""
        return max(self.anchors, key=lambda a: a.tension.to("N").magnitude)

    @property
    def uplift(self) -> bool:
        """Does any anchor go into tension at all?"""
        return self.governing.tension.to("N").magnitude > 0.0

    def of(self, tag: str) -> AnchorDemand:
        """One anchor's demand, by tag."""
        found = next((a for a in self.anchors if a.tag == tag), None)
        if found is None:
            raise KeyError(f"{tag!r} is not an anchor of this pattern")
        return found

    def __str__(self) -> str:
        over = render(self.overturning, pretty=True)
        resist = render(self.resisting, pretty=True)
        if not self.uplift:
            return (
                f"no uplift: {over} overturning against {resist} resisting "
                f"({self.stability_ratio:.2f}); {render(self.sliding, pretty=True)} shear "
                f"on the anchors"
            )
        return (
            f"{self.governing} governs; {over} overturning against {resist} resisting "
            f"({self.stability_ratio:.2f})"
        )


def anchor_pattern_demand(
    *,
    anchors: tuple[AnchorPosition, ...],
    weight: Quantity,
    lateral_force: Quantity,
    height: Quantity,
    direction: tuple[float, float] = (1.0, 0.0),
    centre_of_gravity: tuple[Quantity, Quantity] | None = None,
) -> AnchorageDemand:
    """The tension and shear on each anchor of a pattern under a lateral force.

    ``anchors`` are plan positions in the base's own coordinates; ``weight`` is what the
    equipment weighs (a force, not a mass — the acceleration it is carried at is the
    caller's); ``lateral_force`` acts horizontally along ``direction`` at ``height`` above
    the base plane. ``centre_of_gravity`` is where the weight acts in plan, and defaults
    to the centroid of the anchor pattern.

    The overturning moment is ``H·h``. The tipping axis is the line through the anchors
    furthest downwind, perpendicular to ``direction``; the weight resists about it with
    the lever its centre of gravity has. Whatever moment is left is carried by the anchors
    in proportion to their distance from that axis:

        ``T_i = M_net · d_i / Σ d_j²``

    which is the elastic distribution a rigid base gives. An anchor on the tipping axis
    has no lever and takes no tension, and an anchor downwind of it is in compression and
    reported at zero rather than as a negative tension — a negative tension read as a
    capacity is a hold-down nobody installed.

    ``stability_ratio`` is resisting over overturning: below 1.0 the weight alone does not
    hold it and the anchors do the rest, which is the ordinary case and not a failure.
    """
    # A single `AnchorPosition` is a pydantic model, and a pydantic model iterates over
    # its own (field, value) pairs: one anchor passed bare became three "anchors" called
    # tag, x and y. `each_one` is the library's one answer, and it names the parameter.
    anchors = each_one(anchors, AnchorPosition, named="anchors")
    if len(anchors) < 2:
        raise _refuse(
            f"an anchor pattern has at least two anchors; got {len(anchors)}. One anchor "
            f"resists no moment about any axis through it",
            subject="anchors",
        )
    tags = [anchor.tag for anchor in anchors]
    doubled = sorted({tag for tag in tags if tags.count(tag) > 1})
    if doubled:
        raise _refuse(
            f"the anchor {', '.join(doubled)} is declared more than once; an anchor in two "
            f"places carries two shares of one load",
            subject="anchors",
        )
    _check(weight, "[force]", "weight")
    _check(lateral_force, "[force]", "lateral_force")
    _check(height, "[length]", "height")
    for value, name in ((weight, "weight"), (lateral_force, "lateral_force")):
        if value.magnitude < 0:
            raise _refuse(
                f"{name} is a magnitude here; got {value}. A direction is `direction`, and "
                f"a negative force would reverse it silently",
                subject=name,
                source=_FORCE_SOURCE,
            )
    if height.magnitude < 0:
        raise _refuse(
            f"height is measured up from the base plane; got {height}",
            subject="height",
            source=_FORCE_SOURCE,
        )
    if len(direction) != 2 or not all(isinstance(v, (int, float)) for v in direction):
        raise _refuse(
            f"direction is a plan unit vector (x, y); got {direction!r}",
            subject="direction",
            source=_FORCE_SOURCE,
        )
    length = hypot(*direction)
    if not isfinite(length) or length <= 0:
        raise _refuse(
            f"direction has no length, so the force has no direction; got {direction!r}",
            subject="direction",
            source=_FORCE_SOURCE,
        )
    unit = (direction[0] / length, direction[1] / length)

    positions = {anchor.tag: anchor.mm for anchor in anchors}
    along = {tag: point[0] * unit[0] + point[1] * unit[1] for tag, point in positions.items()}
    leeward = max(along.values())
    windward = min(along.values())
    if leeward - windward <= 1e-9:
        raise _refuse(
            f"every anchor lies on one line across the load's direction, so the pattern "
            f"resists no moment about it; the {len(anchors)} anchors are all at the same "
            f"distance along {unit}",
            subject="anchors",
        )

    if centre_of_gravity is None:
        cg_along = sum(along.values()) / len(along)
    else:
        if len(centre_of_gravity) != 2:
            raise _refuse(
                f"centre_of_gravity is a plan point (x, y); got {centre_of_gravity!r}",
                subject="centre_of_gravity",
            )
        cx, cy = centre_of_gravity
        _check(cx, "[length]", "centre_of_gravity x")
        _check(cy, "[length]", "centre_of_gravity y")
        cg_along = cx.to("mm").magnitude * unit[0] + cy.to("mm").magnitude * unit[1]

    force_n = lateral_force.to("N").magnitude
    weight_n = weight.to("N").magnitude
    height_mm = height.to("mm").magnitude
    overturning = force_n * height_mm / 1000.0
    # The weight's lever about the tipping axis. A centre of gravity downwind of the
    # leeward anchors overhangs, and then the weight ADDS to the overturning rather than
    # resisting it — the sign carries that rather than an abs() hiding it.
    weight_lever = (leeward - cg_along) / 1000.0
    resisting = weight_n * weight_lever
    net = overturning - resisting

    levers = {tag: (leeward - value) for tag, value in along.items()}
    sum_squares = sum(value * value for value in levers.values())
    shear_each = force_n / len(anchors)
    demands = tuple(
        AnchorDemand(
            tag=anchor.tag,
            tension=Quantity(
                magnitude=(
                    max(0.0, net * 1000.0 * levers[anchor.tag] / sum_squares) if net > 0.0 else 0.0
                ),
                unit="N",
            ),
            shear=Quantity(magnitude=shear_each, unit="N"),
            lever_mm=round(levers[anchor.tag], 6),
        )
        for anchor in anchors
    )
    ratio = resisting / overturning if overturning > 0 else float("inf")
    return AnchorageDemand(
        anchors=demands,
        overturning=Quantity(magnitude=overturning, unit="N*m"),
        resisting=Quantity(magnitude=resisting, unit="N*m"),
        stability_ratio=ratio,
        sliding=Quantity(magnitude=force_n, unit="N"),
    )


#: How many directions the sweep below tries over the full turn. 720 is a step of half a
#: degree. A square pattern's worst direction is one of its axes, which the sweep hits
#: exactly at step 0; the test that checks it solves that case in closed form rather than
#: taking the sweep's own answer as the standard.
DIRECTION_SWEEP_STEPS = 720


def governing_anchor_direction(
    *,
    anchors: tuple[AnchorPosition, ...],
    weight: Quantity,
    lateral_force: Quantity,
    height: Quantity,
    centre_of_gravity: tuple[Quantity, Quantity] | None = None,
) -> tuple[tuple[float, float], AnchorageDemand]:
    """The plan direction that loads one anchor hardest, and the demand it produces.

    A clause that applies its force "in any direction" — 29 CFR 1910.29(b)(3) is one —
    does not say which direction is worst, and the answer is not the one most people
    guess. **The worst direction is across the pattern's short side**, where the lever is
    least: a 400 x 100 mm pattern takes 4.2 times the anchor tension across its short
    dimension that it takes along its long one. On a square the two axes are the worst and
    the **diagonal is the mildest** — the diagonal looks like it concentrates the moment
    on one corner, and it does, but it also lengthens every lever, so the sum of squares
    in the denominator grows faster than the one in the numerator, and it gives the weight
    a longer lever as well. (That holds wherever the pattern lifts at all. A pattern the
    weight holds down in every direction has no tension anywhere, and no worst direction
    to find — the sweep reports zero and the stability ratio says why.)

    **This is a sweep, not a solve**, and that is stated rather than hidden: the tension
    is a ratio of two functions of the direction, and the worst of it is found by trying
    :data:`DIRECTION_SWEEP_STEPS` directions over the turn. A square pattern has a closed
    form the test checks this against.

    Returns the unit direction and the full :class:`AnchorageDemand` at it, so the caller
    reads the governing anchor's tension off the result rather than recomputing it.
    """
    worst: tuple[tuple[float, float], AnchorageDemand] | None = None
    for step in range(DIRECTION_SWEEP_STEPS):
        angle = 2.0 * pi * step / DIRECTION_SWEEP_STEPS
        direction = (cos(angle), sin(angle))
        try:
            found = anchor_pattern_demand(
                anchors=anchors,
                weight=weight,
                lateral_force=lateral_force,
                height=height,
                direction=direction,
                centre_of_gravity=centre_of_gravity,
            )
        except _AnchorageInputError:
            # A direction along which every anchor lies on one line resists no moment and
            # is refused by the demand itself. It is a direction the pattern cannot be
            # loaded in, not a worst case, so the sweep passes over it — and if EVERY
            # direction is refused the refusal comes back below rather than a None.
            continue
        if (
            worst is None
            or found.governing.tension.to("N").magnitude
            > worst[1].governing.tension.to("N").magnitude
        ):
            worst = (direction, found)
    if worst is None:  # pragma: no cover - a pattern of two anchors refuses before here
        raise _refuse(
            "no direction loads this pattern: every one of them is refused",
            subject="anchors",
        )
    return worst
