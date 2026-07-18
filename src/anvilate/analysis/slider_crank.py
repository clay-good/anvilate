"""T1 analytical slider-crank (piston) kinematics (exact closed-form).

The slider-crank turns rotation into straight-line reciprocation — the piston and
connecting rod of every engine and pump. A crank of radius r spins at angle θ, and
the rod of length L links its pin to the slider, which travels along the cylinder
axis. The wrist-pin distance from the crank axis is exactly

    s = r·cos θ + √(L² − r²·sin²θ),

so the slider displacement from top dead centre (θ = 0, s = r + L) is

    x = r·(1 − cos θ) + L − √(L² − r²·sin²θ),

running from 0 at TDC to the full stroke 2r at bottom dead centre. Differentiating
with respect to time gives the exact slider velocity

    v = ẋ = ω·r·sin θ·(1 + r·cos θ / √(L² − r²·sin²θ)),

which is zero at both dead centres and near-maximum around mid-stroke. The
asymmetry between the two halves — the extra r·cos θ / √(…) term — is the
finite-rod effect that a short rod (small L/r) exaggerates and an infinite rod
(pure SHM) erases.

The crank angle θ is a plain-float degrees value; the crank radius, rod length,
and crank speed are dimension-checked :class:`~anvilate.units.Quantity` values,
with L > r (the rod must be longer than the crank or the linkage jams).
"""

from __future__ import annotations

from math import cos, radians, sin, sqrt

from ..units import Quantity

__all__ = [
    "slider_crank_displacement",
    "slider_crank_velocity",
    "slider_crank_acceleration",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _geometry(crank_radius: Quantity, rod_length: Quantity) -> tuple[float, float]:
    """Validate and return (r, L) in mm — the shared linkage dimensions."""
    _require(crank_radius, "[length]", "crank_radius")
    _require(rod_length, "[length]", "rod_length")
    r = crank_radius.to("mm").magnitude
    length = rod_length.to("mm").magnitude
    if r <= 0:
        raise ValueError(f"crank_radius must be positive; got {crank_radius}")
    if length <= r:
        raise ValueError(
            f"rod_length must exceed crank_radius (or the linkage jams); "
            f"got rod {rod_length} vs crank {crank_radius}"
        )
    return r, length


def slider_crank_displacement(
    *, crank_radius: Quantity, rod_length: Quantity, crank_angle: float
) -> Quantity:
    """The slider displacement from top dead centre, x = r(1 − cos θ) + L − √(L² − r²sin²θ).

    The distance the slider (piston) has travelled from top dead centre for a crank
    at ``crank_angle`` θ (degrees). ``crank_radius`` r and ``rod_length`` L (L > r)
    set the linkage; the result runs from 0 at TDC (θ = 0) to the full stroke 2r at
    bottom dead centre (θ = 180°). Returns the displacement in mm.
    """
    r, length = _geometry(crank_radius, rod_length)
    theta = radians(crank_angle)
    x = r * (1.0 - cos(theta)) + length - sqrt(length**2 - (r * sin(theta)) ** 2)
    return Quantity(magnitude=x, unit="mm")


def slider_crank_velocity(
    *,
    crank_radius: Quantity,
    rod_length: Quantity,
    crank_angle: float,
    crank_speed: Quantity,
) -> Quantity:
    """The slider velocity v = ω·r·sin θ·(1 + r·cos θ / √(L² − r²sin²θ)).

    The exact instantaneous slider speed for a crank at ``crank_angle`` θ (degrees)
    turning at ``crank_speed`` ω. ``crank_radius`` r and ``rod_length`` L (L > r)
    set the linkage; ω is a rotational frequency (rpm or rad/s). The velocity is
    zero at both dead centres and the finite-rod term r·cos θ / √(…) makes the two
    half-strokes asymmetric. Returns the velocity in m/s (signed: positive as the
    slider moves away from top dead centre).
    """
    r, length = _geometry(crank_radius, rod_length)
    if not crank_speed.has_dimension("[frequency]"):
        raise ValueError(
            f"crank_speed must be a rotational-speed ([frequency]) quantity; got "
            f"{crank_speed.dimensionality} ({crank_speed})"
        )
    theta = radians(crank_angle)
    omega = crank_speed.to("rad/s").magnitude
    root = sqrt(length**2 - (r * sin(theta)) ** 2)
    dx_dtheta_mm = r * sin(theta) * (1.0 + r * cos(theta) / root)
    return Quantity(magnitude=dx_dtheta_mm / 1000.0 * omega, unit="m/s")


def slider_crank_acceleration(
    *,
    crank_radius: Quantity,
    rod_length: Quantity,
    crank_angle: float,
    crank_speed: Quantity,
) -> Quantity:
    """The exact slider acceleration a = ω²·d²x/dθ² of a slider-crank.

    The instantaneous slider acceleration for a crank at ``crank_angle`` θ
    (degrees) turning at constant ``crank_speed`` ω — the quantity that, times the
    reciprocating mass, is the inertia (shaking) force an engine balancer fights.
    ``crank_radius`` r and ``rod_length`` L (L > r) set the linkage; ω is a
    rotational frequency. Acceleration peaks at top dead centre (r·ω²·(1 + r/L))
    and is smaller in magnitude at bottom dead centre (r·ω²·(1 − r/L)) — the
    finite-rod asymmetry that a piston engine feels as a second-order shake.
    Returns the acceleration in m/s².
    """
    r, length = _geometry(crank_radius, rod_length)
    if not crank_speed.has_dimension("[frequency]"):
        raise ValueError(
            f"crank_speed must be a rotational-speed ([frequency]) quantity; got "
            f"{crank_speed.dimensionality} ({crank_speed})"
        )
    theta = radians(crank_angle)
    omega = crank_speed.to("rad/s").magnitude
    root = sqrt(length**2 - (r * sin(theta)) ** 2)
    d2x_dtheta2_mm = r * cos(theta) + r**2 * (
        cos(2.0 * theta) / root + r**2 * sin(theta) ** 2 * cos(theta) ** 2 / root**3
    )
    return Quantity(magnitude=d2x_dtheta2_mm / 1000.0 * omega**2, unit="m/s**2")
