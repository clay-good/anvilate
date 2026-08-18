"""Worked example: the calculation is not the evidence, and the plan is not the test.

The spreader beam of ``spreader_beam_device_screen.py``, rated 100 kN, screened under
ASME BTH-1. Once the physics passes, an engineer still owes a verification plan — and
the standards the checks already cite prescribe most of it.

The plan the scorecard implies:

* **Proof load test**, ASME B30.20 with OSHA 29 CFR 1926.251(a)(4): apply **125 kN**,
  1.25× the rated load, and accept no permanent deformation, crack, or loss of function.
  One test stands behind every BTH-1 member check on the device, which is why they share
  an item.
* **Dimensional inspection** of the pin fit: measure within the 0.05 mm tolerance, with
  the instrument good to 0.005 mm — a tenth of the tolerance. That 10:1 ratio is
  *measurement practice, not a clause*, and the plan says so rather than borrowing
  authority it does not have.
* **The weld check is verified by analysis alone.** That is a legitimate method and it is
  counted. A matrix that lists only the physical tests looks identical whether one check
  or twelve went unverified.
* **The fatigue check did not run, so it gets no test — and is named unresolved.** There
  is no physical counterpart to an analysis that was never performed. A shorter plan
  would read as a smaller job.

Then the part that matters most: with the plan written and nothing performed, the plan's
status is **not_evaluated**. Not "ready", not "expected to pass". Intending to test
something is not testing it, and no amount of green analysis upstream changes that —
nothing here infers a result from a passing check, because that substitution is the
whole thing this exists to prevent.

Record the proof-test outcome — value, date, performer, instrument, all four required,
because an anonymous record is closer to a claim than to evidence — and the item flips to
`pass`. The plan as a whole stays `not_evaluated` while the dimensional inspection is
still outstanding and the fatigue check is still unresolved.

The 1.25 and the 0.80 in the acceptance line are the same rule read from both ends:
B30.20 caps the proof load at 125% of rated, and holds that the rated load may not exceed
80% of the load the device sustained. 1/1.25 = 0.80 exactly, and the test suite asserts
it — a proof factor transcribed wrong breaks the identity.

Scope: this plans verification. It does not execute it, acquire data, or qualify or
certify anything.

Run it directly (``python examples/lifter_verification_matrix.py``); :func:`build_plan`
is exercised in the test suite.
"""

from __future__ import annotations

from datetime import date

from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry
from anvilate.units import Quantity
from anvilate.verification import (
    VerificationOutcome,
    VerificationPlan,
    plan_verification,
    record_outcome,
)

RATED_LOAD = Quantity.parse("100 kN")
PIN_TOLERANCE = Quantity.parse("0.05 mm")

_BTH1 = "ASME BTH-1 §3-2/§3-3 (allowable stresses)"


def screened_lifter() -> Scorecard:
    """The spreader beam's scorecard, as the BTH-1 device screen produced it."""
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "beam bending", computed=1.19, required=1.0
            ).model_copy(update={"reference": _BTH1}),
            ScorecardEntry.from_safety_factor(
                "bail pin bearing", computed=1.16, required=1.0
            ).model_copy(update={"reference": _BTH1}),
            ScorecardEntry.from_safety_factor("pin fit", computed=2.0, required=1.0).model_copy(
                update={"reference": "ISO 286 H7/g6 clearance fit"}
            ),
            ScorecardEntry.from_safety_factor(
                "weld throat", computed=1.40, required=1.0
            ).model_copy(update={"reference": "AWS D1.1 fillet weld"}),
            ScorecardEntry(
                name="fatigue",
                status=CheckStatus.NOT_EVALUATED,
                detail="Service Class 2 with no cycle data supplied",
                reference="ASME BTH-1 §3-1.4 (Service Class)",
            ),
        )
    )


def build_plan() -> VerificationPlan:
    """The verification plan the screened lifter implies."""
    return plan_verification(
        screened_lifter(),
        parameters={"rated_load": RATED_LOAD, "tolerance": PIN_TOLERANCE},
    )


def after_proof_test() -> VerificationPlan:
    """The same plan once the proof test has actually been performed and recorded."""
    return record_outcome(
        build_plan(),
        name="Proof load test",
        outcome=VerificationOutcome(
            passed=True,
            measured="125.4 kN held 10 min; no permanent set measurable at the bail",
            performed_on=date(2026, 8, 18),
            performed_by="M. Okonkwo, lifting test bay",
            instrument="Load cell LC-4471, cal. due 2027-02-11",
        ),
    )


def main() -> None:
    plan = build_plan()
    print(plan.summary())
    print()
    print(plan.matrix())
    print("\n  what each planned test asks for:")
    for item in plan.items:
        print(f"    {item.name} — {item.archetype.citation}")
        print(f"      {item.acceptance}")
        print(f"      accuracy: {item.required_accuracy}")
    print(f"\n  plan status with nothing performed: {plan.status.value}")
    print("  (a plan is not evidence; intending to test something is not testing it)")

    performed = after_proof_test()
    proof = next(item for item in performed.items if item.name == "Proof load test")
    print(f"\n  after recording the proof test: item is {proof.status.value}")
    print(f"    {proof.outcome.measured}")
    print(f"    by {proof.outcome.performed_by} on {proof.outcome.performed_on.isoformat()}")
    print(f"  plan status: {performed.status.value} — the inspection is still outstanding")


if __name__ == "__main__":
    main()
