"""T1 analytical scotch-yoke kinematics (exact simple harmonic motion).

A scotch yoke converts rotation into reciprocation with a pin sliding in a straight
slot — no connecting rod. Dropping the rod drops the finite-rod asymmetry too, so
the slider moves in *pure* simple harmonic motion: it is exactly the infinite-rod
limit of the slider-crank. For a crank of radius r at angle θ turning at speed ω,

    x = r·(1 − cos θ),   v = ω·r·sin θ,   a = ω²·r·cos θ,

the displacement running 0 → 2r over half a turn. Unlike the slider-crank, the
acceleration is a clean cosine: it peaks at *equal* magnitude r·ω² at both dead
centres, so a scotch-yoke pump or valve actuator has no second-order shake to
balance — the reason it is chosen where smooth reciprocation matters more than the
extra friction of the sliding yoke.

The crank angle θ is a plain-float degrees value; the crank radius and speed are
dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import cos, radians, sin

from ..units import Quantity

__all__ = [
    "scotch_yoke_displacement",
    "scotch_yoke_velocity",
    "scotch_yoke_acceleration",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _crank_radius_mm(crank_radius: Quantity) -> float:
    _require(crank_radius, "[length]", "crank_radius")
    r = crank_radius.to("mm").magnitude
    if r <= 0:
        raise ValueError(f"crank_radius must be positive; got {crank_radius}")
    return r


def _speed_rad_s(crank_speed: Quantity) -> float:
    if not crank_speed.has_dimension("[frequency]"):
        raise ValueError(
            f"crank_speed must be a rotational-speed ([frequency]) quantity; got "
            f"{crank_speed.dimensionality} ({crank_speed})"
        )
    return crank_speed.to("rad/s").magnitude


def scotch_yoke_displacement(*, crank_radius: Quantity, crank_angle: float) -> Quantity:
    """The slider displacement from top dead centre, x = r·(1 − cos θ).

    ``crank_radius`` r sets the stroke (2r) and ``crank_angle`` θ (degrees) the
    crank position; the result runs from 0 at TDC (θ = 0) to the full stroke 2r at
    BDC (θ = 180°). Returns the displacement in mm.
    """
    r = _crank_radius_mm(crank_radius)
    return Quantity(magnitude=r * (1.0 - cos(radians(crank_angle))), unit="mm")


def scotch_yoke_velocity(
    *, crank_radius: Quantity, crank_angle: float, crank_speed: Quantity
) -> Quantity:
    """The slider velocity v = ω·r·sin θ (pure sinusoid).

    ``crank_radius`` r, ``crank_angle`` θ (degrees), and ``crank_speed`` ω (rpm or
    rad/s) describe the motion. The velocity is a clean sinusoid — zero at both dead
    centres, ω·r at mid-stroke — with none of the slider-crank's half-stroke
    asymmetry. Returns the velocity in m/s.
    """
    r = _crank_radius_mm(crank_radius)
    omega = _speed_rad_s(crank_speed)
    return Quantity(magnitude=r / 1000.0 * omega * sin(radians(crank_angle)), unit="m/s")


def scotch_yoke_acceleration(
    *, crank_radius: Quantity, crank_angle: float, crank_speed: Quantity
) -> Quantity:
    """The slider acceleration a = ω²·r·cos θ (pure cosine).

    ``crank_radius`` r, ``crank_angle`` θ (degrees), and ``crank_speed`` ω describe
    the motion. The acceleration is a pure cosine, peaking at *equal* magnitude
    r·ω² at both dead centres (positive at TDC, negative at BDC) — the symmetry that
    frees a scotch yoke of the slider-crank's second-order shake. Returns the
    acceleration in m/s².
    """
    r = _crank_radius_mm(crank_radius)
    omega = _speed_rad_s(crank_speed)
    return Quantity(magnitude=r / 1000.0 * omega**2 * cos(radians(crank_angle)), unit="m/s**2")
