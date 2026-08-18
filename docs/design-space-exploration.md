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
because a grid walks its first parameter slowest, so those 20 points are the three
shallowest height rows and every one of them fails.

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

Out of scope: topology optimisation, FEA in the loop, surrogate models, and Bayesian
optimisation. When an evaluation costs microseconds, an exhaustive seeded sweep with
exact sorting is faster than the machinery for avoiding one.
