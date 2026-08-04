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
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

__all__ = [
    "choked_mass_flow_rate",
    "critical_pressure_ratio",
    "isentropic_area_ratio",
    "mach_number",
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


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
