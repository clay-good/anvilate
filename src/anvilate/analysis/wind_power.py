"""T1 analytical wind-turbine power checks (closed-form).

The power in the wind, and the fraction a turbine can take from it, complete the renewable trio with
:mod:`anvilate.analysis.solar_pv` and :mod:`anvilate.analysis.energy_storage`.

The kinetic power crossing a unit area of moving air is ½·ρ·V³ — it rises with the *cube* of wind
speed, so a site with 25% more wind holds nearly twice the power, which is why turbine siting lives
and dies on the wind resource.

A turbine cannot take all of it: slowing the air too much would dam the flow, so Betz's law caps the
extractable fraction at 16/27 ≈ 0.593 of the incident power. Real rotors reach a power coefficient
C_p of ~0.35–0.45. The power a rotor of swept area A = π·D²/4 delivers is then P = ½·ρ·A·V³·C_p,
with C_p the caller's value (bounded by the Betz limit).

Sources: Manwell, *Wind Energy Explained*, and Burton, *Wind Energy Handbook*,
for the power-coefficient, Betz-limit and rotor relations.
"""

from __future__ import annotations

from math import pi

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite
from ..units.rotation import angular_speed_rad_per_s

_SITE_SOURCE = "the site wind resource assessment (met-mast speeds, heights, shear)"
_TURBINE_SOURCE = "the turbine manufacturer's datasheet (rotor size, speed, rating, Cp/Ct)"
_AIR_SOURCE = "the site air density at hub height from the design basis"
_PRODUCTION_SOURCE = "the turbine's metered production record for the period"


class _WindPowerInputError(RefusalError, ValueError):
    """A wind-turbine power input that cannot be used without correction."""


def _wind_power_refusal(message: str, *, subject: str, source: str) -> _WindPowerInputError:
    return _WindPowerInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _wind_power_input_source(name: str) -> str:
    if name in {
        "reference_height",
        "reference_speed",
        "shear_exponent",
        "target_height",
        "wind_speed",
    }:
        return _SITE_SOURCE
    if name == "air_density":
        return _AIR_SOURCE
    if name in {"energy_produced", "period"}:
        return _PRODUCTION_SOURCE
    return _TURBINE_SOURCE


__all__ = [
    "BETZ_LIMIT",
    "actuator_disc_power_coefficient",
    "actuator_disc_thrust_coefficient",
    "wind_power_density",
    "wind_turbine_rotor_thrust",
    "wind_shear_speed",
    "wind_turbine_power",
    "wind_turbine_tip_speed_ratio",
    "capacity_factor",
]

BETZ_LIMIT = 16.0 / 27.0  # ≈ 0.593, the maximum fraction of wind power any turbine can extract


def wind_shear_speed(
    *,
    reference_speed: Quantity,
    reference_height: Quantity,
    target_height: Quantity,
    shear_exponent: float = 0.14,
) -> Quantity:
    """The wind speed at hub height from a lower measurement, V₂ = V₁·(h₂/h₁)^α.

    Wind resource is measured on a met mast tens of metres up and the turbine runs a hundred metres
    up, so every number in this module starts with a speed that has to be carried to hub height
    first. The power-law (Hellmann) profile does it: V₂ = ``reference_speed``·(``target_height``/
    ``reference_height``)^``shear_exponent``, with α ≈ 0.14 (the "1/7 power law") over open terrain,
    ~0.10 over water, and 0.25 or more over forest and built-up ground, where surface roughness
    drags the lower air back hardest. Because power goes as V³, a modest shear gain is a large
    energy gain — which is the whole argument for taller towers. Returns the wind speed at the
    target height in m/s.
    """
    _check(reference_speed, "[length]/[time]", "reference_speed")
    _check(reference_height, "[length]", "reference_height")
    _check(target_height, "[length]", "target_height")
    # A NaN exponent passes every comparison, and `base ** nan` is exactly 1.0 when the
    # base is 1.0 — so the NaN vanishes instead of propagating and the result reads as
    # an ordinary answer.
    require_finite(shear_exponent, name="shear_exponent")
    v1 = reference_speed.to("m/s").magnitude
    h1 = reference_height.to("m").magnitude
    h2 = target_height.to("m").magnitude
    if v1 < 0:
        raise _wind_power_refusal(
            "reference_speed must be non-negative", subject="reference_speed", source=_SITE_SOURCE
        )
    for subject, magnitude in (("reference_height", h1), ("target_height", h2)):
        if magnitude <= 0:
            raise _wind_power_refusal(
                "reference_height and target_height must be positive",
                subject=subject,
                source=_SITE_SOURCE,
            )
    if shear_exponent < 0:
        raise _wind_power_refusal(
            "shear_exponent must be non-negative", subject="shear_exponent", source=_SITE_SOURCE
        )
    return Quantity(magnitude=v1 * (h2 / h1) ** shear_exponent, unit="m/s")


def wind_power_density(*, air_density: Quantity, wind_speed: Quantity) -> Quantity:
    """The kinetic power per unit area in the wind, P/A = ½·ρ·V³.

    The power crossing a unit area facing the wind, from the ``air_density`` ρ and the
    ``wind_speed`` V: P/A = ½·ρ·V³. Because it goes as the cube of speed, a turbine's output is far
    more sensitive to where it sits than to how big it is — doubling the wind speed lifts the power
    eightfold. Returns the power density in W/m².
    """
    _check(air_density, "[mass]/[length]**3", "air_density")
    _check(wind_speed, "[length]/[time]", "wind_speed")
    rho = air_density.to("kg/m**3").magnitude
    v = wind_speed.to("m/s").magnitude
    if rho <= 0:
        raise _wind_power_refusal(
            "air_density must be positive", subject="air_density", source=_AIR_SOURCE
        )
    if v < 0:
        raise _wind_power_refusal(
            "wind_speed must be non-negative", subject="wind_speed", source=_SITE_SOURCE
        )
    return Quantity(magnitude=0.5 * rho * v**3, unit="W/m**2")


def wind_turbine_power(
    *,
    air_density: Quantity,
    rotor_diameter: Quantity,
    wind_speed: Quantity,
    power_coefficient: float,
) -> Quantity:
    """The electrical power a wind turbine produces, P = ½·ρ·A·V³·C_p.

    The rotor of ``rotor_diameter`` D sweeps an area A = π·D²/4 and extracts a fraction
    ``power_coefficient`` C_p of the wind power crossing it: P = ½·ρ·A·V³·C_p, from the
    ``air_density`` ρ and the ``wind_speed`` V. C_p is the caller's from the turbine's curve and
    cannot exceed the Betz limit :data:`BETZ_LIMIT` (16/27) — the aerodynamic ceiling; real rotors
    reach ~0.35–0.45. Returns the power in watts.
    """
    require_finite(power_coefficient, name="power_coefficient")
    _check(air_density, "[mass]/[length]**3", "air_density")
    _check(rotor_diameter, "[length]", "rotor_diameter")
    _check(wind_speed, "[length]/[time]", "wind_speed")
    rho = air_density.to("kg/m**3").magnitude
    d = rotor_diameter.to("m").magnitude
    v = wind_speed.to("m/s").magnitude
    for subject, magnitude in (("air_density", rho), ("rotor_diameter", d)):
        if magnitude <= 0:
            raise _wind_power_refusal(
                "air_density and rotor_diameter must be positive",
                subject=subject,
                source=_wind_power_input_source(subject),
            )
    if v < 0:
        raise _wind_power_refusal(
            "wind_speed must be non-negative", subject="wind_speed", source=_SITE_SOURCE
        )
    if not 0.0 < power_coefficient <= BETZ_LIMIT:
        raise _wind_power_refusal(
            f"power_coefficient must be in (0, {BETZ_LIMIT:.4f}] (the Betz limit)",
            subject="power_coefficient",
            source=_TURBINE_SOURCE,
        )
    area = pi * d**2 / 4.0
    return Quantity(magnitude=0.5 * rho * area * v**3 * power_coefficient, unit="W")


def wind_turbine_tip_speed_ratio(
    *,
    rotor_speed: Quantity,
    rotor_radius: Quantity,
    wind_speed: Quantity,
) -> float:
    """The tip speed ratio of a wind turbine, λ = ω·R/V.

    The single most important aerodynamic parameter of a rotor: how fast the blade *tips* move
    compared to the wind, λ = ``rotor_speed``·``rotor_radius``/``wind_speed``. Every rotor has an
    optimal tip speed ratio where it extracts the most power — around 6–8 for a modern three-blade
    turbine, lower for many-bladed water pumpers. Turn too slowly (low λ) and wind slips between the
    blades untouched; too fast (high λ) and the blades stall each other in turbulence. A
    variable-speed turbine holds λ near its optimum by tracking the wind. ``rotor_speed`` is an
    angular rate (rpm or rad/s). Returns the dimensionless tip speed ratio.
    """
    _check(rotor_speed, "1/[time]", "rotor_speed")
    _check(rotor_radius, "[length]", "rotor_radius")
    _check(wind_speed, "[length]/[time]", "wind_speed")
    omega = angular_speed_rad_per_s(rotor_speed, name="rotor_speed")
    r = rotor_radius.to("m").magnitude
    v = wind_speed.to("m/s").magnitude
    for subject, magnitude in (("rotor_speed", omega), ("rotor_radius", r), ("wind_speed", v)):
        if magnitude <= 0:
            raise _wind_power_refusal(
                "rotor_speed, rotor_radius, and wind_speed must be positive",
                subject=subject,
                source=_wind_power_input_source(subject),
            )
    return omega * r / v


def capacity_factor(
    *,
    energy_produced: Quantity,
    rated_power: Quantity,
    period: Quantity,
) -> float:
    """The capacity factor, CF = E/(P_rated·t).

    The fraction of its nameplate a generator actually delivers over time: the ``energy_produced`` E
    divided by what it would have made running flat out at its ``rated_power`` P for the whole
    ``period`` t, CF = E/(P·t). It rolls the intermittency and the derating into one number —
    onshore wind runs around 0.35, offshore 0.45–0.55, rooftop solar 0.15–0.25, a baseload plant
    above 0.9. It is the honest way to compare an intermittent renewable against firm capacity.
    Returns the dimensionless capacity factor (0 to 1).
    """
    _check(energy_produced, "[energy]", "energy_produced")
    _check(rated_power, "[power]", "rated_power")
    _check(period, "[time]", "period")
    e = energy_produced.to("J").magnitude
    p = rated_power.to("W").magnitude
    t = period.to("s").magnitude
    if e < 0 or p <= 0 or t <= 0:
        raise _wind_power_refusal(
            "rated_power and period must be positive, energy non-negative",
            subject="energy_produced, rated_power, and period",
            source=_PRODUCTION_SOURCE,
        )
    cf = e / (p * t)
    # Exactly the rated output, converted from other energy units, lands a few parts in
    # 1e16 past 1; within rounding it is a capacity factor of one, not an impossibility.
    if 1.0 < cf <= 1.0 + 1e-9:
        cf = 1.0
    if cf > 1.0:
        raise _wind_power_refusal(
            "energy_produced exceeds the rated output for the period (CF > 1)",
            subject="energy_produced, rated_power, and period",
            source=_PRODUCTION_SOURCE,
        )
    return cf


def actuator_disc_power_coefficient(*, axial_induction_factor: float) -> float:
    """The actuator-disc power coefficient, C_P = 4a(1 − a)².

    The module states Betz's law in prose and takes the cap on faith; this derives it. A turbine
    slows the air passing through it, and the ``axial_induction_factor`` a is the fraction of the
    freestream speed it removes at the disc. Extracting more per unit of air (larger a) means
    passing less air (the flow spreads and slows), so the product has an interior maximum.

    Differentiating gives a = 1/3, where C_P = 16/27 — the module's own :data:`BETZ_LIMIT`,
    recovered rather than asserted. a is a plain float in [0, 0.5]; above 0.5 the one-dimensional
    momentum theory predicts reversed flow in the wake and stops being valid. Returns the power
    coefficient as a plain float.
    """
    require_finite(axial_induction_factor, name="axial_induction_factor")
    a = axial_induction_factor
    if not 0.0 <= a <= 0.5:
        raise _wind_power_refusal(
            f"axial_induction_factor must lie in [0, 0.5]; above 0.5 momentum theory predicts a "
            f"reversed wake and no longer holds. Got {a}",
            subject="axial_induction_factor",
            source=_TURBINE_SOURCE,
        )
    return 4.0 * a * (1.0 - a) ** 2


def actuator_disc_thrust_coefficient(*, axial_induction_factor: float) -> float:
    """The actuator-disc thrust coefficient, C_T = 4a(1 − a).

    The load that comes with the power of :func:`actuator_disc_power_coefficient`. Unlike C_P,
    C_T does not peak inside the valid range — it climbs to 1.0 at a = 0.5 — so the operating
    point that maximises power is not the one that maximises load. At the Betz point a = 1/3 the
    thrust coefficient is 8/9 ≈ 0.889, which is why a rotor tuned for peak energy capture still
    pushes on its tower with nearly the full stagnation load. Returns a plain float.
    """
    require_finite(axial_induction_factor, name="axial_induction_factor")
    a = axial_induction_factor
    if not 0.0 <= a <= 0.5:
        raise _wind_power_refusal(
            f"axial_induction_factor must lie in [0, 0.5]; got {a}",
            subject="axial_induction_factor",
            source=_TURBINE_SOURCE,
        )
    return 4.0 * a * (1.0 - a)


def wind_turbine_rotor_thrust(
    *,
    air_density: Quantity,
    rotor_diameter: Quantity,
    wind_speed: Quantity,
    thrust_coefficient: float,
) -> Quantity:
    """The axial thrust on the rotor, T = ½·ρ·A·V²·C_T with A = π·D²/4.

    The module computed the power a rotor takes from the wind but not the *load* it carries doing
    it — and the load is what sizes the tower and the foundation, not the power. The rotor is a
    drag device as much as a lift device: it pushes downwind with a force set by the swept area
    and the square of the wind speed.

    A 100 m rotor at 12 m/s with C_T = 0.80 (see
    :func:`actuator_disc_thrust_coefficient`) carries 554 kN — at a 90 m hub that is 49.9 MN·m of
    overturning moment, which is the governing case for the structure and was unreachable from
    this module before. Note the thrust goes as V², not the V³ of the power, so the loads and the
    energy do not scale together: the survival case is a parked rotor in a storm, where there is
    no power at all. Returns the thrust in kN.
    """
    require_finite(thrust_coefficient, name="thrust_coefficient")
    _check(air_density, "[mass]/[length]**3", "air_density")
    _check(rotor_diameter, "[length]", "rotor_diameter")
    _check(wind_speed, "[length]/[time]", "wind_speed")
    rho = air_density.to("kg/m**3").magnitude
    d = rotor_diameter.to("m").magnitude
    v = wind_speed.to("m/s").magnitude
    if rho <= 0:
        raise _wind_power_refusal(
            f"air_density must be positive; got {air_density}",
            subject="air_density",
            source=_AIR_SOURCE,
        )
    if d <= 0:
        raise _wind_power_refusal(
            f"rotor_diameter must be positive; got {rotor_diameter}",
            subject="rotor_diameter",
            source=_TURBINE_SOURCE,
        )
    if v < 0:
        raise _wind_power_refusal(
            f"wind_speed must be non-negative; got {wind_speed}",
            subject="wind_speed",
            source=_SITE_SOURCE,
        )
    if not 0.0 <= thrust_coefficient <= 1.0:
        raise _wind_power_refusal(
            f"thrust_coefficient must lie in [0, 1]; got {thrust_coefficient}",
            subject="thrust_coefficient",
            source=_TURBINE_SOURCE,
        )
    area = pi * d * d / 4.0
    return Quantity(magnitude=0.5 * rho * area * v * v * thrust_coefficient / 1000.0, unit="kN")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _wind_power_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_wind_power_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _wind_power_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_wind_power_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
