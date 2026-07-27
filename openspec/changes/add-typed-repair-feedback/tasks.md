# Tasks: Typed repair feedback

## 1. Scorecard contract

- [ ] 1.1 Extend the scorecard record type with optional repair-hint fields (parameter,
      direction, corrective value, hint provenance)
- [ ] 1.2 Add optional upper margin bound to acceptance criteria; new over-margin warning
      rendering
- [ ] 1.3 Governing-check computation and governing-change diff across revalidations

## 2. Analysis bindings

- [ ] 2.1 Bind existing design inverses (isolator deflection, Lewis module, bearing
      rating, bolt count, …) to their forward checks as hint providers
- [ ] 2.2 Monotonicity declarations for hint direction on non-inverse checks

## 3. Tests

- [ ] 3.1 Hint correctness: corrective value satisfies the forward check at the required
      margin (round-trip per bound inverse)
- [ ] 3.2 Two-sided band: pass, over-margin warning, and opt-in behavior
- [ ] 3.3 Governing-check identification and change reporting

## 4. Docs & examples

- [ ] 4.1 Example: a failing screen repaired by its inverse in one step
- [ ] 4.2 Documentation for the over-margin warning and how to declare bands
