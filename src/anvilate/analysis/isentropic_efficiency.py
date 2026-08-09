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
:func:`~anvilate.analysis.gas_compression.adiabatic_discharge_temperature`) and its efficiency. All
temperatures must be absolute; inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values, and the efficiencies are plain floats.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "compressor_isentropic_efficiency",
    "turbine_isentropic_efficiency",
    "compressor_actual_discharge_temperature",
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
    if t2s > t1:
        raise ValueError("isentropic_outlet_temperature must be at most inlet_temperature")
    if t2a >= t1:
        raise ValueError("actual_outlet_temperature must be below inlet_temperature")
    return (t1 - t2a) / (t1 - t2s)


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


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
