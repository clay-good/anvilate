"""Worked example: the weld is the design, in welded aluminum.

Aluminum's signature trap is that welding it destroys the temper. A 6061-T6
extrusion is heat-treated to a compressive yield of 35 ksi, and the arc undoes
that heat treatment for about an inch either side of the weld: inside that
heat-affected zone the same metal is down to about 15 ksi, permanently, unless
the part is re-solution-treated and re-aged. Steel has nothing comparable — a
welded A992 member is still A992 — so the habit does not transfer, and a
designer who checks the parent metal alone is out by more than a factor of two.

The member here is a walkway platform beam: a 6061-T6 rectangular tube with a
90 mm flat wall 5 mm thick, screened in compression at kL/r = 45 against a
demand of 100 MPa. Run unwelded it is governed by member buckling at 178.5 MPa,
a safety factor of 1.79. Declare the weld at the connection and the same screen
runs a second time on the weld-affected properties, reports both, and hands back
the lesser: 87.4 MPa, a safety factor of 0.87. The same beam, the same load, and
the weld is the whole difference between pass and fail.

The third case is the one that matters most for a screening library: a member
declared welded whose weld-affected properties were never supplied. That does
not fall back to the parent metal, and it does not pass. It comes back
NOT_EVALUATED naming what is missing, because a check made on the wrong material
is worse than a check that admits it did not run.

Run it directly (``python examples/welded_aluminum_platform_beam.py``);
:func:`screen_platform_beam` is exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    AlloyProperties,
    EdgeSupport,
    TemperGroup,
    aluminum_compression_scorecard,
    aluminum_compression_strength,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

# Properties are the user's to supply, with their provenance — Anvilate ships no
# alloy database and reproduces none of the ADM's property tables.
WELD_AFFECTED = AlloyProperties(
    name="6061-T6 (weld-affected)",
    compressive_yield=Quantity.parse("15 ksi"),
    tensile_yield=Quantity.parse("15 ksi"),
    tensile_ultimate=Quantity.parse("24 ksi"),
    elastic_modulus=Quantity.parse("10100 ksi"),
    temper_group=TemperGroup.ARTIFICIALLY_AGED,
    source="ADM 2020 Table A.3.5, read by the engineer of record",
)
PARENT = AlloyProperties(
    name="6061-T6",
    compressive_yield=Quantity.parse("35 ksi"),
    tensile_yield=Quantity.parse("35 ksi"),
    tensile_ultimate=Quantity.parse("38 ksi"),
    elastic_modulus=Quantity.parse("10100 ksi"),
    temper_group=TemperGroup.ARTIFICIALLY_AGED,
    source="ADM 2020 Table A.3.4, read by the engineer of record",
    weld_affected=WELD_AFFECTED,
)
# The tube wall: flat width between the corner radii, held on both edges.
FLAT_WIDTH = Quantity.parse("90 mm")
THICKNESS = Quantity.parse("5 mm")
SLENDERNESS = 45.0  # kL/r for the braced platform beam
DEMAND = Quantity.parse("100 MPa")  # the compressive stress from the platform load


def _entry(name: str, *, welded: bool, properties: AlloyProperties) -> ScorecardEntry:
    strength = aluminum_compression_strength(
        properties=properties,
        slenderness=SLENDERNESS,
        flat_width=FLAT_WIDTH,
        thickness=THICKNESS,
        edge_support=EdgeSupport.BOTH_EDGES,
        welded=welded,
    )
    return aluminum_compression_scorecard(
        name,
        demand_stress=DEMAND,
        strength=strength,
        missing="the weld-affected F_cyw for 6061-T6 was not supplied",
    )


def screen_platform_beam() -> Scorecard:
    """The same beam three ways: unwelded, welded, and welded with no HAZ data."""
    bare = PARENT.model_copy(update={"weld_affected": None})
    return Scorecard(
        entries=[
            _entry("unwelded member", welded=False, properties=PARENT),
            _entry("welded at the connection", welded=True, properties=PARENT),
            _entry("welded, no HAZ data supplied", welded=True, properties=bare),
        ],
    )


def main() -> None:
    card = screen_platform_beam()
    print(f"6061-T6 walkway platform beam, compression: {card.status.value}")
    for entry in card.entries:
        factor = "  —  " if entry.safety_factor is None else f"{entry.safety_factor:.2f}"
        print(f"  {entry.name:<32} {entry.status.value:<14} SF {factor}")
        print(f"      {entry.detail}")


if __name__ == "__main__":
    main()
