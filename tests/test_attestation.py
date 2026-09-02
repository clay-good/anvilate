"""The attestation layer: content address, envelope shape, signing, and verification."""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from anvilate.attestation import (
    CYCLONEDX_SPEC_VERSION,
    DSSE_PAYLOAD_TYPE,
    PREDICATE_TYPE,
    STATEMENT_TYPE,
    AIDisclosure,
    AIEvent,
    AnvilatePredicate,
    Attestation,
    AttestationSigner,
    Component,
    ComponentKind,
    EnvironmentBOM,
    EvidenceBundle,
    LocalHmacSigner,
    Signature,
    SignatureState,
    Subject,
    ValueOrigin,
    VerificationReport,
    canonical_json,
    dsse_pae,
    sha256_hex,
    verify_attestation,
)
from anvilate.evidence import SourceRecord
from anvilate.review import DecisionOrigin
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

# Deliberately wide. The first version of this gate matched only `uuid4(` while the docs
# advertised it as catching "uuid", and it saw none of uuid1, time_ns, perf_counter,
# utcnow, secrets, or os.urandom. The second named seven `random` functions while the docs
# said "module-level random.*", leaving sample, randrange, choices, getrandbits, randbytes
# and the whole distribution family uncovered. A gate narrower than its own claim is worse
# than no gate, so this matches `random.<anything>` and the meta-test below proves it fires
# on every construct the documentation names.
_NONDETERMINISM = re.compile(
    r"\b("
    r"datetime\.now|datetime\.utcnow|date\.today|"
    r"time\.time|time\.time_ns|time\.monotonic|time\.perf_counter|time\.process_time|"
    r"uuid\.uuid\d|uuid[1345]|"
    r"random\.\w+|"
    r"secrets\.\w+|os\.urandom"
    r")\s*\("
)

_SECRET = b"an unguessable local signing secret"


def _bom() -> EnvironmentBOM:
    return EnvironmentBOM(
        application=Component(name="anvilate", version="0.0.1", kind=ComponentKind.APPLICATION),
        components=(
            Component(name="pint", version="0.24.4"),
            Component(name="pydantic", version="2.9.2"),
            Component(name="anvilate_materials", version="2026.03", kind=ComponentKind.DATA),
        ),
    )


def _scorecard() -> Scorecard:
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("bending", computed=2.4, required=1.67),
            ScorecardEntry.from_safety_factor("bolt shear", computed=1.9, required=2.0),
        )
    )


def _predicate(**overrides) -> AnvilatePredicate:
    fields = {
        "spec_digest": sha256_hex(b"the spec document"),
        "scorecard": _scorecard(),
        "citations": (
            SourceRecord(
                ref="ASTM-A36",
                kind="material",
                name="ASTM A36 structural steel",
                sources=("ASTM A36/A36M-19",),
            ),
        ),
        "bom": _bom(),
        "ai_disclosure": AIDisclosure.none(origins={"length": DecisionOrigin.USER}),
    }
    fields.update(overrides)
    return AnvilatePredicate(**fields)


def _bundle(**overrides) -> EvidenceBundle:
    return EvidenceBundle(
        subjects=(
            Subject.over("scorecard.json", b'{"status":"fail"}'),
            Subject.over("bracket.dxf", b"0\nSECTION\n"),
        ),
        predicate=_predicate(**overrides),
    )


# --- canonical serialisation ----------------------------------------------------------


def test_canonical_json_sorts_keys_and_drops_incidental_whitespace():
    assert canonical_json({"b": 1, "a": [1, 2]}) == '{"a":[1,2],"b":1}'
    # Two dicts built in different insertion orders serialise identically -- the whole
    # premise of a content address over a mapping.
    assert canonical_json({"x": 1, "y": 2}) == canonical_json({"y": 2, "x": 1})


def test_canonical_json_keeps_non_ascii_as_itself():
    # ensure_ascii would emit ø; the escaping choice must not change the digest.
    assert canonical_json({"source": "Ø"}) == '{"source":"Ø"}'


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_canonical_json_refuses_non_finite_numbers(bad):
    # json.dumps emits bare NaN/Infinity by default: valid Python, invalid JSON. A bundle
    # carrying one would hash cleanly here and fail in every conformant reader.
    with pytest.raises(ValueError, match="non-finite"):
        canonical_json({"margin": bad})


# --- DSSE pre-authentication encoding -------------------------------------------------


def test_dsse_pae_matches_the_specified_encoding():
    # PAE("http://example.com/HelloWorld", "hello world") from the DSSE specification.
    assert dsse_pae("http://example.com/HelloWorld", b"hello world") == (
        b"DSSEv1 29 http://example.com/HelloWorld 11 hello world"
    )


def test_dsse_pae_lengths_are_byte_counts_not_character_counts():
    # A multi-byte payload whose character count differs from its byte count: if the
    # length were characters, two different payloads could share an encoding.
    payload = "Ø".encode()
    assert len(payload) == 2
    assert dsse_pae("t", payload) == b"DSSEv1 1 t 2 " + payload


def test_dsse_pae_binds_the_payload_type():
    # The point of PAE: the same bytes under a different type must not produce the same
    # thing to sign, or a signature transplants between document types.
    assert dsse_pae("a", b"x") != dsse_pae("b", b"x")


# --- the statement and its content address --------------------------------------------


def test_the_statement_is_an_in_toto_statement_v1():
    statement = _bundle().statement()
    assert statement["_type"] == STATEMENT_TYPE
    assert statement["predicateType"] == PREDICATE_TYPE
    assert statement["subject"] == [
        {"name": "scorecard.json", "digest": {"sha256": sha256_hex(b'{"status":"fail"}')}},
        {"name": "bracket.dxf", "digest": {"sha256": sha256_hex(b"0\nSECTION\n")}},
    ]


def test_the_predicate_type_is_versioned_in_its_uri():
    # A breaking predicate change takes a new URI rather than redefining documents
    # already signed under this one.
    assert re.search(r"/v\d+$", PREDICATE_TYPE)


def test_identical_inputs_reproduce_the_identical_digest_across_processes():
    """Two builds agree — in separate interpreters, under different hash seeds.

    Comparing two digests inside one process is nearly a tautology: it shares the module
    state, the dict insertion orders, and one PYTHONHASHSEED. The reproducibility being
    claimed is across runs, so this claims it across runs.
    """
    script = (
        "import sys; sys.path.insert(0, 'tests');"
        "from test_attestation import _bundle; print(_bundle().digest)"
    )
    digests = set()
    for seed in ("0", "1", "12345"):
        env = os.environ | {"PYTHONHASHSEED": seed, "PYTHONPATH": "src"}
        out = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(Path(__file__).resolve().parent.parent),
            env=env,
        )
        digests.add(out.stdout.strip())
    assert len(digests) == 1, f"the digest depends on the interpreter's hash seed: {digests}"
    assert digests == {_bundle().digest}


def test_a_changed_database_version_changes_the_digest():
    bumped = _bom().model_copy(
        update={
            "components": (
                Component(name="pint", version="0.24.4"),
                Component(name="pydantic", version="2.9.2"),
                Component(name="anvilate_materials", version="2026.09", kind=ComponentKind.DATA),
            )
        }
    )
    assert _bundle(bom=bumped).digest != _bundle().digest


def test_a_changed_verdict_changes_the_digest():
    passing = Scorecard(
        entries=(ScorecardEntry.from_safety_factor("bending", computed=2.4, required=1.67),)
    )
    assert _bundle(scorecard=passing).digest != _bundle().digest


def test_a_changed_spec_changes_the_digest():
    assert _bundle(spec_digest=sha256_hex(b"a revised spec")).digest != _bundle().digest


# The digest of the fixture bundle, pinned. Restating `sha256_hex(canonical_json(...))`
# here would pass however the canonicalisation drifted -- it is the implementation with
# the same words. A literal is the only form of this assertion that can fail.
#
# It moved once, from 5c23d7d8..., when `Scorecard.status` became a serialised field. That
# is the pin working: the scorecard is inside the bundle, so a scorecard document that says
# something new *is* a different bundle, and a content address that had not moved would
# have meant the verdict was not covered by it.
#
# It moved a third time, from 85fecef9..., when `ScorecardEntry.comparison` shipped — the
# two quantities behind a comparison verdict, so a report can state the comparison in its
# own units rather than in the ones it happened to be screened in. The same reasoning: what
# a check compared is part of what the document says.
#
# It moved again, from 75e70720..., when `ScorecardEntry.underived` shipped — the field on
# which a check states that it has no formula to show and why. Same reasoning: whether a
# reviewer is owed a derivation is part of what the document says, so a bundle carrying
# that statement is a different bundle from one that does not.
_GOLDEN_DIGEST = "986709d5139ef8e1c3e8e16f3a8a247d5e8827000b04430a212afddf5b5e10e8"


def test_the_fixture_bundle_hashes_to_its_pinned_digest():
    assert _bundle().digest == _GOLDEN_DIGEST


def test_a_bundle_with_no_subject_is_refused():
    with pytest.raises(ValidationError, match="attests to nothing"):
        EvidenceBundle(subjects=(), predicate=_predicate())


def test_two_subjects_cannot_share_a_name():
    with pytest.raises(ValidationError, match="share a name"):
        EvidenceBundle(
            subjects=(Subject.over("a.dxf", b"one"), Subject.over("a.dxf", b"two")),
            predicate=_predicate(),
        )


def test_a_predicate_must_name_the_spec_it_screened():
    with pytest.raises(ValidationError, match="digest of the spec"):
        _predicate(spec_digest="   ")


@pytest.mark.parametrize("bad", ["", "abc", "A" * 64, "g" * 64])
def test_a_subject_digest_must_be_lowercase_hex_sha256(bad):
    with pytest.raises(ValidationError, match="SHA-256"):
        Subject(name="x.dxf", sha256=bad)


# --- the environment BOM ---------------------------------------------------------------


def test_the_bom_is_a_cyclonedx_document():
    doc = _bom().to_cyclonedx()
    assert doc["bomFormat"] == "CycloneDX"
    assert doc["specVersion"] == CYCLONEDX_SPEC_VERSION
    assert doc["metadata"]["component"] == {
        "type": "application",
        "name": "anvilate",
        "version": "0.0.1",
    }
    assert {c["name"] for c in doc["components"]} == {"pint", "pydantic", "anvilate_materials"}


def test_the_bom_carries_no_timestamp_or_serial_number():
    # Both are optional in CycloneDX and both are unique per emission. Either one makes
    # two byte-identical builds produce two different bundles.
    doc = _bom().to_cyclonedx()
    assert "serialNumber" not in doc
    assert "timestamp" not in doc["metadata"]


def test_an_unversioned_component_is_refused():
    with pytest.raises(ValidationError, match="no version"):
        Component(name="pint", version="  ")


def test_the_bom_application_must_be_declared_an_application():
    with pytest.raises(ValidationError, match="must be declared as an application"):
        EnvironmentBOM(application=Component(name="anvilate", version="0.0.1"))


def test_the_bom_refuses_a_duplicated_component():
    with pytest.raises(ValidationError, match="twice"):
        EnvironmentBOM(
            application=Component(name="anvilate", version="0.0.1", kind=ComponentKind.APPLICATION),
            components=(
                Component(name="pint", version="0.24"),
                Component(name="pint", version="0.25"),
            ),
        )


# --- AI-involvement disclosure ----------------------------------------------------------


def test_a_hand_authored_spec_says_no_model_participated():
    disclosure = AIDisclosure.none()
    assert disclosure.participated is False
    assert "no language model participated" in str(disclosure)


def test_a_disclosure_names_model_backend_and_confirmation():
    disclosure = AIDisclosure(
        participated=True,
        events=(
            AIEvent(
                stage="intent compilation",
                model="qwen2.5-coder:14b",
                backend="ollama",
                confirmed_by="C. Good, PE",
            ),
            AIEvent(stage="critic edit", model="qwen2.5-coder:14b", backend="ollama"),
        ),
        origins={"web_thickness": DecisionOrigin.MODEL, "span": DecisionOrigin.USER},
    )
    assert [e.confirmed for e in disclosure.events] == [True, False]
    assert len(disclosure.unconfirmed_events) == 1
    assert "1 unconfirmed" in str(disclosure)


def test_a_model_drafted_value_cannot_claim_no_model_participated():
    # The failure this disclosure exists to prevent is omission, so it is a construction
    # error rather than something a reader has to notice.
    with pytest.raises(ValidationError, match="attributed to a model"):
        AIDisclosure(participated=False, origins={"web_thickness": DecisionOrigin.MODEL})


def test_a_disclosure_of_participation_must_say_where():
    with pytest.raises(ValidationError, match="must say where"):
        AIDisclosure(participated=True)


def test_a_no_participation_disclosure_cannot_carry_events():
    with pytest.raises(ValidationError, match="no model participated but lists"):
        AIDisclosure(
            participated=False,
            events=(AIEvent(stage="critic edit", model="m", backend="ollama"),),
        )


@pytest.mark.parametrize("field", ["stage", "model", "backend"])
def test_an_event_must_identify_itself(field):
    fields = {"stage": "critic edit", "model": "m", "backend": "ollama"}
    fields[field] = "  "
    with pytest.raises(ValidationError, match="non-empty"):
        AIEvent(**fields)


def test_the_disclosure_travels_in_the_predicate_body():
    body = _predicate().to_json_dict()
    assert body["aiDisclosure"]["participated"] is False
    assert body["status"] == CheckStatus.FAIL.value


# --- the envelope -----------------------------------------------------------------------


def test_an_unsigned_envelope_is_a_state_not_an_omission():
    envelope = Attestation.unsigned(_bundle())
    assert envelope.signed is False
    assert envelope.to_envelope()["signatures"] == []
    assert envelope.bundle_digest == _bundle().digest


def test_the_envelope_is_dsse_shaped_and_round_trips_its_statement():
    envelope = Attestation.signed_by(_bundle(), LocalHmacSigner(_SECRET))
    wire = envelope.to_envelope()
    assert wire["payloadType"] == DSSE_PAYLOAD_TYPE
    # Standard tooling reads the payload as base64 of the statement JSON.
    decoded = json.loads(base64.b64decode(wire["payload"]).decode("utf-8"))
    assert decoded == _bundle().statement()
    assert wire["signatures"][0]["algorithm"] == "hmac-sha256"


def test_the_signature_is_over_the_pae_not_the_bare_payload():
    bundle = _bundle()
    signer = LocalHmacSigner(_SECRET)
    envelope = Attestation.signed_by(bundle, signer)
    expected = signer.sign(dsse_pae(DSSE_PAYLOAD_TYPE, bundle.payload()))
    assert envelope.signatures[0].raw == expected
    assert envelope.signatures[0].raw != signer.sign(bundle.payload())


def test_the_keyid_is_stable_per_key_and_does_not_expose_the_secret():
    first = LocalHmacSigner(_SECRET)
    assert first.keyid == LocalHmacSigner(_SECRET).keyid
    assert first.keyid != LocalHmacSigner(b"a different local secret!!").keyid
    assert _SECRET.hex() not in first.keyid


def test_a_too_short_signing_secret_is_refused():
    with pytest.raises(ValueError, match="too short"):
        LocalHmacSigner(b"short")


def test_the_local_signer_satisfies_the_signer_protocol():
    assert isinstance(LocalHmacSigner(_SECRET), AttestationSigner)


# --- verification -------------------------------------------------------------------------


def _artifacts() -> dict[str, bytes]:
    return {"scorecard.json": b'{"status":"fail"}', "bracket.dxf": b"0\nSECTION\n"}


def test_a_signed_bundle_verifies_offline_against_its_artifacts():
    signer = LocalHmacSigner(_SECRET)
    report = verify_attestation(
        Attestation.signed_by(_bundle(), signer), artifacts=_artifacts(), signer=signer
    )
    assert report.status is CheckStatus.PASS
    assert report.signature_state is SignatureState.SYMMETRIC_VERIFIED
    assert set(report.checked_subjects) == set(_artifacts())
    assert report.problems == ()


def test_a_symmetric_verification_is_not_called_attested():
    # HMAC proves possession of the shared secret, not authorship. Whoever can verify it
    # could also have produced it, so the strict flag stays False.
    signer = LocalHmacSigner(_SECRET)
    report = verify_attestation(
        Attestation.signed_by(_bundle(), signer), artifacts=_artifacts(), signer=signer
    )
    assert report.attested is False


def test_an_unsigned_bundle_is_never_presented_as_attested():
    report = verify_attestation(Attestation.unsigned(_bundle()), artifacts=_artifacts())
    assert report.signature_state is SignatureState.UNSIGNED
    assert report.status is CheckStatus.PASS  # the digests did match
    assert report.attested is False
    assert "unsigned" in str(report)


def test_a_signature_nobody_checked_is_not_evaluated():
    # No key supplied: the signature is present and unverified. Reporting PASS here would
    # be the exact silent green the library refuses everywhere else.
    report = verify_attestation(
        Attestation.signed_by(_bundle(), LocalHmacSigner(_SECRET)), artifacts=_artifacts()
    )
    assert report.signature_state is SignatureState.NOT_CHECKED
    assert report.status is CheckStatus.NOT_EVALUATED
    assert report.attested is False


def test_a_subject_nobody_supplied_is_unchecked_not_assumed_intact():
    report = verify_attestation(
        Attestation.unsigned(_bundle()), artifacts={"bracket.dxf": b"0\nSECTION\n"}
    )
    assert report.unchecked_subjects == ("scorecard.json",)
    assert report.status is CheckStatus.NOT_EVALUATED
    assert "1 subject(s) not supplied" in str(report)


def test_verification_with_no_artifacts_at_all_is_not_a_pass():
    report = verify_attestation(Attestation.unsigned(_bundle()))
    assert report.status is CheckStatus.NOT_EVALUATED
    assert set(report.unchecked_subjects) == set(_artifacts())


def test_a_tampered_artifact_fails_and_names_the_subject():
    tampered = _artifacts() | {"bracket.dxf": b"0\nSECTION\n999\n"}
    report = verify_attestation(Attestation.unsigned(_bundle()), artifacts=tampered)
    assert report.status is CheckStatus.FAIL
    assert len(report.problems) == 1
    assert "'bracket.dxf' digest mismatch" in report.problems[0]
    assert "scorecard.json" in report.checked_subjects


def test_a_tampered_payload_fails_the_signature_check():
    signer = LocalHmacSigner(_SECRET)
    envelope = Attestation.signed_by(_bundle(), signer)
    # Re-point the envelope at a different statement, keeping the original signature.
    forged = envelope.model_copy(
        update={
            "payload": base64.b64encode(
                _bundle(spec_digest=sha256_hex(b"a revised spec")).payload()
            ).decode("ascii")
        }
    )
    report = verify_attestation(forged, artifacts=_artifacts(), signer=signer)
    assert report.status is CheckStatus.FAIL
    assert report.signature_state is SignatureState.INVALID
    assert any("no signature verified" in p for p in report.problems)


def test_a_signature_from_another_key_does_not_verify():
    envelope = Attestation.signed_by(_bundle(), LocalHmacSigner(_SECRET))
    report = verify_attestation(
        envelope, artifacts=_artifacts(), signer=LocalHmacSigner(b"someone else's secret key")
    )
    assert report.signature_state is SignatureState.INVALID
    assert report.status is CheckStatus.FAIL


def test_an_artifact_the_bundle_never_covered_is_reported_not_ignored():
    # The caller handed in a file believing it was covered. Silently verifying the two
    # subjects and returning PASS would confirm a belief that is false.
    report = verify_attestation(
        Attestation.unsigned(_bundle()), artifacts=_artifacts() | {"stray.step": b"ISO-10303-21;"}
    )
    assert report.status is CheckStatus.FAIL
    assert any("not a subject of this bundle" in p for p in report.problems)


def test_an_unknown_predicate_type_is_refused_by_name():
    bundle = _bundle()
    statement = bundle.statement() | {"predicateType": "https://example.com/other/v1"}
    envelope = Attestation(
        payload=base64.b64encode(canonical_json(statement).encode("utf-8")).decode("ascii")
    )
    report = verify_attestation(envelope, artifacts=_artifacts())
    assert report.status is CheckStatus.FAIL
    assert any("does not know" in p for p in report.problems)


def test_a_foreign_statement_type_is_refused():
    statement = _bundle().statement() | {"_type": "https://in-toto.io/Statement/v0.1"}
    envelope = Attestation(
        payload=base64.b64encode(canonical_json(statement).encode("utf-8")).decode("ascii")
    )
    report = verify_attestation(envelope, artifacts=_artifacts())
    assert any("statement type is" in p for p in report.problems)


def test_an_unreadable_payload_fails_rather_than_raising():
    envelope = Attestation(payload=base64.b64encode(b"not json at all").decode("ascii"))
    report = verify_attestation(envelope)
    assert report.status is CheckStatus.FAIL
    assert any("not readable JSON" in p for p in report.problems)


# --- byte-determinism gate over the whole package -------------------------------------------


def test_no_shipped_module_reads_a_wall_clock_or_a_random_identifier():
    """The determinism the content address rests on, enforced rather than assumed.

    A single ``datetime.now()`` in any writer makes every rebuild a new bundle and the
    digest meaningless. The audit that preceded this module found the tree already clean
    — ``review.ReviewRecord.reviewed_on`` is a declared input, not today's date — and
    this keeps it that way.
    """
    source = Path(__file__).resolve().parent.parent / "src" / "anvilate"
    offenders = []
    pattern = _NONDETERMINISM
    scanned = 0
    for path in sorted(source.rglob("*.py")):
        scanned += 1
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            if pattern.search(line):
                offenders.append(f"{path.relative_to(source)}:{number}: {line.strip()}")
    # A wrong root reads no files and reports no offenders, which is the shape this gate
    # would fail silently in — the determinism the content address rests on is the claim.
    assert scanned > 200, f"the wall-clock sweep read only {scanned} modules"
    assert not offenders, (
        "non-deterministic calls in shipped code — a wall clock or a random identifier "
        "in any writer destroys the reproducible bundle digest:\n" + "\n".join(offenders)
    )


# --- what a five-agent audit found the day this module shipped ----------------------------
#
# Every test below is a defect that was live in the first commit of this module. They sit
# together because the pattern is one pattern: `EvidenceBundle` refuses malformed bundles at
# construction, and the verifier — the half that reads documents it did not build — trusted
# that the thing in front of it had been built by the other half.


def _envelope_over(statement: object) -> Attestation:
    """An envelope carrying an arbitrary payload, bypassing the model that builds one."""
    return Attestation(
        payload=base64.b64encode(canonical_json(statement).encode("utf-8")).decode("ascii")
    )


def test_a_statement_with_no_subjects_cannot_verify():
    # The strongest forgery was the simplest: drop the subject key and the envelope came
    # back PASS while attesting to no artifact at all. With an asymmetric signer that was
    # attested=True over nothing.
    statement = _bundle().statement()
    del statement["subject"]
    report = verify_attestation(_envelope_over(statement))
    assert report.status is CheckStatus.FAIL
    assert any("attests to no artifact" in p for p in report.problems)


def test_an_empty_subject_list_cannot_verify():
    statement = _bundle().statement() | {"subject": []}
    report = verify_attestation(_envelope_over(statement))
    assert report.status is CheckStatus.FAIL
    assert any("attests to no artifact" in p for p in report.problems)


@pytest.mark.parametrize("payload", [[1, 2, 3], 5, None, "hi", True])
def test_a_payload_that_is_not_a_statement_object_reports_rather_than_raises(payload):
    report = verify_attestation(_envelope_over(payload))
    assert report.status is CheckStatus.FAIL
    assert any("not a statement object" in p for p in report.problems)


@pytest.mark.parametrize("subject", ["abc", {"a": 1}, 3, ["a.dxf"], [None]])
def test_a_malformed_subject_list_reports_rather_than_raises(subject):
    report = verify_attestation(_envelope_over(_bundle().statement() | {"subject": subject}))
    assert report.status is CheckStatus.FAIL
    assert report.problems


def test_a_subject_with_no_digest_is_a_problem_not_a_match():
    statement = _bundle().statement() | {"subject": [{"name": "lug.dxf"}]}
    report = verify_attestation(_envelope_over(statement), artifacts={"lug.dxf": b"anything"})
    assert report.status is CheckStatus.FAIL
    assert any("no sha256 digest" in p for p in report.problems)


def test_a_payload_that_is_not_valid_base64_is_refused_at_the_door():
    # The error path itself used to re-decode and raise binascii.Error out of a function
    # whose contract is to report what did not match.
    with pytest.raises(ValidationError, match="not valid base64"):
        Attestation(payload="!!!!not base64!!!!")


def test_junk_spliced_into_the_payload_cannot_ride_along():
    # Non-strict b64decode DISCARDS characters outside the alphabet, so an envelope with
    # junk in its payload string decoded to the same bytes, hashed to the same digest, and
    # kept a valid signature: a tampered envelope that verified.
    envelope = Attestation.signed_by(_bundle(), LocalHmacSigner(_SECRET))
    spliced = envelope.payload[:8] + "!!" + envelope.payload[8:]
    # Parsing a wire envelope goes through the constructor, which is where it is refused.
    with pytest.raises(ValidationError, match="not valid base64"):
        Attestation(payload=spliced, signatures=envelope.signatures)
    # `model_copy` is refused too, since `Attestation` re-validates a copy — so the
    # tampered envelope is built with `model_construct`, which is pydantic's documented
    # bypass and the only remaining way such an object comes into existence.
    with pytest.raises(ValidationError, match="not valid base64"):
        envelope.model_copy(update={"payload": spliced})
    # The verifier still has to report rather than raise: defence in depth, because the
    # constructor is not the only door an object arrives through.
    smuggled = Attestation.model_construct(
        payload_type=envelope.payload_type, payload=spliced, signatures=envelope.signatures
    )
    report = verify_attestation(smuggled)
    assert report.status is CheckStatus.FAIL
    assert any("not valid base64" in p for p in report.problems)


def test_a_signature_that_is_not_valid_base64_is_refused():
    with pytest.raises(ValidationError, match="not valid base64"):
        Signature(keyid="k", algorithm="hmac-sha256", sig="not base64 ***")


def test_a_signature_under_another_key_is_reported_not_ignored():
    # DSSE envelopes are legitimately multi-signer, so a foreign signature is not a
    # failure. It is also not a check, and the report used to come back PASS with no trace
    # of the signature it could not evaluate.
    signer = LocalHmacSigner(_SECRET)
    envelope = Attestation.signed_by(_bundle(), signer)
    with_extra = envelope.model_copy(
        update={
            "signatures": (
                *envelope.signatures,
                Signature(keyid="someone-elses-key", algorithm="ed25519", sig="AAAA"),
            )
        }
    )
    report = verify_attestation(with_extra, artifacts=_artifacts(), signer=signer)
    assert report.unverified_signatures == ("someone-elses-key",)
    assert report.status is CheckStatus.NOT_EVALUATED
    assert "1 signature(s) under other keys" in str(report)


def test_a_renamed_artifact_is_not_matched_on_its_bytes():
    # The docstring used to claim the opposite. Verification looks the artifact up by
    # name; the name is part of the claim, not a label on it.
    report = verify_attestation(
        Attestation.unsigned(_bundle()),
        artifacts={"scorecard.json": b'{"status":"fail"}', "lug_rev_b.dxf": b"0\nSECTION\n"},
    )
    assert report.status is CheckStatus.FAIL
    assert report.unchecked_subjects == ("bracket.dxf",)
    assert any("not a subject of this bundle" in p for p in report.problems)


def test_the_origin_map_cannot_be_written_to_after_validation():
    # `frozen=True` does not reach inside a mutable field. As a plain dict, origins could
    # be given a MODEL attribution after construction — defeating the one invariant the
    # class exists for, and moving the digest of an already-signed statement.
    disclosure = AIDisclosure.none(origins={"span": DecisionOrigin.USER})
    assert disclosure.origin_map == {"span": DecisionOrigin.USER}
    disclosure.origin_map["span"] = DecisionOrigin.MODEL  # a copy, by construction
    assert disclosure.origin_map == {"span": DecisionOrigin.USER}
    with pytest.raises(ValidationError):
        disclosure.origins = ()


def test_a_field_cannot_be_attributed_twice():
    with pytest.raises(ValidationError, match="attributed twice"):
        AIDisclosure(
            participated=False,
            origins=(
                ValueOrigin(field="span", origin=DecisionOrigin.USER),
                ValueOrigin(field="span", origin=DecisionOrigin.DETERMINISTIC),
            ),
        )


def test_the_signature_binds_the_envelopes_own_payload_type():
    # signed_by used to sign the module constant while verify read the envelope's field.
    # Equivalent today, and a trap the moment a second payload type exists.
    signer = LocalHmacSigner(_SECRET)
    envelope = Attestation.signed_by(_bundle(), signer)
    relabelled = envelope.model_copy(update={"payload_type": "application/vnd.other+json"})
    assert verify_attestation(relabelled, artifacts=_artifacts(), signer=signer).status is (
        CheckStatus.FAIL
    )


def test_the_determinism_gate_detects_what_its_docs_claim_it_detects():
    """Prove the gate fires, rather than trusting a regex nobody ran against a violation."""
    for offender in (
        "x = datetime.now()",
        "x = datetime.utcnow()",
        "x = date.today()",
        "x = time.time()",
        "x = time.time_ns()",
        "x = time.monotonic()",
        "x = time.perf_counter()",
        "x = time.process_time()",
        "x = uuid.uuid1()",
        "x = uuid.uuid5(ns, name)",
        "x = uuid4()",
        "x = random.random()",
        "x = random.sample(pool, 3)",
        "x = random.getrandbits(32)",
        "x = secrets.token_hex(8)",
        "x = os.urandom(16)",
    ):
        assert _NONDETERMINISM.search(offender), f"the determinism gate does not see {offender!r}"
    for innocent in ("rng = Random(seed)", "self._rng.gauss(0, 1)", "# monotonic in r"):
        assert not _NONDETERMINISM.search(innocent), (
            f"the determinism gate false-positives on {innocent!r}"
        )


# --- what a re-audit of the fixes found ------------------------------------------------
#
# The patches above were themselves audited, and four of them had a second edge. Making
# `origins` immutable is the instructive one: as a dict it was order-independent for free,
# because `canonical_json` sorts keys. Moving to a tuple to stop post-validation mutation
# handed that responsibility back to the model, and sorting only the Mapping path meant a
# caller passing the field's own declared type got a different digest for the same content.


def test_the_digest_does_not_depend_on_the_order_origins_were_declared_in():
    forward = AIDisclosure.none(origins={"a": DecisionOrigin.USER, "b": DecisionOrigin.USER})
    backward = AIDisclosure(
        participated=False,
        origins=(
            ValueOrigin(field="b", origin=DecisionOrigin.USER),
            ValueOrigin(field="a", origin=DecisionOrigin.USER),
        ),
    )
    assert forward.origin_map == backward.origin_map
    assert [o.field for o in backward.origins] == ["a", "b"]  # sorted by the model
    assert _bundle(ai_disclosure=forward).digest == _bundle(ai_disclosure=backward).digest


def test_the_v1_predicate_still_writes_origins_as_an_object():
    # The in-memory shape moved from a dict to a tuple of pairs. That is an internal
    # choice, and a consumer pinned to `.../screening/v1` must not see it: the URI carries
    # the promise, and this module's own comment on PREDICATE_TYPE makes it.
    body = _predicate(
        ai_disclosure=AIDisclosure.none(origins={"span": DecisionOrigin.USER})
    ).to_json_dict()
    assert body["aiDisclosure"]["origins"] == {"span": "user"}
    assert set(body["aiDisclosure"]) == {"participated", "events", "origins"}


def test_a_junk_signature_is_reported_rather_than_raised_out_of_the_verifier():
    # `Signature` validates its base64 at construction, and a copy is re-validated now, so
    # both of those doors are shut. The verifier is still required to report rather than
    # raise on one that got in some other way — `model_construct` is that way.
    signer = LocalHmacSigner(_SECRET)
    envelope = Attestation.signed_by(_bundle(), signer)
    with pytest.raises(ValidationError, match="not valid base64"):
        envelope.signatures[0].model_copy(update={"sig": "!!!not base64!!!"})
    junk = Signature.model_construct(
        keyid=envelope.signatures[0].keyid, algorithm="hmac-sha256", sig="!!!not base64!!!"
    )
    smuggled = Attestation.model_construct(
        payload_type=envelope.payload_type, payload=envelope.payload, signatures=(junk,)
    )
    report = verify_attestation(smuggled, artifacts=_artifacts(), signer=signer)
    assert report.signature_state is SignatureState.INVALID
    assert report.status is CheckStatus.FAIL


def test_an_invalid_signature_fails_the_report_even_with_no_prose_problem():
    # The verifier always appends a sentence alongside INVALID, so reading only `problems`
    # was right in practice and wrong in principle. VerificationReport is exported.
    report = VerificationReport(
        bundle_digest="0" * 64,
        signature_state=SignatureState.INVALID,
        predicate_type=PREDICATE_TYPE,
        checked_subjects=("a.dxf",),
    )
    assert report.status is CheckStatus.FAIL
    assert report.attested is False


def test_the_attestation_pages_database_bump_is_the_one_the_digest_sees():
    """`docs/evidence-attestation.md` names two versions and says the digest moves.

    The versions are the page's, read out of the sentence rather than restated here, so
    a page that names a bump the bundle does not carry stops matching.
    """
    page = " ".join(
        (Path(__file__).resolve().parent.parent / "docs" / "evidence-attestation.md")
        .read_text()
        .split()
    )
    claim = re.search(
        r"Bump `(\w+)` from ([\d.]+) to ([\d.]+) and the digest moves, even with the spec "
        r"untouched",
        page,
    )
    assert claim is not None, "the database-bump sentence on the attestation page has moved"

    name, before, after = claim.groups()
    baseline = _bom()
    assert any(c.name == name and c.version == before for c in baseline.components), (
        f"the page bumps {name} from {before}, which is not the version the bundle carries"
    )
    bumped = baseline.model_copy(
        update={
            "components": tuple(
                c.model_copy(update={"version": after}) if c.name == name else c
                for c in baseline.components
            )
        }
    )
    assert _bundle(bom=bumped).digest != _bundle().digest


# --- the BOM is read, not typed -----------------------------------------------------------


def test_the_environment_bom_reports_the_versions_that_are_installed():
    """The one part of an attestation nobody can check by reading it.

    Every caller in this repository used to hand-write the inventory, and two of them
    attested `pint 0.24.4` and `pydantic 2.9.2` against an environment running 0.25.3 and
    2.13.5. A bill of materials whose versions are whatever the author last typed is a
    provenance record that cannot be wrong out loud.
    """
    from importlib.metadata import version

    from anvilate.attestation import EnvironmentBOM

    bom = EnvironmentBOM.of_this_environment()
    assert bom.application.name == "anvilate"
    assert bom.application.version == version("anvilate")
    reported = {component.name: component.version for component in bom.components}
    assert reported, "the BOM found no components at all"
    for name, stated in reported.items():
        assert stated == version(name), f"{name} attested as {stated}, installed {version(name)}"


def test_the_bom_is_derived_from_the_declared_dependencies():
    """A dependency added to the project appears without anybody remembering to add it here,
    which is the only reason this is derived rather than a list."""
    from importlib.metadata import requires

    from anvilate.attestation import EnvironmentBOM

    declared = {
        re.split(r"[<>=!~;\[ ]", requirement, maxsplit=1)[0].strip()
        for requirement in requires("anvilate") or ()
    }
    reported = {component.name for component in EnvironmentBOM.of_this_environment().components}
    assert "pint" in declared and "pydantic" in declared
    assert reported <= declared, f"the BOM invents {sorted(reported - declared)}"


def test_dev_tooling_is_not_reported_as_having_produced_the_bundle():
    """pytest and ruff are installed in a contributor's environment and had no part in
    producing a bundle. A BOM listing them is claiming they did."""
    from anvilate.attestation import EnvironmentBOM

    reported = {component.name for component in EnvironmentBOM.of_this_environment().components}
    assert not reported & {"pytest", "ruff", "jsonschema"}, sorted(reported)
    # And the rule is "the dev extra", not "these three names": `export`'s ezdxf really does
    # write the DXF, so it belongs in the inventory when it is installed.
    pytest.importorskip("ezdxf")
    # A red here usually means the installed metadata predates the `export` extra rather
    # than that the BOM is wrong. The metadata-drift gate in tests/test_contract.py says
    # which of the two it is, and how to refresh the snapshot.
    assert "ezdxf" in reported


def test_a_declared_dependency_that_is_not_installed_is_left_out(monkeypatch):
    """Not recorded at a placeholder version. An optional extra nobody installed contributed
    nothing to this bundle, and saying it did is the same lie in the other direction."""
    from importlib.metadata import PackageNotFoundError

    from anvilate.attestation import EnvironmentBOM

    def _absent(name):
        if name == "pint":
            raise PackageNotFoundError(name)
        return _real_version(name)

    from importlib import metadata

    _real_version = metadata.version
    monkeypatch.setattr(metadata, "version", _absent)
    reported = {component.name for component in EnvironmentBOM.of_this_environment().components}
    assert "pint" not in reported, "an uninstalled dependency was reported anyway"
    assert "pydantic" in reported, "the whole inventory vanished, so this proved nothing"


def test_no_example_hardcodes_a_version_that_has_drifted():
    """The examples are how a reader learns to build a bundle, so a stale literal there
    teaches the defect. Any version literal an example states for a package that is actually
    installed must match what is installed."""
    from importlib.metadata import PackageNotFoundError
    from importlib.metadata import version as installed_version

    examples = Path(__file__).resolve().parent.parent / "examples"
    pattern = re.compile(r'Component\(\s*name="([a-z0-9_-]+)",\s*version="([^"]+)"')
    checked = 0
    for path in sorted(examples.glob("*.py")):
        for name, stated in pattern.findall(path.read_text()):
            try:
                real = installed_version(name)
            except PackageNotFoundError:
                continue  # a versioned dataset, which no package index knows
            checked += 1
            assert stated == real, (
                f"{path.name} attests {name} {stated}; this environment has {real}. "
                "Use EnvironmentBOM.of_this_environment() rather than a literal"
            )
    assert checked == 0, (
        "an example still states a version for an installed package; the point is that "
        "none of them do"
    )


# --- the predicate's schema, not only its type label --------------------------------------


def _wire(predicate) -> Attestation:
    """The example bundle's envelope with `predicate` swapped in, unsigned."""
    import base64

    envelope = Attestation.unsigned(_bundle()).to_envelope()
    statement = json.loads(base64.b64decode(envelope["payload"]))
    statement["predicate"] = predicate
    payload = json.dumps(statement, sort_keys=True, separators=(",", ":")).encode()
    return Attestation.model_validate({**envelope, "payload": base64.b64encode(payload).decode()})


def _honest_predicate() -> dict:
    return _bundle().predicate.to_json_dict()


def test_a_predicate_that_is_not_the_shape_its_type_declares_fails_verification():
    """`evidence-attestation` names three checks: signature, subject digests, **and
    predicate schema**. Two were implemented.

    A predicate of `{"anything": "at all"}` verified PASS whenever the type string matched
    and the subject digests did — an envelope carrying no scorecard, no citations and no
    bill of materials came back clean, which is the one answer a verifier must never give.
    """
    artifacts = _artifacts()
    honest = verify_attestation(_wire(_honest_predicate()), artifacts=artifacts)
    assert honest.status is CheckStatus.PASS and not honest.problems

    for predicate in ({}, {"anything": "at all"}):
        report = verify_attestation(_wire(predicate), artifacts=artifacts)
        assert report.status is CheckStatus.FAIL, predicate
        assert "which its own type requires" in " ".join(report.problems), predicate

    # A predicate that is not an object at all says *that*, rather than reporting six
    # missing keys — which is what a key check alone produces for a list, since every key
    # is missing from it. The message is the difference and so it is what is asserted.
    for predicate in ([1, 2, 3], "a string", 7):
        report = verify_attestation(_wire(predicate), artifacts=artifacts)
        assert report.status is CheckStatus.FAIL, predicate
        assert "not an object" in " ".join(report.problems), (predicate, report.problems)


@pytest.mark.parametrize(
    "key", ["specDigest", "status", "scorecard", "citations", "bom", "aiDisclosure"]
)
def test_every_key_the_predicate_writer_emits_is_one_the_verifier_requires(key):
    """Parametrised over the keys, and the writer's own output is the source of the list.

    A required key the checker forgot would show up here as a removal that verifies clean.
    """
    assert key in _honest_predicate(), f"the writer no longer emits {key!r}"
    stripped = {k: v for k, v in _honest_predicate().items() if k != key}
    report = verify_attestation(_wire(stripped), artifacts=_artifacts())
    assert report.status is CheckStatus.FAIL
    assert key in " ".join(report.problems)


def test_the_verifier_requires_every_key_the_writer_emits():
    """The other direction, and the one a per-key test cannot give.

    `to_json_dict` gaining a field that the verifier does not require would leave a hole no
    parametrised list notices, because the list is written by hand. `sections` is optional
    on the writer's side and is exempt for that reason.
    """
    from anvilate.attestation import _PREDICATE_REQUIRED_KEYS

    emitted = set(_honest_predicate()) - {"sections"}
    assert emitted == set(_PREDICATE_REQUIRED_KEYS), (
        f"the writer emits {sorted(emitted)}; the verifier requires "
        f"{sorted(_PREDICATE_REQUIRED_KEYS)}"
    )


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("specDigest", "nope", "not a sha256 hex digest"),
        ("status", "maybe", "not a scorecard status"),
        ("scorecard", {"entries": [{"nope": 1}]}, "scorecard does not validate"),
        ("bom", {"x": 1}, "not a CycloneDX document"),
        ("citations", "not a list", "not a list"),
        ("aiDisclosure", "not an object", "not an object"),
    ],
)
def test_a_present_but_wrong_predicate_field_is_named(field, value, expected):
    """Present-and-wrong is the case a required-keys check alone cannot see."""
    report = verify_attestation(
        _wire({**_honest_predicate(), field: value}), artifacts=_artifacts()
    )
    assert report.status is CheckStatus.FAIL
    assert expected in " ".join(report.problems), report.problems


def test_the_schema_check_runs_only_for_the_type_this_verifier_understands():
    """An unknown predicate type is already refused; validating a foreign predicate against
    this schema would report the wrong thing about it."""
    import base64

    envelope = Attestation.unsigned(_bundle()).to_envelope()
    statement = json.loads(base64.b64decode(envelope["payload"]))
    statement["predicateType"] = "https://example.com/other/v1"
    statement["predicate"] = {"whatever": "that schema says"}
    payload = json.dumps(statement, sort_keys=True, separators=(",", ":")).encode()
    foreign = Attestation.model_validate(
        {**envelope, "payload": base64.b64encode(payload).decode()}
    )
    reported = verify_attestation(foreign, artifacts=_artifacts()).problems
    # Exactly one complaint, and it is about the type. Asserting that some *phrase* is
    # absent is weaker than it looks — the schema check's messages talk about missing keys,
    # so a negative on the word "schema" passes while every key is being reported.
    assert len(reported) == 1, reported
    assert "which this verifier does not know" in reported[0]


# --- the BOM against the schema it declares conformance to ---------------------------------
#
# `to_cyclonedx()` emits a document that says `"bomFormat": "CycloneDX"` and names a spec
# version. Until now the only thing holding that claim was this file's own idea of the
# shape. CycloneDX publishes the JSON Schema, so the claim is checkable, and the pattern is
# the one `test_qif.py` and `test_dcc.py` already use: opt-in because the schema is a
# separate download, and the scheduled CI job proves it did not skip.

_CYCLONEDX_SCHEMAS = {
    "http://cyclonedx.org/schema/jsf-0.82.schema.json": "jsf-0.82.schema.json",
    "http://cyclonedx.org/schema/spdx.schema.json": "spdx.schema.json",
}


def _cyclonedx_schema():
    """The published schema as a parsed document, or a skip saying which part is missing."""
    location = os.environ.get("ANVILATE_CYCLONEDX_SCHEMA")
    if not location:
        pytest.skip(
            "set ANVILATE_CYCLONEDX_SCHEMA to a directory holding bom-1.6.schema.json and "
            "the two schemas it references (jsf-0.82, spdx) from "
            "https://github.com/CycloneDX/specification/tree/master/schema"
        )
    directory = Path(location)
    # Which file to read is decided by what is *there*, not by the constant under test.
    # Naming the file `bom-{CYCLONEDX_SPEC_VERSION}.schema.json` made a wrong constant skip
    # this gate rather than fail it: the schema for the version it wrongly claimed was
    # simply absent. A skip is not a pass, and a gate that disarms itself on the mutation
    # it exists to catch is worse than no gate.
    available = sorted(directory.glob("bom-*.schema.json"))
    if not available:
        pytest.skip(f"no bom-*.schema.json under {location}")
    by_version = {path.name[len("bom-") : -len(".schema.json")]: path for path in available}
    bom = by_version.get(CYCLONEDX_SPEC_VERSION)
    assert bom is not None, (
        f"this module emits CycloneDX {CYCLONEDX_SPEC_VERSION} and {location} holds the "
        f"schemas for {sorted(by_version)}; nothing here can check that claim"
    )
    return json.loads(bom.read_text(encoding="utf-8")), directory


def _cyclonedx_validator():
    jsonschema = pytest.importorskip("jsonschema")
    referencing = pytest.importorskip("referencing")
    from referencing.jsonschema import DRAFT7

    schema, directory = _cyclonedx_schema()
    resources = []
    for uri, filename in _CYCLONEDX_SCHEMAS.items():
        referenced = directory / filename
        if not referenced.exists():
            pytest.skip(f"no {filename} under {directory}; the BOM schema references it")
        contents = json.loads(referenced.read_text(encoding="utf-8"))
        resources.append((uri, referencing.Resource(contents=contents, specification=DRAFT7)))
    registry = referencing.Registry().with_resources(resources)
    return jsonschema.Draft7Validator(schema, registry=registry), schema


def test_the_bom_validates_against_the_published_cyclonedx_schema():
    """The real conformance check, and it is run over every component kind this can emit.

    A BOM built from the live environment exercises the ordinary path, and a hand-built one
    adds the two kinds that path never produces: the caller-stated versioned database, and
    an application entry sitting among the components. The top level and the component
    definition are both ``additionalProperties: false``, so a key emitted under a name
    CycloneDX does not define fails here rather than shipping in a document that says it is
    CycloneDX.
    """
    validator, _ = _cyclonedx_validator()

    stated = EnvironmentBOM(
        application=Component(name="anvilate", version="0.0.1", kind=ComponentKind.APPLICATION),
        components=(
            Component(name="pint", version="0.25.3"),
            Component(name="asme-bth-1", version="2023", kind=ComponentKind.DATA),
            Component(name="calculix", version="2.21", kind=ComponentKind.APPLICATION),
        ),
    )
    for bom in (EnvironmentBOM.of_this_environment(), stated):
        document = bom.to_cyclonedx()
        errors = sorted(validator.iter_errors(document), key=lambda error: list(error.path))
        assert not errors, "\n".join(f"{list(error.path)}: {error.message}" for error in errors)


def test_every_component_kind_is_one_the_published_schema_defines():
    """The anchor, and it is not the same check as validating a document.

    A document only exercises the kinds its fixture happens to build, so a `ComponentKind`
    added to the enum and emitted by some caller elsewhere would ship unvalidated. Every
    member is held against the schema's own `component.type` enumeration instead.
    """
    schema, _ = _cyclonedx_schema()
    published = set(schema["definitions"]["component"]["properties"]["type"]["enum"])
    unknown = sorted(kind.value for kind in ComponentKind if kind.value not in published)
    assert not unknown, (
        f"{unknown} is emitted as a CycloneDX component type and the {CYCLONEDX_SPEC_VERSION} "
        f"schema defines only {sorted(published)}"
    )


def test_the_declared_spec_version_is_the_schema_the_document_is_checked_against():
    """The one claim in the document the schema itself does not hold.

    `specVersion` is declared as a plain string with `"1.6"` as an *example* — no enum, no
    pattern — so a BOM emitting `"1.4"` validates against the 1.6 schema and reports the
    wrong spec to every reader. Held here against the schema's own `$id`, which is the only
    place the file says which version it is.
    """
    schema, _ = _cyclonedx_schema()
    assert schema["$id"] == f"http://cyclonedx.org/schema/bom-{CYCLONEDX_SPEC_VERSION}.schema.json"
    assert "enum" not in schema["properties"]["specVersion"], (
        "specVersion is now constrained by the schema; this gate is no longer the only "
        "thing holding it and should say so"
    )
    assert EnvironmentBOM.of_this_environment().to_cyclonedx()["specVersion"] == (
        CYCLONEDX_SPEC_VERSION
    )
