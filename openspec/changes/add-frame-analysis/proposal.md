# Change: Frame analysis — member forces solved from the frame, not typed into each member

## Why

Anvilate checks a member against a force somebody gave it. For a single beam that force
is a load case. For a frame of members, a skid, a machine base, a guardrail run, a
mezzanine or a product whose load path has more supports than statics can resolve, the
force in each member comes from how stiff the members are, and today nothing in Anvilate
computes that:

- `product-screening` carries product loads to ground by rigid-body statics and, by its
  own rule, names an indeterminate path rather than guessing a split. That is the right
  refusal, and it leaves every real frame unresolved.
- The member-force doorway (`docs/analysis-interop.md`) accepts forces from Pynite or a
  commercial solver, with every convention declared. That works for an engineer who runs
  a frame solver. The engineer who asked their agent for "a skid frame for this pump" has
  not run one, and the agent cannot.
- A frame of members is already a shipped combination. It draws and exports, and each
  member is screened against a force the agent typed, so a typo in one member's moment is
  invisible: every member still passes on the number it was given. `add-drive-trains`
  removed exactly this failure for gearboxes by deriving torques from one input; this
  change does the same for frames.

The method is the oldest deterministic solver in structural engineering: the direct
stiffness method, linear elastic, first order. It needs no mesh, no external binary, and
no convergence study, and its answers are checked against closed-form cases in every
textbook. Pynite (MIT, 3.2.0 released 2026-09-13) does static, P-Δ and modal analysis of
3D frames and is tested against textbook problems in CI; the project has listed it as the
reference implementation since the start. It is the referee here, not a dependency.

## What Changes

| Area | Change |
| --- | --- |
| Frame declaration | A frame is declared over tagged items: nodes, members with their section and material, supports by restrained freedom, member end releases, and loads (nodal, distributed, point, and self-weight from density). A frame-of-members combination and a product's connections can each declare one. |
| Linear elastic solve | Direct stiffness, three-dimensional, first order by default. A mechanism (singular stiffness) is refused naming the free rigid-body or mechanism mode. Equilibrium of reactions against applied loads is reported as a residual. Second-order (P-Δ) analysis runs only when declared, with the method named. |
| Member forces to checks | Each member's axial force, shears, moments and torsion at stations become member-force records in the shape the existing ingestion contract defines, with Anvilate's own axis and sign convention declared on the record, so the existing member checks run on them as dependent entries. |
| Indeterminate paths resolved | Where a product's load path is indeterminate and a frame model over its connections is declared, the split comes from the solve and is attributed to it; without a declared model the existing refusal stands. |
| Deflections | Nodal and mid-member deflections against limits the document declares. No default limit. |
| Verification | Closed-form cases (propped cantilever, fixed-fixed beam, continuous beam, portal frame) re-derived from public textbook solutions, plus a cross-check against Pynite as an optional referee, gate every release. |

## Impact

- New capability: `frame-analysis`. Delta: `analysis-library` (ADDED).
- Builds on the member-force and section-property ingestion doctrine in
  `analysis-library` (the solve produces what the doorway accepts, with the same declared
  conventions), `add-product-structure` and `add-interface-contracts` (connections are
  where members meet), `add-check-dependency-graph` (member checks depend on the solve
  entry), and `add-product-screening` (the indeterminate-path rule gains a resolution it
  can attribute). Feeds `add-walking-working-surfaces-pack` (guardrail and stair frames),
  `add-equipment-anchorage` (reactions at anchors) and `add-ifc-structural-export`.
- Optional dependency: Pynite (MIT) as a referee in tests and as an opt-in alternative
  engine whose identity and version are recorded. The in-house solve has no new
  dependency beyond the numerical library already installed.
- Explicitly out:
  - Plates, shells and solids (that is `add-local-fea`).
  - Nonlinear material, large displacement, contact, cables.
  - Semi-rigid connection stiffness. Connections are rigid or released as declared.
  - Dynamics beyond the existing equivalent-static screens; modal analysis of frames is a
    later phase under the same contract.
