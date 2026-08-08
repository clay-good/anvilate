"""T1 analytical DC-circuit (Ohm's law) checks (closed-form).

The most basic electrical relations govern a resistive DC circuit: Ohm's law ties the voltage across
a resistor to the current through it, the power it dissipates follows, and resistors in parallel
combine into a smaller equivalent. These underlie the practical AC feeder and machine relations of
:mod:`anvilate.analysis.electrical` (which handle three-phase power, conductor sizing, and motors)
and the reactive components of :mod:`anvilate.analysis.reactive_circuit`.

Ohm's law gives the voltage V = I·R across a resistance R carrying a current I. The electrical work
that current does against the resistance turns into heat at the rate P = I²·R (equivalently V²/R or
V·I) — the Joule heating that sizes a resistor's wattage. Resistors wired in parallel share the
current and present a combined resistance R = 1/Σ(1/Rᵢ), always smaller than the smallest branch,
because adding a path only makes it easier for current to flow. Inputs and outputs are
dimension-checked :class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..units import Quantity

__all__ = [
    "ohms_law_voltage",
    "parallel_resistance",
    "resistive_power",
]


def ohms_law_voltage(*, current: Quantity, resistance: Quantity) -> Quantity:
    """Ohm's law, V = I·R.

    The voltage across a resistor of ``resistance`` R carrying a ``current`` I: V = I·R. It is the
    drop a current develops across a resistance — the reading a voltmeter shows across the element.
    Returns the voltage in V.
    """
    _check(current, "[current]", "current")
    _check(resistance, "[resistance]", "resistance")
    i = current.to("A").magnitude
    r = resistance.to("ohm").magnitude
    if i < 0:
        raise ValueError("current must be non-negative")
    if r < 0:
        raise ValueError("resistance must be non-negative")
    return Quantity(magnitude=i * r, unit="V")


def resistive_power(*, current: Quantity, resistance: Quantity) -> Quantity:
    """The resistive (Joule) power, P = I²·R.

    The power a resistor of ``resistance`` R dissipates as heat while carrying a ``current`` I:
    P = I²·R (equivalently V·I or V²/R). It rises with the square of current, which is why a small
    overcurrent overheats a component. Returns the power in W.
    """
    _check(current, "[current]", "current")
    _check(resistance, "[resistance]", "resistance")
    i = current.to("A").magnitude
    r = resistance.to("ohm").magnitude
    if r < 0:
        raise ValueError("resistance must be non-negative")
    return Quantity(magnitude=i * i * r, unit="W")


def parallel_resistance(*, resistances: Sequence[Quantity]) -> Quantity:
    """The parallel equivalent resistance, R = 1/Σ(1/Rᵢ).

    The single resistance equivalent to the ``resistances`` Rᵢ wired in parallel: R = 1/Σ(1/Rᵢ). It
    is always smaller than the smallest branch, since each added path gives the current another way
    through. Returns the equivalent resistance in ohm.
    """
    if len(resistances) == 0:
        raise ValueError("resistances must contain at least one resistor")
    conductance_sum = 0.0
    for idx, res in enumerate(resistances):
        _check(res, "[resistance]", f"resistances[{idx}]")
        r = res.to("ohm").magnitude
        if r <= 0:
            raise ValueError("each resistance must be positive")
        conductance_sum += 1.0 / r
    return Quantity(magnitude=1.0 / conductance_sum, unit="ohm")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
