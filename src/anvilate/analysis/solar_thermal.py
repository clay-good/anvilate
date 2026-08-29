"""T1 analytical solar-thermal (flat-plate collector) checks (closed-form).

Where :mod:`anvilate.analysis.solar_pv` turns sunlight into electricity, a solar-thermal collector
turns it into hot water, and the two behave differently: a PV module loses efficiency as it heats
up, while a thermal collector *lives* on the temperature it reaches — but the hotter its fluid runs
above ambient, the faster it bleeds heat back to the sky. That trade is the whole story of collector
performance, and the standard collector-test model (ISO 9806 / EN 12975, Duffie & Beckman) captures
it in one line.

The instantaneous efficiency is η = η₀ − a₁·(T_m − T_a)/G − a₂·(T_m − T_a)²/G: the optical
(zero-loss) efficiency η₀ that would be reached if the fluid ran at ambient, minus a linear and a
quadratic loss term driven by the temperature rise (T_m − T_a) of the mean fluid over ambient,
normalized by the irradiance G. The loss coefficients a₁ [W/(m²·K)] and a₂ [W/(m²·K²)] come from
the collector's certified test curve; a₂ is often small and defaults to zero (the first-order
model). The useful heat a collector of area A then delivers is Q = η·G·A.

Push the temperature rise far enough — or cut off the flow on a hot day — and the losses climb to
meet the whole absorbed input: efficiency falls to zero and the collector sits at its *stagnation*
temperature, the no-flow maximum that sets the material and pressure-relief requirements. Setting
η = 0 and solving for the rise gives it directly.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity

__all__ = [
    "collector_stagnation_temperature",
    "collector_useful_heat",
    "flat_plate_collector_efficiency",
]


def flat_plate_collector_efficiency(
    *,
    optical_efficiency: float,
    loss_coefficient: Quantity,
    mean_fluid_temperature: Quantity,
    ambient_temperature: Quantity,
    irradiance: Quantity,
    second_order_loss_coefficient: Quantity | None = None,
) -> float:
    """The instantaneous collector efficiency, η = η₀ − a₁·ΔT/G − a₂·ΔT²/G.

    The fraction of incident sunlight a flat-plate collector delivers as useful heat, from the
    ``optical_efficiency`` η₀ (the zero-loss efficiency, ≈ 0.7–0.8, reached when the fluid runs at
    ambient), the ``loss_coefficient`` a₁ [W/(m²·K)] and optional ``second_order_loss_coefficient``
    a₂ [W/(m²·K²)] of the collector's test curve, the temperature rise ΔT = T_m − T_a of the
    ``mean_fluid_temperature`` over the ``ambient_temperature``, and the ``irradiance`` G. The
    hotter the fluid runs above ambient, the more heat leaks back and the lower η — the opposite of
    a PV module, which the temperature rise *helps*. Feeds :func:`collector_useful_heat`. A result
    at or below zero means the collector is below its useful threshold (losses meet or exceed the
    absorbed input); see :func:`collector_stagnation_temperature` for where that happens. Returns
    the dimensionless efficiency.
    """
    _fraction(optical_efficiency, "optical_efficiency")
    _check(loss_coefficient, "[power] / [length]**2 / [temperature]", "loss_coefficient")
    _check(mean_fluid_temperature, "[temperature]", "mean_fluid_temperature")
    _check(ambient_temperature, "[temperature]", "ambient_temperature")
    _check(irradiance, "[power] / [length]**2", "irradiance")
    a1 = loss_coefficient.to("W/(m**2*K)").magnitude
    delta_t = mean_fluid_temperature.to("degC").magnitude - ambient_temperature.to("degC").magnitude
    g = irradiance.to("W/m**2").magnitude
    if a1 < 0:
        raise ValueError("loss_coefficient must be non-negative")
    if g <= 0:
        raise ValueError("irradiance must be positive")
    a2 = 0.0
    if second_order_loss_coefficient is not None:
        _check(
            second_order_loss_coefficient,
            "[power] / [length]**2 / [temperature]**2",
            "second_order_loss_coefficient",
        )
        a2 = second_order_loss_coefficient.to("W/(m**2*K**2)").magnitude
        if a2 < 0:
            raise ValueError("second_order_loss_coefficient must be non-negative")
    return optical_efficiency - a1 * delta_t / g - a2 * delta_t**2 / g


def collector_useful_heat(
    *,
    efficiency: float,
    irradiance: Quantity,
    area: Quantity,
) -> Quantity:
    """The useful heat a collector delivers, Q = η·G·A.

    The thermal power a collector of aperture ``area`` A collects at ``efficiency`` η (its own
    value, or from :func:`flat_plate_collector_efficiency`) under an ``irradiance`` G: Q = η·G·A. It
    is the heat available to the tank or load — the collector-side counterpart of a PV array's
    electrical output. Returns the useful heat in watts.
    """
    _fraction(efficiency, "efficiency")
    _check(irradiance, "[power] / [length]**2", "irradiance")
    _check(area, "[area]", "area")
    g = irradiance.to("W/m**2").magnitude
    a = area.to("m**2").magnitude
    if g <= 0 or a <= 0:
        raise ValueError("irradiance and area must be positive")
    return Quantity(magnitude=efficiency * g * a, unit="W")


def collector_stagnation_temperature(
    *,
    optical_efficiency: float,
    loss_coefficient: Quantity,
    ambient_temperature: Quantity,
    irradiance: Quantity,
    second_order_loss_coefficient: Quantity | None = None,
) -> Quantity:
    """The no-flow stagnation temperature, where the losses meet the absorbed input (η = 0).

    With the pump off on a sunny day, a collector's fluid heats until its losses climb to equal the
    whole absorbed input and the efficiency of :func:`flat_plate_collector_efficiency` falls to
    zero. Setting η = 0 and solving for the temperature rise gives the stagnation rise: linearly
    ΔT = η₀·G/a₁, or when a second-order term is present the positive root of a₂·ΔT² + a₁·ΔT −
    η₀·G = 0. The stagnation temperature is that rise above the ``ambient_temperature`` T_a, from
    the ``optical_efficiency`` η₀, the ``loss_coefficient`` a₁, the optional
    ``second_order_loss_coefficient`` a₂, and the ``irradiance`` G. It is the hottest the collector
    reaches and sets the material, glycol-degradation, and pressure-relief limits of the loop — flat
    plates commonly stagnate near 150–200 °C. Returns the stagnation temperature in °C.
    """
    _fraction(optical_efficiency, "optical_efficiency")
    _check(loss_coefficient, "[power] / [length]**2 / [temperature]", "loss_coefficient")
    _check(ambient_temperature, "[temperature]", "ambient_temperature")
    _check(irradiance, "[power] / [length]**2", "irradiance")
    a1 = loss_coefficient.to("W/(m**2*K)").magnitude
    g = irradiance.to("W/m**2").magnitude
    t_a = ambient_temperature.to("degC").magnitude
    if a1 <= 0:
        raise ValueError("loss_coefficient must be positive")
    if g <= 0:
        raise ValueError("irradiance must be positive")
    a2 = 0.0
    if second_order_loss_coefficient is not None:
        _check(
            second_order_loss_coefficient,
            "[power] / [length]**2 / [temperature]**2",
            "second_order_loss_coefficient",
        )
        a2 = second_order_loss_coefficient.to("W/(m**2*K**2)").magnitude
        if a2 < 0:
            raise ValueError("second_order_loss_coefficient must be non-negative")
    if a2 == 0.0:
        delta_t = optical_efficiency * g / a1
    else:
        delta_t = (-a1 + sqrt(a1**2 + 4.0 * a2 * optical_efficiency * g)) / (2.0 * a2)
    return Quantity(magnitude=t_a + delta_t, unit="degC")


def _fraction(value: float, name: str) -> None:
    if not 0.0 < value <= 1.0:
        raise ValueError(f"{name} must be in (0, 1]; got {value}")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
