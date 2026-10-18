# Tasks: Local FEA

Implements the T3 requirements in `validation-gauntlet`. Phase 1 needs only built parts;
phase 2 needs `add-product-structure`.

## 1. Pipeline on parts

- [ ] 1.1 Solver and mesher discovery (setting, environment, path), version pins, digest
      and solver build recorded in the bundle; `doctor` entries per `add-guided-design-journey`
- [ ] 1.2 Tag signatures recorded at build; signature matching after import, verified
- [ ] 1.3 Gmsh meshing: second-order tets, size fields from tagged features, physical groups
- [ ] 1.4 Deck writer (shared with `add-cae-handoff`): materials with sources, supports and
      loads by tag, one step per load case, unit system stated
- [ ] 1.5 Sandboxed ccx subprocess with CPU, memory and time caps; cancellation leaves no
      process
- [ ] 1.6 `.frd`/`.dat` readers in-repo, gated on the pinned version
- [ ] 1.7 Convergence study (three meshes, GCI) feeding the existing gate; singularity
      reporting with read-off alternatives

## 2. Physics

- [ ] 2.1 Linear static and modal checks against spec limits
- [ ] 2.2 Steady-state heat transfer: temperatures, fluxes, generation, film convection
- [ ] 2.3 Thermal stress by sequential `*TEMPERATURE` read on the same mesh
- [ ] 2.4 T1-versus-T3 comparison entries with a stated agreement band

## 3. Products

- [ ] 3.1 Sub-tree assembly mesh; connections as `*TIE` (or conformal `fragment` where
      declared)
- [ ] 3.2 Unconnected-slave-node file read; a tie that did not connect fails the run
- [ ] 3.3 Idealization statement per connection; joint hand screens kept
- [ ] 3.4 Worked case: the gear reducer housing with covers, loaded by the bearing
      reactions from `add-drive-trains`, with oil-side heat

## 4. Verification and surface

- [ ] 4.1 NAFEMS LE1, LE10 and T4 with re-derived targets; closed-form cases; the gate on
      version changes
- [ ] 4.2 Contour picture with the labeled peak; deck, mesh and results in the output folder
- [ ] 4.3 Task execution with progress; content-digest result cache
- [ ] 4.4 A docs page: what the FEA tier does, its assumptions, how to install the solver
- [ ] 4.5 Owner decision on solver provisioning (see `design.md`), recorded in
      `docs/design-decisions.md` if it adds a decision
