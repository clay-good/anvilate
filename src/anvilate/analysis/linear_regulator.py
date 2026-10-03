"""T1 analytical linear-voltage-regulator dissipation checks (closed-form).

A linear regulator (an LDO or a classic three-terminal part) holds its output voltage by dropping
the excess across a series pass transistor, so every volt of headroom between input and output is
burned as heat at the full load current. That makes the regulator simple and quiet but inefficient
whenever the input sits well above the output — the reason a 12 V-to-5 V linear stage runs hot while
a switching converter does not.

The pass element dissipates P = (V_in − V_out)·I_load, and the regulator's own quiescent current
adds V_in·I_q on top; the total is the heat the package (and any heatsink) must carry. The
efficiency is just the voltage ratio scaled by the current overhead, η = V_out·I_load /
(V_in·(I_load + I_q)), which for a linear regulator can never exceed V_out/V_in — the headroom is
lost by design. These two numbers decide whether a linear part is adequate or a switcher is needed,
and whether the chosen package can shed the heat.

The relations assume the regulator is in regulation (input above output plus dropout) and a steady
load; they are the thermal-screening estimate, not a transient or startup analysis.

Sources: Sedra & Smith, *Microelectronic Circuits* (voltage regulators) — the dissipation a
linear regulator's dropout and load current impose, and the efficiency that leaves.
"""

from __future__ import annotations

from ..refusal import RefusalError, Remedy
from ..units import Quantity, require_finite

_RAIL_SOURCE = "the power-tree design (input rail and regulated output voltage)"
_LOAD_SOURCE = "the load's current budget"
_DATASHEET_SOURCE = "the regulator datasheet's quiescent (ground) current"


class _LinearRegulatorInputError(RefusalError, ValueError):
    """A linear-regulator input that cannot be used without correction."""


def _linear_regulator_refusal(
    message: str, *, subject: str, source: str
) -> _LinearRegulatorInputError:
    return _LinearRegulatorInputError(
        message,
        remedies=(Remedy(action="replace", subject=subject, source=source),),
    )


def _linear_regulator_input_source(name: str) -> str:
    if name == "load_current":
        return _LOAD_SOURCE
    if name == "quiescent_current":
        return _DATASHEET_SOURCE
    return _RAIL_SOURCE


__all__ = [
    "linear_regulator_dissipation",
    "linear_regulator_efficiency",
]


def linear_regulator_dissipation(
    *,
    input_voltage: Quantity,
    output_voltage: Quantity,
    load_current: Quantity,
    quiescent_current: Quantity | None = None,
) -> Quantity:
    """The heat a linear regulator dissipates, P = (V_in − V_out)·I_load + V_in·I_q.

    The pass transistor drops the headroom at the full load current, P = (V_in − V_out)·I_load, and
    the regulator's own ``quiescent_current`` I_q draws V_in·I_q more: the total is the power the
    package must shed. Inputs are the ``input_voltage`` V_in, the ``output_voltage`` V_out, the
    ``load_current`` I_load, and an optional ``quiescent_current`` I_q (taken as zero if omitted).
    The input must exceed the output (a linear regulator cannot boost). Compare the result against
    the package's derated dissipation to decide whether a heatsink — or a switching converter — is
    needed. Returns the dissipation in watts.
    """
    _check(input_voltage, "[electric_potential]", "input_voltage")
    _check(output_voltage, "[electric_potential]", "output_voltage")
    _check(load_current, "[current]", "load_current")
    v_in = input_voltage.to("V").magnitude
    v_out = output_voltage.to("V").magnitude
    i_load = load_current.to("A").magnitude
    i_q = _quiescent(quiescent_current)
    if v_out <= 0:
        raise _linear_regulator_refusal(
            "output_voltage must be positive", subject="output_voltage", source=_RAIL_SOURCE
        )
    if v_in <= v_out:
        raise _linear_regulator_refusal(
            "input_voltage must exceed output_voltage (a linear regulator cannot boost)",
            subject="input_voltage and output_voltage",
            source=_RAIL_SOURCE,
        )
    if i_load < 0:
        raise _linear_regulator_refusal(
            "load_current must be non-negative", subject="load_current", source=_LOAD_SOURCE
        )
    return Quantity(magnitude=(v_in - v_out) * i_load + v_in * i_q, unit="W")


def linear_regulator_efficiency(
    *,
    input_voltage: Quantity,
    output_voltage: Quantity,
    load_current: Quantity,
    quiescent_current: Quantity | None = None,
) -> float:
    """The efficiency of a linear regulator, η = V_out·I_load / (V_in·(I_load + I_q)).

    The useful output power over the input power drawn: η = V_out·I_load/(V_in·(I_load + I_q)), from
    the ``input_voltage`` V_in, ``output_voltage`` V_out, ``load_current`` I_load, and optional
    ``quiescent_current`` I_q (zero if omitted). Because a linear regulator throws away the
    headroom, its efficiency can never exceed V_out/V_in — dropping 12 V to 5 V caps it near 42%,
    which is why a large step-down is done with a switcher instead. The input must exceed the
    output. Returns the efficiency as a plain float in (0, 1).
    """
    _check(input_voltage, "[electric_potential]", "input_voltage")
    _check(output_voltage, "[electric_potential]", "output_voltage")
    _check(load_current, "[current]", "load_current")
    v_in = input_voltage.to("V").magnitude
    v_out = output_voltage.to("V").magnitude
    i_load = load_current.to("A").magnitude
    i_q = _quiescent(quiescent_current)
    if v_out <= 0:
        raise _linear_regulator_refusal(
            "output_voltage must be positive", subject="output_voltage", source=_RAIL_SOURCE
        )
    if v_in <= v_out:
        raise _linear_regulator_refusal(
            "input_voltage must exceed output_voltage (a linear regulator cannot boost)",
            subject="input_voltage and output_voltage",
            source=_RAIL_SOURCE,
        )
    if i_load <= 0:
        raise _linear_regulator_refusal(
            "load_current must be positive", subject="load_current", source=_LOAD_SOURCE
        )
    return v_out * i_load / (v_in * (i_load + i_q))


def _quiescent(quiescent_current: Quantity | None) -> float:
    if quiescent_current is None:
        return 0.0
    _check(quiescent_current, "[current]", "quiescent_current")
    i_q = quiescent_current.to("A").magnitude
    if i_q < 0:
        raise _linear_regulator_refusal(
            "quiescent_current must be non-negative",
            subject="quiescent_current",
            source=_DATASHEET_SOURCE,
        )
    return i_q


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise _linear_regulator_refusal(
            f"{name} must be a {expected} quantity; got {value!r}",
            subject=name,
            source=_linear_regulator_input_source(name),
        )
    if not value.has_dimension(expected):
        raise _linear_regulator_refusal(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})",
            subject=name,
            source=_linear_regulator_input_source(name),
        )
    # The dimension is the easy half. Every comparison with NaN is False, so a NaN walks
    # past whatever `<= 0` guard follows; an infinity passes it too and then divides to
    # zero or overflows an `int()`. The `_require` helper in forty-eight sibling modules
    # has called this since it was written and this one, in a hundred and sixty-four, did
    # not — the same helper in two generations.
    require_finite(value, name=name)
