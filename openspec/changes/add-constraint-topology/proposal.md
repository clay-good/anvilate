# Change: Constraint topology — count the constraints before trusting the stress

## Why

Ask a precision-instrument designer what most often ruins a mount and the answer is not
strength. It is over-constraint: two features both preventing the same degree of freedom.
The part assembles, the analysis passes, and then it distorts on bolt-up, drifts with
temperature, wears unpredictably, and never returns to the same position twice. The
literature is unambiguous — where a degree of freedom is constrained more than once, the
redundant constraints are either ineffective or they deform the body, and **the loads
become indeterminate**.

That last clause is why this belongs in Anvilate specifically. An indeterminate load path
means the stress screen downstream of it is not conservative, not unconservative, but
unfounded — and today Anvilate would report it as a clean number with a citation. A
screening tool that reports a confident stress in an over-constrained joint is doing the
thing this project refuses to do.

Nothing screens this. It is taught in precision machine design, it has a canonical
literature, and it is pure counting — no mesh, no solver, no material data. It applies far
beyond optics: fixtures and subplates, bolted brackets, bearing pairs, machine guards,
robot end-effector adapters, and every kinematic or flexure mount. It is the cheapest
high-value screen still missing from the T0/T1 layer.

## What Changes

- New capability spec `constraint-topology`: a body's constraints are declared as typed
  data, the constrained degrees of freedom are counted, and each of the six is reported as
  under-, exactly-, or over-constrained with the responsible constraints named.
- Under-constraint is reported as a named rigid-body freedom, not as a generic warning —
  "free to rotate about the bore axis" is actionable; "under-constrained" is not.
- **Over-constraint marks the load path indeterminate**, and every downstream strength,
  deflection, and alignment screen that depends on it reports its result as resting on an
  indeterminate load path — or declines to report it.
- A declared intentional over-constraint is accepted with its justification recorded, so
  the common deliberate cases (a bolted flange face, a press fit) are not noise, while an
  undeclared one is a finding.
- `spec-ir` gains the constraint declaration so topology is part of the document.

## Impact

- Affected specs: new `constraint-topology`; `spec-ir` (ADDED). Interacts with
  `validation-gauntlet` (a new T0 screen and a qualifier on downstream results),
  `assembly-robotics` (joints already carry a typed model), `check-dependency-graph`
  (indeterminacy propagates along declared consumption), and `tolerance-management`
  (an over-constrained interface is where tolerance stack-ups bite).
- Affected code (when implemented): a constraint type, a degree-of-freedom counter, the
  indeterminacy qualifier, and the downstream propagation.
- Explicitly out: solving the indeterminate load path; contact or friction modeling;
  compliance-based constraint analysis, which is a stiffness question rather than a
  counting one; and automatic inference of constraints from geometry.
