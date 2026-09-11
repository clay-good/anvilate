# Tasks: Constraint topology

## 1. Contracts

- [ ] 1.1 Constraint type: the feature it acts at, the degrees of freedom it removes, its
      kind, and whether it is declared intentionally redundant with a justification
- [ ] 1.2 Constraint archetypes for the common interfaces (planar face, pin in hole, slot,
      ball in vee, ball in cone, flat contact, bonded joint, flexure blade)
- [ ] 1.3 Spec IR declaration, round-trip, and diff legibility

## 2. Counting

- [ ] 2.1 Per-degree-of-freedom tally in a declared reference frame
- [ ] 2.2 Under-constrained freedoms named physically, not as an index
- [ ] 2.3 Over-constrained freedoms with every responsible constraint named
- [ ] 2.4 Exactly-constrained reported as a positive result, with the count shown

## 3. Consequences

- [ ] 3.1 Indeterminacy qualifier on the affected load path
- [ ] 3.2 Propagation: downstream screens consuming that path carry the qualifier or
      decline, via the declared-consumption mechanism
- [ ] 3.3 Declared intentional redundancy suppresses the finding and records the reason

## 4. Tests

- [ ] 4.1 A three-bolt-and-two-dowel plate is reported over-constrained with the dowels
      named — the textbook case
- [ ] 4.2 A ball-vee-flat coupling is reported exactly constrained with six accounted for
- [ ] 4.3 A stress screen on an over-constrained path cannot render an unqualified number
- [ ] 4.4 Removing a constraint changes the tally, proving the count is computed from the
      declaration and not asserted in the test

## 5. Docs & examples

- [ ] 5.1 Worked example: the same mount over-constrained and then exactly constrained,
      with both reports side by side
