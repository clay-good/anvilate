"""T1 analytical switching DC-DC converter checks (closed-form, ideal / continuous conduction).

A switching regulator sets its output voltage by the fraction of each cycle its switch is on — the
duty cycle D — rather than by burning off the excess as a linear regulator does. The three canonical
non-isolated topologies each convert the input a different way: the buck steps voltage down, the
boost steps it up, and the buck-boost can do either (with an inverted output). These ideal transfer
functions (loss-free, continuous-conduction) are the first sizing step for any point-of-load supply,
and they are distinct from the fixed-ratio :func:`anvilate.analysis.electrical` transformer (which
needs AC and cannot change its ratio on the fly).

For the buck, V_out = D * V_in, always at or below the input. For the boost, V_out = V_in / (1 - D),
always at or above it, rising steeply as D approaches 1. For the buck-boost, V_out = V_in*D/(1 - D)
(magnitude; the real output is inverted), below the input for D < 0.5 and above it for D > 0.5. In
every case the duty cycle is the single control knob, and these relations set the operating D a
target output needs.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "boost_output_voltage",
    "buck_boost_output_voltage",
    "buck_output_voltage",
]


def buck_output_voltage(*, input_voltage: Quantity, duty_cycle: float) -> Quantity:
    """The buck (step-down) output voltage, V_out = D * V_in.

    A buck converter's ideal output: the ``input_voltage`` V_in scaled by the ``duty_cycle`` D (the
    fraction of each switching cycle the high-side switch conducts), V_out = D * V_in. The output is
    always at or below the input, and D is the single control knob a feedback loop turns. Assumes an
    ideal, continuous-conduction converter. Returns the output voltage in V.
    """
    _check(input_voltage, "[electric_potential]", "input_voltage")
    v_in = input_voltage.to("V").magnitude
    if not 0.0 < duty_cycle < 1.0:
        raise ValueError("duty_cycle must be in (0, 1)")
    return Quantity(magnitude=duty_cycle * v_in, unit="V")


def boost_output_voltage(*, input_voltage: Quantity, duty_cycle: float) -> Quantity:
    """The boost (step-up) output voltage, V_out = V_in / (1 - D).

    A boost converter's ideal output: the ``input_voltage`` V_in divided by (1 - ``duty_cycle`` D),
    V_out = V_in / (1 - D). The output is always at or above the input and rises steeply as D nears
    1 (where losses and stress make the ideal relation optimistic). Assumes an ideal,
    continuous-conduction converter. Returns the output voltage in V.
    """
    _check(input_voltage, "[electric_potential]", "input_voltage")
    v_in = input_voltage.to("V").magnitude
    if not 0.0 < duty_cycle < 1.0:
        raise ValueError("duty_cycle must be in (0, 1)")
    return Quantity(magnitude=v_in / (1.0 - duty_cycle), unit="V")


def buck_boost_output_voltage(*, input_voltage: Quantity, duty_cycle: float) -> Quantity:
    """The buck-boost output voltage magnitude, V_out = V_in * D / (1 - D).

    A buck-boost converter's ideal output magnitude: the ``input_voltage`` V_in times
    ``duty_cycle`` D over (1 - D), V_out = V_in * D/(1 - D) (the physical output is inverted in
    polarity). It steps down for D < 0.5 and up for D > 0.5, so one topology spans both. Assumes an
    ideal, continuous-conduction converter. Returns the output voltage magnitude in V.
    """
    _check(input_voltage, "[electric_potential]", "input_voltage")
    v_in = input_voltage.to("V").magnitude
    if not 0.0 < duty_cycle < 1.0:
        raise ValueError("duty_cycle must be in (0, 1)")
    return Quantity(magnitude=v_in * duty_cycle / (1.0 - duty_cycle), unit="V")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
