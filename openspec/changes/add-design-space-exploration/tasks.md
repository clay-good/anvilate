# Tasks: Design-space exploration

## 1. Contracts

- [ ] 1.1 Study type (parameters + bounds + units, objectives, constraints, strategy,
      budget, seed)
- [ ] 1.2 Study result type (evaluated set, front, governing constraint per point,
      coverage)

## 2. Implementation

- [ ] 2.1 Seeded samplers: full-factorial grid and Sobol, deterministic ordering
- [ ] 2.2 Evaluation over registered checks with feasibility marking
- [ ] 2.3 Exact non-dominated sorting; governing-constraint attribution
- [ ] 2.4 Budget/time enforcement with coverage reporting
- [ ] 2.5 Evidence-bundle serialization of the full sweep

## 3. Tests

- [ ] 3.1 Determinism: same seed → identical evaluated set and order
- [ ] 3.2 Front correctness against a brute-force reference on a small analytic space
- [ ] 3.3 Truncation reports provisional; infeasible points retained and labeled

## 4. Docs & examples

- [ ] 4.1 Example: lightest passing bracket across thickness and rib count, front plotted
- [ ] 4.2 Explanation page: why the agent may propose a study but never supply a number
