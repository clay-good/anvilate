"""Worked example: a spur gear checked both ways — and pitting, not bending, governs.

The Lewis equation screens a gear tooth for root bending, but a real gear is rated by
AGMA against two independent failure modes: tooth-root bending fatigue *and* surface
pitting (contact fatigue). This pinion — 20 teeth, module 5 mm (100 mm pitch diameter),
50 mm face, carrying 250 N*m — passes both, but with very different margins:

  * AGMA bending stress is 98 MPa against a 250 MPa allowable bending strength — a
    utilization of 0.39.
  * AGMA contact stress is 826 MPa against a 1200 MPa allowable contact strength —
    a utilization of 0.69.

So the gear is governed by pitting, not bending. A design that stops at the Lewis (or
AGMA) bending check reads a comfortable 0.39 and misses that the flanks are the real
constraint — the usual story for a through-hardened steel gear.

The example composes the tangential load with both AGMA stresses, sharing one set of
derating factors (K_o, K_v, K_s, K_H), and reports the governing mode by utilization.

Run it directly (``python examples/spur_gear_agma_check.py``);
:func:`gear_utilizations` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    agma_bending_stress,
    agma_contact_stress,
    gear_tangential_load,
)
from anvilate.units import Quantity

TORQUE = Quantity.parse("250 N*m")
PITCH_DIAMETER = Quantity.parse("100 mm")
MODULE = Quantity.parse("5 mm")
FACE_WIDTH = Quantity.parse("50 mm")
STEEL = Quantity.parse("200000 MPa")

BENDING_GEOMETRY = 0.40  # AGMA J factor
CONTACT_GEOMETRY = 0.10  # AGMA I factor
ALLOWABLE_BENDING = Quantity.parse("250 MPa")  # S_t, through-hardened steel
ALLOWABLE_CONTACT = Quantity.parse("1200 MPa")  # S_c, through-hardened steel

# One shared set of load-derating factors.
DERATING = {
    "overload_factor": 1.25,
    "dynamic_factor": 1.2,
    "size_factor": 1.0,
    "load_distribution_factor": 1.3,
}


def gear_utilizations() -> dict[str, float]:
    """Return the bending and contact stress utilizations (stress / allowable)."""
    tangential = gear_tangential_load(torque=TORQUE, pitch_diameter=PITCH_DIAMETER)

    bending = agma_bending_stress(
        tangential_load=tangential,
        module=MODULE,
        face_width=FACE_WIDTH,
        geometry_factor=BENDING_GEOMETRY,
        **DERATING,
    )
    contact = agma_contact_stress(
        tangential_load=tangential,
        pinion_pitch_diameter=PITCH_DIAMETER,
        face_width=FACE_WIDTH,
        geometry_factor=CONTACT_GEOMETRY,
        modulus_pinion=STEEL,
        modulus_gear=STEEL,
        **DERATING,
    )
    return {
        "bending": bending.to("MPa").magnitude / ALLOWABLE_BENDING.to("MPa").magnitude,
        "pitting": contact.to("MPa").magnitude / ALLOWABLE_CONTACT.to("MPa").magnitude,
    }


def main() -> None:
    utils = gear_utilizations()
    governing = max(utils, key=lambda k: utils[k])
    for mode, util in utils.items():
        marker = "  <-- governs" if mode == governing else ""
        print(f"{mode:8s} utilization: {util:.2f}{marker}")


if __name__ == "__main__":
    main()
