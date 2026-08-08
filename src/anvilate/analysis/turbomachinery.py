"""T1 analytical turbomachine (Euler head) checks (closed-form).

Every centrifugal pump, fan, and compressor impeller obeys one governing relation — Euler's
turbomachine equation — which sets the head a rotor can theoretically impart from the velocity
triangles at its inlet and outlet, before any friction or leakage loss. It is the design ceiling the
actual head (the rho*g*Q*H of :mod:`anvilate.analysis.pump`) is measured against, and it is a
distinct calculation: the pump module rates a machine from its *delivered* head, while this module
predicts the head from the *geometry and speed* of the impeller.

The chain is three steps. The blade tip speed U = pi*D*N is the rotor kinematics. The outlet swirl
(tangential) velocity c_theta = U - c_m/tan(beta) closes the outlet velocity triangle from the blade
angle beta and the meridional (through-flow) velocity c_m — backward-curved vanes (beta < 90 deg)
trade head for a stable, non-overloading characteristic, radial vanes (beta = 90 deg) give
c_theta = U, and forward-curved vanes (beta > 90 deg) push head higher at the cost of stability.
The Euler head H = (U2*c_theta2 - U1*c_theta1)/g then follows, usually with no inlet swirl
(c_theta1 = 0) for a well-designed inlet.
"""

from __future__ import annotations

from math import pi, radians, tan

from ..units import Quantity

_STANDARD_GRAVITY = Quantity(magnitude=9.80665, unit="m/s**2")

__all__ = [
    "blade_tip_speed",
    "euler_head",
    "impeller_outlet_swirl_velocity",
]


def blade_tip_speed(*, diameter: Quantity, rotational_speed: Quantity) -> Quantity:
    """The blade tip (peripheral) speed U = pi*D*N of a rotor.

    The linear speed of an impeller rim of ``diameter`` D turning at ``rotational_speed`` N — the
    U that anchors both velocity triangles. It is the single strongest lever on head, which scales
    with U squared, so it is capped by the rotor material's stress limit. Returns the speed in m/s.
    """
    _check(diameter, "[length]", "diameter")
    if not rotational_speed.has_dimension("1/[time]"):
        raise ValueError(
            f"rotational_speed must be a 1/[time] quantity; got "
            f"{rotational_speed.dimensionality} ({rotational_speed})"
        )
    d = diameter.to("m").magnitude
    # N is a revolution count per time, not an angular rate: convert via rpm (revolution is a real
    # unit) so the 2*pi rad-per-revolution factor of .to("1/s") is not applied. A rad/s input still
    # converts correctly.
    n = rotational_speed.to("rpm").magnitude / 60.0
    if d <= 0:
        raise ValueError("diameter must be positive")
    if n <= 0:
        raise ValueError("rotational_speed must be positive")
    return Quantity(magnitude=pi * d * n, unit="m/s")


def impeller_outlet_swirl_velocity(
    *,
    blade_speed: Quantity,
    meridional_velocity: Quantity,
    blade_angle: float,
) -> Quantity:
    """The outlet swirl velocity c_theta = U - c_m/tan(beta) from the velocity triangle.

    The tangential component of the absolute flow leaving the impeller: the ``blade_speed`` U less
    the slip the ``meridional_velocity`` c_m carries back through the ``blade_angle`` beta (degrees,
    measured from the tangent). Backward-curved vanes (beta < 90) give c_theta < U and a stable
    characteristic; radial vanes (beta = 90) give c_theta = U; forward-curved (beta > 90) give
    c_theta > U for more head but a rising-then-falling, less stable curve. Returns c_theta in m/s.
    """
    _check(blade_speed, "[length]/[time]", "blade_speed")
    _check(meridional_velocity, "[length]/[time]", "meridional_velocity")
    u = blade_speed.to("m/s").magnitude
    cm = meridional_velocity.to("m/s").magnitude
    if u <= 0:
        raise ValueError("blade_speed must be positive")
    if cm <= 0:
        raise ValueError("meridional_velocity must be positive")
    if not 0.0 < blade_angle < 180.0:
        raise ValueError("blade_angle must be in (0, 180) degrees")
    ctheta = u - cm / tan(radians(blade_angle))
    return Quantity(magnitude=ctheta, unit="m/s")


def euler_head(
    *,
    outlet_blade_speed: Quantity,
    outlet_swirl_velocity: Quantity,
    inlet_blade_speed: Quantity | None = None,
    inlet_swirl_velocity: Quantity | None = None,
) -> Quantity:
    """The Euler head H = (U2*c_theta2 - U1*c_theta1)/g.

    The theoretical head an impeller imparts, from Euler's turbomachine equation: the ``outlet``
    blade speed U2 and swirl c_theta2 (from :func:`impeller_outlet_swirl_velocity`) less the inlet
    product U1*c_theta1, over g. A well-designed inlet has no pre-swirl, so ``inlet_blade_speed``
    and ``inlet_swirl_velocity`` default to zero and H = U2*c_theta2/g. This is the loss-free
    ceiling the delivered head of :mod:`anvilate.analysis.pump` falls below. Returns the head in m.
    """
    _check(outlet_blade_speed, "[length]/[time]", "outlet_blade_speed")
    _check(outlet_swirl_velocity, "[length]/[time]", "outlet_swirl_velocity")
    u2 = outlet_blade_speed.to("m/s").magnitude
    ct2 = outlet_swirl_velocity.to("m/s").magnitude
    if u2 <= 0:
        raise ValueError("outlet_blade_speed must be positive")
    if inlet_blade_speed is None:
        u1 = 0.0
    else:
        _check(inlet_blade_speed, "[length]/[time]", "inlet_blade_speed")
        u1 = inlet_blade_speed.to("m/s").magnitude
        if u1 < 0:
            raise ValueError("inlet_blade_speed must be non-negative")
    if inlet_swirl_velocity is None:
        ct1 = 0.0
    else:
        _check(inlet_swirl_velocity, "[length]/[time]", "inlet_swirl_velocity")
        ct1 = inlet_swirl_velocity.to("m/s").magnitude
    g = _STANDARD_GRAVITY.to("m/s**2").magnitude
    head = (u2 * ct2 - u1 * ct1) / g
    if head <= 0:
        raise ValueError(
            "Euler head is non-positive; the outlet swirl work does not exceed the inlet swirl work"
        )
    return Quantity(magnitude=head, unit="m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
