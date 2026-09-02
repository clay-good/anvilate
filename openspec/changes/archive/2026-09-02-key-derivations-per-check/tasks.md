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
- [x] 4.1c `AISC 360-16 §L3` — twenty of the twenty-six load cases had a closed form and
      now state it; six have a peak at a position that is solved for rather than written,
      and they declare `numeric_result`. The symbols moved onto `BeamBendingResult`,
      because the pack's fixed F/L/E/I set could not name an offset, a patch length, a
      peak intensity or an end couple. The count in the proposal was three, from reading
      the two bisections and the couple; it was six once every branch was read.

## Status

Shipped. Derivation coverage went from 42/62 worked to 43/62 worked and 45/62 answered,
and all three clauses this change was written to unblock are off the debt list.

Two things were found on the way and are worth keeping. `ASCE 7-22 §2.3.1` was filed as
needing a declaration and was ordinary debt: the factored sum was already on the evidence
record and the spec-driven screen simply never rendered it. And the eight deflection
formulas that already existed were checked by nothing — they are strings beside a number
computed from the code, printed into a signed document, and a transposed coefficient would
have shipped. `tests/test_beam_deflection_formulas.py` reads every one of them back.
