"""T1 analytical external Geneva (Maltese-cross) mechanism geometry (closed-form).

A Geneva drive turns continuous rotation into *intermittent* indexing: a pin on a
driving crank enters a radial slot in the driven wheel, sweeps it round by one
station, then leaves while a locking arc holds the wheel still until the next pin
arrives. It is how film advances a frame at a time and how an indexing table stops
at each station.

For an external Geneva with n slots the driven wheel advances 2π/n per index. The
geometry is set by one right-angle condition: the slot must be radial (aligned with
the crank arm) at entry and exit so the wheel starts and stops with zero velocity —
no impact. That puts the driving centre, driven centre, and pin at a right angle at
the pin, with the half-index angle π/n at the driven centre, so with a centre
distance c the crank radius and the driven engagement radius are

    r_crank = c·sin(π/n),   r_driven = c·cos(π/n).

An external Geneva needs at least three slots (n ≥ 3); below that the slot cannot
close. Lengths are dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import cos, pi, sin

from ..units import Quantity

__all__ = [
    "geneva_index_angle",
    "geneva_crank_radius",
    "geneva_driven_radius",
    "geneva_advance_fraction",
    "geneva_dwell_fraction",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _check_slots(slots: int) -> int:
    whole = int(slots)
    if whole != slots or whole < 3:
        raise ValueError(f"slots must be a whole number ≥ 3 for an external Geneva; got {slots}")
    return whole


def geneva_index_angle(*, slots: int) -> float:
    """The driven-wheel advance per index, 360°/n, of an external Geneva.

    Each engagement steps the driven wheel on by one station — 2π/n, or 360°/n in
    degrees — and the locking arc holds it there until the next pin arrives.
    ``slots`` n is the number of slots (stations), a whole number ≥ 3. Returns the
    index angle in **degrees**.
    """
    n = _check_slots(slots)
    return 360.0 / n


def geneva_crank_radius(*, slots: int, center_distance: Quantity) -> Quantity:
    """The driving crank (pin) radius r = c·sin(π/n) of an external Geneva.

    The pin sits at this radius on the driving crank so that the slot is radial at
    entry and exit and the driven wheel starts and stops with zero velocity.
    ``slots`` n (≥ 3) and ``center_distance`` c (the distance between the driving
    and driven axes, a positive length) fix it by the right-angle engagement
    geometry. Returns the crank radius in mm.
    """
    n = _check_slots(slots)
    _require(center_distance, "[length]", "center_distance")
    c = center_distance.to("mm").magnitude
    if c <= 0:
        raise ValueError(f"center_distance must be positive; got {center_distance}")
    return Quantity(magnitude=c * sin(pi / n), unit="mm")


def geneva_driven_radius(*, slots: int, center_distance: Quantity) -> Quantity:
    """The driven-wheel engagement radius r = c·cos(π/n) of an external Geneva.

    The radius on the driven wheel at which the pin engages the slot mouth — the
    other leg of the right-angle engagement triangle. ``slots`` n (≥ 3) and
    ``center_distance`` c are as in :func:`geneva_crank_radius`; at n = 4 the crank
    and driven radii are equal, and the driven radius grows past the crank radius
    for more slots. Returns the driven engagement radius in mm.
    """
    n = _check_slots(slots)
    _require(center_distance, "[length]", "center_distance")
    c = center_distance.to("mm").magnitude
    if c <= 0:
        raise ValueError(f"center_distance must be positive; got {center_distance}")
    return Quantity(magnitude=c * cos(pi / n), unit="mm")


def geneva_advance_fraction(*, slots: int) -> float:
    """The fraction (n − 2)/(2n) of the cycle an external Geneva spends indexing.

    The driving pin is only in a slot for part of each crank revolution; the rest of
    the turn the locking arc holds the wheel still. For an external Geneva the pin is
    engaged — the wheel is *moving* — for a fraction (n − 2)/(2n) of the cycle: a
    4-slot wheel indexes for a quarter of each turn and dwells the other three
    quarters, and more slots spend more of the cycle moving (a 4-slot at 0.25, a
    6-slot at 0.333, an 8-slot at 0.375). ``slots`` n is the slot count (≥ 3).
    Returns the dimensionless advancing (moving) fraction; its complement is the
    :func:`geneva_dwell_fraction`.
    """
    n = _check_slots(slots)
    return (n - 2) / (2 * n)


def geneva_dwell_fraction(*, slots: int) -> float:
    """The fraction (n + 2)/(2n) of the cycle an external Geneva wheel dwells.

    The complement of :func:`geneva_advance_fraction`: the share of each crank
    revolution the wheel is locked still, when the work at a station actually
    happens. Fewer slots give a longer dwell (a 4-slot rests 75% of the cycle, a
    6-slot 66.7%, an 8-slot 62.5%), so a station that needs a long dwell for its
    operation wants *few* slots — the opposite of what a fine index angle wants.
    ``slots`` n is the slot count (≥ 3). Returns the dimensionless dwell fraction.
    """
    n = _check_slots(slots)
    return (n + 2) / (2 * n)
