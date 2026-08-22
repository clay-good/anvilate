"""Worked example: three drawing callouts that are not annotations.

A 25 mm shaft journal in AISI 4140 (S_u = 655 MPa), running a fully reversed bending
stress of 130 MPa against the estimated rotating-beam endurance limit of 327.5 MPa.
Screened with the drawing ignored — a bare, polished, untreated part — it passes at a
safety factor of 2.52.

The drawing says three things. Each one is an input a check already takes and was never
given:

1. **"AS FORGED, 12.5 µm Ra."** Shigley's Marin surface factor is indexed by production
   method, and an as-forged surface on this steel earns k_a = 0.429. That alone drops the
   corrected endurance limit to 141 MPa and the safety factor from 2.52 to **1.08 — a
   FAIL** against the required 1.50. Same shaft, same load, same steel: the comfortable
   pass was an artifact of screening a polished laboratory specimen.
2. **"ASTM B633 SC1, 5–13 µm."** Plating lands on both sides, so the journal grows 10 to
   26 µm on diameter — Ø25.010 to Ø25.026. On the mating fit that is the difference
   between a slip and a press. On the shaft's threaded end it is worse: a 60° thread's
   pitch diameter moves *four* times the plating thickness, 20 to 52 µm, which can consume
   the whole class allowance.
3. **"HEAT TREAT TO CONDITION QT, 38–42 HRC."** The materials database distinguishes
   conditions in the record identity, and there is no `AISI-4140-QT` record. So the check
   reports NOT_EVALUATED naming the condition — rather than screening the untreated row
   and calling the result a screening of the treated part.

Then the revision. Somebody relaxes the finish callout to machined at 3.2 µm Ra, which
lifts k_a to 0.809 and the safety factor to 2.04 — back inside the requirement. The diff
reports that as one *change* to one characteristic, not a deletion and an unrelated
addition, because the persistent identifier is derived from what the characteristic is —
kind and scope — and never from its value.

One more thing the drawing says, and the library refuses to read: a free-text note. It is
stored, it is distinguishable, and no check may consume it.

Run it directly (``python examples/plated_shaft_callouts_change_the_verdict.py``);
:func:`screen_the_shaft` is exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    estimated_endurance_limit,
    marin_endurance_limit,
    strength_scorecard,
)
from anvilate.callouts import (
    CalloutSet,
    Coating,
    FreeTextNote,
    HeatTreatment,
    ProductionMethod,
    SurfaceFinish,
    callout_diff,
    callout_scorecard,
    marin_surface_factor,
    plated_outer_dimension,
    plated_thread_pitch_diameter_shift,
)
from anvilate.scorecard import Scorecard
from anvilate.standards import default_materials_db
from anvilate.units import Quantity

JOURNAL = "shaft_journal"
STEEL = "AISI-4140"
NOMINAL_DIAMETER = Quantity.parse("25 mm")
BENDING_STRESS = Quantity.parse("130 MPa")
REQUIRED_SF = 1.5

AS_DRAWN = CalloutSet(
    callouts=(
        SurfaceFinish(
            scope=JOURNAL,
            roughness=Quantity.parse("12.5 um"),
            method=ProductionMethod.AS_FORGED,
        ),
        Coating(
            scope=JOURNAL,
            specification="ASTM B633 SC1",
            coating_class="Type III",
            minimum_thickness=Quantity.parse("5 um"),
            maximum_thickness=Quantity.parse("13 um"),
        ),
        HeatTreatment(
            scope=None,
            specification="AMS 2759/1",
            condition="QT",
            hardness="38-42 HRC",
        ),
        FreeTextNote(scope=None, text="finish per shop practice where not specified"),
    )
)

REVISED = CalloutSet(
    callouts=(
        SurfaceFinish(
            scope=JOURNAL,
            roughness=Quantity.parse("3.2 um"),
            method=ProductionMethod.MACHINED,
        ),
        *AS_DRAWN.callouts[1:],
    )
)


def _fatigue_card(callouts: CalloutSet, ultimate: Quantity) -> tuple[Scorecard, float]:
    """The fatigue screen with the declared finish consumed, and the factor it used."""
    finish = callouts.finish_for(JOURNAL)
    factor = 1.0 if finish is None else marin_surface_factor(finish, ultimate_strength=ultimate)
    corrected = marin_endurance_limit(
        base_endurance_limit=estimated_endurance_limit(ultimate_strength=ultimate),
        surface_factor=factor,
    )
    entry = strength_scorecard(
        "journal bending fatigue",
        stress=BENDING_STRESS,
        allowable=corrected,
        required=REQUIRED_SF,
    )
    return Scorecard(entries=(entry,)), factor


def screen_the_shaft():
    """The shaft with the drawing ignored, with it read, and after a revision."""
    ultimate = default_materials_db().get(STEEL).ultimate_strength.quantity

    ignored, ignored_factor = _fatigue_card(CalloutSet(), ultimate)
    as_drawn, as_drawn_factor = _fatigue_card(AS_DRAWN, ultimate)
    revised, revised_factor = _fatigue_card(REVISED, ultimate)

    consumption = callout_scorecard(
        AS_DRAWN,
        ultimate_strength=ultimate,
        base_material=STEEL,
        known_materials=default_materials_db().known_materials(),
    )
    coating = AS_DRAWN.coating_for(JOURNAL)
    plated = plated_outer_dimension(NOMINAL_DIAMETER, coating)
    thread_shift = plated_thread_pitch_diameter_shift(coating)
    diff = callout_diff(AS_DRAWN, REVISED)
    return {
        "ignored": (ignored, ignored_factor),
        "as_drawn": (as_drawn, as_drawn_factor),
        "revised": (revised, revised_factor),
        "consumption": consumption,
        "plated": plated,
        "thread_shift": thread_shift,
        "diff": diff,
    }


def main() -> None:
    result = screen_the_shaft()
    print("FATIGUE, WITH THE DRAWING IGNORED AND READ")
    for label in ("ignored", "as_drawn", "revised"):
        card, factor = result[label]
        (entry,) = card.entries
        print(f"  {label:<9} k_a = {factor:.3f}  {entry}")

    print("\nWHAT THE CALLOUTS DO")
    for entry in result["consumption"].entries:
        print(f"  {entry}")

    low, high = result["plated"]
    shift_low, shift_high = result["thread_shift"]
    print("\nPLATED DIMENSIONS")
    print(
        f"  journal Ø{NOMINAL_DIAMETER.magnitude:g} mm -> "
        f"{low.to('mm').magnitude:.3f}–{high.to('mm').magnitude:.3f} mm"
    )
    print(
        f"  60° thread pitch diameter grows "
        f"{shift_low.to('um').magnitude:.0f}–{shift_high.to('um').magnitude:.0f} µm "
        f"(four times the plating, not twice)"
    )

    print(f"\nREVISION DIFF: {result['diff']}")
    for change in result["diff"].changed:
        print(f"  {change}")


if __name__ == "__main__":
    main()
