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
    "compressor_volumetric_efficiency",
    "ideal_gas_density",
    "isothermal_compression_power",
    "multistage_compression_power",
    "optimal_stage_pressure_ratio",
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


def compressor_volumetric_efficiency(
    *,
    clearance_fraction: float,
    pressure_ratio: float,
    polytropic_exponent: float,
) -> float:
    """The volumetric efficiency of a reciprocating compressor, η_v = 1 − C·(r^(1/n) − 1).

    The rest of this module computes the *ideal* work a compression needs; this is the derate that
    decides how much gas the machine actually delivers. A piston compressor cannot sweep its
    cylinder empty — the ``clearance_fraction`` C (clearance volume over swept volume, typically
    4–12%) stays full of high-pressure gas at the end of the stroke, and that gas re-expands on the
    way back down before the suction valve can open, stealing induction stroke. What it steals
    grows with the ``pressure_ratio`` r = p_2/p_1: η_v = 1 − C·(r^(1/n) − 1), with the
    ``polytropic_exponent`` n of the re-expansion. This is why a single stage is limited to a
    pressure ratio around 4:1 in practice and why staging exists — push r high enough
    (r = (1 + 1/C)^n, about 42:1 at C = 6%) and the re-expansion fills the whole stroke, the
    compressor breathes nothing, and delivery goes to zero. Multiply the swept volume by this to
    get the actual induced volume. Returns the dimensionless volumetric efficiency.
    """
    if not 0.0 <= clearance_fraction < 1.0:
        raise ValueError(f"clearance_fraction must be in [0, 1); got {clearance_fraction}")
    if pressure_ratio < 1.0:
        raise ValueError(f"pressure_ratio must be at least 1; got {pressure_ratio}")
    if polytropic_exponent <= 0.0:
        raise ValueError(f"polytropic_exponent must be positive; got {polytropic_exponent}")
    efficiency = 1.0 - clearance_fraction * (pressure_ratio ** (1.0 / polytropic_exponent) - 1.0)
    if efficiency <= 0.0:
        raise ValueError(
            "the clearance re-expansion fills the whole stroke at this pressure ratio, so the "
            "compressor delivers nothing (volumetric efficiency has fallen to zero)"
        )
    return efficiency


def optimal_stage_pressure_ratio(*, overall_pressure_ratio: float, stages: int) -> float:
    """The per-stage pressure ratio that minimizes multi-stage compression work, r^(1/n).

    With perfect intercooling back to the inlet temperature between stages, the total work is
    least when every stage shares the same pressure ratio — and that equal ratio is the nth root of
    the overall one: r_stage = r^(1/n). ``overall_pressure_ratio`` r = p_out/p_in and ``stages`` n.
    A three-stage machine at an overall 27:1, for instance, runs each stage at 3:1. Returns the
    dimensionless per-stage ratio.
    """
    if overall_pressure_ratio <= 1.0:
        raise ValueError(f"overall_pressure_ratio must exceed 1; got {overall_pressure_ratio}")
    if stages < 1:
        raise ValueError(f"stages must be at least 1; got {stages}")
    return overall_pressure_ratio ** (1.0 / stages)


def multistage_compression_power(
    *,
    volumetric_flow: Quantity,
    inlet_pressure: Quantity,
    overall_pressure_ratio: float,
    stages: int,
    heat_capacity_ratio: float,
) -> Quantity:
    """The ideal power of a multi-stage compressor with optimal intercooling.

    Splitting compression into stages with an intercooler cooling the gas back to inlet temperature
    between them cuts both the work and the discharge temperature. With the optimal equal per-stage
    ratio r^(1/n), the total power is n times a single stage at that smaller ratio:
    P = n·[k/(k−1)]·p₁·Q·[r^((k−1)/(n·k)) − 1]. ``volumetric_flow`` Q₁, ``inlet_pressure`` p₁,
    ``overall_pressure_ratio`` r, number of ``stages`` n, and ``heat_capacity_ratio`` k. As n rises
    the power falls toward the isothermal ideal (see :func:`isothermal_compression_power`); a single
    stage recovers :func:`adiabatic_compression_power`. Returns the power in watts.
    """
    _check(volumetric_flow, "[length]**3/[time]", "volumetric_flow")
    _check(inlet_pressure, "[pressure]", "inlet_pressure")
    q = volumetric_flow.to("m**3/s").magnitude
    p1 = inlet_pressure.to("Pa").magnitude
    if q <= 0 or p1 <= 0:
        raise ValueError("volumetric_flow and inlet_pressure must be positive")
    if overall_pressure_ratio <= 1.0:
        raise ValueError(f"overall_pressure_ratio must exceed 1; got {overall_pressure_ratio}")
    if stages < 1:
        raise ValueError(f"stages must be at least 1; got {stages}")
    if heat_capacity_ratio <= 1.0:
        raise ValueError(f"heat_capacity_ratio must exceed 1; got {heat_capacity_ratio}")
    k = heat_capacity_ratio
    exponent = (k - 1.0) / (stages * k)
    power = stages * (k / (k - 1.0)) * p1 * q * (overall_pressure_ratio**exponent - 1.0)
    return Quantity(magnitude=power, unit="W")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
