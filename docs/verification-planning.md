# Verification planning

**A plan is not evidence.** A verification plan with nothing performed reports
`not_evaluated` — never "ready", never a pass. Intending to test something is not testing
it, and no amount of green analysis upstream changes that: nothing here infers a physical
result from a passing check.

A screening check says a lug will hold; a proof test proves it. Anvilate stopped at the
calculation and left the user to invent the verification the calculation implies — even
though the standards the checks already cite usually prescribe it.

```python
from anvilate.verification import plan_verification

plan = plan_verification(card, parameters={"rated_load": Quantity.parse("100 kN")})
print(plan.summary())
# 3 checks with a physical test (0 of 2 performed), 1 by analysis alone,
# 1 unresolved — plan status not_evaluated
```

## The matrix, from a BTH-1 lifter

| Check | Method | State |
| --- | --- | --- |
| beam bending | test | planned |
| bail pin bearing | test | planned |
| pin fit | inspection | planned |
| weld throat | **analysis** | complete |
| fatigue | — | **unresolved**: the check did not run |

Four things in that table are deliberate.

**Routing runs off the citation, not the check's name.** A caller names checks freely;
the clause they cite is not theirs to choose. A check named "proof load test" that cites
AWS D1.1 is verified by analysis; a check named anything at all that cites ASME BTH-1
gets the proof load.

**Checks share a test when one test covers them.** One proof load stands behind every
BTH-1 member check on the device it loads, so they share an item and the item names all
of them.

**Analysis-only checks are counted, not omitted.** Analysis is one of the four
verification methods and a legitimate one. But "12 checks, 2 tests" and "12 checks, 12
tests" are different deliverables, and a matrix listing only the physical tests renders
identically either way.

**A check that did not run gets no test and is named unresolved.** There is no physical
counterpart to an analysis that was never performed, and an unresolved check holds the
whole plan open. Dropping it would make the plan shorter, and a shorter plan reads as a
smaller job.

## What each archetype asks for

| Archetype | Method | Criterion | Source |
| --- | --- | --- | --- |
| Proof load | Test | 1.25 × rated load, no permanent set | ASME B30.20 with OSHA 29 CFR 1926.251(a)(4) |
| Hydrostatic | Test | 1.3 × MAWP × (S_test/S_design), no leakage | ASME VIII Div 1 UG-99(b) |
| Dimensional | Inspection | within tolerance, instrument to a tenth of it | **practice default, not a cited clause** |

The proof factor is anchored from both ends: B30.20 caps the proof load at 125% of rated
*and* holds that the rated load may not exceed 80% of the load the device sustained.
1/1.25 = 0.80 exactly, both halves appear in the acceptance line, and the test suite
asserts the identity — a proof factor transcribed wrong breaks it.

The 10:1 test accuracy ratio is long-standing measurement practice and **not** a clause in
any standard Anvilate cites, so it is flagged `practice_default` and the acceptance line
says so. A reader can tell which numbers carry a standard's authority and which do not.

A hydrostatic item with no test/design stress ratio supplied takes it as 1.0 and says so
in the criterion, rather than silently assuming the test is at design temperature.

## Missing a quantity is unresolved, not absent

A proof test needs the rated load; a hydrostatic test needs the MAWP; a dimensional
inspection needs the tolerance. When one is not supplied the item is **unresolved with
the reason**, because a proof test whose rated load nobody supplied is not a plan.

## Recording an outcome

The only way an item becomes evidence. All four of value, date, performer and instrument
are required — an untraceable record is closer to a claim than to evidence.

```python
plan = record_outcome(plan, name="Proof load test", outcome=VerificationOutcome(
    passed=True,
    measured="125.4 kN held 10 min; no permanent set measurable at the bail",
    performed_on=date(2026, 8, 18),
    performed_by="M. Okonkwo, lifting test bay",
    instrument="Load cell LC-4471, cal. due 2027-02-11",
))
```

That item flips to `pass`. The plan stays `not_evaluated` while any other item is
outstanding, and a single failed outcome fails the plan.

See [`examples/lifter_verification_matrix.py`](../examples/lifter_verification_matrix.py).

Out of scope: executing tests, acquiring lab data, and any claim of qualification or
certification. This plans verification; it does not qualify anything.
