"""Worked example: a T1 screening of a cantilever bracket, end to end.

Runs the deterministic vertical with no LLM in the loop: pull a material from the
standards database, compute the T1 bending stress and free-end deflection of a
cantilever, and roll both into a scorecard against declared limits. The bracket
is a 500 mm long 20x10 mm 6061-T6 aluminum arm carrying a 100 N tip load.

Run it directly (``python examples/cantilever_bracket_check.py``) to print the
scorecard; :func:`screen_cantilever_bracket` is also exercised in the test suite.

The instructive result: the aluminum bracket passes the yield check comfortably
but fails on deflection — aluminum is stiffness-limited, and the scorecard catches
it rather than showing a silent green.
"""

from __future__ import annotations

from anvilate.analysis import (
    cantilever_end_load,
    deflection_scorecard,
    rectangular_second_moment,
    strength_scorecard,
)
from anvilate.scorecard import Scorecard
from anvilate.standards import default_materials_db
from anvilate.units import Quantity


def screen_cantilever_bracket() -> Scorecard:
    """Screen the example bracket and return the rolled-up scorecard."""
    material = default_materials_db().get("AA-6061-T6")

    inertia = rectangular_second_moment(Quantity.parse("20 mm"), Quantity.parse("10 mm"))
    result = cantilever_end_load(
        force=Quantity.parse("100 N"),
        length=Quantity.parse("500 mm"),
        second_moment=inertia,
        extreme_fibre=Quantity.parse("5 mm"),
        elastic_modulus=material.elastic_modulus.quantity,
    )

    yield_check = strength_scorecard(
        "bending yield",
        stress=result.max_bending_stress,
        allowable=material.yield_strength.quantity,
        required=1.5,
    )
    deflection_check = deflection_scorecard(
        "tip deflection",
        deflection=result.max_deflection,
        limit=Quantity.parse("15 mm"),
    )
    return Scorecard(entries=(yield_check, deflection_check))


def main() -> None:
    card = screen_cantilever_bracket()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
