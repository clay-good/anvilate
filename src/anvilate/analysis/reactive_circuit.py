"""T1 analytical reactive-component checks (energy storage and LC resonance, closed-form).

Capacitors and inductors store energy in fields rather than dissipate it, and a pair of them
exchange that energy back and forth at a resonant frequency — the relations power-electronics and
filter design lean on.

A capacitor holds E = ½·C·V² in its electric field, from the ``capacitance`` C and the ``voltage`` V
across it — the energy a DC-link or snubber capacitor must absorb, or a flash bank must dump. An
inductor holds E = ½·L·I² in its magnetic field, from the ``inductance`` L and the ``current`` I —
the energy that must go somewhere when a switch opens, which is why inductive circuits need
freewheeling paths.

Put the two together and the energy sloshes between them at the LC resonant frequency
f₀ = 1/(2π·√(L·C)) — the tuning of a filter, the ring of a switching node, the frequency a tank
circuit selects.
"""

from __future__ import annotations

from math import pi, sqrt

from ..units import Quantity

__all__ = [
    "capacitor_stored_energy",
    "inductor_stored_energy",
    "lc_resonant_frequency",
]


def capacitor_stored_energy(*, capacitance: Quantity, voltage: Quantity) -> Quantity:
    """The energy stored in a capacitor, E = ½·C·V².

    The energy held in a capacitor's electric field, E = ½·C·V², from the ``capacitance`` C and the
    ``voltage`` V across it. It rises with the *square* of voltage, so a capacitor charged to twice
    the voltage holds four times the energy — the number that sizes a DC-link or snubber capacitor
    for the transient it must ride, and that a discharge (a flash lamp, a spot welder) delivers.
    Returns the stored energy in joules.
    """
    _check(capacitance, "[capacitance]", "capacitance")
    _check(voltage, "[electric_potential]", "voltage")
    c = capacitance.to("F").magnitude
    v = voltage.to("V").magnitude
    if c <= 0:
        raise ValueError("capacitance must be positive")
    return Quantity(magnitude=0.5 * c * v**2, unit="J")


def inductor_stored_energy(*, inductance: Quantity, current: Quantity) -> Quantity:
    """The energy stored in an inductor, E = ½·L·I².

    The energy held in an inductor's magnetic field, E = ½·L·I², from the ``inductance`` L and the
    ``current`` I through it. Rising with the square of current, it is the energy that has to go
    somewhere the instant a switch interrupts the current — dumped into a freewheeling diode or a
    snubber, or it appears as a destructive arc across the opening contacts. Returns the energy in
    joules.
    """
    _check(inductance, "[inductance]", "inductance")
    _check(current, "[current]", "current")
    length = inductance.to("H").magnitude
    i = current.to("A").magnitude
    if length <= 0:
        raise ValueError("inductance must be positive")
    return Quantity(magnitude=0.5 * length * i**2, unit="J")


def lc_resonant_frequency(*, inductance: Quantity, capacitance: Quantity) -> Quantity:
    """The resonant frequency of an LC circuit, f₀ = 1/(2π·√(L·C)).

    An inductor and capacitor trade energy back and forth at a natural frequency set only by their
    values: f₀ = 1/(2π·√(L·C)), from the ``inductance`` L and ``capacitance`` C. It is the tuning of
    an LC filter or oscillator, the frequency a switching node rings at, and the pole a resonant
    converter is driven around. Returns the resonant frequency in hertz.
    """
    _check(inductance, "[inductance]", "inductance")
    _check(capacitance, "[capacitance]", "capacitance")
    length = inductance.to("H").magnitude
    c = capacitance.to("F").magnitude
    if length <= 0 or c <= 0:
        raise ValueError("inductance and capacitance must be positive")
    return Quantity(magnitude=1.0 / (2.0 * pi * sqrt(length * c)), unit="Hz")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
