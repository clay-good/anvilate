"""Worked example: the machining swarf outweighs the bracket.

A 12 kg steel mounting bracket, machined from solid at a 35% yield, is redesigned as a
near-net stamping at 88% yield. The finished part gets *lighter* — 12 kg to 9.5 kg — but
that is not where the carbon went.

Machined from solid, the billet has to be 34.3 kg to leave 12 kg behind. The 22.3 kg of
swarf was still smelted, cast and rolled, and a cradle-to-gate estimate that counts only
the finished mass understates the part by almost three times. The stamped version starts
from 10.8 kg. Same material, same factor, and the yield is the whole story.

Three things this example is careful about, because each is a way to publish a number
that means nothing:

* **The factor carries its scope.** EN 15978 A1-A3 is cradle to gate. Adding an A1-A5
  figure to it produces a number that is neither, and the estimator refuses to.
* **The band travels.** A screening factor is a central value with real spread, and the
  totals below are quoted as ranges because a single number invites a comparison the
  data cannot support.
* **A missing factor is not zero.** The third case leaves the fastener factor out, and
  the scorecard reports NOT_EVALUATED rather than a total that is quietly too low.

The absolute figures are screening grade — comparable against your own variants computed
the same way, not quotable in a disclosure. The comparison is the deliverable.

Run it directly (``python examples/bracket_redesign_embodied_carbon.py``);
:func:`screen_bracket_variants` is exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    CarbonFactor,
    ModuleScope,
    carbon_contribution,
    embodied_carbon_estimate,
    embodied_carbon_scorecard,
    material_loss_mass,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

# No factor table ships with Anvilate. This one is the caller's, with its provenance —
# the redistribution-clean route is a federal generic dataset the user cites by UUID, or
# a product-specific EPD from the actual supplier.
STEEL = CarbonFactor(
    material="steel, hot-rolled section",
    value=1.55,  # kgCO2e per kg
    scope=ModuleScope.A1_A3,
    source="generic federal dataset, cited by the engineer of record",
    dataset_id="oekobaudat-uuid-placeholder",
    version="2024",
    geography="EU",
    band_low=0.75,
    band_high=1.50,
)
BUDGET = Quantity.parse("40 kg")  # kgCO2e allowance for this assembly


def _variant(label: str, finished: str, yield_fraction: float):
    """One bracket variant: the finished part plus the material its yield threw away."""
    finished_mass = Quantity.parse(finished)
    loss = material_loss_mass(finished_mass=finished_mass, yield_fraction=yield_fraction)
    return [
        carbon_contribution(label=f"{label} finished part", mass=finished_mass, factor=STEEL),
        carbon_contribution(label=f"{label} process loss", mass=loss, factor=STEEL),
    ]


def _entry(label: str, contributions) -> ScorecardEntry:
    present = [c for c in contributions if c is not None]
    if len(present) != len(contributions):
        return embodied_carbon_scorecard(
            label,
            estimate=None,
            budget=BUDGET,
            missing="no carbon factor was supplied for the fasteners",
        )
    return embodied_carbon_scorecard(
        label, estimate=embodied_carbon_estimate(present), budget=BUDGET
    )


def screen_bracket_variants() -> Scorecard:
    """Machined from solid, near-net stamped, and one with a factor missing."""
    stamped = _variant("stamped", "9.5 kg", 0.88)
    return Scorecard(
        entries=[
            _entry("machined from solid (35% yield)", _variant("machined", "12 kg", 0.35)),
            _entry("near-net stamping (88% yield)", stamped),
            # Same stamping, plus a fastener set nobody sourced a factor for.
            _entry(
                "stamping + unsourced fasteners",
                [
                    *stamped,
                    carbon_contribution(
                        label="fasteners", mass=Quantity.parse("0.6 kg"), factor=None
                    ),
                ],
            ),
        ]
    )


def main() -> None:
    print("12 kg steel bracket, cradle-to-gate screening (EN 15978 A1-A3)")
    for entry in screen_bracket_variants().entries:
        factor = "  —  " if entry.safety_factor is None else f"{entry.safety_factor:.2f}"
        print(f"  {entry.name:<34} {entry.status.value:<14} budget ratio {factor}")
        print(f"      {entry.detail}")

    machined = embodied_carbon_estimate([c for c in _variant("machined", "12 kg", 0.35) if c])
    stamped = embodied_carbon_estimate([c for c in _variant("stamped", "9.5 kg", 0.88) if c])
    saved = machined.total.to("kg").magnitude - stamped.total.to("kg").magnitude
    print(
        f"\n  the redesign takes 2.5 kg off the part and "
        f"{saved:.1f} kgCO2e off the estimate — "
        f"{100 * saved / machined.total.to('kg').magnitude:.0f}% of it"
    )


if __name__ == "__main__":
    main()
