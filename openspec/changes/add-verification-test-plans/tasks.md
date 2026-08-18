# Tasks: Verification planning

## 1. Contracts

- [x] 1.1 Test archetype registry entry type (check class → archetype, citation or
      practice-default label)
- [x] 1.2 Test item type (driving checks, method + citation, acceptance criteria,
      required accuracy)
- [x] 1.3 Recorded outcome type (value, date, performer, instrument identity)

## 2. Implementation

- [x] 2.1 Plan emitter over scorecard entries via deterministic registry lookup
- [x] 2.2 Acceptance criteria and required-accuracy derivation from check allowables
- [x] 2.3 Verification matrix rendering with analysis-only coverage counts
- [ ] 2.4 Evidence-bundle section; planned-vs-verified status rendering

## 3. Tests

- [x] 3.1 Lifter scorecard emits a proof-load item with correct load and citation
- [x] 3.2 "Not evaluated" check yields no verification and is named unresolved
- [x] 3.3 Plan without outcomes never renders as verified

## 4. Docs & examples

- [x] 4.1 Example: validated lifter with its generated verification matrix
- [x] 4.2 Explanation page: analysis coverage vs physical verification

## Scope as shipped

Everything but 2.4's evidence-bundle section. `src/anvilate/verification.py` carries the
archetype registry, the plan emitter, the acceptance/accuracy derivation, the matrix
rendering with analysis-only coverage counts, and the recorded-outcome type.
`examples/lifter_verification_matrix.py` and `docs/verification-planning.md` are the
example and the explanation page.

**Both numeric criteria were anchored before shipping.** ASME B30.20 caps the proof load
at 125% of rated load and OSHA 29 CFR 1926.251(a)(4) requires that same 125% for
custom-designed lifting accessories; B30.20 also holds the rated load to no more than 80%
of the load sustained in test, and 1/1.25 = 0.80 exactly, so the rule anchors itself from
both ends and the suite asserts the identity. ASME VIII Div 1 UG-99(b) gives the
hydrostatic test as 1.3 x MAWP on the test/design allowable-stress ratio, with UG-100's
pneumatic alternative at 1.1 x — named in the criterion so nobody reads it as a cheaper
version of the same test.

**The 10:1 test accuracy ratio ships as a labelled practice default**, which is what
1.1's "citation or practice-default label" was for. It is measurement practice, not a
clause in any standard Anvilate cites, and the acceptance line says so rather than
borrowing authority.

**Routing is keyed on the citation, not the check name.** A caller names checks freely;
the clause they cite is not theirs to choose. A check named "proof load test" citing AWS
D1.1 is verified by analysis, and the suite pins that.

**2.4, the evidence-bundle section, is left open** for the same reason as
`add-design-space-exploration` 2.5: `anvilate.evidence` collects standards provenance
from a `DesignSpec` and has no hook for a plan. Both bindings belong with
`add-evidence-attestation`, which decides the bundle's shape.

Three archetypes ship (proof load, hydrostatic, dimensional). Weld NDE and bolt-preload
verification were considered and left out: their acceptance criteria are
category-and-contract-specific, and an archetype that cannot state a criterion is a
placeholder rather than a plan. Those checks report as analysis-only, and the count says
so.
