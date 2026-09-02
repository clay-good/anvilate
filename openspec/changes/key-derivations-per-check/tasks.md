# Tasks: Key derivations per check

## 1. Decide

- [ ] 1.1 Where the stated reason lives — a field on `ScorecardEntry`, or on the check that
      builds it. **Blocking**: the gate reads whichever it is, and only the first travels
      into the evidence bundle.
- [ ] 1.2 The three kinds, named. "Lookup" already means "no formula"; a numerically solved
      result needs a name that does not read as either lookup or debt.

## 2. The type (follows 1.1)

- [ ] 2.1 The declaration, refused when empty — a reason that says nothing is the silence
      this replaces.
- [ ] 2.2 An entry may not declare both a derivation and an absence of one.

## 3. The gate (follows 2)

- [ ] 3.1 Coverage counts an entry as answered when it is worked **or** declares why it is
      not, so a clause clears when every entry has answered.
- [ ] 3.2 The side file keeps only clauses that are debt everywhere they are cited.
- [ ] 3.3 The anti-relabelling rule follows the declaration: an entry carrying a computed
      safety factor may not declare "no formula".

## 4. Pay off what it unblocks

- [ ] 4.1 `AISC 360-16 §L3`, `ASCE 7-22 §2.3.1`, `ASME BTH-1 §3-1.4` — declare the
      non-computing entries and write the closed forms that exist.

## Status

Not started. Written rather than half-built: the field is five minutes and the decision in
1.1 is not, and a declaration on the wrong object is harder to move than to add.
