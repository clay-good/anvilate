"""Capstone: a spec's classified load cases, factored and checked in one flow.

The other combination examples hand the engine a load mapping directly. This one
starts where a real project starts — a typed Design Spec — and lets the spec carry
its own load cases, each classified by nature. From there the whole chain runs
itself: the spec aggregates its classified cases into a per-nature demand mapping,
the ASCE 7-22 generator factors them, and the scorecard screens a capacity against
the governing combination.

A mezzanine deck plate carries dead load (self-weight plus fixed equipment), a live
occupancy load, and a wind uplift on its light leading edge. Two checks fall out of
one set of loads. The downward strength check is governed by the gravity
combination; the anchorage is governed by the wind uplift the gravity cases never
show. Neither number was written by hand — the spec classified the cases, and the
combination engine did the factoring and the envelope.

The point of the capstone is the seam: once a load case declares its nature, load
combinations stop being a separate spreadsheet and become part of the same
validated flow as every other check.

Then the same deck with one classification forgotten, because that is the quiet
failure. A combination treats a nature nobody supplied as **zero**, so a 25 kN
conveyor reaction that nobody classified raises nothing — it simply never enters
the sum. Against a 130 kN girder the governing demand reads 85.6 kN and the check
passes at 1.52; classify the same case as live and the demand is 125.6 kN and the
check fails at 1.04. Nothing in the passing entry says a load was left out.

`unclassified_force_cases()` names it, and both the check and the evidence report
``NOT_EVALUATED`` instead: a demand summed from part of the declared loads is not
this part's demand — and that holds whichever way the subset number happened to
land, because a FAIL that is right by accident goes on being reported after the
missing case turns it into a pass.

Run it directly (``python examples/spec_load_combination_check.py``);
:func:`screen_deck`, :func:`partly_classified_spec` and :func:`screen_partly_classified`
are exercised in the test suite.
"""

from __future__ import annotations

from anvilate.loads import LoadNature, asce7_lrfd_basic, combination_scorecard
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.spec import (
    AcceptanceCriteria,
    DesignSpec,
    LoadCase,
    LoadKind,
    Manufacturing,
    ManufacturingProcess,
    MaterialRef,
    Provenanced,
    ValidationTier,
)
from anvilate.units import Quantity, UnitSystem

REQUIRED_SF = 1.5
DECK_STRENGTH_CAPACITY = 90.0  # kN, the deck plate and its beam in bending
ANCHOR_TENSION_CAPACITY = 20.0  # kN, what the edge anchorage can carry in tension
# A second, larger girder used only to show the classification gap flipping a verdict.
GIRDER_CAPACITY = 130.0  # kN


def deck_spec() -> DesignSpec:
    """A mezzanine deck spec whose load cases are classified by nature."""

    def _load(name: str, nature: LoadNature, force: str) -> LoadCase:
        return LoadCase(
            name=name,
            kind=LoadKind.STATIC,
            applied_to="deck",
            force=Quantity.parse(force),
            nature=nature,
        )

    return DesignSpec(
        name="mezzanine_deck",
        description="A mezzanine deck plate with a wind-exposed leading edge.",
        units=Provenanced.stated(UnitSystem.SI),
        material=MaterialRef(ref="ASTM-A36"),
        manufacturing=Manufacturing(process=ManufacturingProcess.SHEET_METAL),
        load_cases=[
            _load("self_weight", LoadNature.DEAD, "12 kN"),
            _load("fixed_equipment", LoadNature.DEAD, "6 kN"),
            _load("occupancy", LoadNature.LIVE, "40 kN"),
            _load("edge_wind_uplift", LoadNature.WIND, "-30 kN"),
        ],
        acceptance=AcceptanceCriteria(tiers=[ValidationTier.T1_ANALYTICAL]),
    )


def partly_classified_spec() -> DesignSpec:
    """The same deck, plus a 25 kN case somebody forgot to classify."""
    spec = deck_spec()
    return DesignSpec(
        **{
            **spec.model_dump(),
            "load_cases": [
                *spec.load_cases,
                LoadCase(
                    name="conveyor_reaction",
                    kind=LoadKind.STATIC,
                    applied_to="deck",
                    force=Quantity.parse("25 kN"),
                ),
            ],
            "combination_basis": "asce7_lrfd",
        }
    )


def _girder_check(loads, *, unclassified=()) -> ScorecardEntry:
    return combination_scorecard(
        "girder strength",
        combinations=asce7_lrfd_basic(),
        loads=loads,
        capacity=GIRDER_CAPACITY * 1000.0,
        required=REQUIRED_SF,
        unclassified=unclassified,
    )


def girder_checks() -> tuple[ScorecardEntry, ScorecardEntry, ScorecardEntry]:
    """The same girder three ways: case forgotten, case classified, and case named.

    The first passes, the second fails, and the third refuses to answer — which is the
    only one of the three a reader can act on when the classification is in doubt.
    """
    spec = partly_classified_spec()
    forgotten = spec.combination_loads()
    classified = {**forgotten, LoadNature.LIVE: forgotten[LoadNature.LIVE] + 25_000.0}
    return (
        _girder_check(forgotten),
        _girder_check(classified),
        _girder_check(forgotten, unclassified=spec.unclassified_force_cases()),
    )


def screen_deck() -> Scorecard:
    """Screen the deck's strength and its anchorage, both from the spec's loads."""
    loads = deck_spec().combination_loads()  # {DEAD: 18000, LIVE: 40000, WIND: -30000}
    combos = asce7_lrfd_basic()
    return Scorecard(
        entries=(
            combination_scorecard(
                "deck strength",
                combinations=combos,
                loads=loads,
                capacity=DECK_STRENGTH_CAPACITY * 1000.0,  # N
                required=REQUIRED_SF,
            ),
            combination_scorecard(
                "edge anchorage uplift",
                combinations=combos,
                loads=loads,
                capacity=ANCHOR_TENSION_CAPACITY * 1000.0,  # N
                required=REQUIRED_SF,
                minimize=True,
            ),
        )
    )


def main() -> None:
    loads = deck_spec().combination_loads()
    print("Loads aggregated from the spec's classified cases (N):")
    for nature, magnitude in sorted(loads.items()):
        print(f"  {nature.value}: {magnitude:+.0f}")
    print()
    card = screen_deck()
    print(card.report())
    for entry in card.entries:
        print(f"  {entry}")
    print(f"\ngoverning check: {card.governing().name}")

    # A 25 kN conveyor reaction nobody classified never enters the sum, so nothing
    # complains — which is why the classification gap has to be an output of its own.
    forgotten, classified, guarded = girder_checks()
    print(f"\na {GIRDER_CAPACITY:g} kN girder, and a 25 kN case nobody classified:")
    print(f"  forgotten:  {forgotten}")
    print(f"  classified: {classified}")
    print(f"  guarded:    {guarded}")
    print(f"  evidence:   {partly_classified_spec().combination_evidence()}")


if __name__ == "__main__":
    main()
