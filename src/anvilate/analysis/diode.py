"""T1 analytical semiconductor-diode (Shockley) checks (closed-form).

A pn-junction diode passes current that rises exponentially with the voltage across it, following
the Shockley ideal-diode equation. This governs every rectifier, LED, and diode-based reference: a
small change in forward voltage swings the current by orders of magnitude, which is why a diode
clamps to a roughly fixed drop and why its current must be set by an external resistor, not by fine
voltage control. It is a distinct nonlinearity from the linear R-L-C elements of
:mod:`anvilate.analysis.reactive_circuit`.

The exponential is scaled by the thermal voltage V_T = k*T/q (about 25.85 mV at 300 K), the natural
voltage scale of carriers at temperature T. The current is then I = I_s * (exp(V/(n*V_T)) - 1), from
the saturation current I_s (the tiny reverse leakage), the applied voltage V, and the ideality
factor n (1 for an ideal junction, up to ~2 with recombination). Inverting it, the forward voltage
at a target current is V = n*V_T*ln(I/I_s + 1) — how the operating point of a diode or LED is found.

Temperature is taken as an absolute temperature (kelvin); V_T is proportional to it.
"""

from __future__ import annotations

from math import expm1, log

from ..units import Quantity

_BOLTZMANN = 1.380649e-23  # J/K
_ELEMENTARY_CHARGE = 1.602176634e-19  # C

__all__ = [
    "diode_current",
    "diode_voltage",
    "thermal_voltage",
]


def thermal_voltage(*, temperature: Quantity) -> Quantity:
    """The thermal voltage, V_T = k*T/q.

    The natural voltage scale of charge carriers at an absolute ``temperature`` T: V_T = k*T/q,
    about 25.85 mV at 300 K. It sets how much forward voltage raises the diode current by a factor
    of e, and it rises with temperature. Returns the thermal voltage in V.
    """
    _check(temperature, "[temperature]", "temperature")
    t = temperature.to("K").magnitude
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    return Quantity(magnitude=_BOLTZMANN * t / _ELEMENTARY_CHARGE, unit="V")


def diode_current(
    *,
    saturation_current: Quantity,
    voltage: Quantity,
    temperature: Quantity,
    ideality_factor: float = 1.0,
) -> Quantity:
    """The diode current, I = I_s * (exp(V/(n*V_T)) - 1).

    The Shockley ideal-diode current: the ``saturation_current`` I_s (reverse leakage) times the
    exponential of the applied ``voltage`` V over n times the thermal voltage (set by the absolute
    ``temperature`` T), less one, with ``ideality_factor`` n (1 ideal, up to ~2 with recombination).
    Forward voltage swings this by orders of magnitude; reverse voltage floors it at -I_s. Returns
    the current in A.
    """
    _check(saturation_current, "[current]", "saturation_current")
    _check(voltage, "[electric_potential]", "voltage")
    _check(temperature, "[temperature]", "temperature")
    i_s = saturation_current.to("A").magnitude
    v = voltage.to("V").magnitude
    t = temperature.to("K").magnitude
    if i_s <= 0:
        raise ValueError("saturation_current must be positive")
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    if ideality_factor <= 0:
        raise ValueError("ideality_factor must be positive")
    v_t = _BOLTZMANN * t / _ELEMENTARY_CHARGE
    return Quantity(magnitude=i_s * expm1(v / (ideality_factor * v_t)), unit="A")


def diode_voltage(
    *,
    current: Quantity,
    saturation_current: Quantity,
    temperature: Quantity,
    ideality_factor: float = 1.0,
) -> Quantity:
    """The forward voltage at a target current, V = n*V_T*ln(I/I_s + 1).

    The inverse of :func:`diode_current`: the forward voltage that drives a target forward
    ``current`` I through a diode of ``saturation_current`` I_s at absolute ``temperature`` T, with
    ``ideality_factor`` n. It is how the operating point (and the ~0.6-0.7 V drop of a silicon
    diode, or the higher drop of an LED) is found. Returns the voltage in V.
    """
    _check(current, "[current]", "current")
    _check(saturation_current, "[current]", "saturation_current")
    _check(temperature, "[temperature]", "temperature")
    i = current.to("A").magnitude
    i_s = saturation_current.to("A").magnitude
    t = temperature.to("K").magnitude
    if i <= 0:
        raise ValueError("current must be positive")
    if i_s <= 0:
        raise ValueError("saturation_current must be positive")
    if t <= 0:
        raise ValueError("temperature must be positive (absolute temperature)")
    if ideality_factor <= 0:
        raise ValueError("ideality_factor must be positive")
    v_t = _BOLTZMANN * t / _ELEMENTARY_CHARGE
    return Quantity(magnitude=ideality_factor * v_t * log(i / i_s + 1.0), unit="V")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
