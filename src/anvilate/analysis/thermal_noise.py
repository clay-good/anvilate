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

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite
from ..units.rotation import count_rate_per_second

_COMPONENT_SOURCE = "the schematic's resistor value or measured source resistance"
_TEMPERATURE_SOURCE = "the component's absolute operating temperature"
_BANDWIDTH_SOURCE = "the measurement system's equivalent noise bandwidth"


class _ThermalNoiseInputError(RefusalError, ValueError):
    """A thermal-noise input that cannot be used without correction."""


def _thermal_noise_refusal(message: str, *, subject: str, source: str) -> _ThermalNoiseInputError:
    return _ThermalNoiseInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _thermal_noise_input_source(name: str) -> str:
    if name == "temperature":
        return _TEMPERATURE_SOURCE
    if name == "bandwidth":
        return _BANDWIDTH_SOURCE
    return _COMPONENT_SOURCE


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
        raise _thermal_noise_refusal(
            "resistance must be positive", subject="resistance", source=_COMPONENT_SOURCE
        )
    if t <= 0:
        raise _thermal_noise_refusal(
            "temperature must be positive (absolute temperature)",
            subject="temperature",
            source=_TEMPERATURE_SOURCE,
        )
    if b < 0:
        raise _thermal_noise_refusal(
            "bandwidth must be non-negative", subject="bandwidth", source=_BANDWIDTH_SOURCE
        )
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
        raise _thermal_noise_refusal(
            "temperature must be positive (absolute temperature)",
            subject="temperature",
            source=_TEMPERATURE_SOURCE,
        )
    if b < 0:
        raise _thermal_noise_refusal(
            "bandwidth must be non-negative", subject="bandwidth", source=_BANDWIDTH_SOURCE
        )
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
        raise _thermal_noise_refusal(
            "resistance must be positive", subject="resistance", source=_COMPONENT_SOURCE
        )
    if t <= 0:
        raise _thermal_noise_refusal(
            "temperature must be positive (absolute temperature)",
            subject="temperature",
            source=_TEMPERATURE_SOURCE,
        )
    if b < 0:
        raise _thermal_noise_refusal(
            "bandwidth must be non-negative", subject="bandwidth", source=_BANDWIDTH_SOURCE
        )
    return Quantity(magnitude=sqrt(4.0 * _BOLTZMANN * t * b / r), unit="A")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _thermal_noise_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_thermal_noise_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _thermal_noise_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_thermal_noise_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
