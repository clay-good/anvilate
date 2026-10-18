# Design notes: Design optimization

Research done on 2026-10-17.

## Why a search now, when the module docstring argues for a sweep

`src/anvilate/explore.py` argues that a seeded exhaustive sweep beats Bayesian
optimization when each evaluation takes microseconds. That holds for one part. It fails
for a product with ten variables, and for any objective that needs a solver run of up to
a minute. The sweep stays the default wherever its plan fits the budget; a search is for
the cases where it does not.

## Libraries

| Library | License | Mixed variables | Repeatable for a seed | Decision |
| --- | --- | --- | --- | --- |
| pymoo | Apache-2.0 | `Real`, `Integer`, `Choice`, `Binary` via `MixedVariableGA`; NSGA-II-style survival for several objectives | Yes, with `seed=` | Evolutionary search (optional extra) |
| SciPy `minimize(method="cobyqa")` (1.14+) | BSD-3 | Continuous, derivative-free, constrained | Deterministic | Local refinement |
| SciPy `differential_evolution` | BSD-3 | `integrality=` per variable | Yes, with `rng=` (`seed=` is legacy) | Alternative single-objective search |
| Optuna | MIT | Native integer and categorical | Not when parallel (its own FAQ) | Not used |
| Dakota | LGPL-2.1+ | Wide | Seedable | Not used: separate C++ program, license |

Sources: https://pymoo.org/customization/mixed.html ,
https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.differential_evolution.html ,
https://docs.scipy.org/doc/scipy/release/1.14.0-notes.html ,
https://github.com/optuna/optuna/blob/master/docs/source/faq.rst

## Topology optimization

| Tool | License | Note |
| --- | --- | --- |
| dl4to4ocp | MIT | Runs DL4TO on CadQuery/build123d solids: the closest fit to this stack |
| DL4TO | Apache-2.0 | PyTorch SIMP on structured grids |
| PyTopo3D | MIT | SIMP, marching-cubes STL output |
| beso (CalculiX) | LGPL-3.0 | Needs FreeCAD; not used |
| JAX-FEM | GPL-3.0 | Not usable in MIT code |

Turning a density field into a B-rep is an open research problem (skeleton fitting,
B-spline lofting, voxel-to-frame reconstruction), and nTop treats manual reconstruction as
"a major impediment". Hence seeds, never parts.

## Benchmarks

- **Golinski speed reducer.** Golinski 1970 (doi:10.1016/0022-2569(70)90064-9), reduced to
  11 constraints by Ray 2003 (doi:10.2514/2.1984). Seven variables: face width, module,
  pinion teeth (integer), two shaft lengths, two shaft diameters. Best-known weight about
  2,994.4 at (3.5, 0.7, 17, 7.3, 7.715, 3.350, 5.287); published values differ in the third
  decimal, so the test tolerance must allow for that. Reference code:
  https://psdr.readthedocs.io/en/latest/_modules/psdr/demos/golinski.html . A regression
  benchmark only, not engineering validation: its constants are ad hoc.

## How others frame "optimized"

- Fusion generative design produces "multiple editable design solutions using a single
  cloud solve": https://help.autodesk.com/cloudhelp/ENU/Fusion-GenerativeDesign/files/GD-OVERVIEW.htm
- Altair OptiStruct encodes manufacturing limits as constraints (draw direction, minimum
  member size), and calls minimum member size quality control, not quantity control.
- SOLIDWORKS' AI companions (2026 FD01, beta) need cloud-stored data for some skills.

## Evidence that checking is the gap

- "Self-Improving CAD Generation Agents with FEA as Feedback" (arXiv 2605.17448, May
  2026): no strict-passing multi-part STEP assembly from Codex or Claude Code on the first
  attempt; the best setup met about 20% of the requirements.
- CAD-bench (ICML 2026): about 4% on functional gearbox checks.
