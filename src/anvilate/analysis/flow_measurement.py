"""T1 analytical flow-measurement checks (differential-pressure meters, closed-form).

Most industrial flow is measured by making the fluid speed up through a restriction and reading
the pressure drop that costs. An orifice plate, a venturi, or a flow nozzle all obey the same
Bernoulli-plus-continuity relation:

    Q = C_d · A_throat / √(1 − β⁴) · √(2·Δp/ρ)

where A_throat is the throat area, β = d/D the throat-to-pipe diameter ratio, Δp the measured
pressure drop, and ρ the density. The whole character of the device lives in the discharge
coefficient C_d (~0.6 for a sharp orifice, ~0.98 for a smooth venturi) and the 1/√(1 − β⁴)
velocity-of-approach factor. Running the relation forward turns a measured Δp into a flow;
running it backward (:func:`differential_pressure_for_flow`) sizes the pressure transmitter's
range for a target flow.

A pitot tube measures a point velocity instead of a bulk flow, from the stagnation (dynamic)
pressure: V = √(2·Δp/ρ). Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import pi, sqrt

from ..units import Quantity

__all__ = [
    "differential_pressure_for_flow",
    "dynamic_pressure",
    "obstruction_meter_flow_rate",
    "orifice_permanent_pressure_loss",
    "pitot_velocity",
]


def obstruction_meter_flow_rate(
    *,
    discharge_coefficient: float,
    throat_diameter: Quantity,
    pipe_diameter: Quantity,
    pressure_drop: Quantity,
    density: Quantity,
) -> Quantity:
    """The volumetric flow through an orifice, venturi, or nozzle from its pressure drop.

    The forward reading of a differential-pressure flow meter: Q = C_d·A/√(1 − β⁴)·√(2·Δp/ρ), the
    flow that produces a measured ``pressure_drop`` Δp across a restriction. The
    ``discharge_coefficient`` C_d captures the device (~0.6 orifice, ~0.98 venturi),
    ``throat_diameter`` d and
    ``pipe_diameter`` D set the throat area A = π·d²/4 and the β = d/D velocity-of-approach factor,
    and ``density`` ρ is the fluid density. Returns the volumetric flow rate in m³/s.
    """
    _check(throat_diameter, "[length]", "throat_diameter")
    _check(pipe_diameter, "[length]", "pipe_diameter")
    _check(pressure_drop, "[pressure]", "pressure_drop")
    _check(density, "[mass]/[length]**3", "density")
    d = throat_diameter.to("m").magnitude
    big_d = pipe_diameter.to("m").magnitude
    dp = pressure_drop.to("Pa").magnitude
    rho = density.to("kg/m**3").magnitude
    if not 0.0 < discharge_coefficient <= 1.0:
        raise ValueError(f"discharge_coefficient must be in (0, 1]; got {discharge_coefficient}")
    if d <= 0 or big_d <= 0 or rho <= 0:
        raise ValueError("throat_diameter, pipe_diameter, and density must be positive")
    if dp < 0:
        raise ValueError("pressure_drop must be non-negative")
    if d >= big_d:
        raise ValueError("throat_diameter must be smaller than pipe_diameter")
    beta = d / big_d
    area = pi / 4.0 * d**2
    q = discharge_coefficient * area / sqrt(1.0 - beta**4) * sqrt(2.0 * dp / rho)
    return Quantity(magnitude=q, unit="m**3/s")


def orifice_permanent_pressure_loss(
    *,
    pressure_drop: Quantity,
    discharge_coefficient: float,
    throat_diameter: Quantity,
    pipe_diameter: Quantity,
) -> Quantity:
    """The unrecovered pressure loss across an orifice plate (ISO 5167-2).

    The Δp a differential-pressure meter *measures* is not the pressure it *costs*: downstream of
    the restriction the jet re-expands and recovers part of it, and only the rest is lost for good
    to turbulence. That permanent loss is the pumping bill the meter charges forever, and it is what
    decides orifice versus venturi on anything with a real energy budget. From the measured
    ``pressure_drop`` Δp, the ``discharge_coefficient`` C_d, and the β = d/D set by
    ``throat_diameter`` d and ``pipe_diameter`` D:

        Δϖ = Δp·(√(1 − β⁴(1 − C_d²)) − C_d·β²)/(√(1 − β⁴(1 − C_d²)) + C_d·β²)

    A small β (a hard squeeze, a large readable Δp) loses almost all of it — about 95% at β = 0.2,
    falling to roughly 63% at β = 0.6 and 45% at β = 0.75 — so the pressure drop that buys
    measurement resolution is bought back in permanent pump work. A venturi's gradual diffuser
    recovers far more, which is the whole reason to pay for one. Returns the permanent loss in Pa.
    """
    _check(pressure_drop, "[pressure]", "pressure_drop")
    _check(throat_diameter, "[length]", "throat_diameter")
    _check(pipe_diameter, "[length]", "pipe_diameter")
    dp = pressure_drop.to("Pa").magnitude
    d = throat_diameter.to("m").magnitude
    big_d = pipe_diameter.to("m").magnitude
    if not 0.0 < discharge_coefficient <= 1.0:
        raise ValueError(f"discharge_coefficient must be in (0, 1]; got {discharge_coefficient}")
    if dp < 0:
        raise ValueError("pressure_drop must be non-negative")
    if d <= 0 or big_d <= 0:
        raise ValueError("throat_diameter and pipe_diameter must be positive")
    if d >= big_d:
        raise ValueError("throat_diameter must be smaller than pipe_diameter")
    beta = d / big_d
    root = sqrt(1.0 - beta**4 * (1.0 - discharge_coefficient**2))
    recovered = discharge_coefficient * beta**2
    return Quantity(magnitude=dp * (root - recovered) / (root + recovered), unit="Pa")


def differential_pressure_for_flow(
    *,
    flow_rate: Quantity,
    discharge_coefficient: float,
    throat_diameter: Quantity,
    pipe_diameter: Quantity,
    density: Quantity,
) -> Quantity:
    """The pressure drop a differential-pressure meter produces at a given flow (sizing inverse).

    The inverse of :func:`obstruction_meter_flow_rate`, Δp = (ρ/2)·[Q·√(1 − β⁴)/(C_d·A)]² — the
    signal a meter puts out at a target ``flow_rate`` Q, used to size the pressure transmitter's
    range. ``discharge_coefficient`` C_d, ``throat_diameter`` d and ``pipe_diameter`` D (giving the
    throat area and β), and ``density`` ρ are as in the forward relation. Returns Δp in kPa.
    """
    _check(flow_rate, "[length]**3/[time]", "flow_rate")
    _check(throat_diameter, "[length]", "throat_diameter")
    _check(pipe_diameter, "[length]", "pipe_diameter")
    _check(density, "[mass]/[length]**3", "density")
    q = flow_rate.to("m**3/s").magnitude
    d = throat_diameter.to("m").magnitude
    big_d = pipe_diameter.to("m").magnitude
    rho = density.to("kg/m**3").magnitude
    if not 0.0 < discharge_coefficient <= 1.0:
        raise ValueError(f"discharge_coefficient must be in (0, 1]; got {discharge_coefficient}")
    if q <= 0 or d <= 0 or big_d <= 0 or rho <= 0:
        raise ValueError("flow_rate, throat_diameter, pipe_diameter, and density must be positive")
    if d >= big_d:
        raise ValueError("throat_diameter must be smaller than pipe_diameter")
    beta = d / big_d
    area = pi / 4.0 * d**2
    velocity_term = q * sqrt(1.0 - beta**4) / (discharge_coefficient * area)
    dp = 0.5 * rho * velocity_term**2
    return Quantity(magnitude=dp / 1000.0, unit="kPa")


def dynamic_pressure(*, velocity: Quantity, density: Quantity) -> Quantity:
    """The dynamic (velocity) pressure of a moving fluid, Δp = ½·ρ·V².

    The pressure a flow carries by virtue of its motion — the forward of :func:`pitot_velocity`.
    Bringing a stream of ``density`` ρ moving at ``velocity`` V to rest raises its pressure by
    ½·ρ·V²: this is what a pitot tube reads, and in a duct it is the *velocity pressure* that adds
    to the static pressure to make the fan total pressure (see
    :func:`~anvilate.analysis.fan_total_pressure`). For standard air (ρ ≈ 1.2 kg/m³) a 10 m/s duct
    velocity is 60 Pa. Returns the dynamic pressure in Pa.
    """
    _check(velocity, "[length]/[time]", "velocity")
    _check(density, "[mass]/[length]**3", "density")
    v = velocity.to("m/s").magnitude
    rho = density.to("kg/m**3").magnitude
    if rho <= 0:
        raise ValueError("density must be positive")
    return Quantity(magnitude=0.5 * rho * v**2, unit="Pa")


def pitot_velocity(*, dynamic_pressure: Quantity, density: Quantity) -> Quantity:
    """The local flow velocity from a pitot tube's dynamic pressure, V = √(2·Δp/ρ).

    A pitot tube reads the stagnation (dynamic) pressure of the flow it faces, and Bernoulli turns
    that into a point velocity: V = √(2·Δp/ρ). ``dynamic_pressure`` Δp is the difference between
    the stagnation and static pressures and ``density`` ρ the fluid density. Returns the velocity
    in m/s.
    """
    _check(dynamic_pressure, "[pressure]", "dynamic_pressure")
    _check(density, "[mass]/[length]**3", "density")
    dp = dynamic_pressure.to("Pa").magnitude
    rho = density.to("kg/m**3").magnitude
    if dp < 0 or rho <= 0:
        raise ValueError("dynamic_pressure must be non-negative and density positive")
    return Quantity(magnitude=sqrt(2.0 * dp / rho), unit="m/s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
