"""Worked example: the lightest bracket, and the three ways a sweep lies about it.

A 400 mm steel cantilever bracket carrying 1.2 kN at its tip, screened for bending yield
at SF 1.5 and for a 2.0 mm tip deflection limit. Two free parameters: section height 20
to 60 mm, plate thickness 4 to 12 mm, nine steps each. Eighty-one designs, all evaluated
in a few milliseconds because every check is closed-form.

Twenty-six pass. Five of those are non-dominated on (mass, height) — a real trade, since
a shallow bracket fits where a deep one does not:

| Height × thickness | Mass | Governed by |
| 40 × 12 mm | 1.507 kg | bending yield, SF 1.67 |
| 45 × 9 mm | 1.272 kg | bending yield, SF 1.58 |
| 50 × 7 mm | 1.099 kg | bending yield, SF 1.52 |
| 55 × 6 mm | 1.036 kg | bending yield, SF 1.58 |
| 60 × 5 mm | 0.942 kg | bending yield, SF 1.56 |

**Lie 1: the lightest design.** The lightest thing in the box is the 20 × 4 mm section at
0.251 kg — **3.75× lighter** than the lightest one that works. It fails bending. An
optimiser that ranks by mass and forgets feasibility returns it, and it is not close.

**Lie 2: the front that is the whole space.** Fifty-five of the eighty-one points are
infeasible. Drop them and the plot shows a tidy front from 0.94 to 1.51 kg with no
indication that two thirds of the box is unbuildable — and no indication of *where* the
boundary is, which is the half of a sweep a designer actually uses. Infeasible points are
kept and labelled here, with the check that stopped each one named.

**Lie 3: the truncated sweep that reports a front anyway.** Cap the budget at 20 of the
81 points. A grid walks its first parameter slowest, so those 20 points are the three
shallowest height rows — every one of them fails. The result reports 25% coverage,
`provisional`, **zero feasible**, and `best("mass")` returns `None`. Not a front, not a
recommendation, and not silence either.

Spend the same 20-point budget on the Halton sequence instead and it finds 7 feasible
designs and a 1.097 kg best. That is the argument for a low-discrepancy sequence in one
line: at a budget below the grid, *where* the points go decides whether you find the
feasible region at all.

What the module will not do: propose a number. A model may propose which parameters to
sweep, over what bounds, against what objectives — every value in the result comes from
the deterministic evaluator, and a non-finite one is refused rather than sorted.

Run it directly (``python examples/lightest_passing_bracket.py``); :func:`sweep` is
exercised in the test suite.
"""

from __future__ import annotations

from collections.abc import Mapping

from anvilate.analysis import (
    cantilever_end_load,
    deflection_scorecard,
    rectangular_second_moment,
    strength_scorecard,
)
from anvilate.explore import (
    Objective,
    Parameter,
    SamplingStrategy,
    Study,
    StudyEvaluation,
    StudyResult,
    run_study,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

TIP_LOAD = Quantity.parse("1200 N")
SPAN = Quantity.parse("400 mm")
YIELD = Quantity.parse("250 MPa")  # S355 plate, user-supplied
ELASTIC_MODULUS = Quantity.parse("200 GPa")
DEFLECTION_LIMIT = Quantity.parse("2.0 mm")
REQUIRED_SF = 1.5
STEEL_DENSITY = 7850.0  # kg/m3

PARAMETERS = (
    Parameter(name="height", low=20.0, high=60.0, unit="mm", steps=9),
    Parameter(name="thickness", low=4.0, high=12.0, unit="mm", steps=9),
)
OBJECTIVES = (Objective(name="mass"), Objective(name="height"))


def evaluate(parameters: Mapping[str, float]) -> StudyEvaluation:
    """Screen one bracket: bending yield and tip deflection, and report its mass."""
    height = parameters["height"]
    thickness = parameters["thickness"]
    second_moment = rectangular_second_moment(
        Quantity(magnitude=thickness, unit="mm"), Quantity(magnitude=height, unit="mm")
    )
    beam = cantilever_end_load(
        force=TIP_LOAD,
        length=SPAN,
        second_moment=second_moment,
        extreme_fibre=Quantity(magnitude=height / 2.0, unit="mm"),
        elastic_modulus=ELASTIC_MODULUS,
    )
    card = Scorecard(
        entries=(
            strength_scorecard(
                "bending yield",
                stress=beam.max_bending_stress,
                allowable=YIELD,
                required=REQUIRED_SF,
            ),
            deflection_scorecard(
                "tip deflection", deflection=beam.max_deflection, limit=DEFLECTION_LIMIT
            ),
        )
    )
    volume_mm3 = thickness * height * SPAN.to("mm").magnitude
    return StudyEvaluation(
        objectives={"mass": STEEL_DENSITY * volume_mm3 * 1e-9, "height": height},
        scorecard=card,
    )


def sweep(
    *, budget: int | None = None, strategy: SamplingStrategy = SamplingStrategy.GRID
) -> StudyResult:
    """Run the bracket study, optionally truncated to ``budget`` points."""
    study = Study(
        name="cantilever bracket",
        parameters=PARAMETERS,
        objectives=OBJECTIVES,
        strategy=strategy,
        budget=budget,
    )
    return run_study(study, evaluate)


def main() -> None:
    full = sweep()
    print(full.summary())
    print("\n  the front (mass against height):")
    for point in full.front:
        print(
            f"    {point.parameters['height']:.0f} x {point.parameters['thickness']:.0f} mm"
            f"  {point.objectives['mass']:.3f} kg   governed by "
            f"{point.governing_check} at SF {point.governing_safety_factor:.2f}"
        )

    lightest_evaluated = min(full.points, key=lambda p: p.objectives["mass"])
    lightest_passing = full.best("mass")
    print(
        f"\n  lightest evaluated: {lightest_evaluated.objectives['mass']:.3f} kg "
        f"({lightest_evaluated.status.value}, stopped by "
        f"{lightest_evaluated.governing_check})"
    )
    print(
        f"  lightest passing:   {lightest_passing.objectives['mass']:.3f} kg "
        f"— {lightest_passing.objectives['mass'] / lightest_evaluated.objectives['mass']:.2f}x "
        f"heavier than the thing an infeasibility-blind optimiser returns"
    )
    print(f"  infeasible points kept and labelled: {len(full.points) - len(full.feasible)}")

    truncated = sweep(budget=20)
    print(f"\n  {truncated.summary()}")
    print(f"    best('mass') -> {truncated.best('mass')}")
    halton = sweep(budget=20, strategy=SamplingStrategy.HALTON)
    print(f"  {halton.summary()}")
    best = halton.best("mass")
    print(f"    best('mass') -> {best.objectives['mass']:.3f} kg on the same 20-point budget")


if __name__ == "__main__":
    main()
