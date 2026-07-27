# Tasks: Typed MBD callouts

## 1. Contracts

- [ ] 1.1 Callout types: surface finish, coating/plating, heat treatment, structured note
- [ ] 1.2 Persistent characteristic identifier assignment, stable across regeneration and
      revision (adopting MBC-class semantics)
- [ ] 1.3 Tag-scoped resolution and validation

## 2. Implementation

- [ ] 2.1 Fatigue surface-factor derivation from declared finish, cited
- [ ] 2.2 Plated-dimension handling in fit and thread-engagement checks
- [ ] 2.3 Heat-treat condition in material property resolution
- [ ] 2.4 Consumed-value and contradiction reporting in the scorecard

## 3. Tests

- [ ] 3.1 Identifier stability across regeneration and revision; callout diff
- [ ] 3.2 Finish callout measurably changes a fatigue result and is reported
- [ ] 3.3 Unknown heat-treat condition → "not evaluated"; contradiction surfaced

## 4. Docs & examples

- [ ] 4.1 Example: shaft where declared finish and plating change the verdict
- [ ] 4.2 Explanation page: callouts are inputs, not annotations
