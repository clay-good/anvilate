# Tasks: Attested evidence

## 1. Determinism groundwork

- [x] 1.1 Byte-determinism audit of existing writers (DXF, scorecard JSON, evidence
      serialization): strip timestamps, stabilize float formatting
- [x] 1.2 Bundle digest definition (spec + toolchain + database versions + artifacts)
      and canonical serialization

## 2. Attestation

- [x] 2.1 Anvilate predicate schema (versioned, published) carrying scorecard, citations,
      provenance, versions
- [x] 2.2 in-toto envelope emitter
- [x] 2.3 Signing: CI keyless path and local-key path; unsigned state recorded honestly
- [x] 2.4 `verify` command: signature + subject digests + predicate schema, offline-capable

## 3. BOM & disclosure

- [x] 3.1 CycloneDX environment BOM embedded per bundle
- [x] 3.2 AI-involvement disclosure record (model, backend, events, confirmations)

## 4. Tests & docs

- [x] 4.1 Reproducibility test: identical inputs → identical digest
- [x] 4.2 Tamper test: modified artifact fails verification naming the subject
- [x] 4.3 Docs: what an attested bundle claims and how to verify one

## Scope as shipped

`src/anvilate/attestation.py`, `tests/test_attestation.py`,
`examples/attested_evidence_bundle.py`, `docs/evidence-attestation.md`.

**The determinism groundwork turned out to be an audit with nothing to fix, and that is
worth recording rather than assuming.** A grep of the shipped package for `datetime.now`,
`date.today`, `time.time`, and `uuid` came back empty: `review.ReviewRecord.reviewed_on`
is a declared input, not today's date, and no writer stamps a clock. So 1.1 shipped as a
gate instead of a fix — `test_no_shipped_module_reads_a_wall_clock_or_a_random_identifier`
keeps it that way, because one `now()` in one exporter silently makes every rebuild a new
bundle and the content address worthless. The same reasoning is why the CycloneDX BOM omits
its optional `metadata.timestamp` and `serialNumber`.

**Canonical JSON refuses non-finite numbers, which is a real trap and not a formality.**
`json.dumps` writes bare `NaN` and `Infinity` by default — valid Python, invalid JSON. A
bundle carrying a NaN margin would hash cleanly here and fail in every conformant reader
it was produced for. A check that could not produce a number reports `NOT_EVALUATED`; it
does not emit one no parser accepts.

**The bundled signer is symmetric, and the surface says so in three places.** Anvilate's
runtime dependencies are pure-Python and few, so `LocalHmacSigner` is HMAC-SHA256 over the
DSSE pre-authentication encoding. HMAC proves possession of the shared secret, not
authorship: whoever can verify it could have produced it. `SignatureState` separates
`SYMMETRIC_VERIFIED` from `VERIFIED`, `VerificationReport.attested` is True only for the
latter, and the docs lead with the limit. `AttestationSigner` is the seam an Ed25519 key
plugs into with no new dependency.

**Deferred, and why:** the Sigstore *keyless* path (2.3) needs a network round trip to a
transparency log and a dependency the project does not carry; Rekor inclusion proofs
likewise. The local-key path and the honest-unsigned path both ship, which is what
air-gapped operation actually needs. The envelope is the standard DSSE shape, so adding a
keyless signer later does not invalidate a document already produced.
