# Change: Local FEA — build the T3 tier with Gmsh and CalculiX, for parts and products

## Why

The specs have promised a T3 tier since the start: linear-static FEA per load case with a
mesh-convergence gate, modal screening, "no silent green" on a mesh failure
(`validation-gauntlet`). The stack table names Gmsh and CalculiX. None of it is built.
`run_fea_validation` can only answer *not evaluated*, `trim-agent-tool-set` proposes
removing it until a solver ships, and `anvilate doctor` fails on every install because the
solver is missing. Meanwhile the question users bring keeps getting bigger: not "is this
bracket thick enough" but "will this gearbox housing hold its bearings, and how hot does
it run".

Hand methods answer most of a part's questions, and they cannot answer these:

- **Stress where no handbook case fits.** A housing with ribs, bosses and bearing bores
  is not a beam, a plate or a cylinder.
- **Heat and the stress it causes.** A gearbox housing warmed from inside and cooled
  from outside, or a bracket between a hot motor and a cold frame.
- **Several parts together.** Covers bolted to a housing share the load in a way no part
  card sees.

The tools are ready. CalculiX 2.23 (October 2025) and Gmsh 4.15.2 install on macOS,
Linux and Windows from conda-forge, and Gmsh also from a PyPI wheel. Both are GPL, which
is why the architecture has always been subprocess-and-files. An MIT-licensed MCP server
already runs STEP → Gmsh → CalculiX for agents, which shows the loop is practical. What
Anvilate adds is what that server does not have: semantic tags from the spec instead of
faces picked by bounding box, the convergence gate, a verdict against cited limits, and
the comparison with the hand check for the same quantity.

## What Changes

| Area | Change |
| --- | --- |
| The pipeline | Built solid with tags → Gmsh mesh with tags mapped to physical groups by geometric signature → CalculiX deck → solver subprocess in the sandbox → result files read into typed check entries. No human step. |
| Analyses | Linear static per load case (the existing requirement), modal (existing), **steady-state thermal**, and **thermal stress** (the temperature field applied to the structural step). Buckling follows under the same contract. |
| Products | A product or a sub-tree solved as one model with each declared connection tied. A joint that bonding misrepresents stays checked by its own hand screen, and the result says so. |
| Singularities | A peak that grows under refinement at a sharp corner or a point load is reported as a singularity, never as a stress, with the reading that would make it one. |
| FEA beside the hand check | Where T1 and T3 screen the same quantity, the card shows both and warns when they disagree. |
| Finding the solver | Located from a setting, the environment or the path; version pinned; recorded in the bundle. Absent means not evaluated with the install command, never a silent download. |
| Verified | NAFEMS-class benchmarks (re-derived targets), a thermal benchmark, and closed-form cases gate every solver or mesher version change. |
| Agent surface | A contour picture the agent can see, files the engineer can open, cancellable tasks for long runs, results cached by content digest. |

## Impact

- New capability: `local-fea`. Implements the existing `validation-gauntlet` T3
  requirements (linear static, mesh convergence, modal, no silent green, stated
  assumptions) rather than restating them.
- Shares its mesher and deck writer with `add-cae-handoff`: the deck Anvilate solves and
  the deck it hands the analyst come from one writer.
- Feeds `add-design-optimization` (FEA objectives and constraints) and
  `add-guided-design-journey` (the `simulated` stage). Uses `add-drive-trains` for housing
  loads (bearing reactions) and `add-product-structure` for item paths.
- Settles `trim-agent-tool-set`'s open row: the FEA tool returns real verdicts once this
  ships.
- **One decision for the owner, recorded under `design.md`:** whether `anvilate fetch`
  may install a digest-pinned solver binary with consent (a new design decision beside
  D3), or whether the solver stays a user install through conda-forge, a package manager
  or the official container. The spec allows either and forbids only a silent download.
- Explicitly out:
  - Frictional and separating contact, bolt pretension, and plasticity in the first
    phase. They need nonlinear solves and a different convergence story.
  - Transient thermal, explicit dynamics, and fatigue from FEA stress fields.
  - CFD.
  - Running commercial solvers (that is `add-cae-handoff`).
  - Shipping any GPL binary inside the wheel.
