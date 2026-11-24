# Tasks: Local FEA

Implements the T3 requirements in `validation-gauntlet`. Phase 1 needs only built parts;
phase 2 needs `add-product-structure`.

## 1. Pipeline on parts

- [ ] 1.1 Solver and mesher discovery (setting, environment, path), version pins, digest
      and solver build recorded in the bundle; `doctor` entries per `add-guided-design-journey`
      — **waits on the owner's licensing decision** (design.md, "The licensing question"):
      what this discovers depends on whether Gmsh may be imported or must be a subprocess.
      Two further notes from 2026-11-24. The version pins cannot be written from here:
      neither program is installed on this machine, so what `ccx -v` and `gmsh --version`
      actually print has not been READ, and a parser written from a remembered format is
      the thing this repository refuses. And `doctor`'s entry should stay as it is until
      the pipeline exists — it says no FEA backend is shipped, which is true; telling a
      user to install CalculiX before 1.3 to 1.7 are built would point them at something
      Anvilate cannot yet use
- [ ] 1.2 Tag signatures recorded at build; signature matching after import, verified
      (`anvilate.mesh`: `face_signatures` records each tagged face's area, its AREA
      centroid and — where the face is flat — the way it faces, and `match_face_signatures`
      puts those against the faces that came back. Verified, never assumed: a tag matching
      nothing, a tag matching two faces, and a face two tags both claim are each refused by
      name, because a load on the wrong face is a different problem solved correctly and
      nothing downstream says so. The centroid is `CenterOf.MASS` and not the parametric
      centre — on a shaft's outside surface those differ by a radius — and a curved face
      records no normal rather than the one at its parametric centre. What waits on 1.3 is
      the other side: no mesher is wired in, so the signatures of an IMPORTED solid have no
      producer yet, and the round-trip tolerances are float-noise defaults rather than a
      mesher's measured ones)
- [ ] 1.3 Gmsh meshing: second-order tets, size fields from tagged features, physical groups
      — **waits on the same decision.** "Meshing with size fields and physical groups"
      reads as the Python API, which is in-process and therefore linking a GPL-2.0+ library
      into an MIT project; a subprocess pipeline over `.geo`/`.msh` is the alternative and
      is a different design. The wheel is not the obstacle: gmsh 4.15.2 publishes
      `py2.py3-none` wheels that install on every Python here and in CI (checked
      2026-11-24), which is precisely why the licence has to be settled first
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
