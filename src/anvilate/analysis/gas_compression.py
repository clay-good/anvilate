"""T1 analytical gas-compression checks (compressor power and discharge, closed-form).

Compressing a gas is the pneumatic analog of pumping a liquid, but a gas heats and shrinks as
it is squeezed, so the work depends on *how* it is compressed. Two idealizations bracket the
real machine. If the gas is cooled continuously so its temperature never rises (isothermal), the
power is the gentlest possible, P = p₁·Q₁·ln(r) for a pressure ratio r = p₂/p₁. If it is
compressed fast with no heat removed (adiabatic/isentropic), the gas heats up and the work is
higher, P = [k/(k−1)]·p₁·Q₁·[r^((k−1)/k) − 1], where k is the ratio of specific heats (~1.4 for
air). A real compressor sits between the two; the adiabatic case also sets how hot the discharge
runs, T₂ = T₁·r^((k−1)/k) — the number that decides intercooling and lubricant choice.

The gas's own density follows the ideal-gas law, ρ = p/(R·T), from the specific gas constant R.
The gas constant R and the specific-heat ratio k are properties the caller supplies. Inputs and
outputs are dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "adiabatic_compression_power",
    "adiabatic_discharge_temperature",
    "ideal_gas_density",
    "isothermal_compression_power",
]


def ideal_gas_density(
    *,
    pressure: Quantity,
    temperature: Quantity,
    specific_gas_constant: Quantity,
) -> Quantity:
    """The density of an ideal gas, ρ = p/(R·T).

    The mass per unit volume a gas holds at a given state: ρ = p/(R·T) from the absolute
    ``pressure`` p, the absolute ``temperature`` T, and the gas's ``specific_gas_constant`` R
    (287 J/(kg·K) for air). Returns the density in kg/m³.
    """
    _check(pressure, "[pressure]", "pressure")
    _check(temperature, "[temperature]", "temperature")
    _check(specific_gas_constant, "[length]**2/[time]**2/[temperature]", "specific_gas_constant")
    p = pressure.to("Pa").magnitude
    t = temperature.to("K").magnitude
    r = specific_gas_constant.to("J/(kg*K)").magnitude
    if p <= 0 or t <= 0 or r <= 0:
        raise ValueError("pressure, temperature, and specific_gas_constant must be positive")
    return Quantity(magnitude=p / (r * t), unit="kg/m**3")


def isothermal_compression_power(
    *,
    volumetric_flow: Quantity,
    inlet_pressure: Quantity,
    pressure_ratio: float,
) -> Quantity:
    """The ideal isothermal compression power, P = p₁·Q₁·ln(r).

    The least power a compressor could take, reached only if the gas were cooled enough to stay at
    constant temperature: P = p₁·Q₁·ln(r). ``volumetric_flow`` Q₁ is the inlet (suction) volume
    flow, ``inlet_pressure`` p₁ the absolute suction pressure, and ``pressure_ratio`` r = p₂/p₁ the
    compression ratio. A real machine always takes more (see
    :func:`adiabatic_compression_power`). Returns the power in watts.
    """
    from math import log

    _check(volumetric_flow, "[length]**3/[time]", "volumetric_flow")
    _check(inlet_pressure, "[pressure]", "inlet_pressure")
    q = volumetric_flow.to("m**3/s").magnitude
    p1 = inlet_pressure.to("Pa").magnitude
    if q <= 0 or p1 <= 0:
        raise ValueError("volumetric_flow and inlet_pressure must be positive")
    if pressure_ratio <= 1.0:
        raise ValueError(f"pressure_ratio must exceed 1 (compression); got {pressure_ratio}")
    return Quantity(magnitude=p1 * q * log(pressure_ratio), unit="W")


def adiabatic_compression_power(
    *,
    volumetric_flow: Quantity,
    inlet_pressure: Quantity,
    pressure_ratio: float,
    heat_capacity_ratio: float,
) -> Quantity:
    """The ideal adiabatic (isentropic) compression power, P = [k/(k−1)]·p₁·Q₁·[r^((k−1)/k) − 1].

    The power an uncooled single-stage compressor takes, the gas heating as it is squeezed:
    P = [k/(k−1)]·p₁·Q₁·[r^((k−1)/k) − 1]. ``volumetric_flow`` Q₁ is the inlet volume flow,
    ``inlet_pressure`` p₁ the suction pressure, ``pressure_ratio`` r = p₂/p₁, and
    ``heat_capacity_ratio`` k the ratio of specific heats (~1.4 for air, ~1.3 for steam). Always
    exceeds the isothermal power of :func:`isothermal_compression_power`; a real compressor's shaft
    power is this over its efficiency. Returns the power in watts.
    """
    _check(volumetric_flow, "[length]**3/[time]", "volumetric_flow")
    _check(inlet_pressure, "[pressure]", "inlet_pressure")
    q = volumetric_flow.to("m**3/s").magnitude
    p1 = inlet_pressure.to("Pa").magnitude
    if q <= 0 or p1 <= 0:
        raise ValueError("volumetric_flow and inlet_pressure must be positive")
    if pressure_ratio <= 1.0:
        raise ValueError(f"pressure_ratio must exceed 1 (compression); got {pressure_ratio}")
    if heat_capacity_ratio <= 1.0:
        raise ValueError(f"heat_capacity_ratio must exceed 1; got {heat_capacity_ratio}")
    k = heat_capacity_ratio
    exponent = (k - 1.0) / k
    power = (k / (k - 1.0)) * p1 * q * (pressure_ratio**exponent - 1.0)
    return Quantity(magnitude=power, unit="W")


def adiabatic_discharge_temperature(
    *,
    inlet_temperature: Quantity,
    pressure_ratio: float,
    heat_capacity_ratio: float,
) -> Quantity:
    """The adiabatic (isentropic) discharge temperature, T₂ = T₁·r^((k−1)/k).

    How hot a gas leaves an uncooled compression stage: T₂ = T₁·r^((k−1)/k). ``inlet_temperature``
    T₁ is the absolute suction temperature, ``pressure_ratio`` r = p₂/p₁, and
    ``heat_capacity_ratio`` k the ratio of specific heats. This rise is why high-ratio compressors
    are staged with
    intercoolers — air taken from 15 °C to seven atmospheres in one shot leaves near 250 °C.
    Returns the discharge temperature in kelvin.
    """
    _check(inlet_temperature, "[temperature]", "inlet_temperature")
    t1 = inlet_temperature.to("K").magnitude
    if t1 <= 0:
        raise ValueError("inlet_temperature must be positive (absolute)")
    if pressure_ratio <= 1.0:
        raise ValueError(f"pressure_ratio must exceed 1 (compression); got {pressure_ratio}")
    if heat_capacity_ratio <= 1.0:
        raise ValueError(f"heat_capacity_ratio must exceed 1; got {heat_capacity_ratio}")
    k = heat_capacity_ratio
    return Quantity(magnitude=t1 * pressure_ratio ** ((k - 1.0) / k), unit="K")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
