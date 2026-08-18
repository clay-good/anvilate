# Tasks: Design-space exploration

## 1. Contracts

- [x] 1.1 Study type (parameters + bounds + units, objectives, constraints, strategy,
      budget, seed)
- [x] 1.2 Study result type (evaluated set, front, governing constraint per point,
      coverage)

## 2. Implementation

- [x] 2.1 Seeded samplers: full-factorial grid and Sobol, deterministic ordering
- [x] 2.2 Evaluation over registered checks with feasibility marking
- [x] 2.3 Exact non-dominated sorting; governing-constraint attribution
- [x] 2.4 Budget/time enforcement with coverage reporting
- [ ] 2.5 Evidence-bundle serialization of the full sweep

## 3. Tests

- [x] 3.1 Determinism: same seed → identical evaluated set and order
- [x] 3.2 Front correctness against a brute-force reference on a small analytic space
- [x] 3.3 Truncation reports provisional; infeasible points retained and labeled

## 4. Docs & examples

- [x] 4.1 Example: lightest passing bracket across thickness and rib count, front plotted
- [x] 4.2 Explanation page: why the agent may propose a study but never supply a number

## Scope as shipped

Everything but 2.5. `src/anvilate/explore.py` carries the study and result types, both
samplers, the exact non-dominated sort with governing-constraint attribution, and budget
enforcement with coverage reporting. `examples/lightest_passing_bracket.py` and
`docs/design-space-exploration.md` are the example and the explanation page.

**Sobol was replaced by Halton, deliberately.** 2.1 asked for Sobol; Sobol needs
published direction numbers per dimension and no anchor was available to check them
against, which is exactly the guess the citation contract exists to prevent. Halton is
the radical inverse of the index in one prime base per dimension — elementary enough to
verify by hand, and the suite does: base 2 gives 1/2, 1/4, 3/4, 1/8, 5/8 and base 3 gives
1/3, 2/3, 1/9. It degrades above eight dimensions and raises there rather than striping
quietly.

**2.5, evidence-bundle serialisation, is left open.** `StudyResult` is a frozen pydantic
model so `model_dump()` already round-trips the whole sweep; what is missing is the
binding into `anvilate.evidence`, which today collects standards provenance from a
`DesignSpec` and has no hook for a study. That is a bundle-shape decision, not
arithmetic, and it belongs with the attestation work in `add-evidence-attestation`.

**The three rules that turned out to carry the change**, all of them versions of the
library's silent-green doctrine:

1. A point that did not pass is never on the front, and `NOT_EVALUATED` is not a pass.
   The lightest design in the worked example is 3.75x lighter than the lightest passing
   one, and it fails.
2. Infeasible points are kept and labelled, never dropped. A front over the survivors
   looks like the whole space.
3. A truncated sweep reports `provisional` coverage and, if nothing feasible was reached,
   `best()` returns `None` rather than the best of the failures.
