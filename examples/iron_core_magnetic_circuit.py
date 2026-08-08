"""Worked example: flux in an iron-core magnetic circuit.

A coil wound on an iron core drives magnetic flux around the core just as a battery drives current
around a wire. Hopkinson's law makes the analogy exact: the coil's magnetomotive force is the
"voltage," the core's reluctance is the "resistance," and the flux is the "current."

Take a 300-turn coil carrying 1.5 A on a closed iron ring 0.6 m long with a 4 cm^2 (4e-4 m^2) cross
section and a relative permeability of 2,000. The magnetomotive force is 450 ampere-turns, the
core reluctance is about 597,000 A/Wb, and the resulting flux is about 7.5e-4 Wb — a flux density
of about 1.9 T in the core. This example reports the magnetomotive force, the reluctance, and flux.

Run it directly (``python examples/iron_core_magnetic_circuit.py``);
:func:`core_flux` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    magnetic_flux,
    magnetic_reluctance,
    magnetomotive_force,
)
from anvilate.units import Quantity

TURNS = 300.0
CURRENT = Quantity(magnitude=1.5, unit="A")
PATH_LENGTH = Quantity(magnitude=0.6, unit="m")
CORE_AREA = Quantity(magnitude=4e-4, unit="m**2")
RELATIVE_PERMEABILITY = 2000.0


def core_flux() -> dict[str, float]:
    """Return the magnetomotive force, the reluctance, and the flux of the magnetic circuit."""
    mmf = magnetomotive_force(turns=TURNS, current=CURRENT)
    reluctance = magnetic_reluctance(
        path_length=PATH_LENGTH,
        area=CORE_AREA,
        relative_permeability=RELATIVE_PERMEABILITY,
    )
    flux = magnetic_flux(magnetomotive_force=mmf, reluctance=reluctance)
    return {
        "mmf_ampere_turns": mmf.to("A").magnitude,
        "reluctance_per_henry": reluctance.to("1/H").magnitude,
        "flux_mwb": flux.to("Wb").magnitude * 1000.0,
    }


def main() -> None:
    d = core_flux()
    print(f"magnetomotive force: {d['mmf_ampere_turns']:.0f} A-turns")
    print(f"reluctance: {d['reluctance_per_henry']:.0f} /H")
    print(f"flux: {d['flux_mwb']:.3f} mWb")


if __name__ == "__main__":
    main()
