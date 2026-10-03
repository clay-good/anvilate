"""T1 analytical vehicle road-load checks (closed-form).

Sizing a drivetrain — a car's motor, a conveyor tug, a mobile machine's engine, an EV's battery —
starts from the road load: the sum of the resistances the vehicle must overcome to hold a speed.
Three forces make it up. Rolling resistance, the tyre and bearing losses, is a roughly constant
fraction of the weight. Grade resistance is the component of weight along a slope. Aerodynamic drag
(the ½·ρ·C_d·A·v² of :mod:`anvilate.analysis.drag`) grows with the square of speed and dominates at
highway pace. The power to sustain a speed is their sum times that speed.

Rolling resistance is F_r = C_rr·m·g, from the vehicle mass m and the rolling coefficient C_rr (a
few thousandths for a car tyre on tarmac, more on soft ground). Grade resistance is F_g = m·g·sin θ
on a slope of angle θ, the pull that makes hills the hardest duty. Add these to the aerodynamic drag
and the tractive power a steady speed needs is P = F·v — the number that sets the motor rating and,
over a drive cycle, the fuel or battery draw.

Sources: Gillespie, *Fundamentals of Vehicle Dynamics* — the rolling and grade resistances, the
tractive power they demand at speed, and the Ackermann steer angle a wheelbase and turn radius
set.
"""

from __future__ import annotations

from math import atan, degrees, radians, sin

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_MASS_SOURCE = "the vehicle's gross vehicle weight rating or weighbridge record"
_TIRE_SOURCE = "the tire manufacturer's rolling-resistance coefficient data"
_ROUTE_SOURCE = "the route survey's road grade and the drive cycle's speeds"
_DRIVELINE_SOURCE = "the drivetrain's tractive-effort curve at the operating point"
_CHASSIS_SOURCE = "the chassis drawing's wheelbase and the turning-circle specification"


class _VehicleInputError(RefusalError, ValueError):
    """A vehicle road-load input that cannot be used without correction."""


def _vehicle_refusal(message: str, *, subject: str, source: str) -> _VehicleInputError:
    return _VehicleInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _vehicle_input_source(name: str) -> str:
    if name == "vehicle_mass":
        return _MASS_SOURCE
    if name == "rolling_resistance_coefficient":
        return _TIRE_SOURCE
    if name in {"grade_angle", "speed"}:
        return _ROUTE_SOURCE
    if name == "tractive_force":
        return _DRIVELINE_SOURCE
    return _CHASSIS_SOURCE


STANDARD_GRAVITY_M_PER_S2 = 9.80665

__all__ = [
    "ackermann_steer_angle",
    "grade_resistance_force",
    "rolling_resistance_force",
    "tractive_power",
]


def rolling_resistance_force(
    *, vehicle_mass: Quantity, rolling_resistance_coefficient: float
) -> Quantity:
    """The rolling resistance, F_r = C_rr·m·g.

    The near-constant drag of tyre deformation and bearing losses: the ``vehicle_mass`` m times
    gravity, scaled by the ``rolling_resistance_coefficient`` C_rr (about 0.010-0.015 for a car tyre
    on tarmac, higher on gravel or soft ground), F_r = C_rr·m·g. It is roughly independent of speed,
    so it dominates the road load at low speed and in stop-start driving. Returns the force in N.
    """
    require_finite(rolling_resistance_coefficient, name="rolling_resistance_coefficient")
    _check(vehicle_mass, "[mass]", "vehicle_mass")
    m = vehicle_mass.to("kg").magnitude
    if m <= 0:
        raise _vehicle_refusal(
            "vehicle_mass must be positive", subject="vehicle_mass", source=_MASS_SOURCE
        )
    if rolling_resistance_coefficient < 0:
        raise _vehicle_refusal(
            "rolling_resistance_coefficient must be non-negative",
            subject="rolling_resistance_coefficient",
            source=_TIRE_SOURCE,
        )
    force = rolling_resistance_coefficient * m * STANDARD_GRAVITY_M_PER_S2
    return Quantity(magnitude=force, unit="N")


def grade_resistance_force(*, vehicle_mass: Quantity, grade_angle: float) -> Quantity:
    """The grade resistance, F_g = m·g·sin θ.

    The component of weight acting down a slope, which the drive must overcome to climb: the
    ``vehicle_mass`` m times gravity times the sine of the ``grade_angle`` θ (degrees), F_g =
    m·g·sin θ. It vanishes on the flat and grows fast on a hill — a 10% grade (~5.7°) already adds
    about a tenth of the vehicle's weight to the pull, which is why hill-climb sets the peak duty.
    Returns the force in N (positive uphill).
    """
    require_finite(grade_angle, name="grade_angle")
    _check(vehicle_mass, "[mass]", "vehicle_mass")
    m = vehicle_mass.to("kg").magnitude
    if m <= 0:
        raise _vehicle_refusal(
            "vehicle_mass must be positive", subject="vehicle_mass", source=_MASS_SOURCE
        )
    if not -90.0 <= grade_angle <= 90.0:
        raise _vehicle_refusal(
            "grade_angle must be in [-90, 90] degrees", subject="grade_angle", source=_ROUTE_SOURCE
        )
    return Quantity(magnitude=m * STANDARD_GRAVITY_M_PER_S2 * sin(radians(grade_angle)), unit="N")


def tractive_power(*, tractive_force: Quantity, speed: Quantity) -> Quantity:
    """The tractive power to hold a speed, P = F·v.

    The power the drivetrain must deliver at the wheels to sustain a steady speed against the total
    road load: the ``tractive_force`` F — the sum of rolling (:func:`rolling_resistance_force`),
    grade (:func:`grade_resistance_force`), and aerodynamic drag — times the ``speed`` v, P = F·v.
    It sizes
    the motor or engine rating for a target cruise, and integrated over a drive cycle it is the fuel
    or battery energy the vehicle draws. Returns the power in kW.
    """
    _check(tractive_force, "[force]", "tractive_force")
    _check(speed, "[length]/[time]", "speed")
    f = tractive_force.to("N").magnitude
    v = speed.to("m/s").magnitude
    if f <= 0:
        raise _vehicle_refusal(
            "tractive_force must be positive", subject="tractive_force", source=_DRIVELINE_SOURCE
        )
    if v <= 0:
        raise _vehicle_refusal("speed must be positive", subject="speed", source=_ROUTE_SOURCE)
    return Quantity(magnitude=f * v / 1000.0, unit="kW")


def ackermann_steer_angle(*, wheelbase: Quantity, turn_radius: Quantity) -> Quantity:
    """The kinematic (Ackermann) steer angle, δ = arctan(L/R).

    The steering angle a vehicle's front wheels need to hold a turn at low speed, from the geometry
    of the bicycle model: the ``wheelbase`` L and the turn ``turn_radius`` R (to the rear axle)
    give δ = arctan(L/R). A tighter turn (smaller R) or a longer wheelbase demands more lock, which
    is why long vehicles need wide turning circles. It is the zero-slip reference the actual steer
    angle departs from as cornering forces build. Returns the steer angle in degrees.
    """
    _check(wheelbase, "[length]", "wheelbase")
    _check(turn_radius, "[length]", "turn_radius")
    length = wheelbase.to("m").magnitude
    r = turn_radius.to("m").magnitude
    if length <= 0:
        raise _vehicle_refusal(
            "wheelbase must be positive", subject="wheelbase", source=_CHASSIS_SOURCE
        )
    if r <= 0:
        raise _vehicle_refusal(
            "turn_radius must be positive", subject="turn_radius", source=_CHASSIS_SOURCE
        )
    return Quantity(magnitude=degrees(atan(length / r)), unit="degree")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _vehicle_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_vehicle_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _vehicle_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_vehicle_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
