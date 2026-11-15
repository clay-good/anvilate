"""Worked example: a proof test that held less than the check predicted.

A below-the-hook lifting lug screens green — the pin-connected plate check computes a
tensile capacity of 100 kN against the 80 kN the device is rated for, and the card reads
``pass``. ASME BTH-1 then requires the finished device to be proof loaded, so the plan
calls for one, and the load cell reads 92 kN before the plate yields.

That is the failure the escaped-defect process exists for: a green-checked part that did
not hold. The verdict does not change — the analysis said what it said, and editing it
after the fact would destroy the record — but the card now carries the finding, with a
ratio of 0.92 against a declared band of 0.05, and a candidate is filed with the evidence
bundle's digest for a person to disposition.

Nothing here re-tunes the check from the test. A correlation is information for a person
and a regression for CI, never a calibration.

The example reports the correlation ratio, the ratio's shortfall against the band and the
number of candidates filed.

Run it directly (``python examples/proof_test_correlation.py``);
:func:`proof_test_correlation` is also exercised in the test suite.
"""

from __future__ import annotations

from datetime import date

from anvilate.credibility import (
    AcceptanceBand,
    CredibilityFactor,
    HeldEvidence,
    PredictionSense,
    annotate,
    candidates,
    correlate,
    propose_factor_set,
)
from anvilate.derivation import DerivationAbsence, Underived
from anvilate.scorecard import (
    CheckStatus,
    Comparison,
    LimitSense,
    Scorecard,
    ScorecardEntry,
)
from anvilate.units import Quantity
from anvilate.verification import VerificationOutcome, plan_verification, record_outcome

RATED_LOAD = Quantity.parse("80 kN")
PREDICTED_CAPACITY = Quantity.parse("100 kN")
MEASURED_CAPACITY = Quantity.parse("92 kN")
BUNDLE_DIGEST = "sha256:1f0a9c4e"

#: Declared with its source, because a corridor nobody can attribute is an arbitrary one.
ACCEPTANCE_BAND = AcceptanceBand(
    fraction=0.05, source="the device's proof-test procedure, §4.2 acceptance"
)


def _card() -> Scorecard:
    """The lug as it screened: a passing check carrying the two numbers it compared."""
    return Scorecard(
        entries=(
            ScorecardEntry(
                name="lug tension",
                status=CheckStatus.PASS,
                detail="tensile capacity 100 kN against the 80 kN rated load",
                reference="ASME BTH-1-2020 §3-3.3.1 (pin-connected plates)",
                underived=Underived(
                    kind=DerivationAbsence.LOOKUP,
                    reason="the capacity is stated for this example rather than worked",
                ),
                comparison=Comparison(
                    measured=Quantity.parse("120 kN"),
                    limit=PREDICTED_CAPACITY,
                    sense=LimitSense.AT_LEAST,
                    measured_label="tensile capacity",
                    limit_label="capacity required of the test",
                ),
            ),
        )
    )


def proof_test_correlation() -> dict[str, float]:
    """Correlate the recorded proof load with the prediction and file what it implies."""
    card = _card()
    plan = plan_verification(card, parameters={"rated_load": RATED_LOAD})
    plan = record_outcome(
        plan,
        name="Proof load test",
        outcome=VerificationOutcome(
            passed=True,
            measured="held 92 kN, then permanent set at the pin hole",
            performed_on=date(2026, 11, 1),
            performed_by="A. Tester",
            instrument="load cell SN-7741",
            measured_value=MEASURED_CAPACITY,
            instrument_uncertainty=Quantity.parse("0.3 kN"),
        ),
    )

    found = correlate(
        plan,
        card,
        bands={"lug tension": ACCEPTANCE_BAND},
        senses={"lug tension": PredictionSense.CAPACITY},
    )
    correlation = found[0]
    annotated = annotate(card, found)
    filed = candidates(found, bundle_digest=BUNDLE_DIGEST)

    # The eight factors, from the evidence this run actually holds. Validation scores
    # zero: the one recorded test did not agree, so there is no favourable comparison.
    factors = propose_factor_set(
        "lug tension",
        HeldEvidence(
            cited_data_records=1,
            worked_example_anchors=1,
            inputs_with_an_origin=2,
            inputs_total=2,
        ),
    )

    return {
        "ratio": correlation.ratio,
        "shortfall_beyond_band": abs(correlation.ratio - 1.0) - ACCEPTANCE_BAND.fraction,
        "candidates_filed": float(len(filed)),
        "verdict_is_still_pass": float(annotated.status is CheckStatus.PASS),
        "validation_level": float(factors.level(CredibilityFactor.VALIDATION)),
    }


def main() -> None:
    card = _card()
    plan = plan_verification(card, parameters={"rated_load": RATED_LOAD})
    plan = record_outcome(
        plan,
        name="Proof load test",
        outcome=VerificationOutcome(
            passed=True,
            measured="held 92 kN, then permanent set at the pin hole",
            performed_on=date(2026, 11, 1),
            performed_by="A. Tester",
            instrument="load cell SN-7741",
            measured_value=MEASURED_CAPACITY,
        ),
    )
    found = correlate(
        plan,
        card,
        bands={"lug tension": ACCEPTANCE_BAND},
        senses={"lug tension": PredictionSense.CAPACITY},
    )
    annotated = annotate(card, found)

    print(plan.matrix())
    print()
    print(found[0])
    print(f"the check's verdict is unchanged: {annotated.entries[0].status.value}")
    print()
    for candidate in candidates(found, bundle_digest=BUNDLE_DIGEST):
        print(candidate)


if __name__ == "__main__":
    main()
