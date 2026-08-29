"""T1 analytical Johnson-Nyquist thermal-noise checks (closed-form).

The random thermal motion of charge carriers in any resistor generates a small fluctuating voltage
across it — Johnson-Nyquist noise — even with no current flowing. It sets the noise floor of every
amplifier, sensor, and measurement, and no circuit at a given temperature and bandwidth can read a
signal cleanly below it. This is the fundamental electrical noise the electronics of
:mod:`anvilate.analysis.diode` and :mod:`anvilate.analysis.reactive_circuit` sit on top of.

The open-circuit noise voltage over a bandwidth B is V_rms = sqrt(4*k*T*R*B), from the Boltzmann
constant k, the absolute temperature T, and the resistance R — colder, lower-R, narrower-band
front ends are quieter. The available noise power a source can deliver to a matched load is simply
P = k*T*B, independent of R (about -174 dBm in a 1 Hz band at 290 K, the reference noise floor of RF
engineering). The short-circuit noise current is the dual, I_rms = sqrt(4*k*T*B/R).

Sources: Sedra & Smith, *Microelectronic Circuits* (noise) — the Johnson-Nyquist thermal noise
voltage of a resistance in a bandwidth, the available noise power kTB, and the equivalent noise
current.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity
from ..units.rotation import count_rate_per_second

_BOLTZMANN = 1.380649e-23  # J/K

__all__ = [
    "johnson_noise_current",
    "johnson_noise_power",
    "johnson_noise_voltage",
]


def johnson_noise_voltage(
    *, resistance: Quantity, temperature: Quantity, bandwidth: Quantity
) -> Quantity:
    """The Johnson noise voltage, V_rms = sqrt(4*k*T*R*B).

    The rms open-circuit thermal-noise voltage across a ``resistance`` R at absolute ``temperature``
    T over a measurement ``bandwidth`` B, V_rms = sqrt(4*k*T*R*B). It is the noise floor a voltage
    measurement or amplifier input cannot beat; cooling, lowering R, or narrowing B all reduce it.
    Returns the noise voltage in V (rms).
    """
    _check(resistance, "[electric_potential]/[current]", "resistance")
    _check(temperature, "[temperature]", "temperature")
    _check(bandwidth, "1/[time]", "bandwidth")
    r = resistance.to("ohm").magnitude
    t = temperature.to("K").magnitude
    b = count_rate_per_second(bandwidth, name="bandwidth")
    if r <= 0:
        raise ValueError("resistance must be positive")
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    if b < 0:
        raise ValueError("bandwidth must be non-negative")
    return Quantity(magnitude=sqrt(4.0 * _BOLTZMANN * t * r * b), unit="V")


def johnson_noise_power(*, temperature: Quantity, bandwidth: Quantity) -> Quantity:
    """The available thermal noise power, P = k*T*B.

    The maximum noise power a resistor at absolute ``temperature`` T delivers to a matched load over
    a ``bandwidth`` B, P = k*T*B — independent of the resistance. It is about -174 dBm in a 1 Hz
    band at 290 K, the reference floor RF sensitivity is quoted against. Returns the power in W.
    """
    _check(temperature, "[temperature]", "temperature")
    _check(bandwidth, "1/[time]", "bandwidth")
    t = temperature.to("K").magnitude
    b = count_rate_per_second(bandwidth, name="bandwidth")
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    if b < 0:
        raise ValueError("bandwidth must be non-negative")
    return Quantity(magnitude=_BOLTZMANN * t * b, unit="W")


def johnson_noise_current(
    *, resistance: Quantity, temperature: Quantity, bandwidth: Quantity
) -> Quantity:
    """The Johnson noise current, I_rms = sqrt(4*k*T*B/R).

    The rms short-circuit thermal-noise current through a ``resistance`` R at absolute
    ``temperature`` T over a ``bandwidth`` B, I_rms = sqrt(4*k*T*B/R) — the current-domain dual of
    the noise voltage. It is the noise floor of a current measurement, and unlike the voltage it
    falls as R rises, so a high source resistance is quieter in current terms. Returns I in A (rms).
    """
    _check(resistance, "[electric_potential]/[current]", "resistance")
    _check(temperature, "[temperature]", "temperature")
    _check(bandwidth, "1/[time]", "bandwidth")
    r = resistance.to("ohm").magnitude
    t = temperature.to("K").magnitude
    b = count_rate_per_second(bandwidth, name="bandwidth")
    if r <= 0:
        raise ValueError("resistance must be positive")
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    if b < 0:
        raise ValueError("bandwidth must be non-negative")
    return Quantity(magnitude=sqrt(4.0 * _BOLTZMANN * t * b / r), unit="A")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
