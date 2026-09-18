# Constraint topology

A mount rarely fails on strength. It fails on over-constraint: two features both
preventing the same degree of freedom. The part assembles and the analysis passes. Then it
distorts on bolt-up, drifts with temperature and never returns to the same position twice.
Where a freedom is constrained more than once, the redundant constraints either do nothing
or deform the body, and the loads become indeterminate. A stress screened across that path
is not conservative or unconservative. It is unfounded.

`anvilate.topology` counts a body's six freedoms against the constraints its author
declares. It does not solve for the load division, and it never infers a constraint from
geometry.

## What you get

```python
from anvilate.topology import Constraint, ConstraintKind, Frame, Freedom, tally

frame = Frame(name="plate frame", x="along the dowel line", y="across the dowel line",
              z="the plate normal")
counted = tally("sensor plate", frame, (
    Constraint(feature="machined face", kind=ConstraintKind.PLANAR_FACE,
               removes=(Freedom.TZ, Freedom.RX, Freedom.RY)),
    Constraint(feature="dowel A", kind=ConstraintKind.PIN_IN_HOLE,
               removes=(Freedom.TX, Freedom.TY)),
    Constraint(feature="dowel B", kind=ConstraintKind.PIN_IN_HOLE,
               removes=(Freedom.TX, Freedom.RZ)),
))
counted.over()           # translation along x: dowel A and dowel B, both named
counted.entry()          # FAIL, with each interface's contribution: 3 + 2 + 2 = 7 removed
counted.qualify(shear)   # a dowel-shear result, carrying the indeterminate load path
```

Each freedom comes out in one of five states:

| State | Meaning |
| --- | --- |
| free | Nothing removes it and nobody declared it intended. Named physically: "rotation about z (the plate normal): FREE", never an index. A finding. |
| intended | Nothing removes it, and the body declares it on purpose, with the purpose. Not a finding. |
| exact | Exactly one constraint removes it. |
| over | More than one does, undeclared. Every competing constraint is named, and the consequence is stated: which of them carries the load depends on manufacturing variation, not on design intent. A finding. |
| declared redundant | More than one does, and each redundancy is declared with a justification and the mechanism that makes it tolerable. Not a finding, and the justification is printed wherever the tally is. |

## The rules

| Rule | What it means |
| --- | --- |
| The frame is part of the answer | Every tally names its frame, and every freedom is named against the frame's own words for its axes. "Rotation about z" is actionable only when z is "the bore axis". |
| A constraint counts what its interface removes | Each kind removes a fixed number of freedoms: a planar face 3, a pin in a hole 2 (4 with a long engagement), a slot 1 (2 long), a ball in a vee 2, a ball in a cone 3, a flat contact 1, a bonded joint 6, a blade flexure 3. A declaration that miscounts its own interface is refused. |
| The arithmetic is shown | The entry lists each interface's contribution and the total, so a reader can check the count. |
| Declaring a redundancy does not silence what it does not resolve | Only a compliant interface determines how the load divides: it sheds its share to the stiff constraint. A controlled assembly sequence or a machining operation at assembly (match-reaming) removes the strain locked in at fit-up. Under service load the division is still set by stiffness nobody declared, so the path stays indeterminate. |
| An indeterminate path travels | `qualify(entry)` appends the cause to any result that ran, naming the freedoms and the competing constraints. A number on an over-constrained path is never printed plain. Resolving the redundancy clears it. |
| Nothing is inferred | A body that declares no constraints is `not_evaluated`, naming the body. It has not been counted, and that is different from counting to zero. An intended freedom that a constraint removes anyway is refused. |

[`examples/over_constrained_mount.py`](../examples/over_constrained_mount.py) runs the same
plate with two round dowels and then with one dowel moved into a slot, side by side.

## In a Design Spec

A document declares how its part is located under `constraint_topology`, each constraint
acting at a feature the document already tags:

```yaml
constraint_topology:
  frame: {name: plate frame, x: along the dowel line, y: across it, z: the plate normal}
  constraints:
    - {feature: mounting_face, kind: planar_face, removes: [tz, rx, ry]}
    - {feature: dowel_a, kind: pin_in_hole, removes: [tx, ty]}
    - {feature: dowel_b, kind: slot, removes: [rz]}
  intended: []
```

`screen_spec` adds one `constraint topology` entry, and when the count says the load path is
indeterminate, every element check that ran carries the qualifier in its own line. Moving
location duty from one feature to another shows in the spec diff as a change to this list. A
constraint at an untagged feature, or an intended freedom that a constraint removes, is
refused when the document is read.

## Status

This is the constraint type, its archetypes, the per-freedom tally, the indeterminacy
qualifier and the Design Spec declaration (`openspec/changes/add-constraint-topology`, every
task). Screening a document qualifies every element check on an indeterminate part. Along a
[dependency chain](check-dependencies.md),
`tally.qualify_downstream(run, "bolt load")` qualifies the named check and every check the
graph says consumes it, directly or through others. A check the graph does not connect to the
load path is left as it ran.
