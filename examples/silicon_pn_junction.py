"""Worked example: the electrostatics of a silicon pn junction.

Where p-type and n-type silicon meet, a depletion region forms with a built-in potential, a width,
and a capacitance — the three numbers that define a diode's static behavior and set the tuning of a
varactor. This example works them for a moderately-doped silicon junction at room temperature.

The junction has 1e22 /m^3 acceptors and 1e22 /m^3 donors, against silicon's intrinsic carrier
density of 1e16 /m^3, at 300 K. Its built-in potential is about 0.71 V — the familiar barrier of a
silicon diode. The depletion region spreads to about 0.43 micrometres, using silicon's permittivity
(relative permittivity 11.7). Across that gap the junction presents about 24 nF/cm^2 of capacitance,
which shrinks as reverse bias widens the depletion region — the effect a varactor exploits to tune a
circuit. The example reports the built-in potential, the depletion width, and the junction
capacitance.

Run it directly (``python examples/silicon_pn_junction.py``);
:func:`junction_electrostatics` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    built_in_potential,
    depletion_width,
    junction_capacitance_per_area,
)
from anvilate.units import Quantity

ACCEPTOR_DENSITY = Quantity(magnitude=1e22, unit="1/m**3")
DONOR_DENSITY = Quantity(magnitude=1e22, unit="1/m**3")
INTRINSIC_DENSITY = Quantity(magnitude=1e16, unit="1/m**3")  # silicon
TEMPERATURE = Quantity(magnitude=300.0, unit="K")
SILICON_PERMITTIVITY = Quantity(magnitude=11.7 * 8.8541878128e-12, unit="F/m")


def junction_electrostatics() -> dict[str, float]:
    """Return the built-in potential, depletion width, and junction capacitance per area."""
    v_bi = built_in_potential(
        acceptor_density=ACCEPTOR_DENSITY,
        donor_density=DONOR_DENSITY,
        intrinsic_density=INTRINSIC_DENSITY,
        temperature=TEMPERATURE,
    )
    width = depletion_width(
        built_in_potential=v_bi,
        permittivity=SILICON_PERMITTIVITY,
        acceptor_density=ACCEPTOR_DENSITY,
        donor_density=DONOR_DENSITY,
    )
    capacitance = junction_capacitance_per_area(
        permittivity=SILICON_PERMITTIVITY, depletion_width=width
    )
    return {
        "built_in_potential_v": v_bi.to("V").magnitude,
        "depletion_width_um": width.to("um").magnitude,
        "capacitance_nf_cm2": capacitance.to("F/m**2").magnitude * 1e-4 / 1e-9,
    }


def main() -> None:
    d = junction_electrostatics()
    print(f"built-in potential: {d['built_in_potential_v']:.2f} V")
    print(f"depletion width: {d['depletion_width_um']:.2f} um")
    print(f"junction capacitance: {d['capacitance_nf_cm2']:.0f} nF/cm^2")


if __name__ == "__main__":
    main()
