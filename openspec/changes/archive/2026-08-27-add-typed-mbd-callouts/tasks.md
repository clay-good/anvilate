# Tasks: Typed MBD callouts

## 1. Contracts

- [x] 1.1 Callout types: surface finish, coating/plating, heat treatment, structured note
- [x] 1.2 Persistent characteristic identifier assignment, stable across regeneration and
      revision (adopting MBC-class semantics)
- [x] 1.3 Tag-scoped resolution and validation

## 2. Implementation

- [x] 2.1 Fatigue surface-factor derivation from declared finish, cited
- [x] 2.2 Plated-dimension handling in fit and thread-engagement checks
- [x] 2.3 Heat-treat condition in material property resolution
- [x] 2.4 Consumed-value and contradiction reporting in the scorecard

## 3. Tests

- [x] 3.1 Identifier stability across regeneration and revision; callout diff
- [x] 3.2 Finish callout measurably changes a fatigue result and is reported
- [x] 3.3 Unknown heat-treat condition → "not evaluated"; contradiction surfaced

## 4. Docs & examples

- [x] 4.1 Example: shaft where declared finish and plating change the verdict
- [x] 4.2 Explanation page: callouts are inputs, not annotations

## Scope as shipped

`src/anvilate/callouts.py`, `tests/test_callouts.py`,
`examples/plated_shaft_callouts_change_the_verdict.py`, `docs/typed-callouts.md`.

**Identity had to be derived from what the characteristic IS, not from its value.** The
requirement is that an identifier survives regeneration *and revision*, and those pull in
opposite directions if you hash the callout: a content hash changes when the value does,
which turns every revision into a deletion plus an unrelated addition and destroys exactly
the continuity the identifier exists for. Deriving it from (kind, scope, category) instead
gives an identifier that is stable under a value change, distinct per face and per kind,
and needs no counter and no registry to reproduce. That is the MBC-class property without
the MBC registry, and it is what makes `callout_diff` able to say "this face's finish got
tighter" rather than "a finish disappeared and a different one appeared".

**A roughness value is not a production method, and the published fit is by method.**
Shigley's surface-factor table is indexed by how the surface was made. So the callout
carries both, the derivation reads the method, and the Ra is checked against the range the
method typically attains — which turns "as-forged, 0.4 µm Ra" into a reported
contradiction instead of a number averaged toward whichever half you trusted. The bands
overlap deliberately; only a clear inconsistency is flagged.

**The constants anchored against themselves.** The published table gives both the MPa and
the kpsi constant sets, and k_a is dimensionless, so `a_kpsi = a_MPa·(MPa/kpsi)^b` must
hold at every S_u. It does for all four rows to the table's own rounding — a transcription
check with no external source, asserted in the suite. Same shape for the plated thread:
the 4x pitch-diameter multiplier is written as `2/sin(30°)` and the suite checks the
derivation rather than the digit.

**2.3 shipped as a refusal, not a resolution.** The bundled database carries the condition
in the record identity (`AA-6061-T6`, `AISI-1018-CD`), so a declared condition either
resolves to a record or it does not — and `AISI-4140` in condition `QT` does not.
Inventing properties for a hardness range would have been the silent green; the check
reports NOT_EVALUATED naming the condition. A hardness range travels with the callout for
the drawing and the inspection and is never converted into a strength.

**Deferred:** nothing in the task list, but two adjacent things stay out of scope on
purpose — authoring a coating-process ontology, and finish or coating *selection* advice.
Anvilate consumes declared callouts; it does not recommend them. The typed
`ProcessNote` categories are carried and reported as consumed by nothing, which is honest
rather than empty: the first check that wants one will find the value already typed.
