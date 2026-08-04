"""T1 analytical geotechnical checks (Rankine earth pressure, Terzaghi bearing, closed-form).

Two problems sit under almost every foundation and retaining wall, and both have clean
closed forms in terms of the soil's friction angle φ and unit weight γ.

*Lateral earth pressure* (Rankine): a wall retaining level cohesionless backfill feels a
pressure that grows linearly with depth. The coefficient is a pure function of φ —
K_a = tan²(45° − φ/2) when the soil is pushing the wall away (active) and
K_p = tan²(45° + φ/2) when the wall pushes into the soil (passive) — and the resultant
thrust on a wall of height H is the triangle's area, ½·K·γ·H² per unit length (plus a
K·q·H rectangle for any uniform surcharge q).

*Bearing capacity* (Terzaghi): the ultimate pressure a strip footing can carry before the
soil shears is q_ult = c·N_c + q·N_q + ½·γ·B·N_γ — a cohesion term, a surcharge (embedment)
term, and a self-weight term, each scaled by a dimensionless bearing-capacity factor that
depends only on φ. :func:`bearing_capacity_factors` returns N_c, N_q, N_γ from the standard
closed forms (N_q from Reissner, N_c from Prandtl, N_γ from Vesić's 2(N_q+1)·tanφ).

Angles are passed in degrees (a bare float, as elsewhere in this library); other inputs and
all outputs are dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import exp, pi, radians, tan

from ..units import Quantity

__all__ = [
    "bearing_capacity_factors",
    "rankine_earth_pressure_coefficient",
    "rankine_lateral_thrust",
    "terzaghi_bearing_capacity",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _check_friction_angle(friction_angle: float) -> None:
    if not 0.0 <= friction_angle < 90.0:
        raise ValueError(f"friction_angle must be in [0, 90) degrees; got {friction_angle}")


def rankine_earth_pressure_coefficient(*, friction_angle: float, passive: bool = False) -> float:
    """The Rankine lateral earth-pressure coefficient for level cohesionless backfill.

    The ratio of horizontal to vertical effective stress behind a smooth wall retaining level
    granular soil, a pure function of the drained friction angle φ: the active coefficient
    K_a = tan²(45° − φ/2) governs when the soil yields and pushes the wall out, and the passive
    K_p = tan²(45° + φ/2) — its reciprocal — the much larger resistance the wall mobilizes
    pushing back into the soil. ``friction_angle`` φ is in degrees; set ``passive`` True for K_p.
    Returns the dimensionless coefficient.
    """
    _check_friction_angle(friction_angle)
    if passive:
        return tan(radians(45.0 + friction_angle / 2.0)) ** 2
    return tan(radians(45.0 - friction_angle / 2.0)) ** 2


def rankine_lateral_thrust(
    *,
    unit_weight: Quantity,
    height: Quantity,
    friction_angle: float,
    passive: bool = False,
    surcharge: Quantity | None = None,
) -> Quantity:
    """The Rankine resultant lateral thrust on a wall of height H, per unit wall length.

    Integrating the Rankine pressure over the wall gives the horizontal force the backfill
    delivers: the soil's own triangular pressure contributes ½·K·γ·H² and any uniform surface
    ``surcharge`` q adds a rectangular K·q·H. ``unit_weight`` γ is the soil's total unit weight,
    ``height`` H the retained height, ``friction_angle`` φ (degrees) sets the coefficient via
    :func:`rankine_earth_pressure_coefficient`, and ``passive`` selects K_p over K_a. Returns the
    thrust per unit wall length in kN/m — multiply by the wall length for the total force, and
    note the soil triangle's resultant acts at H/3 above the base.
    """
    _require(unit_weight, "[force]/[length]**3", "unit_weight")
    _require(height, "[length]", "height")
    gamma = unit_weight.to("kN/m**3").magnitude
    h = height.to("m").magnitude
    if gamma <= 0 or h <= 0:
        raise ValueError("unit_weight and height must be positive")
    k = rankine_earth_pressure_coefficient(friction_angle=friction_angle, passive=passive)
    thrust = 0.5 * k * gamma * h**2
    if surcharge is not None:
        _require(surcharge, "[pressure]", "surcharge")
        q = surcharge.to("kPa").magnitude
        if q < 0:
            raise ValueError("surcharge must be non-negative")
        thrust += k * q * h
    return Quantity(magnitude=thrust, unit="kN/m")


def bearing_capacity_factors(*, friction_angle: float) -> dict[str, float]:
    """The Terzaghi/Vesić bearing-capacity factors N_c, N_q, N_γ from the friction angle.

    The three dimensionless multipliers in the bearing-capacity equation, each a function of the
    drained friction angle φ alone: N_q = e^(π·tanφ)·tan²(45° + φ/2) (Reissner's surcharge term),
    N_c = (N_q − 1)·cotφ (Prandtl, with the φ→0 limit N_c = π + 2 = 5.14), and
    N_γ = 2·(N_q + 1)·tanφ (Vesić). ``friction_angle`` φ is in degrees. Returns a dict with keys
    ``"N_c"``, ``"N_q"``, ``"N_gamma"`` — feed them to :func:`terzaghi_bearing_capacity`.
    """
    _check_friction_angle(friction_angle)
    phi = radians(friction_angle)
    n_q = exp(pi * tan(phi)) * tan(radians(45.0 + friction_angle / 2.0)) ** 2
    if friction_angle == 0.0:
        n_c = pi + 2.0  # Prandtl limit; (N_q - 1)/tan(phi) is 0/0 at phi = 0
    else:
        n_c = (n_q - 1.0) / tan(phi)
    n_gamma = 2.0 * (n_q + 1.0) * tan(phi)
    return {"N_c": n_c, "N_q": n_q, "N_gamma": n_gamma}


def terzaghi_bearing_capacity(
    *,
    cohesion: Quantity,
    surcharge: Quantity,
    unit_weight: Quantity,
    width: Quantity,
    bearing_factor_c: float,
    bearing_factor_q: float,
    bearing_factor_gamma: float,
) -> Quantity:
    """The Terzaghi ultimate bearing pressure of a strip footing, q_ult.

    The pressure at which the soil beneath a long footing shears and the footing plunges, summed
    from three mechanisms: q_ult = c·N_c + q·N_q + ½·γ·B·N_γ, a cohesion term, a surcharge term
    for the soil above founding level (``surcharge`` q = γ·D_f), and a self-weight term over the
    footing ``width`` B. ``cohesion`` c and ``surcharge`` q are pressures, ``unit_weight`` γ the
    soil unit weight, and the three ``bearing_factor_*`` are N_c, N_q, N_γ from
    :func:`bearing_capacity_factors` (or a table). Returns q_ult in kPa; divide by a factor of
    safety (typically 3) for the allowable bearing pressure.
    """
    _require(cohesion, "[pressure]", "cohesion")
    _require(surcharge, "[pressure]", "surcharge")
    _require(unit_weight, "[force]/[length]**3", "unit_weight")
    _require(width, "[length]", "width")
    c = cohesion.to("kPa").magnitude
    q = surcharge.to("kPa").magnitude
    gamma = unit_weight.to("kN/m**3").magnitude
    b = width.to("m").magnitude
    if c < 0 or q < 0:
        raise ValueError("cohesion and surcharge must be non-negative")
    if gamma <= 0 or b <= 0:
        raise ValueError("unit_weight and width must be positive")
    q_ult = c * bearing_factor_c + q * bearing_factor_q + 0.5 * gamma * b * bearing_factor_gamma
    return Quantity(magnitude=q_ult, unit="kPa")
