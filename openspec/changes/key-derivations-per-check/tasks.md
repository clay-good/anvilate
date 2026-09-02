# Tasks: Key derivations per check

## 1. Decide

- [x] 1.1 Where the stated reason lives — **on the entry**. It travels into the evidence
      bundle and the JSON with the verdict it explains, and the gate reads it off the same
      collector it already reads derivations from. The builder was the alternative and it
      keeps the identity problem this change exists to escape: the gate would have to reach
      the builder to read it, and a builder is not what a reviewer holds.
- [x] 1.2 The three kinds, named: `lookup`, `numeric_result`, and debt. The first two are
      `DerivationAbsence` members and are declarable. **Debt is not a member** — it is the
      absence of any declaration, and a check that could file its own debt would retire it
      by describing it. The change's own spec delta said all three were declarable; it was
      corrected before this was built.

## 2. The type (follows 1.1)

- [x] 2.1 `Underived(kind, reason)`, refused when the reason is blank.
- [x] 2.2 An entry may not declare both a derivation and an absence of one — and the check
      runs on `model_copy` too, via `RevalidatedModel`, because copying is how every pack
      in the library finishes an entry.

## 3. The gate (follows 2)

- [x] 3.1 Coverage counts an entry as answered when it is worked **or** declares why it is
      not, so a clause clears when every entry has answered. The run prints both figures;
      they are different measurements and only one of them can ever reach 100%.
- [x] 3.2 The side file keeps only clauses that are debt everywhere they are cited.
- [x] 3.3 The anti-relabelling rule, made mechanical: an entry carrying a computed safety
      factor may not declare an absence of derivation in **any** kind. Enforced by the
      type, so it is unconstructable rather than merely reported.

## 4. Pay off what it unblocks

- [x] 4.1a `ASCE 7-22 §2.3.1` — the spec-driven screen names the governing combination and
      now writes out its factored sum, through the same renderer `combination_scorecard`
      uses. It was debt, not a lookup: the demand was already on the evidence record.
- [x] 4.1b `ASME BTH-1 §3-1.4` — the Class 0 entry declares itself a `lookup`. It states
      the standard's own exemption and computes nothing.
- [ ] 4.1c `AISC 360-16 §L3` — twenty-three beam load cases need a `deflection_formula`
      written down, and the pack needs to supply the case-specific symbols (offset,
      patch length, peak intensity, end moment) that those formulas name. The three
      fixed-pinned and fixed-fixed triangular maxima declare `numeric_result`.

## Status

Sections 1–3 shipped, and two of the three blocked clauses came off the list with them —
derivation coverage went 42/62 worked to 43/62 worked and 44/62 answered, and the two
figures can now differ, which is the whole point. 4.1c is the remaining work: it is
twenty-three closed forms plus a widening of the deflection derivation's symbol set, and
it is now payable, which it was not before.
