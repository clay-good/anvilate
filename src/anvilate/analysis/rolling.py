"""T1 analytical flat-rolling (bulk-deformation) checks (closed-form).

Rolling squeezes a strip thinner by passing it between two rotating rolls, and it is the highest-
tonnage metal-forming process there is. Sizing a pass turns on three things: whether the rolls will
even grab the strip, how long the contact between roll and strip is, and how much force that contact
puts on the rolls. It sits alongside the forging in :mod:`anvilate.analysis.forging` as the other
half of bulk deformation.

The rolls only bite if the reduction is not too greedy: friction has to drag the strip in against
the wedging of the gap, which caps the *draft* (the thickness removed, Δh = h₀ − h₁) at μ²·R
for rolls of radius R and a friction coefficient μ. Ask for more reduction than that in one pass and
the strip just skids at the roll faces.

Within that limit, the strip and roll touch over a projected contact length L = √(R·Δh) — the chord
of the arc of contact — and the rolls press on the strip across that length with a force
F = Y_avg·w·L, the average flow stress Y_avg of the (work-hardening) strip times its width w and the
contact length. Because L grows with the square root of the draft and the radius, a bigger roll or a
heavier pass drives the force up — the reason heavy reductions need big, stiff mills.
"""

from __future__ import annotations

from math import pi, sqrt

from ..units import Quantity

__all__ = [
    "rolling_power",
    "maximum_draft",
    "rolling_contact_length",
    "rolling_force",
]


def maximum_draft(*, roll_radius: Quantity, friction_coefficient: float) -> Quantity:
    """The maximum draft the rolls can bite, Δh_max = μ²·R.

    The largest thickness reduction a pass can take before the strip skids instead of feeding: the
    rolls only drag the strip in if friction overcomes the gap's wedging, which caps the draft at
    Δh_max = μ²·R, from the ``roll_radius`` R and the die-strip ``friction_coefficient`` μ. Ask a
    single pass for more reduction than this and the rolls spin against a strip they cannot grab —
    the check that a proposed pass schedule is even feasible. Returns the maximum draft as a length.
    """
    _check(roll_radius, "[length]", "roll_radius")
    r = roll_radius.to("mm").magnitude
    if r <= 0:
        raise ValueError("roll_radius must be positive")
    if friction_coefficient < 0:
        raise ValueError("friction_coefficient must be non-negative")
    return Quantity(magnitude=friction_coefficient**2 * r, unit="mm")


def rolling_contact_length(*, roll_radius: Quantity, draft: Quantity) -> Quantity:
    """The projected roll-strip contact length, L = √(R·Δh).

    The length over which the roll and strip touch in a pass — the chord of the arc of contact —
    from the ``roll_radius`` R and the ``draft`` Δh (the thickness the pass removes, h₀ − h₁):
    L = √(R·Δh). It is the length the rolling force acts over (see :func:`rolling_force`), and it
    grows with the square root of both the radius and the draft, so a larger roll spreads the same
    reduction over a longer bite. Returns the contact length as a length.
    """
    _check(roll_radius, "[length]", "roll_radius")
    _check(draft, "[length]", "draft")
    r = roll_radius.to("mm").magnitude
    dh = draft.to("mm").magnitude
    if r <= 0:
        raise ValueError("roll_radius must be positive")
    if dh <= 0:
        raise ValueError("draft must be positive")
    return Quantity(magnitude=sqrt(r * dh), unit="mm")


def rolling_force(
    *,
    flow_stress: Quantity,
    strip_width: Quantity,
    contact_length: Quantity,
) -> Quantity:
    """The roll separating force, F = Y_avg·w·L.

    The force the rolls press on the strip with, from the average ``flow_stress`` Y_avg of the strip
    (the mean of its entry and exit flow stress as it work-hardens; from
    :func:`anvilate.analysis.forging.flow_stress_power_law`), its ``strip_width`` w, and the
    ``contact_length`` L (from :func:`rolling_contact_length`): F = Y_avg·w·L. This is the force the
    mill stand and its bearings must carry, and it grows with the contact length — so heavier passes
    on bigger rolls demand stiffer, stronger mills. Returns the rolling force in kN.
    """
    _check(flow_stress, "[pressure]", "flow_stress")
    _check(strip_width, "[length]", "strip_width")
    _check(contact_length, "[length]", "contact_length")
    y = flow_stress.to("Pa").magnitude
    w = strip_width.to("m").magnitude
    length = contact_length.to("m").magnitude
    if y <= 0:
        raise ValueError("flow_stress must be positive")
    if w <= 0 or length <= 0:
        raise ValueError("strip_width and contact_length must be positive")
    return Quantity(magnitude=y * w * length / 1000.0, unit="kN")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def rolling_power(
    *, rolling_force: Quantity, contact_length: Quantity, roll_speed: Quantity
) -> Quantity:
    """The rolling mill power, P = 2·π·N·F·L.

    The power the mill drive must deliver for one pass. The module sizes the separating *force*
    (:func:`rolling_force`) but nothing sized the motor, which is the other half of a pass-schedule
    check — and force alone carries no information about speed, so it cannot answer the question.

    Each roll applies its share of the ``rolling_force`` F at a lever arm of about half the
    ``contact_length`` L, giving a torque F·L/2 per roll; two rolls turning at ``roll_speed`` N
    revolutions per unit time then take P = 2·(2π·N)·(F·L/2) = 2·π·N·F·L.

    A 500 mm-diameter mill taking 5 mm off a 200 mm-wide strip at 200 MPa average flow stress and
    100 rpm needs 524 kW. The half-contact-length lever arm is the idealisation here; an
    independent plastic-work check — the specific energy Y·ln(h₀/h₁) times the volume rate — puts
    the same pass at 467 kW, so treat this as accurate to roughly 10-15% and the honest side of
    the two, since it is the larger. Excludes friction in the bearings and drive train. Returns
    the power in W.
    """
    _check(rolling_force, "[force]", "rolling_force")
    _check(contact_length, "[length]", "contact_length")
    if not roll_speed.has_dimension("[frequency]"):
        raise ValueError(
            f"roll_speed must be a [frequency] quantity; got {roll_speed.dimensionality} "
            f"({roll_speed})"
        )
    f = rolling_force.to("N").magnitude
    length = contact_length.to("m").magnitude
    n = roll_speed.to("rad/s").magnitude / (2.0 * pi)
    if f <= 0:
        raise ValueError("rolling_force must be positive")
    if length <= 0:
        raise ValueError("contact_length must be positive")
    if n <= 0:
        raise ValueError("roll_speed must be positive")
    return Quantity(magnitude=2.0 * pi * n * f * length, unit="W")
