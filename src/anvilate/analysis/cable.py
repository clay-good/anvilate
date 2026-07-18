"""T1 analytical cable-sag statics for a uniformly loaded cable (parabolic form).

A cable strung between two level supports and carrying a load spread evenly along
the span — its own weight to a good approximation, or a deck load — hangs in a
parabola (the shallow-sag limit of the catenary). Two numbers size it: how far it
dips, and how hard it pulls on the anchors.

For a horizontal span L carrying w per unit length at a horizontal tension H, the
midspan sag is

    d = w·L² / (8·H),

so halving the sag doubles the tension — a taut cable is a high-tension cable. Each
support also takes a vertical reaction w·L/2, and combining it with H gives the
peak (support) tension

    T_max = √(H² + (w·L/2)²),

always larger than H. Loads, spans, and tensions are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

__all__ = [
    "parabolic_cable_sag",
    "parabolic_cable_max_tension",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _inputs(weight_per_length: Quantity, span: Quantity) -> tuple[float, float]:
    _require(weight_per_length, "[force] / [length]", "weight_per_length")
    _require(span, "[length]", "span")
    w = weight_per_length.to("N/m").magnitude
    length = span.to("m").magnitude
    if w <= 0:
        raise ValueError(f"weight_per_length must be positive; got {weight_per_length}")
    if length <= 0:
        raise ValueError(f"span must be positive; got {span}")
    return w, length


def parabolic_cable_sag(
    *, weight_per_length: Quantity, span: Quantity, horizontal_tension: Quantity
) -> Quantity:
    """The midspan sag of a uniformly loaded cable, d = w·L²/(8·H).

    ``weight_per_length`` w is the load per unit length along the span,
    ``span`` L the horizontal distance between level supports, and
    ``horizontal_tension`` H the (constant) horizontal component of the cable
    tension. The sag grows with the square of the span and falls inversely with the
    tension, so a longer or slacker cable dips much more. All three must be
    positive. Returns the midspan sag in metres.
    """
    w, length = _inputs(weight_per_length, span)
    _require(horizontal_tension, "[force]", "horizontal_tension")
    h = horizontal_tension.to("N").magnitude
    if h <= 0:
        raise ValueError(f"horizontal_tension must be positive; got {horizontal_tension}")
    return Quantity(magnitude=w * length**2 / (8.0 * h), unit="m")


def parabolic_cable_max_tension(
    *, weight_per_length: Quantity, span: Quantity, horizontal_tension: Quantity
) -> Quantity:
    """The peak (support) cable tension, T_max = √(H² + (w·L/2)²).

    At each support the cable carries the horizontal tension H plus the vertical
    reaction w·L/2 it lifts, and their resultant is the largest tension anywhere in
    the cable — the value the anchors and the cable's own strength must meet.
    ``weight_per_length`` w, ``span`` L, and ``horizontal_tension`` H are as in
    :func:`parabolic_cable_sag`. Returns the maximum tension in newtons, always
    exceeding H.
    """
    w, length = _inputs(weight_per_length, span)
    _require(horizontal_tension, "[force]", "horizontal_tension")
    h = horizontal_tension.to("N").magnitude
    if h <= 0:
        raise ValueError(f"horizontal_tension must be positive; got {horizontal_tension}")
    vertical_reaction = w * length / 2.0
    return Quantity(magnitude=sqrt(h**2 + vertical_reaction**2), unit="N")
