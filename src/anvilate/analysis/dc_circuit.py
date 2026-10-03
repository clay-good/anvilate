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

Sources: Nilsson, *Electric Circuits* (resistive circuits) — Ohm's law, the power a resistance
dissipates, the maximum-power-transfer condition R_L = R_th, and the parallel-resistance
combination.
"""

from __future__ import annotations

from collections.abc import Sequence

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_SCHEMATIC_SOURCE = "the circuit schematic's resistor values or measured resistances"
_OPERATING_SOURCE = "the circuit's measured or specified operating current or voltage"
_SOURCE_DATASHEET = "the source's datasheet (open-circuit voltage and internal resistance)"


class _DcCircuitInputError(RefusalError, ValueError):
    """A DC-circuit input that cannot be used without correction."""


def _dc_circuit_refusal(message: str, *, subject: str, source: str) -> _DcCircuitInputError:
    return _DcCircuitInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _dc_circuit_input_source(name: str) -> str:
    if name == "current":
        return _OPERATING_SOURCE
    if name in {"source_resistance", "source_voltage"}:
        return _SOURCE_DATASHEET
    return _SCHEMATIC_SOURCE


__all__ = [
    "maximum_power_transfer",
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
        raise _dc_circuit_refusal(
            "current must be non-negative", subject="current", source=_OPERATING_SOURCE
        )
    if r < 0:
        raise _dc_circuit_refusal(
            "resistance must be non-negative", subject="resistance", source=_SCHEMATIC_SOURCE
        )
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
        raise _dc_circuit_refusal(
            "resistance must be non-negative", subject="resistance", source=_SCHEMATIC_SOURCE
        )
    return Quantity(magnitude=i * i * r, unit="W")


def maximum_power_transfer(*, source_voltage: Quantity, source_resistance: Quantity) -> Quantity:
    """The maximum power a source can deliver to a load, P_max = V_s²/(4·R_s).

    The maximum-power-transfer theorem: a source of open-circuit ``source_voltage`` V_s and internal
    ``source_resistance`` R_s delivers the most power when the load is matched to the source
    (R_load = R_s), and that peak is P_max = V_s²/(4·R_s). At the match the load and the internal
    resistance drop equal halves of V_s, so exactly half the power is lost inside the source — the
    transfer is efficient in power delivered but only 50% efficient, which is why power systems
    deliberately run un-matched (R_load ≫ R_s) while signal and RF stages match for maximum
    transfer. It caps what a battery, amplifier, antenna, or thermoelectric source can drive.
    Returns the maximum load power in W.
    """
    _check(source_voltage, "[electric_potential]", "source_voltage")
    _check(source_resistance, "[resistance]", "source_resistance")
    v_s = source_voltage.to("V").magnitude
    r_s = source_resistance.to("ohm").magnitude
    if v_s < 0:
        raise _dc_circuit_refusal(
            "source_voltage must be non-negative",
            subject="source_voltage",
            source=_SOURCE_DATASHEET,
        )
    if r_s <= 0:
        raise _dc_circuit_refusal(
            "source_resistance must be positive",
            subject="source_resistance",
            source=_SOURCE_DATASHEET,
        )
    return Quantity(magnitude=v_s**2 / (4.0 * r_s), unit="W")


def parallel_resistance(*, resistances: Sequence[Quantity]) -> Quantity:
    """The parallel equivalent resistance, R = 1/Σ(1/Rᵢ).

    The single resistance equivalent to the ``resistances`` Rᵢ wired in parallel: R = 1/Σ(1/Rᵢ). It
    is always smaller than the smallest branch, since each added path gives the current another way
    through. Returns the equivalent resistance in ohm.
    """
    if not isinstance(resistances, Sequence):
        raise _dc_circuit_refusal(
            f"resistances must be a sequence, not a single value; got {resistances!r}",
            subject="resistances",
            source=_SCHEMATIC_SOURCE,
        )
    if len(resistances) == 0:
        raise _dc_circuit_refusal(
            "resistances must contain at least one resistor",
            subject="resistances",
            source=_SCHEMATIC_SOURCE,
        )
    conductance_sum = 0.0
    for idx, res in enumerate(resistances):
        _check(res, "[resistance]", f"resistances[{idx}]")
        r = res.to("ohm").magnitude
        if r <= 0:
            raise _dc_circuit_refusal(
                "each resistance must be positive", subject="resistances", source=_SCHEMATIC_SOURCE
            )
        conductance_sum += 1.0 / r
    return Quantity(magnitude=1.0 / conductance_sum, unit="ohm")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _dc_circuit_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_dc_circuit_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _dc_circuit_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_dc_circuit_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
