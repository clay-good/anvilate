"""T1 analytical drum brakes: band and short-shoe (closed-form).

**Band brake.** A band brake wraps a flexible band (usually lined steel) around
a rotating drum and tightens it; friction between band and drum builds the band
tension exponentially around the wrap exactly as in the capstan relation
(:mod:`~anvilate.analysis.belt`), and the braking torque is the tension
difference acting at the drum radius:

    T = (T₁ − T₂)·D/2 = T₁·(1 − e^(−μ·β))·D/2

with T₁ the tight-side (anchor-side, against rotation) tension, μ the lining
friction, β the wrap angle, and D the drum diameter. The lining is protected by
capping its contact pressure, which peaks at the tight end of the band:

    p_max = 2·T₁/(b·D)

for a band width b — compared against the lining maker's allowable (a user
input, like any allowable stress).

**Short-shoe brake.** A block (shoe) brake presses a lined pad onto the drum
with a pivoted lever; for a shoe short enough to take the pressure as uniform,
lever moment equilibrium about the pivot sets the shoe normal force:

    N = F·c / (b ∓ μ·a)

with F the actuation force at lever arm c, b the normal-force arm, and a the
friction-force arm. The sign is the interesting part: when the drum's rotation
drags the shoe *into* engagement (self-energizing, the − sign), friction helps
apply the brake and the same hand force brakes harder; rotated the other way
(+) it fights the application. Push the geometry to b ≤ μ·a and a
self-energizing shoe needs no force at all — it grabs (self-locking), which a
brake designer avoids and a backstop designer seeks. The braking torque is then
T = μ·N·D/2.

These are the Shigley Ch. 16 forms. Tensions, lengths, and torques are
dimension-checked :class:`~anvilate.units.Quantity` values; the **wrap angle is
a plain float in radians**, matching :mod:`~anvilate.analysis.belt` (the units
layer does not carry dimensionless angles).
"""

from __future__ import annotations

from math import exp

from ..units import Quantity
from .belt import belt_max_transmissible_force, belt_slack_tension, capstan_tension_ratio

__all__ = [
    "band_brake_torque",
    "differential_band_brake_actuation_force",
    "differential_band_brake_is_self_locking",
    "band_brake_tight_tension_for_torque",
    "band_brake_max_lining_pressure",
    "short_shoe_normal_force",
    "short_shoe_brake_torque",
    "short_shoe_is_self_locking",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _drum_radius_m(drum_diameter: Quantity) -> float:
    _require(drum_diameter, "[length]", "drum_diameter")
    d = drum_diameter.to("m").magnitude
    if d <= 0:
        raise ValueError(f"drum_diameter must be positive; got {drum_diameter}")
    return d / 2.0


def band_brake_torque(
    *,
    tight_tension: Quantity,
    drum_diameter: Quantity,
    friction_coefficient: float,
    wrap_angle: float,
) -> Quantity:
    """The braking torque of a band brake, T = T₁·(1 − e^(−μ·β))·D/2.

    ``tight_tension`` T₁ is the band tension at the anchored (tight) end,
    ``drum_diameter`` D the drum it wraps, ``friction_coefficient`` μ the
    band-on-drum lining friction, and ``wrap_angle`` β the arc of contact **in
    radians**. The tension difference the wrap can develop
    (:func:`~anvilate.analysis.belt.belt_max_transmissible_force`) acts at the
    drum radius — this is the most torque the brake holds before the drum slips
    under the band. Returns the torque in N·m.
    """
    force = belt_max_transmissible_force(
        tight_tension=tight_tension,
        friction_coefficient=friction_coefficient,
        wrap_angle=wrap_angle,
    )
    radius = _drum_radius_m(drum_diameter)
    return Quantity(magnitude=force.to("N").magnitude * radius, unit="N*m")


def band_brake_tight_tension_for_torque(
    *,
    torque: Quantity,
    drum_diameter: Quantity,
    friction_coefficient: float,
    wrap_angle: float,
) -> Quantity:
    """The tight-side tension a braking torque requires, T₁ = 2T/(D·(1 − e^(−μ·β))).

    The inverse of :func:`band_brake_torque` — the anchor-side band tension the
    band, its anchor pin, and the lever must be sized for so the brake holds a
    target ``torque`` on a drum of ``drum_diameter``. ``friction_coefficient``
    must be positive and ``wrap_angle`` (radians) positive. Returns the tension
    in newtons.
    """
    _require(torque, "[force] * [length]", "torque")
    if friction_coefficient <= 0:
        raise ValueError(f"friction_coefficient must be positive; got {friction_coefficient}")
    if wrap_angle <= 0:
        raise ValueError(f"wrap_angle (radians) must be positive; got {wrap_angle}")
    t = torque.to("N*m").magnitude
    if t <= 0:
        raise ValueError(f"torque must be positive; got {torque}")
    radius = _drum_radius_m(drum_diameter)
    grip = 1.0 - exp(-friction_coefficient * wrap_angle)
    return Quantity(magnitude=t / (radius * grip), unit="N")


def band_brake_max_lining_pressure(
    *,
    tight_tension: Quantity,
    band_width: Quantity,
    drum_diameter: Quantity,
) -> Quantity:
    """The peak band-to-drum contact pressure, p_max = 2·T₁/(b·D).

    Band pressure follows the local band tension (p = 2·T/(b·D) from equilibrium
    of a band element), so it peaks at the tight end where the tension is T₁.
    Compare against the lining manufacturer's allowable pressure (a user input —
    e.g. ~0.34 MPa for woven lining, ~1 MPa for sintered) to size the band width
    ``band_width`` b for a drum of ``drum_diameter`` D. Returns the pressure in
    MPa.
    """
    _require(tight_tension, "[force]", "tight_tension")
    _require(band_width, "[length]", "band_width")
    t1 = tight_tension.to("N").magnitude
    if t1 < 0:
        raise ValueError(f"tight_tension must be non-negative; got {tight_tension}")
    b = band_width.to("mm").magnitude
    if b <= 0:
        raise ValueError(f"band_width must be positive; got {band_width}")
    d = drum_diameter.to("mm").magnitude
    if d <= 0:
        raise ValueError(f"drum_diameter must be positive; got {drum_diameter}")
    return Quantity(magnitude=2.0 * t1 / (b * d), unit="MPa")


def _positive_length_m(value: Quantity, name: str) -> float:
    _require(value, "[length]", name)
    magnitude = value.to("m").magnitude
    if magnitude <= 0:
        raise ValueError(f"{name} must be positive; got {value}")
    return magnitude


def short_shoe_is_self_locking(
    *,
    normal_arm: Quantity,
    friction_arm: Quantity,
    friction_coefficient: float,
) -> bool:
    """Whether a self-energizing short-shoe brake grabs on its own, b ≤ μ·a.

    When the friction moment about the lever pivot reaches the normal-force
    moment (``normal_arm`` b ≤ μ·``friction_arm`` a), a self-energizing shoe
    needs no actuation force — once touched to the turning drum it drags itself
    on. That ends a brake's controllability (avoid it by keeping b comfortably
    above μ·a at the lining's *highest* plausible friction), but it is exactly
    what a backstop or one-way holdback wants. ``friction_coefficient`` μ must
    be non-negative.
    """
    if friction_coefficient < 0:
        raise ValueError(f"friction_coefficient must be non-negative; got {friction_coefficient}")
    b = _positive_length_m(normal_arm, "normal_arm")
    a = _positive_length_m(friction_arm, "friction_arm")
    return b <= friction_coefficient * a


def short_shoe_normal_force(
    *,
    actuation_force: Quantity,
    force_arm: Quantity,
    normal_arm: Quantity,
    friction_arm: Quantity,
    friction_coefficient: float,
    self_energizing: bool,
) -> Quantity:
    """The shoe-on-drum normal force of a short-shoe brake, N = F·c/(b ∓ μ·a).

    Moment equilibrium of the brake lever about its pivot: the ``actuation_force``
    F acts at ``force_arm`` c, the drum pushes back on the shoe at ``normal_arm``
    b, and the friction drag μ·N acts at ``friction_arm`` a. With
    ``self_energizing`` True the drum rotation drags the shoe into engagement, the
    friction moment helps apply the shoe, and the denominator is b − μ·a — the
    same hand force presses harder (refuses self-locking geometry, b ≤ μ·a, where
    N is unbounded; check :func:`short_shoe_is_self_locking`). With False it is
    b + μ·a and friction fights the application — the same shoe brakes harder in
    one rotation direction than the other. Returns the normal force in newtons.
    """
    _require(actuation_force, "[force]", "actuation_force")
    f = actuation_force.to("N").magnitude
    if f < 0:
        raise ValueError(f"actuation_force must be non-negative; got {actuation_force}")
    if friction_coefficient < 0:
        raise ValueError(f"friction_coefficient must be non-negative; got {friction_coefficient}")
    c = _positive_length_m(force_arm, "force_arm")
    b = _positive_length_m(normal_arm, "normal_arm")
    a = _positive_length_m(friction_arm, "friction_arm")
    if self_energizing:
        denominator = b - friction_coefficient * a
        if denominator <= 0:
            raise ValueError(
                f"self-locking geometry: normal_arm ({normal_arm}) <= mu*friction_arm "
                f"({friction_coefficient} * {friction_arm}); the shoe grabs without force"
            )
    else:
        denominator = b + friction_coefficient * a
    return Quantity(magnitude=f * c / denominator, unit="N")


def short_shoe_brake_torque(
    *,
    normal_force: Quantity,
    drum_diameter: Quantity,
    friction_coefficient: float,
) -> Quantity:
    """The braking torque a short shoe develops, T = μ·N·D/2.

    The friction drag μ·N of the shoe (``normal_force`` N from
    :func:`short_shoe_normal_force`) acting at the drum radius. ``μ`` must be
    non-negative. Returns the torque in N·m.
    """
    _require(normal_force, "[force]", "normal_force")
    n = normal_force.to("N").magnitude
    if n < 0:
        raise ValueError(f"normal_force must be non-negative; got {normal_force}")
    if friction_coefficient < 0:
        raise ValueError(f"friction_coefficient must be non-negative; got {friction_coefficient}")
    radius = _drum_radius_m(drum_diameter)
    return Quantity(magnitude=friction_coefficient * n * radius, unit="N*m")


def differential_band_brake_actuation_force(
    *,
    tight_tension: Quantity,
    slack_arm: Quantity,
    tight_arm: Quantity,
    lever_length: Quantity,
    friction_coefficient: float,
    wrap_angle: float,
) -> Quantity:
    """The lever force a band brake needs, F = (T₂·a − T₁·b)/L — **signed**.

    The brake lever anchors the band's slack end at ``slack_arm`` a and its
    tight end at ``tight_arm`` b from the pivot, with the operator pulling at
    ``lever_length`` L; the capstan relation ties T₂ to the ``tight_tension`` T₁
    (:func:`~anvilate.analysis.belt.belt_slack_tension`). With b = 0 this is the
    *simple* band brake, F = T₂·a/L. Making b > 0 (the differential layout) lets
    the tight side help pull the band on, cutting the hand force — and pushed to
    a ≤ b·e^(μ·β) the returned force reaches **zero or negative: the brake is
    self-locking** and holds with no force at all (a backstop, not a service
    brake; see :func:`differential_band_brake_is_self_locking`). Arms and lever
    must be lengths (a, L positive; b non-negative). Returns the force in
    newtons, signed.
    """
    slack = belt_slack_tension(
        tight_tension=tight_tension,
        friction_coefficient=friction_coefficient,
        wrap_angle=wrap_angle,
    )
    a = _positive_length_m(slack_arm, "slack_arm")
    _require(tight_arm, "[length]", "tight_arm")
    b = tight_arm.to("m").magnitude
    if b < 0:
        raise ValueError(f"tight_arm must be non-negative; got {tight_arm}")
    length = _positive_length_m(lever_length, "lever_length")
    t1 = tight_tension.to("N").magnitude
    t2 = slack.to("N").magnitude
    return Quantity(magnitude=(t2 * a - t1 * b) / length, unit="N")


def differential_band_brake_is_self_locking(
    *,
    slack_arm: Quantity,
    tight_arm: Quantity,
    friction_coefficient: float,
    wrap_angle: float,
) -> bool:
    """Whether a differential band brake grabs on its own, a ≤ b·e^(μ·β).

    The tight side's pull on its ``tight_arm`` b overpowers the slack side's on
    ``slack_arm`` a once a ≤ b·e^(μ·β) — the tension ratio does the levering —
    and the applied band winds itself tight with no lever force. That is the
    self-locking geometry a controllable brake must stay clear of (at the
    lining's *highest* plausible μ) and a backstop deliberately adopts. Arms are
    as in :func:`differential_band_brake_actuation_force`.
    """
    ratio = capstan_tension_ratio(friction_coefficient=friction_coefficient, wrap_angle=wrap_angle)
    a = _positive_length_m(slack_arm, "slack_arm")
    _require(tight_arm, "[length]", "tight_arm")
    b = tight_arm.to("m").magnitude
    if b < 0:
        raise ValueError(f"tight_arm must be non-negative; got {tight_arm}")
    return a <= b * ratio
