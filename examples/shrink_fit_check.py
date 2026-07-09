"""Worked example: screening an ISO 286 shrink fit for hub yielding.

Ties three subsystems together with no LLM: the **tolerance** layer resolves an
ISO 286 interference fit (Ø40 H7/s6) into its worst-case diametral interference,
the **analysis** layer turns that overlap into a thick-wall (Lamé) contact
pressure and the tensile hoop stress it drives at the hub bore, and the
**materials** DB supplies the steel's elastic constants and yield. The hub bore
hoop stress — the value that governs whether the hub cracks when pressed on — is
screened against yield into a :class:`~anvilate.scorecard.Scorecard`.

The tightest interference (the most negative clearance the fit allows) is the
worst case for hub stress, so that is what is screened.

Run it directly (``python examples/shrink_fit_check.py``); :func:`screen_shrink_fit`
is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import interference_fit, strength_scorecard
from anvilate.scorecard import Scorecard
from anvilate.standards import default_materials_db
from anvilate.tolerance.iso286 import fit
from anvilate.units import Quantity

SHAFT_DIAMETER = Quantity.parse("40 mm")
HUB_OUTER_DIAMETER = Quantity.parse("80 mm")
FIT_DESIGNATION = "H7/s6"  # a standard medium-drive interference fit
STEEL = "AISI-1045-CD"


def screen_shrink_fit() -> Scorecard:
    """Resolve the fit, compute the hub hoop stress, screen it against yield."""
    press = fit(FIT_DESIGNATION, SHAFT_DIAMETER)
    # Tightest interference = the most negative clearance; radial = diametral / 2.
    diametral_interference = abs(press.min_clearance.to("mm").magnitude)
    radial_interference = Quantity(magnitude=diametral_interference / 2, unit="mm")

    steel = default_materials_db().get(STEEL)
    result = interference_fit(
        radial_interference=radial_interference,
        interface_diameter=SHAFT_DIAMETER,
        hub_outer_diameter=HUB_OUTER_DIAMETER,
        hub_modulus=steel.elastic_modulus.quantity,
        hub_poisson=steel.poisson_ratio.value,
        shaft_modulus=steel.elastic_modulus.quantity,
        shaft_poisson=steel.poisson_ratio.value,
    )
    entry = strength_scorecard(
        "hub bore hoop",
        stress=result.hub_hoop_stress,
        allowable=steel.yield_strength.quantity,
        required=2.0,
    )
    return Scorecard(entries=(entry,))


def main() -> None:
    card = screen_shrink_fit()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
