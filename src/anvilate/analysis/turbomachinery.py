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

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite
from ..units.rotation import revolutions_per_second

_IMPELLER_SOURCE = "the impeller drawing (diameter, blade angle, and blade count)"
_SPEED_SOURCE = "the machine's rated speed from its datasheet"
_TRIANGLE_SOURCE = "the velocity triangles from the stage design calculation"


class _TurbomachineryInputError(RefusalError, ValueError):
    """A turbomachinery input that cannot be used without correction."""


def _turbomachinery_refusal(
    message: str, *, subject: str, source: str
) -> _TurbomachineryInputError:
    return _TurbomachineryInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _turbomachinery_input_source(name: str) -> str:
    if name in {"blade_angle", "blade_count", "diameter"}:
        return _IMPELLER_SOURCE
    if name == "rotational_speed":
        return _SPEED_SOURCE
    return _TRIANGLE_SOURCE


_STANDARD_GRAVITY = Quantity(magnitude=9.80665, unit="m/s**2")

__all__ = [
    "blade_tip_speed",
    "euler_head",
    "flow_coefficient",
    "impeller_outlet_swirl_velocity",
    "stage_loading_coefficient",
    "stanitz_slip_factor",
]


def blade_tip_speed(*, diameter: Quantity, rotational_speed: Quantity) -> Quantity:
    """The blade tip (peripheral) speed U = pi*D*N of a rotor.

    The linear speed of an impeller rim of ``diameter`` D turning at ``rotational_speed`` N — the
    U that anchors both velocity triangles. It is the single strongest lever on head, which scales
    with U squared, so it is capped by the rotor material's stress limit. Returns the speed in m/s.
    """
    _check(diameter, "[length]", "diameter")
    if not isinstance(rotational_speed, Quantity):
        raise _turbomachinery_refusal(
            f"rotational_speed must be a 1/[time] quantity; got {rotational_speed!r}",
            subject="rotational_speed",
            source=_SPEED_SOURCE,
        )
    if not rotational_speed.has_dimension("1/[time]"):
        raise _turbomachinery_refusal(
            f"rotational_speed must be a 1/[time] quantity; got "
            f"{rotational_speed.dimensionality} ({rotational_speed})",
            subject="rotational_speed",
            source=_SPEED_SOURCE,
        )
    d = diameter.to("m").magnitude
    n = revolutions_per_second(rotational_speed, name="rotational_speed")
    if d <= 0:
        raise _turbomachinery_refusal(
            "diameter must be positive", subject="diameter", source=_IMPELLER_SOURCE
        )
    if n <= 0:
        raise _turbomachinery_refusal(
            "rotational_speed must be positive", subject="rotational_speed", source=_SPEED_SOURCE
        )
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
        raise _turbomachinery_refusal(
            "blade_speed must be positive", subject="blade_speed", source=_TRIANGLE_SOURCE
        )
    if cm <= 0:
        raise _turbomachinery_refusal(
            "meridional_velocity must be positive",
            subject="meridional_velocity",
            source=_TRIANGLE_SOURCE,
        )
    if not 0.0 < blade_angle < 180.0:
        raise _turbomachinery_refusal(
            "blade_angle must be in (0, 180) degrees",
            subject="blade_angle",
            source=_IMPELLER_SOURCE,
        )
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
        raise _turbomachinery_refusal(
            "outlet_blade_speed must be positive",
            subject="outlet_blade_speed",
            source=_TRIANGLE_SOURCE,
        )
    if inlet_blade_speed is None:
        u1 = 0.0
    else:
        _check(inlet_blade_speed, "[length]/[time]", "inlet_blade_speed")
        u1 = inlet_blade_speed.to("m/s").magnitude
        if u1 < 0:
            raise _turbomachinery_refusal(
                "inlet_blade_speed must be non-negative",
                subject="inlet_blade_speed",
                source=_TRIANGLE_SOURCE,
            )
    if inlet_swirl_velocity is None:
        ct1 = 0.0
    else:
        _check(inlet_swirl_velocity, "[length]/[time]", "inlet_swirl_velocity")
        ct1 = inlet_swirl_velocity.to("m/s").magnitude
    g = _STANDARD_GRAVITY.to("m/s**2").magnitude
    head = (u2 * ct2 - u1 * ct1) / g
    if head <= 0:
        raise _turbomachinery_refusal(
            "Euler head is non-positive; the outlet swirl work does not exceed the inlet swirl "
            "work",
            subject=(
                "outlet_blade_speed, outlet_swirl_velocity, inlet_blade_speed, and "
                "inlet_swirl_velocity"
            ),
            source=_TRIANGLE_SOURCE,
        )
    return Quantity(magnitude=head, unit="m")


def flow_coefficient(*, axial_velocity: Quantity, blade_speed: Quantity) -> float:
    """The turbomachine flow coefficient, φ = C_a/U.

    The dimensionless throughput of a stage: the ``axial_velocity`` C_a (the through-flow velocity)
    over the ``blade_speed`` U, φ = C_a/U. Together with the :func:`stage_loading_coefficient` it
    fixes a stage's place on the Smith / Cordier chart, where efficiency contours live — a low φ is
    a lightly loaded, large-diameter machine, a high φ a compact high-flow one. It is the same
    similarity number that makes two geometrically similar stages run alike. Both velocities must
    be positive. Returns the dimensionless flow coefficient.
    """
    _check(axial_velocity, "[length]/[time]", "axial_velocity")
    _check(blade_speed, "[length]/[time]", "blade_speed")
    c_a = axial_velocity.to("m/s").magnitude
    u = blade_speed.to("m/s").magnitude
    if c_a <= 0:
        raise _turbomachinery_refusal(
            "axial_velocity must be positive", subject="axial_velocity", source=_TRIANGLE_SOURCE
        )
    if u <= 0:
        raise _turbomachinery_refusal(
            "blade_speed must be positive", subject="blade_speed", source=_TRIANGLE_SOURCE
        )
    return c_a / u


def stage_loading_coefficient(*, specific_work: Quantity, blade_speed: Quantity) -> float:
    """The turbomachine stage loading coefficient, ψ = Δh₀/U².

    How hard a single stage works, made dimensionless: the ``specific_work`` Δh₀ (the stagnation
    enthalpy change per unit mass the stage adds or extracts) over the square of the ``blade_speed``
    U, ψ = Δh₀/U². A high ψ packs more work into one stage (fewer stages, but steeper blade turning
    and more loss), a low ψ spreads it over many gentle stages. With the :func:`flow_coefficient`
    it is the pair a compressor or turbine stage is designed and compared on. ``specific_work`` is
    an energy per mass (m²/s²); U must be positive. Returns the dimensionless loading coefficient.
    """
    _check(specific_work, "[length]**2/[time]**2", "specific_work")
    _check(blade_speed, "[length]/[time]", "blade_speed")
    dh0 = specific_work.to("m**2/s**2").magnitude
    u = blade_speed.to("m/s").magnitude
    if dh0 <= 0:
        raise _turbomachinery_refusal(
            "specific_work must be positive", subject="specific_work", source=_TRIANGLE_SOURCE
        )
    if u <= 0:
        raise _turbomachinery_refusal(
            "blade_speed must be positive", subject="blade_speed", source=_TRIANGLE_SOURCE
        )
    return dh0 / u**2


def stanitz_slip_factor(*, blade_count: int) -> float:
    """The Stanitz slip factor of a centrifugal impeller, σ = 1 − 0.63·π/Z.

    :func:`euler_head` is the loss-free ceiling, and this is the first and largest step down from
    it. A real impeller has a finite number of blades, so the flow between them does not follow the
    blade angle exactly: it retains a relative eddy that reduces the outlet swirl and therefore the
    head. Stanitz's correlation for radial-ish blades puts the deficit at σ = 1 − 0.63·π/``Z`` from
    the ``blade_count`` Z alone, and the head the impeller actually imparts is H = σ·H_Euler.

    Slip is not a loss — no energy is dissipated, the impeller simply transfers less than the blade
    geometry suggests — so it applies before, and on top of, the hydraulic efficiency. It is also
    large: a 7-blade impeller slips to σ = 0.717, meaning the Euler head overstates the deliverable
    head by 39%, which is why a screening calculation that stops at Euler is optimistic by a margin
    no efficiency factor accounts for. More blades slip less but block and rub more, so real
    impellers land at 5-9. Requires Z > 0.63·π ≈ 1.98 (below that the correlation goes non-physical
    and is meaningless anyway). Returns the dimensionless slip factor, between 0 and 1.
    """
    require_finite(blade_count, name="blade_count")
    if int(blade_count) != blade_count:
        raise _turbomachinery_refusal(
            f"blade_count must be a whole number of blades; got {blade_count}",
            subject="blade_count",
            source=_IMPELLER_SOURCE,
        )
    z = int(blade_count)
    if z <= 0.63 * pi:
        raise _turbomachinery_refusal(
            f"blade_count must exceed 0.63*pi ~ 1.98 for the Stanitz correlation; got {z}",
            subject="blade_count",
            source=_IMPELLER_SOURCE,
        )
    return 1.0 - 0.63 * pi / z


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _turbomachinery_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_turbomachinery_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _turbomachinery_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_turbomachinery_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
