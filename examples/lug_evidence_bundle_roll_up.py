"""Worked example: what the *part* is, once every layer has had its say.

A lifting lug screens to two passing checks. Each layer that looks at it afterwards ships
its own verdict, and separately they are all correct. The question none of them answers on
its own is the one somebody actually asks: **is this part good?**

Four states of the same lug, in order:

1. **Checks only.** PASS — and the bundle says, in the same line, that verification,
   review, exploration, and callouts are *not covered*. A screening bundle is a legitimate
   thing to produce; it is not a verified part, and "we did not test it" must not read the
   same as "we tested it and it held".
2. **Plus a verification plan, nothing performed.** The scorecard has not changed. The
   bundle drops to NOT_EVALUATED, because the layer that would have said "verified" has
   not said it. A plan is not evidence, and the bundle inherits that rather than restating
   the physics as a substitute for the test.
3. **The proof load performed and passed.** Now PASS, and `test-verified` — the only state
   in which that phrase is true.
4. **Reviewed, then somebody changes the load.** The review record no longer covers the
   artifact, and a stale record is worse than no record: from the outside it reads exactly
   like a review. It pulls the bundle back to NOT_EVALUATED and names itself.

Finally the whole thing is sealed: `assemble_evidence_bundle` hands the roll-up to the
attestation layer, so the content-addressed statement carries the same conclusion the
reviewer saw rather than leaving a verifier to recompute it from the parts. The digest
moves when a layer arrives, because the bundle is then claiming more.

Run it directly (``python examples/lug_evidence_bundle_roll_up.py``);
:func:`roll_up_the_lug` is exercised in the test suite.
"""

from __future__ import annotations

from datetime import date

from anvilate.attestation import (
    AIDisclosure,
    EnvironmentBOM,
    sha256_hex,
)
from anvilate.bundle import BundleSections, assemble_evidence_bundle
from anvilate.review import ReviewRecord, artifact_digest, build_dossier
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.verification import (
    VerificationArchetype,
    VerificationItem,
    VerificationMethod,
    VerificationOutcome,
    VerificationPlan,
)

TOOLCHAIN = "anvilate 0.0.1"
SPEC = b'{"part": "lifting lug", "rated_load_kN": 50}'

LUG = Scorecard(
    entries=(
        ScorecardEntry.from_safety_factor("pin bearing", computed=2.7, required=2.0),
        ScorecardEntry.from_safety_factor("net tension", computed=3.3, required=2.0),
    )
)

PROOF_LOAD = VerificationArchetype(
    key="proof_load",
    method=VerificationMethod.TEST,
    title="proof load test",
    citation="ASME B30.20 / OSHA 29 CFR 1926.251(a)(4)",
)


def _plan(*, performed: bool) -> VerificationPlan:
    outcome = (
        VerificationOutcome(
            passed=True,
            measured="no permanent set at 62.5 kN (125% of rated)",
            performed_on=date(2026, 8, 20),
            performed_by="Test Lab Ltd",
            instrument="calibrated load cell, cal due 2027-01",
        )
        if performed
        else None
    )
    return VerificationPlan(
        items=(
            VerificationItem(
                name="lug proof load",
                archetype=PROOF_LOAD,
                driving_checks=("pin bearing", "net tension"),
                acceptance="no permanent deformation at 125% of the rated load",
                outcome=outcome,
            ),
        ),
        analysis_only=(),
        unresolved=(),
    )


def _bom() -> EnvironmentBOM:
    """Read from the environment, not typed. This example declared `pint 0.24.4` and
    `pydantic 2.9.2` while running against 0.25.3 and 2.13.5 — a false toolchain record
    inside the document whose whole purpose is provenance."""
    return EnvironmentBOM.of_this_environment()


def roll_up_the_lug():
    """The four states, and the sealed bundle for the verified one."""
    checks_only = BundleSections(scorecard=LUG)
    planned = BundleSections(scorecard=LUG, verification=_plan(performed=False))
    performed = BundleSections(scorecard=LUG, verification=_plan(performed=True))

    # Reviewed against a toolchain that has since moved: the record no longer applies.
    record = ReviewRecord(
        reviewer="A. Engineer, P.E.",
        reviewed_on=date(2026, 8, 5),
        covers_digest=artifact_digest(LUG, toolchain="anvilate 0.0.0"),
        scope="both lug checks",
    )
    stale = BundleSections(
        scorecard=LUG,
        verification=_plan(performed=True),
        review=build_dossier(LUG, toolchain=TOOLCHAIN, record=record),
    )

    sealed = assemble_evidence_bundle(
        performed,
        subjects=(),
        artifacts={"scorecard.json": LUG.model_dump_json().encode("utf-8")},
        spec_digest=sha256_hex(SPEC),
        bom=_bom(),
        ai_disclosure=AIDisclosure.none(),
    )
    unsealed = assemble_evidence_bundle(
        checks_only,
        subjects=(),
        artifacts={"scorecard.json": LUG.model_dump_json().encode("utf-8")},
        spec_digest=sha256_hex(SPEC),
        bom=_bom(),
        ai_disclosure=AIDisclosure.none(),
    )
    return {
        "checks_only": checks_only,
        "planned": planned,
        "performed": performed,
        "stale": stale,
        "sealed": sealed,
        "unsealed": unsealed,
    }


def main() -> None:
    result = roll_up_the_lug()
    for label in ("checks_only", "planned", "performed", "stale"):
        print(f"{label.upper().replace('_', ' ')}")
        print("  " + result[label].render().replace("\n", "\n  "))
        print()
    print("SEALED")
    print(f"  verified bundle digest    {result['sealed'].digest}")
    print(f"  checks-only bundle digest {result['unsealed'].digest}")
    print("  the address moves when a layer arrives, because the bundle claims more")


if __name__ == "__main__":
    main()
