# Change: Attested evidence — content-addressed, signed, BOM-carrying bundles

## Why

2026 moved trust from artifacts to evidence trails, and the tooling matured: the in-toto
attestation framework with custom predicate types is the universal envelope
(https://slsa.dev/blog/2023/05/in-toto-and-slsa), Sigstore keyless signing is near-default
for public repos via GitHub Artifact Attestations, and the EU Digital Product Passport
registry went live July 20, 2026 with the iron & steel delegated act landing this year
(https://asuene.com/us/blog/eu-digital-product-passport-the-complete-guide-to-compliance-under-the-espr).
Research found no prior art for cryptographically attested mechanical calculations — the
PE-stamp world signs PDFs, not reproducible computations. Meanwhile the EU AI Act's
Article 50 machine-readable AI-disclosure obligations begin August 2026, and Anvilate's
specs are LLM-drafted by design.

Anvilate already records provenance graphs (headless-automation). This change makes the
bundle verifiable: content-addressed identity, a standard attestation envelope, an
embedded software BOM, and an AI-involvement disclosure — "a seal you can re-run."

## What Changes

- New capability spec `evidence-attestation`: content-addressed bundle identity over
  byte-deterministic artifacts; in-toto attestation with an Anvilate predicate; optional
  Sigstore keyless signing in CI with offline verification; embedded CycloneDX BOM of the
  software environment; AI-involvement disclosure recording LLM drafting and human
  confirmation.

## Impact

- Affected specs: new `evidence-attestation` capability; builds on the provenance-hashing
  requirement in `headless-automation` (unchanged) and the evidence bundle in
  `artifact-export` (unchanged).
- Affected code (when implemented): byte-determinism fixes in exporters (timestamps,
  float formatting), bundle hasher, attestation emitter, CI signing step, verifier
  command.
- Signing is strictly optional; air-gapped mode works unsigned or with a local key.
