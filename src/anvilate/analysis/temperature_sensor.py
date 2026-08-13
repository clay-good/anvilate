"""T1 analytical resistance temperature-sensor characteristics (closed-form).

A resistance thermometer turns temperature into a resistance a bridge or divider can read. Two kinds
dominate: the platinum RTD, whose resistance rises almost linearly with temperature, and the NTC
thermistor, whose resistance falls steeply and exponentially. This module gives their forward and
inverse characteristics — the resistance-side companion to the strain gauge of
:mod:`anvilate.analysis.strain_gauge` and the thermocouple Seebeck voltage of
:mod:`anvilate.analysis.thermoelectric`.

A platinum RTD (Pt100 reads 100 Ω at 0 °C) follows R = R₀·[1 + α·(T − T₀)] over its working range,
with the temperature coefficient α ≈ 0.00385 /K for industrial platinum — nearly linear, which is
why RTDs are the accurate, stable choice. Inverting it reads temperature straight off the measured
resistance. An NTC thermistor is far more sensitive but exponential: R = R₀·exp[β·(1/T − 1/T₀)] by
the β-parameter model, the same 1/T law as an Arrhenius rate, so its resistance can swing by orders
of magnitude across a modest span. Temperatures must be absolute; the coefficient α is a plain float
(per kelvin) and β a temperature. Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import exp

from ..units import Quantity

__all__ = [
    "rtd_resistance",
    "rtd_temperature",
    "thermistor_resistance",
    "thermocouple_voltage",
    "thermocouple_temperature_from_voltage",
]


def rtd_resistance(
    *,
    reference_resistance: Quantity,
    temperature_coefficient: float,
    temperature: Quantity,
    reference_temperature: Quantity,
) -> Quantity:
    """An RTD's resistance, R = R₀·[1 + α·(T − T₀)].

    The (near-linear) resistance of a platinum RTD at ``temperature`` T, from its
    ``reference_resistance`` R₀ at ``reference_temperature`` T₀ (100 Ω at 0 °C for a Pt100) and the
    ``temperature_coefficient`` α (≈ 0.00385 /K for industrial platinum): R = R₀·[1 + α·(T − T₀)].
    The temperatures must be absolute (their difference is what matters). Returns the resistance in
    the units of ``reference_resistance``.
    """
    _check(reference_resistance, "[resistance]", "reference_resistance")
    _check(temperature, "[temperature]", "temperature")
    _check(reference_temperature, "[temperature]", "reference_temperature")
    r0 = reference_resistance.to("ohm").magnitude
    t = temperature.to("K").magnitude
    t0 = reference_temperature.to("K").magnitude
    if r0 <= 0:
        raise ValueError("reference_resistance must be positive")
    if t <= 0 or t0 <= 0:
        raise ValueError("temperatures must be positive absolute (kelvin) values")
    r = r0 * (1.0 + temperature_coefficient * (t - t0))
    if r <= 0:
        raise ValueError("computed resistance is non-positive (temperature below the sensor range)")
    return Quantity(magnitude=r, unit="ohm")


def rtd_temperature(
    *,
    resistance: Quantity,
    reference_resistance: Quantity,
    temperature_coefficient: float,
    reference_temperature: Quantity,
) -> Quantity:
    """The temperature an RTD reads, T = T₀ + (R/R₀ − 1)/α.

    The measurement inverse of :func:`rtd_resistance`: the temperature a platinum RTD reads, from
    measured ``resistance`` R, its ``reference_resistance`` R₀ at ``reference_temperature`` T₀, and
    the ``temperature_coefficient`` α: T = T₀ + (R/R₀ − 1)/α. This is what a data-acquisition system
    computes from the four-wire resistance reading. α must be non-zero and T₀ absolute. Returns the
    temperature in kelvin.
    """
    _check(resistance, "[resistance]", "resistance")
    _check(reference_resistance, "[resistance]", "reference_resistance")
    _check(reference_temperature, "[temperature]", "reference_temperature")
    r = resistance.to("ohm").magnitude
    r0 = reference_resistance.to("ohm").magnitude
    t0 = reference_temperature.to("K").magnitude
    if r <= 0 or r0 <= 0:
        raise ValueError("resistance and reference_resistance must be positive")
    if t0 <= 0:
        raise ValueError("reference_temperature must be positive absolute (kelvin)")
    if temperature_coefficient == 0:
        raise ValueError("temperature_coefficient must be non-zero")
    t = t0 + (r / r0 - 1.0) / temperature_coefficient
    if t <= 0:
        raise ValueError("computed temperature is non-positive (check the resistance and inputs)")
    return Quantity(magnitude=t, unit="K")


def thermistor_resistance(
    *,
    reference_resistance: Quantity,
    beta_constant: Quantity,
    temperature: Quantity,
    reference_temperature: Quantity,
) -> Quantity:
    """An NTC thermistor's resistance, R = R₀·exp[β·(1/T − 1/T₀)].

    The exponentially falling resistance of an NTC thermistor at ``temperature`` T, by the
    β-parameter model: R = R₀·exp[β·(1/T − 1/T₀)], from the ``reference_resistance`` R₀ at
    ``reference_temperature`` T₀ (often 10 kΩ at 25 °C) and the material ``beta_constant`` β (a
    temperature, ≈ 3000–4000 K). Because it depends on 1/T (an Arrhenius law), the resistance is
    sensitive — it can drop by half over ~15 K — giving a thermistor fine resolution over a narrow
    band. Temperatures must be absolute. Returns the resistance in the units of
    ``reference_resistance``.
    """
    _check(reference_resistance, "[resistance]", "reference_resistance")
    _check(beta_constant, "[temperature]", "beta_constant")
    _check(temperature, "[temperature]", "temperature")
    _check(reference_temperature, "[temperature]", "reference_temperature")
    r0 = reference_resistance.to("ohm").magnitude
    beta = beta_constant.to("K").magnitude
    t = temperature.to("K").magnitude
    t0 = reference_temperature.to("K").magnitude
    if r0 <= 0:
        raise ValueError("reference_resistance must be positive")
    if beta <= 0:
        raise ValueError("beta_constant must be positive")
    if t <= 0 or t0 <= 0:
        raise ValueError("temperatures must be positive absolute (kelvin) values")
    return Quantity(magnitude=r0 * exp(beta * (1.0 / t - 1.0 / t0)), unit="ohm")


def thermocouple_voltage(
    *,
    seebeck_coefficient: Quantity,
    measured_temperature: Quantity,
    reference_temperature: Quantity,
) -> Quantity:
    """A thermocouple's Seebeck EMF, V = S·(T − T_ref).

    A junction of two dissimilar metals develops a small voltage set by the temperature *difference*
    between the measuring and reference (cold) junctions: V = S·(``measured_temperature`` T −
    ``reference_temperature`` T_ref), with ``seebeck_coefficient`` S the pair's thermoelectric
    sensitivity (about 41 µV/K for a type-K couple). It is the third temperature sensor beside the
    RTD (:func:`rtd_resistance`) and thermistor (:func:`thermistor_resistance`) — no excitation
    current, wide range, but a tiny, cold-junction-referenced signal. Temperatures must be absolute
    (their difference is what matters); a hotter measuring junction raises the EMF. Returns the
    voltage in millivolts.
    """
    _check(seebeck_coefficient, "[electric_potential]/[temperature]", "seebeck_coefficient")
    _check(measured_temperature, "[temperature]", "measured_temperature")
    _check(reference_temperature, "[temperature]", "reference_temperature")
    s = seebeck_coefficient.to("V/K").magnitude
    t = measured_temperature.to("K").magnitude
    t_ref = reference_temperature.to("K").magnitude
    if s <= 0:
        raise ValueError("seebeck_coefficient must be positive")
    return Quantity(magnitude=s * (t - t_ref) * 1000.0, unit="mV")


def thermocouple_temperature_from_voltage(
    *,
    thermocouple_voltage: Quantity,
    seebeck_coefficient: Quantity,
    reference_temperature: Quantity,
) -> Quantity:
    """The junction temperature from a thermocouple EMF, T = T_ref + V/S.

    The readback inverse of :func:`thermocouple_voltage`, with cold-junction compensation built in:
    a measured ``thermocouple_voltage`` V referenced to a known ``reference_temperature`` T_ref
    (the cold junction, itself measured by an RTD or thermistor at the terminal block) gives the hot
    junction's temperature T = T_ref + V/S, from the ``seebeck_coefficient`` S. This is exactly what
    a thermocouple instrument computes — the raw EMF plus the cold-junction temperature — so a wrong
    reference biases every reading. Returns the measured temperature in kelvin.
    """
    _check(thermocouple_voltage, "[electric_potential]", "thermocouple_voltage")
    _check(seebeck_coefficient, "[electric_potential]/[temperature]", "seebeck_coefficient")
    _check(reference_temperature, "[temperature]", "reference_temperature")
    v = thermocouple_voltage.to("V").magnitude
    s = seebeck_coefficient.to("V/K").magnitude
    t_ref = reference_temperature.to("K").magnitude
    if s <= 0:
        raise ValueError("seebeck_coefficient must be positive")
    return Quantity(magnitude=t_ref + v / s, unit="K")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
