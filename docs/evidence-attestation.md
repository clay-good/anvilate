# Attested evidence

**A seal you can re-run.** A screening result gets a content address: hash the spec, the
verdict, the citations, the environment, and the artifact digests into one canonical
document, wrap it in a standard envelope, and hand somebody the bytes. They re-hash it.
Either it is the same piece of work or it is not, and the difference is visible without
trusting the person who sent it.

The PE-stamp world signs PDFs. This signs the computation.

```python
from anvilate.attestation import (
    Attestation, EvidenceBundle, LocalHmacSigner, Subject, verify_attestation,
)

bundle = EvidenceBundle(subjects=(Subject.over("lug.dxf", dxf_bytes),), predicate=predicate)
bundle.digest            # '475bf2ca…' — the same for every rebuild of the same inputs
envelope = Attestation.signed_by(bundle, LocalHmacSigner(secret))
verify_attestation(envelope, artifacts={"lug.dxf": dxf_bytes}, signer=signer)
# [PASS] bundle 475bf2cadf8b: signature symmetric_verified
```

## What the bundle claims

An [in-toto Statement v1](https://github.com/in-toto/attestation) whose **subjects** are
the produced artifacts by SHA-256, and whose **predicate** —
`https://anvilate.dev/attestation/screening/v1`, versioned in the URI so a breaking change
takes a new one — carries six things:

| Field | What it is |
| --- | --- |
| `specDigest` | the digest of the spec that was screened |
| `status` | the rolled-up verdict, in the scorecard's own tri-state |
| `scorecard` | every check: name, status, detail, margins, derivation |
| `citations` | the standards records behind the numbers, from the provenance roll-up |
| `bom` | a CycloneDX 1.6 inventory of the environment that computed it |
| `aiDisclosure` | whether, where, and by which model an LLM participated |

The envelope is [DSSE](https://github.com/secure-systems-lab/dsse): `payloadType`,
base64 payload, signatures. Standard attestation tooling reads the subjects and skips a
predicate it does not recognize, so the bundle is useful to a verifier that has never
heard of Anvilate.

## Four things that are deliberate

**No wall clock, anywhere.** CycloneDX's `metadata.timestamp` and `serialNumber` are both
optional and both unique per emission, so both are omitted. One timestamp in the payload
makes every rebuild a different document and the content address worth nothing. A gate in
the suite greps the whole shipped package for `datetime.now`, `date.today`, `time.time`,
and `uuid` — the determinism the digest rests on is enforced, not assumed.

**The environment is inside the address.** Bump `anvilate_materials` from 2026.03 to
2026.09 and the digest moves, even with the spec untouched. The same spec screened against
different data is a different piece of work, and a digest that hid that would be the most
expensive kind of false negative.

**Unsigned is a state, not a gap.** Air-gapped runs produce `Attestation.unsigned(...)`,
and nothing thereafter presents it as attested. Verification still checks what it can —
the artifact digests, the statement type, the predicate type — and reports
`signature unsigned` in plain words.

**A signature nobody checked is not a checked signature.** Hand `verify_attestation` a
signed envelope with no key and the report is `NOT_EVALUATED`, not `PASS`. It is the
scorecard's no-silent-green rule applied to the seal itself. Same for artifacts: a subject
you did not supply comes back *unchecked*, never assumed intact, and an artifact you
supplied that the bundle never covered is a **failure** — you believed it was covered and
it was not.

## What the bundled signer does and does not prove

`LocalHmacSigner` is HMAC-SHA256 over the DSSE pre-authentication encoding. It is in the
box because Anvilate's runtime dependencies are pure-Python and few, and it is honest
about its ceiling: **HMAC is symmetric.** Whoever can verify the tag could also have
produced it. That makes a bundle tamper-evident against anyone without the secret; it does
not establish authorship.

So the report distinguishes them. `SignatureState.SYMMETRIC_VERIFIED` is a match on a
shared secret; `VERIFIED` is a match on an asymmetric signature; and
`VerificationReport.attested` — the strict flag — is True only for the latter.

`AttestationSigner` is the seam. Five members (`keyid`, `algorithm`, `symmetric`, `sign`,
`verify`) and an Ed25519 key through `cryptography`, a hardware token, or a Sigstore
keyless flow in CI plugs in without this module growing a dependency.

**Not implemented:** the Sigstore keyless path itself (it needs a network round trip to a
transparency log and a dependency Anvilate does not carry), and Rekor inclusion proofs.
The envelope shape is the standard one, so adding a signer later does not change any
document already produced.

## The AI-involvement disclosure

Anvilate's specs are LLM-drafted by design, so the bundle says so machine-readably: the
model, the backend, the stage (`intent compilation`, `critic edit`), and who confirmed it.
`origins` maps each spec field to where its value came from, in the same
`DecisionOrigin` vocabulary the [reviewer dossier](responsible-charge-review.md) sorts on —
so model-drafted, user-stated, and database-resolved values stay distinguishable in the
bundle and not only in the UI that produced it.

The invariant is enforced at construction, because the failure mode is omission: a
disclosure whose origins attribute any value to a model **cannot** declare that no model
participated. A hand-authored spec uses `AIDisclosure.none()` and says so explicitly,
rather than leaving the field empty and letting a reader guess which kind of silence it is.

`AIDisclosure.unconfirmed_events` is the list a reviewer wants first: model output nobody
accepted.

## Worked example

`examples/attested_evidence_bundle.py` — a lifting lug's bundle rebuilt (same digest), its
materials database bumped (different digest), its drawing tampered with (fails, naming
`'lug.dxf'`), and verified without the key (`NOT_EVALUATED`).
