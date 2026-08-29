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

always larger than H. For a cable that sags too deeply for the parabola, the exact
catenary y = a·cosh(x/a) (a = H/w) gives the sag, arc length, and peak tension in
hyperbolic form, collapsing to the parabolic values in the shallow-sag limit. Loads,
spans, and tensions are dimension-checked :class:`~anvilate.units.Quantity` values.

Sources: the catenary relations as given in Roark's *Formulas for Stress and
Strain*; NFPA 70 (NEC) for conductor ampacity conventions.
"""

from __future__ import annotations

from math import cosh, sinh, sqrt

from ..units import Quantity, require_finite

__all__ = [
    "parabolic_cable_sag",
    "parabolic_cable_max_tension",
    "parabolic_cable_length",
    "catenary_sag",
    "catenary_arc_length",
    "catenary_max_tension",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
    # Dimension is the easy half. A NaN magnitude passes every `<= 0` guard downstream
    # (all comparisons with NaN are False) and is then DROPPED by the max()/min() that
    # picks the governing case, so the answer comes back smaller, complete-looking, and
    # green. See units.require_finite.
    require_finite(value, name=name)


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


# The parabola is the shallow-sag limit of the catenary, and the limit has a number. At
# d/L = 0.10 the parabolic sag runs 1.3% under the exact catenary and T_max 0.4% under; at
# d/L = 0.20 that is 5.2% and 4.3%, and at d/L = 0.40 it is 19% and 27%. Both errors are
# unconservative at once -- the sag is the clearance-to-ground check and T_max sizes the
# cable and its anchors. This module already exports the exact `catenary_sag` and
# `catenary_max_tension` on the identical argument triple, so a refusal has somewhere to
# send the caller.
_SHALLOW_SAG_RATIO_LIMIT = 0.10


def _check_shallow_sag(w: float, length: float, h: float) -> None:
    """Refuse a sag ratio past the shallow-sag scope of the parabolic forms."""
    ratio = w * length / (8.0 * h)
    if ratio > _SHALLOW_SAG_RATIO_LIMIT:
        raise ValueError(
            f"the sag ratio d/L = {ratio:.4g} is past the shallow-sag scope of the parabolic "
            f"forms (d/L <= {_SHALLOW_SAG_RATIO_LIMIT:g}, where the error is about 1%). Both the "
            f"sag and the peak tension come out UNDER the exact values here, which overstates "
            f"clearance and understates the anchor load. Use catenary_sag and "
            f"catenary_max_tension, which take the same arguments and are exact."
        )


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
    _check_shallow_sag(w, length, h)
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
    _check_shallow_sag(w, length, h)
    vertical_reaction = w * length / 2.0
    return Quantity(magnitude=sqrt(h**2 + vertical_reaction**2), unit="N")


def parabolic_cable_length(*, span: Quantity, sag: Quantity) -> Quantity:
    """The arc length of a shallow parabolic cable, S ≈ L·(1 + 8·(d/L)²/3).

    The cable is longer than the straight-line span it crosses, and how much longer
    is what you actually order and cut. For a parabolic profile with span ``span`` L
    and midspan ``sag`` d the developed length is S = L + 8·d²/(3·L), the standard
    shallow-sag series (accurate while d/L is small, as it is for real cables). The
    extra length grows with the square of the sag, so a slack cable needs
    disproportionately more material. Both inputs must be positive lengths. Returns
    the arc length in metres, always at least the span.
    """
    _require(span, "[length]", "span")
    _require(sag, "[length]", "sag")
    length = span.to("m").magnitude
    d = sag.to("m").magnitude
    if length <= 0:
        raise ValueError(f"span must be positive; got {span}")
    if d <= 0:
        raise ValueError(f"sag must be positive; got {sag}")
    return Quantity(magnitude=length + 8.0 * d**2 / (3.0 * length), unit="m")


def _catenary_inputs(
    weight_per_length: Quantity, horizontal_tension: Quantity, span: Quantity
) -> tuple[float, float, float]:
    """Validate a catenary and return (a, half_span, w) in metres/N, all positive.

    ``a = H/w`` is the catenary parameter; ``span`` is the full level-support span so
    the half-span (lowest point to a support) is span/2.
    """
    _require(weight_per_length, "[force] / [length]", "weight_per_length")
    _require(horizontal_tension, "[force]", "horizontal_tension")
    _require(span, "[length]", "span")
    w = weight_per_length.to("N/m").magnitude
    h = horizontal_tension.to("N").magnitude
    length = span.to("m").magnitude
    if w <= 0:
        raise ValueError(f"weight_per_length must be positive; got {weight_per_length}")
    if h <= 0:
        raise ValueError(f"horizontal_tension must be positive; got {horizontal_tension}")
    if length <= 0:
        raise ValueError(f"span must be positive; got {span}")
    return h / w, length / 2.0, w


def catenary_sag(
    *, weight_per_length: Quantity, span: Quantity, horizontal_tension: Quantity
) -> Quantity:
    """The exact midspan sag of a heavy cable hanging in a catenary.

    A cable heavy enough to sag deeply hangs not in a parabola but in a *catenary*,
    the shape y = a·cosh(x/a) a chain takes under its own weight, with the catenary
    parameter a = H/w (horizontal tension over weight per unit length). Between level
    supports the midspan dips below the support line by

        d = a·(cosh(x/a) − 1),   x = L/2,

    the exact result the parabolic :func:`parabolic_cable_sag` approximates — for a
    shallow cable cosh(x/a) − 1 ≈ (x/a)²/2 and this collapses to w·L²/(8·H), but a
    deeply-sagging line (a transmission span, a mooring, a ski lift) needs the exact
    form. ``weight_per_length`` w is the load per unit length *along the cable*,
    ``span`` L the level-support distance, and ``horizontal_tension`` H the constant
    horizontal tension. All three must be positive. Returns the midspan sag in metres.
    """
    a, half_span, _ = _catenary_inputs(weight_per_length, horizontal_tension, span)
    return Quantity(magnitude=a * (cosh(half_span / a) - 1.0), unit="m")


def catenary_arc_length(
    *, weight_per_length: Quantity, span: Quantity, horizontal_tension: Quantity
) -> Quantity:
    """The exact developed arc length of a catenary cable, S = 2·a·sinh(L/2a).

    The length of cable to order for a heavy span: for the catenary y = a·cosh(x/a)
    the arc from the low point out to a support at x = L/2 is a·sinh(x/a), so the full
    level-support length is S = 2·a·sinh(L/2a) with a = H/w. Like :func:`catenary_sag`
    this is the exact counterpart of the shallow parabolic :func:`parabolic_cable_length`.
    ``weight_per_length`` w, ``span`` L, and ``horizontal_tension`` H are as in
    :func:`catenary_sag`. Returns the arc length in metres, always exceeding the span.
    """
    a, half_span, _ = _catenary_inputs(weight_per_length, horizontal_tension, span)
    return Quantity(magnitude=2.0 * a * sinh(half_span / a), unit="m")


def catenary_max_tension(
    *, weight_per_length: Quantity, span: Quantity, horizontal_tension: Quantity
) -> Quantity:
    """The peak (support) tension of a catenary cable, T_max = w·a·cosh(L/2a).

    In a catenary the tension is lowest (equal to H) at the bottom and greatest at
    the supports, where the cable also lifts the full weight of its half-length. The
    exact peak tension is T_max = w·a·cosh(L/2a) = H + w·d — the horizontal tension
    plus the weight of cable hung below support level (``d`` the :func:`catenary_sag`).
    ``weight_per_length`` w, ``span`` L, and ``horizontal_tension`` H are as in
    :func:`catenary_sag`. Returns the maximum tension in newtons, always exceeding H.
    """
    a, half_span, w = _catenary_inputs(weight_per_length, horizontal_tension, span)
    return Quantity(magnitude=w * a * cosh(half_span / a), unit="N")
