# Design-space exploration

**A sweep, not an optimiser.** Every point is evaluated by the same closed-form,
citation-carrying checks as a single screen; the front is the exact non-dominated set of
those points. Nothing here is heuristic, nothing is surrogate-modelled, and the word
"optimal" appears nowhere in its output — a front is the best of what was evaluated, and
when the budget cut the sweep short it says so.

Anvilate answers "does this design pass?". This answers "what is the lightest one that
does?"

```python
from anvilate.explore import Objective, Parameter, Study, StudyEvaluation, run_study

study = Study(
    name="cantilever bracket",
    parameters=(
        Parameter(name="height", low=20.0, high=60.0, unit="mm", steps=9),
        Parameter(name="thickness", low=4.0, high=12.0, unit="mm", steps=9),
    ),
    objectives=(Objective(name="mass"), Objective(name="height")),
)
result = run_study(study, evaluate)   # evaluate: params -> StudyEvaluation
print(result.summary())
# cantilever bracket: 81 of 81 points evaluated (100%, complete), 26 feasible, 5 on the front
```

## The three ways a sweep lies

A 400 mm steel bracket carrying 1.2 kN, screened for bending yield at SF 1.5 and a 2.0 mm
tip deflection. Eighty-one designs, evaluated in milliseconds.

**0. A point that passes on paper may not pass.** `DesignPoint.fragile` marks a feasible
point whose own declared input scatter fails it materially often, and `StudyResult.fragile`
collects them. A front sits at the edge of feasibility, which is where fragility lives, so
these are disproportionately the designs a sweep hands back — and the summary says how many
there are rather than leaving "lightest passing design" to mean "lightest design that
passes on paper".

**1. The lightest design is not the lightest design.** The lightest thing in the box is
0.251 kg and it fails bending. The lightest one that *works* is 0.942 kg — **3.75×
heavier**. Feasibility is decided by the scorecard, and a point that did not pass is
never on the front. `best("mass")` returns the lightest *passing* design, or `None` when
nothing passed, which is a different answer from the lightest evaluated one.

`NOT_EVALUATED` is not feasible either. A design whose governing check could not run has
not been shown to work, and a front is the best thing that works — not the best thing
nobody disproved.

**2. A front over the survivors looks like the whole space.** Fifty-five of the
eighty-one points are infeasible. They are kept and labelled, each naming the check that
stopped it, because the shape of the infeasible region is usually the more useful half of
a sweep — it is what tells you which way to move.

**3. A truncated sweep still reports a front.** Cap the budget at 20 points and the
result is `provisional`, reports 25% coverage, and finds **zero feasible designs** —
because a grid walks its first parameter slowest, so those 20 points are the two
shallowest height rows plus a slice of the third, and every one of them fails.

| 20-point budget | Feasible found | `best("mass")` |
| --- | --- | --- |
| Grid | 0 | `None` |
| Halton | 7 | 1.097 kg |

That table is the entire argument for a low-discrepancy sequence: below the full grid,
*where* the points go decides whether the feasible region is found at all.

See [`examples/lightest_passing_bracket.py`](../examples/lightest_passing_bracket.py).

## Halton, not Sobol

`SamplingStrategy.HALTON` is the radical inverse of the point index in one prime base per
dimension — base 2 gives 1/2, 1/4, 3/4, 1/8, 5/8 and base 3 gives 1/3, 2/3, 1/9. It is
elementary enough to check by hand, and the test suite does exactly that.

Sobol is the better sequence and it is not here, because it needs published direction
numbers per dimension and reproducing those from memory is the kind of guess this
library's citation contract exists to prevent. Halton also degrades above about eight
dimensions, where the high prime bases correlate and the points stripe rather than fill;
past eight it raises and names the grid instead.

**A Halton sweep is always provisional**, however many points it takes. It samples the box
continuously and visits neither bound on any axis, so evaluating a grid's worth of points
is not evaluating the grid — and for a Halton study `coverage` is a *budget* ratio rather
than a coverage claim. Only an untruncated grid sweep reports `complete`.

Neither sampler uses random state. Both are pure functions of the study declaration, so a
study re-run returns the identical set in the identical order and the whole sweep fits in
an evidence bundle.

## The agent may propose the study; it may not supply a number

A model is well placed to say *which* parameters are worth sweeping, over what bounds,
against what objectives — that is a framing judgement, and a wrong one costs compute
rather than correctness. Every objective value comes from the caller's deterministic
evaluator. A non-finite one is refused rather than sorted, because NaN compares False
against everything: it would neither dominate nor be dominated, and would sit on the
front for a reason that is not a reason.

## Tiered evaluation: don't mesh a design a wall thickness already ruled out

A study spends almost all of its time in the evaluator, and most candidates are refuted by
something cheap. `anvilate.explore.tiered_evaluator` turns several evaluators into one that
runs them **cheapest first and stops at the first whose scorecard does not pass**:

```python
from anvilate.explore import tiered_evaluator

evaluate = tiered_evaluator([
    ("geometry", screen_geometry),   # cheap: walls, clearances, mass budget
    ("closed form", screen_checks),  # the T1 analytical library
    ("mesh", run_fea),               # expensive, and most points never reach it
])
```

Every point's record says which tiers ran — `StudyEvaluation.tiers`, carried onto
`DesignPoint.tiers` and `SearchPoint.tiers` — so the saving is visible rather than claimed:
a point whose tuple is one name long is one the expensive tiers never saw.

Three things it is careful about. **The order is your claim, not a measurement**: nothing
here knows what an evaluator costs, so a list in the wrong order is still correct, just not
quick. **Every tier returns the objectives**, because a point refuted at the first tier still
has to be placed, and a later tier may refine an estimate an earlier one made. And a tier
that comes back `NOT_EVALUATED` stops the chain exactly as a `FAIL` does — a design whose
cheap check could not run has not earned an expensive one.

## Search: the best design found under a budget

When the box is too big to sweep, `anvilate.search.run_search` spends the budget where it
matters, on the same evaluator a sweep uses (the objective, and a scorecard that decides
feasibility):

```python
from anvilate.search import SearchStudy, SearchVariable, VariableKind, run_search

study = SearchStudy(name="speed reducer", objective="weight", seed=7, evaluations=4000,
                    variables=(SearchVariable(name="x3", kind=VariableKind.INTEGER,
                                              low=17, high=28), ...))
result = run_search(study, evaluate, starts=[base_design, repaired_design])
print(result)   # the best design found under the stated budget (4000 evaluations), ...
```

| Rule | What it means |
| --- | --- |
| Variables | continuous between bounds, integer between whole-number bounds, or a choice from a list that names its source; an unsourced list ("7.3 mm") is refused |
| Bundled tables | `table_choice("bore", table="bearings", field="bore")` binds a choice to a bundled table (`bearings`: ISO 15 bore, outer diameter, width; `nema_frames`: faceplate, bolt spacing, pilot), cited to the table's dataset record; the result names the rows that hold the chosen value (`bore = 25: 6805, 6005, 6205, 6305`) |
| Strategy | `evolutionary` (seeded differential evolution over the whole box, feasibility first) or `local` (a compass refinement of continuous variables from a declared `start`) |
| Determinism | every candidate of a generation is drawn before any is evaluated, and results are committed in draw order, so one worker and four record the same points; another seed records other ones |
| Feasibility | the scorecard's: a check that failed or did not run makes a point infeasible, and infeasible points are ranked by how far their safety factors fall short |
| Starts | `starts` are evaluated first: the base design, and the design its inverse repairs propose |
| Result | `BEST_FOUND`, never "optimal": every neighbor (a declared step either way, an integer by one, a choice to its adjacent entries) is evaluated for real, and a feasible better one is named and the result labeled *not locally confirmed* |

A result is a proposed edit, never an applied one. `search_diff(result, base_values)` names
each variable (by its path in the Design Spec, such as `element_params.thickness`) with its
base and found value; `apply_search_diff(document, diff)` returns the edited document,
keeping each quantity's unit, and appends to its `study_derived` the study, the seed, the
digest of the search record and the paths it changed, so a value a study chose never reads
as one the engineer stated.

From the shell, a study document names the spec it varies, and `anvilate study` runs it
through the same checks `anvilate check` runs:

```yaml
anvilate_study: 1
spec: padeye.spec.yaml          # relative to this file
name: lighter lug
objective: element_params.thickness
seed: 7
evaluations: 40
variables:
  - {name: element_params.thickness, low: 8, high: 30}
  - {name: element_params.hole_diameter, table: bearings, field: outer_diameter}
```

```text
anvilate study lighter-lug.study.yaml --output studies/
```

It prints the result and the edit it proposes (`element_params.thickness: 20 -> 12.1`), and
writes every point evaluated to `studies/` when asked. The spec is not changed. Over MCP,
`run_study` takes a `run_validation` subject and the same study (without `spec`, which is
the subject's), spends at most 2,000 evaluations per call, and returns a bounded summary
([study-summary 1.0.0](api/schemas/study-summary.schema.json)) with the record written to
the output folder. A candidate
the spec's own validators refuse is infeasible, naming the refusal. Exit 0 when a feasible
design was found, 1 when none was, 3 for a study or spec it cannot read.

The search is held against a published benchmark: the Golinski speed reducer, as Cagnina,
Esquivel and Coello Coello (Informatica 32, 2008) state it, with the pinion's teeth an
integer. With seed 7 and 4,000 evaluations it lands within 0.05% of the published best
weight, 2,996.348165, and every point it reports as feasible satisfies all eleven
constraints. A second, from the same paper, holds the choice variables: the pressure vessel,
whose shell and head thicknesses are stocked plate (multiples of 0.0625 in), lands on the
published best cost, 6,059.714335, to within 0.01%, every candidate taking a stocked
thickness.

Out of scope: topology optimisation, FEA in the loop, surrogate models, and Bayesian
optimisation. When an evaluation costs microseconds, an exhaustive seeded sweep with
exact sorting is faster than the machinery for avoiding one, and a seeded search is the
step beyond it.
