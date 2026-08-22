"""T1 analytical turbomachinery isentropic efficiency (closed-form).

The ideal compressor and turbine of a gas cycle move along a reversible isentrope, but a real one
does not: friction and turbulence make a compressor take *more* work than the isentropic ideal and a
turbine deliver *less*. The isentropic (adiabatic) efficiency is the single number that bridges the
two — the factor that turns the ideal work of :mod:`anvilate.analysis.gas_compression` into the
actual work, and the piece a Brayton or Rankine cycle in :mod:`anvilate.analysis.power_cycles` needs
to drop from its air-standard ceiling to a real machine.

For a constant-c_p ideal gas the enthalpy differences become temperature differences, so the
efficiency reads straight off the inlet, isentropic-outlet, and actual-outlet temperatures. A
compressor's efficiency is the ideal temperature rise over the actual one,
η_c = (T₂ₛ − T₁)/(T₂ₐ − T₁) ≤ 1 (the real machine ends up hotter); a turbine's is the actual drop
over the ideal one, η_t = (T₁ − T₂ₐ)/(T₁ − T₂ₛ) ≤ 1 (the real machine ends up hotter too, having
given up less work). Running the compressor relation backward gives the actual discharge temperature
a real stage reaches from its isentropic value (T₂ₛ from
:func:`~anvilate.analysis.gas_compression.adiabatic_discharge_temperature`) and its efficiency.

The last three functions add the polytropic (small-stage) efficiency, the companion an overall
pressure ratio hides. Because a compressor reheats the gas as it works, the isentropic efficiency
of a whole machine is worse than the polytropic efficiency of its stages, and for a turbine it is
better — the same η_poly gives η_isen < η_poly on compression and η_isen > η_poly on expansion.
These use the pressure ratio and γ directly and return dimensionless floats. All temperatures must
be absolute; inputs and outputs are dimension-checked :class:`~anvilate.units.Quantity` values, and
the efficiencies are plain floats.
"""

from __future__ import annotations

from math import log

from ..units import Quantity

__all__ = [
    "compressor_isentropic_efficiency",
    "turbine_isentropic_efficiency",
    "compressor_actual_discharge_temperature",
    "compressor_polytropic_efficiency",
    "compressor_isentropic_from_polytropic",
    "turbine_isentropic_from_polytropic",
]


def compressor_isentropic_efficiency(
    *,
    inlet_temperature: Quantity,
    isentropic_outlet_temperature: Quantity,
    actual_outlet_temperature: Quantity,
) -> float:
    """A compressor's isentropic efficiency, η_c = (T₂ₛ − T₁)/(T₂ₐ − T₁).

    The ideal (isentropic) temperature rise over the actual one, for a constant-c_p ideal gas:
    η_c = (T₂ₛ − T₁)/(T₂ₐ − T₁), from the ``inlet_temperature`` T₁, the
    ``isentropic_outlet_temperature`` T₂ₛ (the reversible ideal), and the
    ``actual_outlet_temperature`` T₂ₐ. A real compressor delivers the gas hotter than the ideal
    (T₂ₐ > T₂ₛ), so η_c ≤ 1; a lower efficiency means more shaft work for the same pressure ratio.
    All temperatures must be absolute. Returns the dimensionless efficiency as a plain float.
    """
    _check(inlet_temperature, "[temperature]", "inlet_temperature")
    _check(isentropic_outlet_temperature, "[temperature]", "isentropic_outlet_temperature")
    _check(actual_outlet_temperature, "[temperature]", "actual_outlet_temperature")
    t1 = inlet_temperature.to("K").magnitude
    t2s = isentropic_outlet_temperature.to("K").magnitude
    t2a = actual_outlet_temperature.to("K").magnitude
    if t1 <= 0 or t2s <= 0 or t2a <= 0:
        raise ValueError("temperatures must be positive absolute (kelvin) values")
    if t2s < t1:
        raise ValueError("isentropic_outlet_temperature must be at least inlet_temperature")
    if t2a <= t1:
        raise ValueError("actual_outlet_temperature must exceed inlet_temperature")
    # A real compressor delivers the gas HOTTER than the ideal one, so T2a >= T2s and
    # eta_c <= 1 — which this function's own docstring states and never checked, while its
    # sibling `turbine_isentropic_efficiency` refuses the mirror case by name. Swapping the
    # two outlet arguments is the obvious slip and it returned 15.0, then 1.5e6.
    if t2a < t2s:
        raise ValueError(
            f"actual_outlet_temperature ({t2a:.4g} K) is below isentropic_outlet_temperature "
            f"({t2s:.4g} K), giving an isentropic efficiency of {(t2s - t1) / (t2a - t1):.4g}. "
            f"A real compressor delivers the gas hotter than the ideal one, so eta_c <= 1 — "
            f"check whether the two outlet temperatures are the right way round"
        )
    return (t2s - t1) / (t2a - t1)


def turbine_isentropic_efficiency(
    *,
    inlet_temperature: Quantity,
    actual_outlet_temperature: Quantity,
    isentropic_outlet_temperature: Quantity,
) -> float:
    """A turbine's isentropic efficiency, η_t = (T₁ − T₂ₐ)/(T₁ − T₂ₛ).

    The actual temperature drop over the ideal (isentropic) one, for a constant-c_p ideal gas:
    η_t = (T₁ − T₂ₐ)/(T₁ − T₂ₛ), from the ``inlet_temperature`` T₁, the
    ``actual_outlet_temperature`` T₂ₐ, and the ``isentropic_outlet_temperature`` T₂ₛ (the reversible
    ideal). A real turbine extracts less work, so it leaves the gas hotter than the ideal
    (T₂ₐ > T₂ₛ) and η_t ≤ 1. All temperatures must be absolute. Returns the dimensionless efficiency
    as a plain float.
    """
    _check(inlet_temperature, "[temperature]", "inlet_temperature")
    _check(actual_outlet_temperature, "[temperature]", "actual_outlet_temperature")
    _check(isentropic_outlet_temperature, "[temperature]", "isentropic_outlet_temperature")
    t1 = inlet_temperature.to("K").magnitude
    t2a = actual_outlet_temperature.to("K").magnitude
    t2s = isentropic_outlet_temperature.to("K").magnitude
    if t1 <= 0 or t2a <= 0 or t2s <= 0:
        raise ValueError("temperatures must be positive absolute (kelvin) values")
    # The compressor sibling guards its DENOMINATOR strictly and its numerator loosely;
    # this guarded the mirror image, leaving (T₁ − T₂ₛ) — its own denominator — free to
    # reach zero. T₂ₛ = T₁ was a bare ZeroDivisionError, and T₂ₛ a ten-thousandth of a
    # kelvin below it returned an isentropic efficiency of 3,000,000 against a docstring
    # that says η_t ≤ 1. Guard the denominator, and then honour the ceiling the same way
    # `heat_exchanger_effectiveness_from_temperatures` already does.
    if t2s >= t1:
        raise ValueError(
            f"isentropic_outlet_temperature ({isentropic_outlet_temperature}) must be "
            f"below inlet_temperature ({inlet_temperature}): an ideal expansion that "
            f"drops no temperature does no work, and there is no efficiency to take a "
            f"ratio against."
        )
    if t2a >= t1:
        raise ValueError("actual_outlet_temperature must be below inlet_temperature")
    efficiency = (t1 - t2a) / (t1 - t2s)
    if efficiency > 1.0:
        raise ValueError(
            f"the temperatures give an isentropic efficiency of {efficiency:.4g}: the "
            f"actual outlet ({actual_outlet_temperature}) is BELOW the isentropic one "
            f"({isentropic_outlet_temperature}), so the turbine extracted more work than "
            f"the reversible ideal. Check which outlet is which."
        )
    return efficiency


def compressor_actual_discharge_temperature(
    *,
    inlet_temperature: Quantity,
    isentropic_outlet_temperature: Quantity,
    isentropic_efficiency: float,
) -> Quantity:
    """A compressor's actual discharge temperature, T₂ₐ = T₁ + (T₂ₛ − T₁)/η_c.

    The compressor-efficiency relation run backward: the real discharge temperature a stage reaches,
    T₂ₐ = T₁ + (T₂ₛ − T₁)/η_c, from the ``inlet_temperature`` T₁, the
    ``isentropic_outlet_temperature`` T₂ₛ (from an adiabatic-discharge calculation), and the
    ``isentropic_efficiency`` η_c. Because η_c < 1 the actual gas ends up hotter than the ideal —
    the temperature that sizes intercooling and aftercooling. Returns the actual discharge
    temperature in kelvin.
    """
    _check(inlet_temperature, "[temperature]", "inlet_temperature")
    _check(isentropic_outlet_temperature, "[temperature]", "isentropic_outlet_temperature")
    t1 = inlet_temperature.to("K").magnitude
    t2s = isentropic_outlet_temperature.to("K").magnitude
    if t1 <= 0 or t2s <= 0:
        raise ValueError("temperatures must be positive absolute (kelvin) values")
    if t2s < t1:
        raise ValueError("isentropic_outlet_temperature must be at least inlet_temperature")
    if not 0.0 < isentropic_efficiency <= 1.0:
        raise ValueError(f"isentropic_efficiency must be in (0, 1]; got {isentropic_efficiency}")
    t2a = t1 + (t2s - t1) / isentropic_efficiency
    return Quantity(magnitude=t2a, unit="K")


def compressor_polytropic_efficiency(
    *,
    inlet_temperature: Quantity,
    actual_outlet_temperature: Quantity,
    pressure_ratio: float,
    heat_capacity_ratio: float = 1.4,
) -> float:
    """A compressor's polytropic efficiency, η_p = [(γ−1)/γ·ln r]/ln(T₂ₐ/T₁).

    The small-stage (polytropic) efficiency read from the actual temperature rise:
    η_p = [(γ−1)/γ·ln(r)]/ln(T₂ₐ/T₁), from the ``inlet_temperature`` T₁, the
    ``actual_outlet_temperature`` T₂ₐ, the ``pressure_ratio`` r = p₂/p₁, and the
    ``heat_capacity_ratio`` γ. Unlike the isentropic efficiency it does not depend on the pressure
    ratio the way the whole-machine value does, which is why it is the fairer basis for comparing
    stages. All temperatures must be absolute. Returns the dimensionless polytropic efficiency.
    """
    _check(inlet_temperature, "[temperature]", "inlet_temperature")
    _check(actual_outlet_temperature, "[temperature]", "actual_outlet_temperature")
    t1 = inlet_temperature.to("K").magnitude
    t2a = actual_outlet_temperature.to("K").magnitude
    if t1 <= 0 or t2a <= 0:
        raise ValueError("temperatures must be positive absolute (kelvin) values")
    if t2a <= t1:
        raise ValueError("actual_outlet_temperature must exceed inlet_temperature")
    if pressure_ratio <= 1.0:
        raise ValueError("pressure_ratio must exceed 1")
    if heat_capacity_ratio <= 1.0:
        raise ValueError("heat_capacity_ratio must exceed 1")
    exponent = (heat_capacity_ratio - 1.0) / heat_capacity_ratio
    return exponent * log(pressure_ratio) / log(t2a / t1)


def compressor_isentropic_from_polytropic(
    *,
    pressure_ratio: float,
    polytropic_efficiency: float,
    heat_capacity_ratio: float = 1.4,
) -> float:
    """A compressor's isentropic efficiency from its polytropic one, η_c = (r^x−1)/(r^(x/η_p)−1).

    Converts the small-stage ``polytropic_efficiency`` η_p to the whole-machine isentropic
    efficiency at the ``pressure_ratio`` r = p₂/p₁: η_c = (r^x − 1)/(r^(x/η_p) − 1) with
    x = (γ−1)/γ from the ``heat_capacity_ratio`` γ. The reheat effect makes η_c < η_p, and the gap
    widens with the pressure ratio — why a high-ratio compressor's isentropic efficiency looks poor
    even with good stages. Returns the dimensionless isentropic efficiency.
    """
    if pressure_ratio <= 1.0:
        raise ValueError("pressure_ratio must exceed 1")
    if not 0.0 < polytropic_efficiency <= 1.0:
        raise ValueError(f"polytropic_efficiency must be in (0, 1]; got {polytropic_efficiency}")
    if heat_capacity_ratio <= 1.0:
        raise ValueError("heat_capacity_ratio must exceed 1")
    x = (heat_capacity_ratio - 1.0) / heat_capacity_ratio
    return (pressure_ratio**x - 1.0) / (pressure_ratio ** (x / polytropic_efficiency) - 1.0)


def turbine_isentropic_from_polytropic(
    *,
    pressure_ratio: float,
    polytropic_efficiency: float,
    heat_capacity_ratio: float = 1.4,
) -> float:
    """A turbine's isentropic efficiency from its polytropic one, η_t = (1−r^(−x·η_p))/(1−r^(−x)).

    Converts the small-stage ``polytropic_efficiency`` η_p to the whole-machine isentropic
    efficiency across the expansion ``pressure_ratio`` r = p₁/p₂ (inlet over outlet): η_t =
    (1 − r^(−x·η_p))/(1 − r^(−x)) with x = (γ−1)/γ from the ``heat_capacity_ratio`` γ. For a turbine
    the reheat effect works the other way, so η_t > η_p and the gap grows with the pressure ratio.
    Returns the dimensionless isentropic efficiency.
    """
    if pressure_ratio <= 1.0:
        raise ValueError("pressure_ratio must exceed 1")
    if not 0.0 < polytropic_efficiency <= 1.0:
        raise ValueError(f"polytropic_efficiency must be in (0, 1]; got {polytropic_efficiency}")
    if heat_capacity_ratio <= 1.0:
        raise ValueError("heat_capacity_ratio must exceed 1")
    x = (heat_capacity_ratio - 1.0) / heat_capacity_ratio
    return (1.0 - pressure_ratio ** (-x * polytropic_efficiency)) / (1.0 - pressure_ratio ** (-x))


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
