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
    "mach_number",
    "speed_of_sound",
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


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
