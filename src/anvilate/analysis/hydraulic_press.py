"""T1 analytical hydraulic-press (Pascal's principle) checks (closed-form).

A hydraulic press is the fluid version of a lever: press gently on a small piston and a large piston
pushes back hard, because Pascal's principle transmits the same pressure everywhere in the connected
fluid. The force is multiplied by the ratio of piston areas — but, exactly like a mechanical lever,
the large piston moves proportionally less, so no work is created. This complements the
single-cylinder actuator forces of :mod:`anvilate.analysis.hydraulic_cylinder`.

The pressure a fluid transmits is p = F_in/A_in, the input force over the input-piston area, and it
acts equally on the output piston to give F_out = F_in·(A_out/A_in) — a force gain equal to the area
ratio. Because the fluid is incompressible, the swept volumes match (A_in·s_in = A_out·s_out), so
the input piston must travel s_in = s_out·(A_out/A_in), farther by the same ratio the force is
multiplied. Force times distance is unchanged: the press trades stroke for force, never work. Inputs
and outputs are dimension-checked :class:`~anvilate.units.Quantity` values.

Sources: Esposito, *Fluid Power with Applications* (Pascal's law) — the pressure a small piston
transmits, the force it develops on a large one, and the input stroke a given output stroke
costs.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "hydraulic_press_input_stroke",
    "hydraulic_press_output_force",
    "hydraulic_press_transmitted_pressure",
]


def hydraulic_press_transmitted_pressure(
    *, input_force: Quantity, input_piston_area: Quantity
) -> Quantity:
    """The transmitted pressure, p = F_in/A_in.

    The pressure Pascal's principle carries through the fluid, from the ``input_force`` F_in on the
    small piston and its ``input_piston_area`` A_in: p = F_in/A_in. This same pressure acts on every
    surface of the connected fluid, including the large output piston. Returns the pressure in Pa.
    """
    _check(input_force, "[force]", "input_force")
    _check(input_piston_area, "[area]", "input_piston_area")
    f = input_force.to("N").magnitude
    a = input_piston_area.to("m**2").magnitude
    if f < 0:
        raise ValueError("input_force must be non-negative")
    if a <= 0:
        raise ValueError("input_piston_area must be positive")
    return Quantity(magnitude=f / a, unit="Pa")


def hydraulic_press_output_force(
    *, input_force: Quantity, input_piston_area: Quantity, output_piston_area: Quantity
) -> Quantity:
    """The multiplied output force, F_out = F_in·(A_out/A_in).

    The force the large piston develops, from the ``input_force`` F_in and the input and output
    piston areas ``input_piston_area`` A_in and ``output_piston_area`` A_out:
    F_out = F_in·(A_out/A_in). The force gain is the area ratio — a 10:1 area ratio gives a tenfold
    force. Returns the output force in N.
    """
    _check(input_force, "[force]", "input_force")
    _check(input_piston_area, "[area]", "input_piston_area")
    _check(output_piston_area, "[area]", "output_piston_area")
    f = input_force.to("N").magnitude
    a_in = input_piston_area.to("m**2").magnitude
    a_out = output_piston_area.to("m**2").magnitude
    if f < 0:
        raise ValueError("input_force must be non-negative")
    if a_in <= 0 or a_out <= 0:
        raise ValueError("piston areas must be positive")
    return Quantity(magnitude=f * a_out / a_in, unit="N")


def hydraulic_press_input_stroke(
    *, output_stroke: Quantity, input_piston_area: Quantity, output_piston_area: Quantity
) -> Quantity:
    """The input stroke, s_in = s_out·(A_out/A_in).

    How far the small input piston must travel to move the large piston by ``output_stroke`` s_out,
    from the piston areas ``input_piston_area`` A_in and ``output_piston_area`` A_out (equal swept
    volumes): s_in = s_out·(A_out/A_in). The input piston moves farther by the same ratio the force
    is multiplied — trading stroke for force, conserving work. Returns the input stroke in m.
    """
    _check(output_stroke, "[length]", "output_stroke")
    _check(input_piston_area, "[area]", "input_piston_area")
    _check(output_piston_area, "[area]", "output_piston_area")
    s = output_stroke.to("m").magnitude
    a_in = input_piston_area.to("m**2").magnitude
    a_out = output_piston_area.to("m**2").magnitude
    if s < 0:
        raise ValueError("output_stroke must be non-negative")
    if a_in <= 0 or a_out <= 0:
        raise ValueError("piston areas must be positive")
    return Quantity(magnitude=s * a_out / a_in, unit="m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
