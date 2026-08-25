"""T1 analytical thermoelectric (Seebeck / Peltier) checks (closed-form).

A thermoelectric module is a solid-state heat pump and generator in one: pass a current through it
and it pumps heat from one face to the other (Peltier cooling); hold a temperature difference across
it and it produces a voltage (Seebeck generation). With no moving parts it is the refrigeration of
:mod:`anvilate.analysis.refrigeration` reduced to electrons, and the energy conversion of
:mod:`anvilate.analysis.solar_pv` running on heat instead of light. Its performance is bounded by
three closed-form relations.

The Seebeck effect gives the open-circuit voltage a temperature difference produces, V = α·ΔT, from
the module's Seebeck coefficient α — the basis of every thermocouple and thermoelectric generator.
Run in reverse as a cooler, the net heat lifted from the cold face is a balance of three terms,
Q_c = α·I·T_c − ½·I²·R − K·ΔT: the Peltier pumping α·I·T_c, less the half of the Joule heat ½·I²·R
that flows back to the cold side, less the conduction K·ΔT leaking down the gradient. That Joule
term is why more current does not mean more cooling forever, and it sets a hard ceiling: the
greatest temperature difference a single stage can hold, ΔT_max = ½·Z·T_c² with the figure of merit
Z = α²/(R·K) — the coldest the module reaches with no heat load.

Sources: Goldsmid, *Introduction to Thermoelectricity* — the Seebeck voltage from a junction
temperature difference, the Peltier cooling rate, the figure of merit Z and the dimensionless
ZT, and the maximum temperature difference, efficiency and coefficient of performance those
imply.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity
from ..units.temperature import temperature_difference_kelvin

__all__ = [
    "peltier_cooling_rate",
    "seebeck_voltage",
    "thermoelectric_figure_of_merit",
    "thermoelectric_max_cop",
    "thermoelectric_max_efficiency",
    "thermoelectric_zt",
    "thermoelectric_max_temperature_difference",
]


def seebeck_voltage(*, seebeck_coefficient: Quantity, temperature_difference: Quantity) -> Quantity:
    """The Seebeck open-circuit voltage, V = α·ΔT.

    The voltage a thermoelectric module (or thermocouple) develops across a temperature difference:
    the ``seebeck_coefficient`` α times the ``temperature_difference`` ΔT across it: V = α·ΔT.
    It is the basis of thermocouple thermometry and of thermoelectric power generation — the larger
    the temperature drop, the more voltage the module makes. Returns the voltage in V.
    """
    _check(seebeck_coefficient, "[electric_potential]/[temperature]", "seebeck_coefficient")
    _check(temperature_difference, "[temperature]", "temperature_difference")
    alpha = seebeck_coefficient.to("V/K").magnitude
    dt = temperature_difference_kelvin(temperature_difference, name="temperature_difference")
    if alpha <= 0:
        raise ValueError("seebeck_coefficient must be positive")
    if dt <= 0:
        raise ValueError("temperature_difference must be positive")
    return Quantity(magnitude=alpha * dt, unit="V")


def peltier_cooling_rate(
    *,
    seebeck_coefficient: Quantity,
    current: Quantity,
    cold_temperature: Quantity,
    electrical_resistance: Quantity,
    thermal_conductance: Quantity,
    temperature_difference: Quantity,
) -> Quantity:
    """The net Peltier cooling at the cold face, Q_c = α·I·T_c − ½·I²·R − K·ΔT.

    The heat a thermoelectric cooler lifts from its cold face: the Peltier pumping α·I·T_c, from the
    ``seebeck_coefficient`` α, ``current`` I, and absolute ``cold_temperature`` T_c — less
    the half of the Joule heat ½·I²·R (``electrical_resistance`` R) that returns to the cold side,
    less the conduction K·ΔT leaking down the gradient (``thermal_conductance`` K over the
    ``temperature_difference`` ΔT). Raising the current lifts the Peltier term linearly but Joule
    term quadratically, so cooling peaks and then falls; a negative result means the current cannot
    hold that ΔT. Returns the cooling rate in W.
    """
    _check(seebeck_coefficient, "[electric_potential]/[temperature]", "seebeck_coefficient")
    _check(current, "[current]", "current")
    _check(cold_temperature, "[temperature]", "cold_temperature")
    _check(electrical_resistance, "[resistance]", "electrical_resistance")
    _check(thermal_conductance, "[power]/[temperature]", "thermal_conductance")
    _check(temperature_difference, "[temperature]", "temperature_difference")
    alpha = seebeck_coefficient.to("V/K").magnitude
    i = current.to("A").magnitude
    t_c = cold_temperature.to("K").magnitude
    r = electrical_resistance.to("ohm").magnitude
    k = thermal_conductance.to("W/K").magnitude
    dt = temperature_difference_kelvin(temperature_difference, name="temperature_difference")
    if alpha <= 0:
        raise ValueError("seebeck_coefficient must be positive")
    if i <= 0:
        raise ValueError("current must be positive")
    if t_c <= 0:
        raise ValueError("cold_temperature must be positive (absolute, in K)")
    if r <= 0:
        raise ValueError("electrical_resistance must be positive")
    if k <= 0:
        raise ValueError("thermal_conductance must be positive")
    if dt < 0:
        raise ValueError("temperature_difference must be non-negative")
    q_c = alpha * i * t_c - 0.5 * i * i * r - k * dt
    return Quantity(magnitude=q_c, unit="W")


def thermoelectric_figure_of_merit(
    *,
    seebeck_coefficient: Quantity,
    electrical_resistance: Quantity,
    thermal_conductance: Quantity,
) -> Quantity:
    """The thermoelectric figure of merit, Z = α²/(R·K).

    The device figure of merit that sets how good a thermoelectric module is: Z = α²/(R·K), from the
    ``seebeck_coefficient`` α, the ``electrical_resistance`` R, and the ``thermal_conductance`` K.
    A high α makes voltage, but a low R (to limit Joule heating) and a low K (to limit conduction
    leaking heat back down the gradient) matter just as much — Z packages the three-way trade-off
    into one number. It sets the single-stage cooling limit
    (:func:`thermoelectric_max_temperature_difference`, ΔT_max = ½·Z·T_c²) and, multiplied by
    temperature, the dimensionless ZT (:func:`thermoelectric_zt`). Returns Z in units of 1/K.
    """
    _check(seebeck_coefficient, "[electric_potential]/[temperature]", "seebeck_coefficient")
    _check(electrical_resistance, "[resistance]", "electrical_resistance")
    _check(thermal_conductance, "[power]/[temperature]", "thermal_conductance")
    alpha = seebeck_coefficient.to("V/K").magnitude
    r = electrical_resistance.to("ohm").magnitude
    k = thermal_conductance.to("W/K").magnitude
    if alpha <= 0:
        raise ValueError("seebeck_coefficient must be positive")
    if r <= 0:
        raise ValueError("electrical_resistance must be positive")
    if k <= 0:
        raise ValueError("thermal_conductance must be positive")
    return Quantity(magnitude=alpha * alpha / (r * k), unit="1/K")


def thermoelectric_zt(*, figure_of_merit: Quantity, temperature: Quantity) -> float:
    """The dimensionless thermoelectric figure of merit, ZT = Z·T.

    The benchmark by which thermoelectric materials and modules are ranked: the ``figure_of_merit``
    Z (from :func:`thermoelectric_figure_of_merit`, units 1/K) times the absolute ``temperature`` T
    at which the device operates. ZT is dimensionless — around 1 for commercial bismuth-telluride
    near room temperature, and ZT ≳ 2–3 is the target for thermoelectric power generation to rival
    other converters. A higher ZT means both a colder single-stage ΔT_max as a cooler and a higher
    Carnot-fraction efficiency as a generator. Returns the dimensionless ZT as a plain float.
    """
    _check(figure_of_merit, "1/[temperature]", "figure_of_merit")
    _check(temperature, "[temperature]", "temperature")
    z = figure_of_merit.to("1/K").magnitude
    t = temperature.to("K").magnitude
    if z < 0:
        raise ValueError("figure_of_merit must be non-negative")
    if t <= 0:
        raise ValueError("temperature must be positive (absolute, in K)")
    return z * t


def thermoelectric_max_temperature_difference(
    *,
    seebeck_coefficient: Quantity,
    electrical_resistance: Quantity,
    thermal_conductance: Quantity,
    cold_temperature: Quantity,
) -> Quantity:
    """The single-stage cooling limit, ΔT_max = ½·Z·T_c² with Z = α²/(R·K).

    The greatest temperature difference a single-stage thermoelectric cooler can hold with no heat
    load: from the module figure of merit Z = α²/(R·K) — the ``seebeck_coefficient`` α, the
    ``electrical_resistance`` R, and the ``thermal_conductance`` K — and the absolute
    ``cold_temperature`` T_c, ΔT_max = ½·Z·T_c². It is the hard ceiling of the device: no current
    can pull the cold face colder than this, and reaching a larger drop needs cascaded stages. A
    higher figure of merit Z·T buys a deeper ΔT_max. Returns the max temperature difference in K.
    """
    _check(seebeck_coefficient, "[electric_potential]/[temperature]", "seebeck_coefficient")
    _check(electrical_resistance, "[resistance]", "electrical_resistance")
    _check(thermal_conductance, "[power]/[temperature]", "thermal_conductance")
    _check(cold_temperature, "[temperature]", "cold_temperature")
    alpha = seebeck_coefficient.to("V/K").magnitude
    r = electrical_resistance.to("ohm").magnitude
    k = thermal_conductance.to("W/K").magnitude
    t_c = cold_temperature.to("K").magnitude
    if alpha <= 0:
        raise ValueError("seebeck_coefficient must be positive")
    if r <= 0:
        raise ValueError("electrical_resistance must be positive")
    if k <= 0:
        raise ValueError("thermal_conductance must be positive")
    if t_c <= 0:
        raise ValueError("cold_temperature must be positive (absolute, in K)")
    z = alpha * alpha / (r * k)
    return Quantity(magnitude=0.5 * z * t_c * t_c, unit="K")


def thermoelectric_max_efficiency(
    *,
    figure_of_merit: Quantity,
    cold_temperature: Quantity,
    hot_temperature: Quantity,
) -> float:
    """The maximum efficiency of a thermoelectric generator, η_max = η_C·(M − 1)/(M + T_c/T_h).

    Run the same module backwards — hold a temperature difference across it instead of driving
    current through it — and it generates power instead of pumping heat. This is the generation
    counterpart of :func:`thermoelectric_max_cop`: with M = √(1 + Z·T_m) at the mean temperature
    T_m = (T_h + T_c)/2, the best efficiency a single stage reaches converting heat drawn at the
    ``hot_temperature`` T_h and rejected at the ``cold_temperature`` T_c is
    η_max = ((T_h − T_c)/T_h)·(M − 1)/(M + T_c/T_h) — the Carnot efficiency times a material penalty
    set entirely by the device ``figure_of_merit`` Z (from :func:`thermoelectric_figure_of_merit`).
    The penalty is severe: a good ZT ≈ 1 module reaches only about a fifth of Carnot, which is why
    thermoelectric generators are chosen for having no moving parts (spacecraft RTGs, waste-heat
    scavengers) rather than for efficiency. It approaches Carnot only as ZT → ∞. Returns the
    dimensionless maximum efficiency.
    """
    _check(figure_of_merit, "1/[temperature]", "figure_of_merit")
    _check(cold_temperature, "[temperature]", "cold_temperature")
    _check(hot_temperature, "[temperature]", "hot_temperature")
    z = figure_of_merit.to("1/K").magnitude
    t_c = cold_temperature.to("K").magnitude
    t_h = hot_temperature.to("K").magnitude
    if z < 0:
        raise ValueError("figure_of_merit must be non-negative")
    if t_c <= 0 or t_h <= 0:
        raise ValueError("temperatures must be positive (absolute, in K)")
    if t_h <= t_c:
        raise ValueError("hot_temperature must exceed cold_temperature to generate power")
    m = sqrt(1.0 + z * 0.5 * (t_h + t_c))
    return (t_h - t_c) / t_h * (m - 1.0) / (m + t_c / t_h)


def thermoelectric_max_cop(
    *,
    figure_of_merit: Quantity,
    cold_temperature: Quantity,
    hot_temperature: Quantity,
) -> float:
    """The maximum COP of a thermoelectric cooler, COP_max = (T_c/ΔT)·(M − T_h/T_c)/(M + 1).

    The best coefficient of performance a single-stage Peltier cooler reaches, pumping heat from the
    ``cold_temperature`` T_c to the ``hot_temperature`` T_h with a device ``figure_of_merit`` Z
    (from :func:`thermoelectric_figure_of_merit`): with M = √(1 + Z·T_m) at the mean temperature
    T_m = (T_h + T_c)/2, COP_max = (T_c/(T_h − T_c))·(M − T_h/T_c)/(M + 1). It is the thermoelectric
    analogue of the Carnot COP, which it approaches only as ZT → ∞; a real ZT ≈ 1 module manages a
    small fraction of Carnot, the reason Peltier coolers are prized for convenience, not efficiency.
    Returns the dimensionless maximum COP.
    """
    _check(figure_of_merit, "1/[temperature]", "figure_of_merit")
    _check(cold_temperature, "[temperature]", "cold_temperature")
    _check(hot_temperature, "[temperature]", "hot_temperature")
    z = figure_of_merit.to("1/K").magnitude
    t_c = cold_temperature.to("K").magnitude
    t_h = hot_temperature.to("K").magnitude
    if z < 0:
        raise ValueError("figure_of_merit must be non-negative")
    if t_c <= 0 or t_h <= 0:
        raise ValueError("temperatures must be positive (absolute, in K)")
    if t_h <= t_c:
        raise ValueError("hot_temperature must exceed cold_temperature for cooling")
    t_m = 0.5 * (t_h + t_c)
    m = sqrt(1.0 + z * t_m)
    if m <= t_h / t_c:
        raise ValueError(
            "figure_of_merit is too low to pump heat across this temperature difference "
            "(COP would be non-positive)"
        )
    return (t_c / (t_h - t_c)) * (m - t_h / t_c) / (m + 1.0)


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
