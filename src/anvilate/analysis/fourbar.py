"""T1 analytical four-bar linkage Grashof classification (closed-form).

Before a four-bar linkage is anything else it is a question of rotation: can a link
spin all the way round, or only rock back and forth? Grashof's criterion answers it
from the four link lengths alone. Take the shortest link s, the longest l, and the
other two p and q; a link can fully rotate exactly when

    s + l ≤ p + q.

Which link rotates then depends on where the shortest one sits in the loop. With
s + l < p + q (a proper Grashof linkage): if the shortest link is the frame
(ground), both the links pinned to it fully rotate — a double-crank (drag-link); if
the shortest is one of those side links, it becomes the crank of a crank-rocker; and
if the shortest is the coupler, neither input nor output completes a turn — a
double-rocker. When s + l = p + q the linkage passes through a change-point where it
can flip branches, and when s + l > p + q no link rotates fully — a triple-rocker.

The four lengths must also form a closable quadrilateral (the longest shorter than
the sum of the other three). Lengths are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import acos, cos, degrees, radians, sqrt

from ..units import Quantity

__all__ = [
    "is_grashof",
    "fourbar_type",
    "fourbar_transmission_angle",
]


def _lengths_mm(
    ground: Quantity, input_link: Quantity, coupler: Quantity, output_link: Quantity
) -> dict[str, float]:
    named = {
        "ground": ground,
        "input": input_link,
        "coupler": coupler,
        "output": output_link,
    }
    out: dict[str, float] = {}
    for name, value in named.items():
        if not value.has_dimension("[length]"):
            raise ValueError(
                f"{name} link must be a [length] quantity; got {value.dimensionality} ({value})"
            )
        mm = value.to("mm").magnitude
        if mm <= 0:
            raise ValueError(f"{name} link length must be positive; got {value}")
        out[name] = mm
    longest = max(out.values())
    if longest >= sum(out.values()) - longest:
        raise ValueError(
            "link lengths do not form a closable four-bar (the longest link must be "
            "shorter than the sum of the other three)"
        )
    return out


def is_grashof(
    *,
    ground: Quantity,
    input_link: Quantity,
    coupler: Quantity,
    output_link: Quantity,
) -> bool:
    """Whether some link of a four-bar can fully rotate: s + l ≤ p + q.

    Grashof's criterion: with the shortest link s, longest l, and other two p, q,
    at least one link turns all the way round exactly when s + l ≤ p + q (the
    boundary s + l = p + q is the change-point case, which does have a
    fully-rotating link). ``ground``, ``input_link``, ``coupler``, and
    ``output_link`` are the four link lengths in loop order (positive lengths that
    form a closable quadrilateral). Returns True for a Grashof (or change-point)
    linkage, False for a triple-rocker.
    """
    lengths = list(_lengths_mm(ground, input_link, coupler, output_link).values())
    s = min(lengths)
    ll = max(lengths)
    others = sum(lengths) - s - ll
    return s + ll <= others


def fourbar_type(
    *,
    ground: Quantity,
    input_link: Quantity,
    coupler: Quantity,
    output_link: Quantity,
) -> str:
    """The Grashof classification of a four-bar linkage from its four lengths.

    Returns one of ``"double-crank"`` (Grashof, shortest link is the frame — both
    input and output rotate fully, a drag-link), ``"crank-rocker"`` (Grashof,
    shortest is the input or output side link — that link cranks, the other rocks),
    ``"double-rocker"`` (Grashof, shortest is the coupler — neither input nor output
    completes a turn), ``"change-point"`` (s + l = p + q — the linkage can fold and
    switch branches), or ``"triple-rocker"`` (non-Grashof, s + l > p + q — no link
    rotates fully). ``ground``, ``input_link``, ``coupler``, and ``output_link`` are
    the four link lengths in loop order.
    """
    lengths = _lengths_mm(ground, input_link, coupler, output_link)
    values = list(lengths.values())
    s = min(values)
    ll = max(values)
    others = sum(values) - s - ll
    total = s + ll
    if total > others:
        return "triple-rocker"
    if total == others:
        return "change-point"
    # Grashof: classify by which link is the (unique) shortest.
    shortest_name = min(lengths, key=lambda name: lengths[name])
    if shortest_name == "ground":
        return "double-crank"
    if shortest_name == "coupler":
        return "double-rocker"
    return "crank-rocker"


def fourbar_transmission_angle(
    *,
    ground: Quantity,
    input_link: Quantity,
    coupler: Quantity,
    output_link: Quantity,
    input_angle: float,
) -> float:
    """The transmission angle μ between coupler and output at an input angle.

    The transmission angle is the angle the coupler makes with the output link; it
    measures how effectively the coupler force drives the output. Near 90° the force
    goes almost entirely into useful torque, and near 0° or 180° it jams — designers
    keep μ within roughly 40°–140° over the motion. For an input crank at
    ``input_angle`` θ₂ (degrees measured from the ground line), the diagonal between
    the moving input pin and the output ground pivot is
    d = √(r₁² + r₂² − 2·r₁·r₂·cos θ₂), and the law of cosines on the coupler/output
    triangle gives cos μ = (r₃² + r₄² − d²)/(2·r₃·r₄). ``ground`` r₁, ``input_link``
    r₂, ``coupler`` r₃, and ``output_link`` r₄ are the loop-order lengths. Raises if
    the linkage cannot assemble at that input angle. Returns μ in **degrees**,
    0 ≤ μ ≤ 180.
    """
    lengths = _lengths_mm(ground, input_link, coupler, output_link)
    r1, r2, r3, r4 = (
        lengths["ground"],
        lengths["input"],
        lengths["coupler"],
        lengths["output"],
    )
    theta2 = radians(input_angle)
    diagonal = sqrt(r1**2 + r2**2 - 2.0 * r1 * r2 * cos(theta2))
    if diagonal > r3 + r4 or diagonal < abs(r3 - r4):
        raise ValueError(
            f"the linkage cannot assemble at input_angle {input_angle}°: the "
            f"coupler and output cannot reach across the diagonal ({diagonal:.3g} mm)"
        )
    cos_mu = (r3**2 + r4**2 - diagonal**2) / (2.0 * r3 * r4)
    cos_mu = max(-1.0, min(1.0, cos_mu))  # guard float drift past the domain
    return degrees(acos(cos_mu))
