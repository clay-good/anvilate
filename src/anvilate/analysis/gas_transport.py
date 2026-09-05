"""T1 analytical gas transport properties (closed-form).

Every convection, pipe-flow, and boundary-layer check in Anvilate asks the caller to supply the
gas's viscosity, thermal conductivity, and Prandtl number — but those properties are not constants:
they climb steeply with temperature. This module computes them from temperature so a hot-air or
combustion-gas calc need not stop to read a property table. It is the front end that feeds the
Reynolds, Nusselt, and Rayleigh correlations of :mod:`anvilate.analysis.thermal` and the pipe and
boundary-layer checks of :mod:`anvilate.analysis.pipe_flow` and
:mod:`anvilate.analysis.boundary_layer`.

Sutherland's law models a dilute gas as rigid attracting molecules: both the dynamic viscosity
µ = µ_ref·(T/T_ref)^1.5·(T_ref+S)/(T+S) and the thermal conductivity k = k_ref·(T/T_ref)^1.5·
(T_ref+S_k)/(T+S_k) rise with the three-halves power of absolute temperature, tempered by a
Sutherland constant S that captures intermolecular attraction. The Prandtl number Pr = µ·c_p/k then
ties the two transport rates together — how fast momentum diffuses versus heat — and is the
dimensionless group the convection correlations actually consume. Temperatures must be absolute
(kelvin or rankine); inputs and outputs are dimension-checked :class:`~anvilate.units.Quantity`
values, and the Prandtl number is a plain dimensionless float.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "sutherland_viscosity",
    "sutherland_thermal_conductivity",
    "prandtl_number",
]


def sutherland_viscosity(
    *,
    temperature: Quantity,
    reference_viscosity: Quantity,
    reference_temperature: Quantity,
    sutherland_constant: Quantity,
) -> Quantity:
    """A gas's dynamic viscosity by Sutherland's law, µ = µ_ref·(T/T_ref)^1.5·(T_ref+S)/(T+S).

    The dynamic viscosity of a dilute gas rises with temperature (unlike a liquid, which thins):
    µ = µ_ref·(T/T_ref)^1.5·(T_ref+S)/(T+S), from the ``temperature`` T, a reference point
    (``reference_viscosity`` µ_ref at ``reference_temperature`` T_ref), and the
    ``sutherland_constant`` S. For air µ_ref ≈ 1.716e-5 Pa·s at T_ref = 273.15 K with S ≈ 110.4 K.
    All temperatures must be absolute. Returns the viscosity in the ``reference_viscosity`` units.
    """
    _check(temperature, "[temperature]", "temperature")
    _check(reference_viscosity, "[pressure] * [time]", "reference_viscosity")
    _check(reference_temperature, "[temperature]", "reference_temperature")
    _check(sutherland_constant, "[temperature]", "sutherland_constant")
    t = temperature.to("K").magnitude
    t_ref = reference_temperature.to("K").magnitude
    s = sutherland_constant.to("K").magnitude
    if t <= 0 or t_ref <= 0:
        raise ValueError("temperatures must be positive absolute (kelvin) values")
    if s < 0:
        raise ValueError("sutherland_constant must be non-negative")
    factor = (t / t_ref) ** 1.5 * (t_ref + s) / (t + s)
    mu_ref = reference_viscosity.to("Pa*s").magnitude
    return Quantity(magnitude=mu_ref * factor, unit="Pa*s")


def sutherland_thermal_conductivity(
    *,
    temperature: Quantity,
    reference_conductivity: Quantity,
    reference_temperature: Quantity,
    sutherland_constant: Quantity,
) -> Quantity:
    """A gas's thermal conductivity by Sutherland's law, k = k_ref·(T/T_ref)^1.5·(T_ref+S)/(T+S).

    The same three-halves law as :func:`sutherland_viscosity`, applied to conduction: a gas carries
    heat better as it heats up. k = k_ref·(T/T_ref)^1.5·(T_ref+S)/(T+S), from the ``temperature`` T,
    a reference point (``reference_conductivity`` k_ref at ``reference_temperature`` T_ref), and the
    ``sutherland_constant`` S — which differs from the viscosity's (for air k_ref ≈ 0.0241 W/m·K at
    273.15 K with S ≈ 194 K). All temperatures must be absolute. Returns the conductivity in the
    units of ``reference_conductivity``.
    """
    _check(temperature, "[temperature]", "temperature")
    _check(reference_conductivity, "[power] / [length] / [temperature]", "reference_conductivity")
    _check(reference_temperature, "[temperature]", "reference_temperature")
    _check(sutherland_constant, "[temperature]", "sutherland_constant")
    t = temperature.to("K").magnitude
    t_ref = reference_temperature.to("K").magnitude
    s = sutherland_constant.to("K").magnitude
    if t <= 0 or t_ref <= 0:
        raise ValueError("temperatures must be positive absolute (kelvin) values")
    if s < 0:
        raise ValueError("sutherland_constant must be non-negative")
    factor = (t / t_ref) ** 1.5 * (t_ref + s) / (t + s)
    k_ref = reference_conductivity.to("W/(m*K)").magnitude
    return Quantity(magnitude=k_ref * factor, unit="W/(m*K)")


def prandtl_number(
    *,
    dynamic_viscosity: Quantity,
    specific_heat: Quantity,
    thermal_conductivity: Quantity,
) -> float:
    """The Prandtl number of a fluid, Pr = µ·c_p/k.

    The ratio of how fast momentum diffuses to how fast heat diffuses: Pr = µ·c_p/k, from the
    ``dynamic_viscosity`` µ, the ``specific_heat`` c_p at constant pressure, and the
    ``thermal_conductivity`` k. It is the dimensionless property the convection correlations
    consume, setting the relative thickness of the velocity and thermal boundary layers. For gases
    Pr ≈ 0.7 (air ≈ 0.71); for water ≈ 7, for oils in the hundreds, for liquid metals far below 1.
    Returns the dimensionless Prandtl number as a plain float.

    Source: Incropera & DeWitt / Bergman, *Fundamentals of Heat and Mass Transfer*.
    """
    _check(dynamic_viscosity, "[pressure] * [time]", "dynamic_viscosity")
    _check(specific_heat, "[energy]/[mass]/[temperature]", "specific_heat")
    _check(thermal_conductivity, "[power] / [length] / [temperature]", "thermal_conductivity")
    mu = dynamic_viscosity.to("Pa*s").magnitude
    cp = specific_heat.to("J/(kg*K)").magnitude
    k = thermal_conductivity.to("W/(m*K)").magnitude
    if mu < 0 or cp < 0:
        raise ValueError("dynamic_viscosity and specific_heat must be non-negative")
    if k <= 0:
        raise ValueError("thermal_conductivity must be positive")
    return mu * cp / k


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
