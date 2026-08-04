"""Worked example: load-balancing a post-tensioned beam, and the crack margin above it.

T. Y. Lin's insight was that a draped tendon does not just add strength — it applies an upward load
you can size to cancel gravity. This example takes a 12 m post-tensioned beam with a 1500 kN tendon
draped 300 mm and finds the uniform load that prestress balances. Under exactly that load the beam
carries no bending at all: the bottom-fibre stress collapses to a uniform −P/A compression, which
this example confirms directly. It then pushes the beam past balance to a heavier service moment and
reads the bottom-fibre stress climbing back toward tension, and reports the cracking moment — the
applied moment at which that fibre finally reaches the concrete's modulus of rupture and opens.

Run it directly (``python examples/post_tensioned_beam_balancing.py``);
:func:`beam_balancing` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    prestress_balanced_load,
    prestress_bottom_fiber_stress,
    prestress_cracking_moment,
)
from anvilate.units import Quantity

PRESTRESS = Quantity.parse("1500 kN")
DRAPE = Quantity.parse("0.3 m")
SPAN = Quantity.parse("12 m")
AREA = Quantity.parse("0.15 m**2")
SECTION_MODULUS = Quantity.parse("0.02 m**3")
MODULUS_OF_RUPTURE = Quantity.parse("3.5 MPa")


def beam_balancing() -> dict[str, float]:
    """Return the balanced load, the stress under it, and the cracking moment."""
    balanced = prestress_balanced_load(prestress_force=PRESTRESS, tendon_drape=DRAPE, span=SPAN)
    # The moment the balanced load makes at midspan equals P*e, so the fibre stress is uniform.
    balanced_moment = Quantity(
        magnitude=PRESTRESS.to("N").magnitude * DRAPE.to("m").magnitude, unit="N*m"
    )
    stress_at_balance = prestress_bottom_fiber_stress(
        applied_moment=balanced_moment,
        prestress_force=PRESTRESS,
        area=AREA,
        tendon_eccentricity=DRAPE,
        section_modulus=SECTION_MODULUS,
    )
    cracking = prestress_cracking_moment(
        prestress_force=PRESTRESS,
        area=AREA,
        tendon_eccentricity=DRAPE,
        section_modulus=SECTION_MODULUS,
        modulus_of_rupture=MODULUS_OF_RUPTURE,
    )
    return {
        "balanced_load_kn_m": balanced.to("kN/m").magnitude,
        "stress_at_balance_mpa": stress_at_balance.to("MPa").magnitude,
        "cracking_moment_kn_m": cracking.to("kN*m").magnitude,
    }


def main() -> None:
    b = beam_balancing()
    print(f"balanced load     : {b['balanced_load_kn_m']:.1f} kN/m (a 300 mm drape, 1500 kN)")
    print(f"stress at balance : {b['stress_at_balance_mpa']:.1f} MPa (uniform −P/A, no bending)")
    print(f"cracking moment   : {b['cracking_moment_kn_m']:.0f} kN·m")
    print("  -> size the prestress to cancel gravity; the beam then rides in pure compression")


if __name__ == "__main__":
    main()
