# Tasks: Design optimization

Phase 1 needs nothing new beyond pymoo. Phase 2 needs `add-local-fea`. Phase 3 is
independent and optional.

## 1. Search over closed-form checks

- [ ] 1.1 Study schema: `search` strategy beside `sweep`; continuous, integer and choice
      variables; budgets in evaluations, solver runs and wall-clock
- [ ] 1.2 Choice variables bound to bundled tables (preferred modules, stock thickness,
      bearing series, motor frames); refusal of unsourced values
- [ ] 1.3 Seeded evolutionary search (pymoo, optional extra) and local refinement (SciPy
      COBYQA); deterministic commit order under parallel evaluation
- [ ] 1.4 Inverse-seeded starting points
- [ ] 1.5 Neighborhood check and the "not locally confirmed" label
- [ ] 1.6 Result as a spec diff; provenance on apply
- [ ] 1.7 Golinski speed-reducer regression from the published definition; a second
      mixed-variable benchmark

## 2. Search with FEA in the loop

- [ ] 2.1 Tiered evaluation, cheapest first; per-point record of tiers run
- [ ] 2.2 Content-digest evaluation cache, shared with `add-local-fea`'s result store
- [ ] 2.3 One MCP tool and one CLI command; task with progress and cancellation
- [ ] 2.4 Worked study: the gear reducer, mass under drive-train checks and housing FEA

## 3. Topology seeds (optional)

- [ ] 3.1 Evaluate dl4to4ocp (MIT) and DL4TO (Apache-2.0) as an optional extra on
      build123d solids; record the license review
- [ ] 3.2 Seed output: density field, picture, labeled mesh; export refusal as a part
- [ ] 3.3 A docs page: what a seed is, and why it is not a part
