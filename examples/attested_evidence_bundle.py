"""Worked example: sealing a screening result so somebody else can re-check it.

A lifting lug screens to three checks and produces two artifacts — the scorecard as
JSON and the drawing as DXF. This wraps that result in an attestation and then does the
four things a second engineer would actually do with one.

1. **Rebuild it.** The same inputs through the same toolchain produce the same bundle
   digest, character for character. Nothing in the payload is a wall clock: the
   CycloneDX BOM omits its optional ``metadata.timestamp`` precisely so that a rebuild
   is a cache hit rather than a new document.
2. **Bump the materials database.** ``anvilate_materials`` moves from 2026.03 to 2026.09
   and the digest changes, because the environment is inside the content address. That
   is the intended behaviour: the same spec screened against different data is a
   different piece of work.
3. **Tamper with the drawing.** One byte appended to the DXF and verification fails,
   naming the subject — not "invalid", but ``'lug.dxf' digest mismatch``.
4. **Verify without the key.** The envelope carries a signature and nothing checked it,
   so the report comes back NOT_EVALUATED. This is the no-silent-green rule applied to
   the seal itself: an unverified signature is not a verified one.

Two honesty notes the example prints out loud. The bundled signer is HMAC — symmetric,
so whoever can verify it could also have produced it. It detects tampering; it does not
establish authorship, and :attr:`VerificationReport.attested` stays False on it.
:class:`AttestationSigner` is the seam for a real asymmetric key. And the spec here was
drafted with a local model, so the bundle carries the disclosure: which model, which
backend, which stage, and which values a human confirmed.

Run it directly (``python examples/attested_evidence_bundle.py``);
:func:`attest_the_lug` is exercised in the test suite.
"""

from __future__ import annotations

from anvilate.attestation import (
    AIDisclosure,
    AIEvent,
    AnvilatePredicate,
    Attestation,
    Component,
    ComponentKind,
    EnvironmentBOM,
    EvidenceBundle,
    LocalHmacSigner,
    Subject,
    sha256_hex,
    verify_attestation,
)
from anvilate.evidence import SourceRecord
from anvilate.review import DecisionOrigin
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

SPEC_SOURCE = b'{"part": "lifting lug", "load_kN": 50, "thickness_mm": 12}'

LUG = Scorecard(
    entries=(
        ScorecardEntry.from_safety_factor("pin bearing", computed=2.7, required=2.0),
        ScorecardEntry.from_safety_factor("net tension", computed=2.2, required=2.0),
        ScorecardEntry(
            name="weld fatigue",
            status=CheckStatus.NOT_EVALUATED,
            detail="not evaluated — no detail category supplied for the fillet weld",
        ),
    )
)

SCORECARD_JSON = LUG.model_dump_json().encode("utf-8")
DRAWING_DXF = b"0\nSECTION\n2\nENTITIES\n0\nENDSEC\n0\nEOF\n"

# The model drafted the plate thickness; the engineer supplied the load and confirmed
# the compilation. A bundle whose origins name a model-drafted value cannot claim that
# no model participated — the disclosure model refuses to be constructed that way.
DISCLOSURE = AIDisclosure(
    participated=True,
    events=(
        AIEvent(
            stage="intent compilation",
            model="qwen2.5-coder:14b",
            backend="ollama (local)",
            confirmed_by="A. Engineer, P.E.",
        ),
    ),
    origins={
        "thickness_mm": DecisionOrigin.MODEL,
        "load_kN": DecisionOrigin.USER,
        "material": DecisionOrigin.DETERMINISTIC,
    },
)


def _bom(materials_version: str) -> EnvironmentBOM:
    return EnvironmentBOM(
        application=Component(name="anvilate", version="0.0.1", kind=ComponentKind.APPLICATION),
        components=(
            Component(name="pint", version="0.24.4"),
            Component(name="pydantic", version="2.9.2"),
            Component(
                name="anvilate_materials",
                version=materials_version,
                kind=ComponentKind.DATA,
            ),
        ),
    )


def _bundle(materials_version: str = "2026.03") -> EvidenceBundle:
    return EvidenceBundle(
        subjects=(
            Subject.over("scorecard.json", SCORECARD_JSON),
            Subject.over("lug.dxf", DRAWING_DXF),
        ),
        predicate=AnvilatePredicate(
            spec_digest=sha256_hex(SPEC_SOURCE),
            scorecard=LUG,
            citations=(
                SourceRecord(
                    ref="ASTM-A36",
                    kind="material",
                    name="ASTM A36 structural steel",
                    sources=("ASTM A36/A36M-19",),
                ),
            ),
            bom=_bom(materials_version),
            ai_disclosure=DISCLOSURE,
        ),
    )


def attest_the_lug():
    """The bundle, its rebuild, a database bump, a tampered artifact, and a missing key."""
    signer = LocalHmacSigner(b"a local signing secret held by the engineer")
    bundle = _bundle()
    envelope = Attestation.signed_by(bundle, signer)
    artifacts = {"scorecard.json": SCORECARD_JSON, "lug.dxf": DRAWING_DXF}

    rebuilt = _bundle()
    bumped = _bundle("2026.09")

    verified = verify_attestation(envelope, artifacts=artifacts, signer=signer)
    tampered = verify_attestation(
        envelope, artifacts=artifacts | {"lug.dxf": DRAWING_DXF + b"\n"}, signer=signer
    )
    unkeyed = verify_attestation(envelope, artifacts=artifacts)
    return bundle, rebuilt, bumped, verified, tampered, unkeyed


def main() -> None:
    bundle, rebuilt, bumped, verified, tampered, unkeyed = attest_the_lug()
    print(f"bundle digest        {bundle.digest}")
    print(f"rebuilt, same inputs {rebuilt.digest}  (identical: {bundle.digest == rebuilt.digest})")
    print(f"materials 2026.09    {bumped.digest}  (moved: {bundle.digest != bumped.digest})")
    print(f"\nscreened verdict     {bundle.predicate.status.value}")
    print(f"disclosure           {bundle.predicate.ai_disclosure}")
    print("\nVERIFICATION")
    print(f"  with the key       {verified}")
    print(f"  attested?          {verified.attested}  (HMAC is symmetric — tamper-evident only)")
    print(f"  tampered drawing   {tampered}")
    print(f"  without the key    {unkeyed}")


if __name__ == "__main__":
    main()
