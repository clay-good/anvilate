"""T1 analytical compressible-flow checks (gas dynamics basics, closed-form).

Once a gas moves fast enough that its density changes appreciably — a compressor blade tip, a relief
valve, a gas pipeline, a nozzle — the incompressible relations stop applying and the yardstick
becomes the Mach number, the flow speed over the local speed of sound. The speed of sound in an
ideal gas is a = √(γ·R·T), so it depends only on the temperature and the gas (about 340 m/s in air
at room temperature). A flow is subsonic below M = 1 and supersonic above it, and the character of
the flow changes completely at M = 1.

Bringing a moving gas to rest recovers its kinetic energy as heat and pressure, raising it to the
*stagnation* condition — the temperature at a probe tip or a closed end is higher than the moving
stream's by the factor T₀/T = 1 + (γ−1)/2·M². That rise is negligible at low Mach but large near
sonic, and it is why high-speed compressor and turbine parts run hot. The specific-heat ratio γ and
the gas constant R are properties the caller supplies. Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.

Sources: Shapiro, *The Dynamics and Thermodynamics of Compressible Fluid
Flow*, and NACA Report 1135 for the isentropic and normal-shock relations; Cengel &
Cimbala, *Fluid Mechanics*, for the nozzle and choked-flow forms.
"""

from __future__ import annotations

from math import asin, atan, degrees, sqrt

from ..units import Quantity
from ..units.temperature import temperature_difference_kelvin

__all__ = [
    "choked_mass_flow_rate",
    "critical_pressure_ratio",
    "eckert_number",
    "isentropic_area_ratio",
    "mach_angle",
    "mach_number",
    "maximum_turning_angle",
    "normal_shock_downstream_mach",
    "normal_shock_pressure_ratio",
    "normal_shock_temperature_ratio",
    "normal_shock_density_ratio",
    "normal_shock_stagnation_pressure_ratio",
    "prandtl_meyer_angle",
    "speed_of_sound",
    "stagnation_density_ratio",
    "stagnation_pressure_ratio",
    "stagnation_temperature_ratio",
]


def speed_of_sound(
    *,
    temperature: Quantity,
    heat_capacity_ratio: float,
    specific_gas_constant: Quantity,
) -> Quantity:
    """The speed of sound in an ideal gas, a = √(γ·R·T).

    How fast a small pressure disturbance travels through the gas, which sets the yardstick for
    every compressible-flow effect: a = √(γ·R·T), from the absolute ``temperature`` T, the
    ``heat_capacity_ratio`` γ (~1.4 for air), and the ``specific_gas_constant`` R (287 J/(kg·K) for
    air). It rises with the square root of temperature and does not depend on pressure. Returns the
    speed of sound in m/s.
    """
    _check(temperature, "[temperature]", "temperature")
    _check(specific_gas_constant, "[length]**2/[time]**2/[temperature]", "specific_gas_constant")
    t = temperature.to("K").magnitude
    r = specific_gas_constant.to("J/(kg*K)").magnitude
    if t <= 0 or r <= 0:
        raise ValueError("temperature and specific_gas_constant must be positive")
    if heat_capacity_ratio <= 1.0:
        raise ValueError(f"heat_capacity_ratio must exceed 1; got {heat_capacity_ratio}")
    return Quantity(magnitude=sqrt(heat_capacity_ratio * r * t), unit="m/s")


def mach_number(*, velocity: Quantity, speed_of_sound: Quantity) -> float:
    """The Mach number M = V/a, the ratio of flow speed to the speed of sound.

    The single number that classifies compressible flow: M = V/a, from the flow ``velocity`` V and
    the local ``speed_of_sound`` a (from :func:`speed_of_sound`). Below 1 the flow is subsonic and
    disturbances travel upstream; above 1 it is supersonic and they cannot; at exactly 1 it is
    sonic (choked). Below about 0.3 the gas behaves as if incompressible. Returns the dimensionless
    Mach number.
    """
    _check(velocity, "[length]/[time]", "velocity")
    _check(speed_of_sound, "[length]/[time]", "speed_of_sound")
    v = velocity.to("m/s").magnitude
    a = speed_of_sound.to("m/s").magnitude
    if v < 0:
        raise ValueError("velocity must be non-negative")
    if a <= 0:
        raise ValueError("speed_of_sound must be positive")
    return v / a


def eckert_number(
    *, velocity: Quantity, specific_heat: Quantity, temperature_difference: Quantity
) -> float:
    """The Eckert number, Ec = V²/(c_p·ΔT).

    The ratio of a flow's kinetic energy to its thermal enthalpy difference: from the ``velocity``
    V, the ``specific_heat`` c_p, and the wall-to-stream ``temperature_difference`` ΔT,
    Ec = V²/(c_p·ΔT). It measures how much viscous dissipation and kinetic heating matter in a
    boundary layer — negligible at low speed but important in high-speed (compressible) flow, where
    aerodynamic heating warms a re-entry body or a fast turbine blade. Related to the Brinkman
    number by Br = Ec·Pr. Returns the dimensionless Eckert number.
    """
    _check(velocity, "[length]/[time]", "velocity")
    _check(specific_heat, "[energy]/[mass]/[temperature]", "specific_heat")
    _check(temperature_difference, "[temperature]", "temperature_difference")
    v = velocity.to("m/s").magnitude
    cp = specific_heat.to("J/(kg*K)").magnitude
    dt = temperature_difference_kelvin(temperature_difference, name="temperature_difference")
    if v < 0:
        raise ValueError("velocity must be non-negative")
    if cp <= 0:
        raise ValueError("specific_heat must be positive")
    if dt <= 0:
        raise ValueError("temperature_difference must be positive")
    return v * v / (cp * dt)


def stagnation_temperature_ratio(*, mach_number: float, heat_capacity_ratio: float) -> float:
    """The stagnation-to-static temperature ratio, T₀/T = 1 + (γ−1)/2·M².

    Bringing a moving gas to rest converts its kinetic energy into a temperature rise, and the
    ratio of the stagnation (total) temperature to the static (stream) temperature is
    T₀/T = 1 + (γ−1)/2·M², from the ``mach_number`` M and ``heat_capacity_ratio`` γ. Negligible at
    low Mach, it climbs steeply toward sonic — which is why the leading edges and closed ends of
    high-speed gas machinery run so much hotter than the free stream. Returns the dimensionless
    ratio T₀/T (≥ 1).
    """
    if mach_number < 0:
        raise ValueError(f"mach_number must be non-negative; got {mach_number}")
    if heat_capacity_ratio <= 1.0:
        raise ValueError(f"heat_capacity_ratio must exceed 1; got {heat_capacity_ratio}")
    return 1.0 + (heat_capacity_ratio - 1.0) / 2.0 * mach_number**2


def stagnation_pressure_ratio(*, mach_number: float, heat_capacity_ratio: float) -> float:
    """The stagnation-to-static pressure ratio, p₀/p = (1 + (γ−1)/2·M²)^(γ/(γ−1)).

    Bringing a compressible stream isentropically to rest raises its pressure by
    p₀/p = (1 + (γ−1)/2·M²)^(γ/(γ−1)), from the ``mach_number`` M and ``heat_capacity_ratio`` γ —
    the temperature ratio raised to γ/(γ−1). It is what a Pitot tube reads in high-speed flow (the
    incompressible ½·ρ·V² form undercounts badly past about Mach 0.3), and the total-to-static ratio
    a nozzle or inlet is designed around. Returns the dimensionless ratio p₀/p (≥ 1).
    """
    temperature_ratio = stagnation_temperature_ratio(
        mach_number=mach_number, heat_capacity_ratio=heat_capacity_ratio
    )
    return temperature_ratio ** (heat_capacity_ratio / (heat_capacity_ratio - 1.0))


def stagnation_density_ratio(*, mach_number: float, heat_capacity_ratio: float) -> float:
    """The stagnation-to-static density ratio, ρ₀/ρ = (1 + (γ−1)/2·M²)^(1/(γ−1)).

    The density rise of a compressible stream brought isentropically to rest,
    ρ₀/ρ = (1 + (γ−1)/2·M²)^(1/(γ−1)), from the ``mach_number`` M and ``heat_capacity_ratio`` γ —
    the temperature ratio raised to 1/(γ−1). With the pressure and temperature ratios it completes
    isentropic set (and is consistent with them through the ideal-gas law, p₀/p = (ρ₀/ρ)·(T₀/T)).
    Returns the dimensionless ratio ρ₀/ρ (≥ 1).
    """
    temperature_ratio = stagnation_temperature_ratio(
        mach_number=mach_number, heat_capacity_ratio=heat_capacity_ratio
    )
    return temperature_ratio ** (1.0 / (heat_capacity_ratio - 1.0))


def isentropic_area_ratio(*, mach_number: float, heat_capacity_ratio: float) -> float:
    """The isentropic nozzle area ratio A/A* (the converging-diverging area-Mach relation).

    A converging-diverging nozzle reaches a given ``mach_number`` M only at a definite area relative
    to its sonic throat: A/A* = (1/M)·[(2/(γ+1))·(1 + (γ−1)/2·M²)]^((γ+1)/(2(γ−1))), from M and the
    ``heat_capacity_ratio`` γ. The ratio is 1 at the throat (M = 1) and rises on *both* sides — a
    subsonic and a supersonic Mach share each area ratio — so the divergent bell sets the exit Mach,
    which is why a rocket nozzle must be matched to its altitude. Returns the dimensionless area
    ratio A/A* (≥ 1).
    """
    if mach_number <= 0:
        raise ValueError(f"mach_number must be positive; got {mach_number}")
    if heat_capacity_ratio <= 1.0:
        raise ValueError(f"heat_capacity_ratio must exceed 1; got {heat_capacity_ratio}")
    g = heat_capacity_ratio
    bracket = (2.0 / (g + 1.0)) * (1.0 + (g - 1.0) / 2.0 * mach_number**2)
    exponent = (g + 1.0) / (2.0 * (g - 1.0))
    return bracket**exponent / mach_number


def critical_pressure_ratio(*, heat_capacity_ratio: float) -> float:
    """The critical (choking) pressure ratio, p*/p₀ = (2/(γ+1))^(γ/(γ−1)).

    The downstream-to-upstream pressure ratio at which a gas flowing through a restriction reaches
    Mach 1 and chokes: p*/p₀ = (2/(γ+1))^(γ/(γ−1)), a function only of ``heat_capacity_ratio`` γ.
    For air it is the famous 0.528 — drop the downstream pressure below 52.8% of the upstream and
    the flow can go no faster, no matter how much further the pressure falls. Below this ratio the
    flow is choked (see :func:`choked_mass_flow_rate`). Returns the dimensionless pressure ratio.
    """
    if heat_capacity_ratio <= 1.0:
        raise ValueError(f"heat_capacity_ratio must exceed 1; got {heat_capacity_ratio}")
    g = heat_capacity_ratio
    return (2.0 / (g + 1.0)) ** (g / (g - 1.0))


def choked_mass_flow_rate(
    *,
    stagnation_pressure: Quantity,
    stagnation_temperature: Quantity,
    orifice_area: Quantity,
    discharge_coefficient: float,
    heat_capacity_ratio: float,
    specific_gas_constant: Quantity,
) -> Quantity:
    """The maximum (choked) gas mass flow through a restriction — the relief-valve sizing form.

    Once a gas is choked (downstream pressure below :func:`critical_pressure_ratio`), the mass flow
    hits a ceiling set only by the upstream conditions and cannot be increased by lowering the
    downstream pressure further: ṁ = C_d·A·p₀·√(γ/(R·T₀))·(2/(γ+1))^((γ+1)/(2(γ−1))). This is the
    worst-case discharge a safety or relief valve must pass. ``stagnation_pressure`` p₀ and
    ``stagnation_temperature`` T₀ are the upstream (vessel) conditions, ``orifice_area`` A the flow
    area, ``discharge_coefficient`` C_d (~0.85 for a nozzle), and ``heat_capacity_ratio`` γ /
    ``specific_gas_constant`` R the gas properties. Returns the choked mass flow in kg/s.
    """
    _check(stagnation_pressure, "[pressure]", "stagnation_pressure")
    _check(stagnation_temperature, "[temperature]", "stagnation_temperature")
    _check(orifice_area, "[area]", "orifice_area")
    _check(specific_gas_constant, "[length]**2/[time]**2/[temperature]", "specific_gas_constant")
    p0 = stagnation_pressure.to("Pa").magnitude
    t0 = stagnation_temperature.to("K").magnitude
    a = orifice_area.to("m**2").magnitude
    r = specific_gas_constant.to("J/(kg*K)").magnitude
    if p0 <= 0 or t0 <= 0 or a <= 0 or r <= 0:
        raise ValueError("pressure, temperature, area, and gas constant must be positive")
    if not 0.0 < discharge_coefficient <= 1.0:
        raise ValueError(f"discharge_coefficient must be in (0, 1]; got {discharge_coefficient}")
    if heat_capacity_ratio <= 1.0:
        raise ValueError(f"heat_capacity_ratio must exceed 1; got {heat_capacity_ratio}")
    g = heat_capacity_ratio
    flux = p0 * sqrt(g / (r * t0)) * (2.0 / (g + 1.0)) ** ((g + 1.0) / (2.0 * (g - 1.0)))
    return Quantity(magnitude=discharge_coefficient * a * flux, unit="kg/s")


def _require_supersonic(upstream_mach: float) -> None:
    if upstream_mach <= 1.0:
        raise ValueError(f"upstream_mach must exceed 1 (a shock needs M > 1); got {upstream_mach}")


def normal_shock_downstream_mach(*, upstream_mach: float, heat_capacity_ratio: float) -> float:
    """The Mach number behind a normal shock, M₂² = ((γ−1)M₁² + 2)/(2γM₁² − (γ−1)).

    A normal shock decelerates a supersonic stream abruptly to subsonic: from the ``upstream_mach``
    M₁ (which must exceed 1) and the ``heat_capacity_ratio`` γ, the downstream Mach is
    M₂ = √[((γ−1)M₁² + 2)/(2γM₁² − (γ−1))]. The result is always below 1 — the flow behind any
    normal shock is subsonic — and it falls as the incoming Mach rises. Returns the downstream Mach
    number (dimensionless).
    """
    if heat_capacity_ratio <= 1.0:
        raise ValueError(f"heat_capacity_ratio must exceed 1; got {heat_capacity_ratio}")
    _require_supersonic(upstream_mach)
    g = heat_capacity_ratio
    m1_sq = upstream_mach * upstream_mach
    m2_sq = ((g - 1.0) * m1_sq + 2.0) / (2.0 * g * m1_sq - (g - 1.0))
    return sqrt(m2_sq)


def normal_shock_pressure_ratio(*, upstream_mach: float, heat_capacity_ratio: float) -> float:
    """The static pressure jump across a normal shock, p₂/p₁ = (2γM₁² − (γ−1))/(γ+1).

    The pressure rises discontinuously across a normal shock: from the ``upstream_mach`` M₁ (> 1)
    and the ``heat_capacity_ratio`` γ, p₂/p₁ = (2γM₁² − (γ−1))/(γ+1). It grows without bound as M₁
    rises —
    a Mach-2 shock in air multiplies the static pressure by 4.5 — which is why supersonic inlets and
    blast waves develop such steep pressure fronts. Returns the pressure ratio (dimensionless, > 1).
    """
    if heat_capacity_ratio <= 1.0:
        raise ValueError(f"heat_capacity_ratio must exceed 1; got {heat_capacity_ratio}")
    _require_supersonic(upstream_mach)
    g = heat_capacity_ratio
    m1_sq = upstream_mach * upstream_mach
    return (2.0 * g * m1_sq - (g - 1.0)) / (g + 1.0)


def normal_shock_temperature_ratio(*, upstream_mach: float, heat_capacity_ratio: float) -> float:
    """The static temperature jump across a normal shock, T₂/T₁.

    The gas heats as it crosses a normal shock, converting kinetic energy to thermal: from the
    ``upstream_mach`` M₁ (> 1) and the ``heat_capacity_ratio`` γ,
    T₂/T₁ = (2γM₁² − (γ−1))·(2 + (γ−1)M₁²)/((γ+1)²·M₁²) — equivalently the pressure ratio
    (:func:`normal_shock_pressure_ratio`) divided by the density ratio
    (:func:`normal_shock_density_ratio`) through the ideal-gas law. A Mach-2 shock in air raises the
    static temperature by ~69 %, the aero-heating that punishes supersonic leading edges. Returns
    the temperature ratio (dimensionless, > 1).
    """
    if heat_capacity_ratio <= 1.0:
        raise ValueError(f"heat_capacity_ratio must exceed 1; got {heat_capacity_ratio}")
    _require_supersonic(upstream_mach)
    g = heat_capacity_ratio
    m1_sq = upstream_mach * upstream_mach
    return (2.0 * g * m1_sq - (g - 1.0)) * (2.0 + (g - 1.0) * m1_sq) / ((g + 1.0) ** 2 * m1_sq)


def normal_shock_density_ratio(*, upstream_mach: float, heat_capacity_ratio: float) -> float:
    """The density jump across a normal shock, ρ₂/ρ₁ = (γ+1)M₁²/((γ−1)M₁² + 2).

    The gas compresses across a normal shock: from the ``upstream_mach`` M₁ (> 1) and the
    ``heat_capacity_ratio`` γ, ρ₂/ρ₁ = (γ+1)M₁²/((γ−1)M₁² + 2). Unlike the pressure and temperature
    ratios it does *not* grow without bound — it approaches a hard ceiling of (γ+1)/(γ−1) = 6 for
    air however strong the shock, because a gas can only be squeezed so far. By continuity this is
    the velocity drop u₁/u₂ across the shock. Returns the density ratio (dimensionless, > 1).
    """
    if heat_capacity_ratio <= 1.0:
        raise ValueError(f"heat_capacity_ratio must exceed 1; got {heat_capacity_ratio}")
    _require_supersonic(upstream_mach)
    g = heat_capacity_ratio
    m1_sq = upstream_mach * upstream_mach
    return (g + 1.0) * m1_sq / ((g - 1.0) * m1_sq + 2.0)


def normal_shock_stagnation_pressure_ratio(
    *, upstream_mach: float, heat_capacity_ratio: float
) -> float:
    """The stagnation-pressure recovery across a normal shock, p₀₂/p₀₁.

    A normal shock is irreversible, so it destroys stagnation (total) pressure even as static
    pressure jumps: from the ``upstream_mach`` M₁ (> 1) and the ``heat_capacity_ratio`` γ,
    p₀₂/p₀₁ = [((γ+1)M₁²/2)/(1 + (γ−1)/2·M₁²)]^(γ/(γ−1))·[(γ+1)/(2γM₁² − (γ−1))]^(1/(γ−1)). It
    is 1 at M₁ = 1 and falls steadily as the shock strengthens (about 0.72 at Mach 2) — the loss a
    supersonic inlet pays and the reason strong shocks are avoided. Returns the total-pressure ratio
    (dimensionless, 0 to 1).
    """
    if heat_capacity_ratio <= 1.0:
        raise ValueError(f"heat_capacity_ratio must exceed 1; got {heat_capacity_ratio}")
    _require_supersonic(upstream_mach)
    g = heat_capacity_ratio
    m1_sq = upstream_mach * upstream_mach
    term1 = (((g + 1.0) * m1_sq / 2.0) / (1.0 + (g - 1.0) / 2.0 * m1_sq)) ** (g / (g - 1.0))
    term2 = ((g + 1.0) / (2.0 * g * m1_sq - (g - 1.0))) ** (1.0 / (g - 1.0))
    return term1 * term2


def prandtl_meyer_angle(*, mach_number: float, heat_capacity_ratio: float) -> Quantity:
    """The Prandtl-Meyer angle, ν(M), of a supersonic expansion fan.

    The angle through which a supersonic flow turns as it expands isentropically from M = 1 (where
    ν = 0) to the ``mach_number`` M, from the ``heat_capacity_ratio`` γ:
    ν = √((γ+1)/(γ−1))·atan(√((γ−1)/(γ+1)·(M²−1))) − atan(√(M²−1)). Turning a supersonic stream
    around a convex corner by an angle Δθ raises its Mach number so that ν grows by Δθ. Returns the
    Prandtl-Meyer angle in degrees.
    """
    if mach_number < 1.0:
        raise ValueError(f"mach_number must be at least 1 (supersonic); got {mach_number}")
    if heat_capacity_ratio <= 1.0:
        raise ValueError(f"heat_capacity_ratio must exceed 1; got {heat_capacity_ratio}")
    g = heat_capacity_ratio
    m2 = mach_number * mach_number - 1.0
    ratio = (g + 1.0) / (g - 1.0)
    nu = sqrt(ratio) * atan(sqrt(m2 / ratio)) - atan(sqrt(m2))
    return Quantity(magnitude=degrees(nu), unit="degree")


def mach_angle(*, mach_number: float) -> Quantity:
    """The Mach angle, µ = asin(1/M), of a supersonic disturbance.

    The half-angle of the Mach cone (or the inclination of a Mach line) trailing a body moving at
    the ``mach_number`` M through a compressible medium: µ = asin(1/M). At M = 1 the cone opens to
    90°; as M rises the cone tightens around the flight path. Returns the Mach angle in degrees.
    """
    if mach_number < 1.0:
        raise ValueError(f"mach_number must be at least 1 (supersonic); got {mach_number}")
    return Quantity(magnitude=degrees(asin(1.0 / mach_number)), unit="degree")


def maximum_turning_angle(*, heat_capacity_ratio: float) -> Quantity:
    """The maximum Prandtl-Meyer turning angle, ν(∞) = (π/2)·(√((γ+1)/(γ−1)) − 1).

    The greatest angle through which a supersonic flow can turn by expansion, reached in the limit
    M → ∞, from the ``heat_capacity_ratio`` γ: ν_max = (π/2)·(√((γ+1)/(γ−1)) − 1) — about 130.5°
    for air (γ = 1.4). A convex turn steeper than this cannot be negotiated by an attached
    expansion; the flow separates into a vacuum. Returns the maximum turning angle in degrees.
    """
    if heat_capacity_ratio <= 1.0:
        raise ValueError(f"heat_capacity_ratio must exceed 1; got {heat_capacity_ratio}")
    ratio = (heat_capacity_ratio + 1.0) / (heat_capacity_ratio - 1.0)
    return Quantity(magnitude=90.0 * (sqrt(ratio) - 1.0), unit="degree")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
