# Tasks: Attested evidence

## 1. Determinism groundwork

- [ ] 1.1 Byte-determinism audit of existing writers (DXF, scorecard JSON, evidence
      serialization): strip timestamps, stabilize float formatting
- [ ] 1.2 Bundle digest definition (spec + toolchain + database versions + artifacts)
      and canonical serialization

## 2. Attestation

- [ ] 2.1 Anvilate predicate schema (versioned, published) carrying scorecard, citations,
      provenance, versions
- [ ] 2.2 in-toto envelope emitter
- [ ] 2.3 Signing: CI keyless path and local-key path; unsigned state recorded honestly
- [ ] 2.4 `verify` command: signature + subject digests + predicate schema, offline-capable

## 3. BOM & disclosure

- [ ] 3.1 CycloneDX environment BOM embedded per bundle
- [ ] 3.2 AI-involvement disclosure record (model, backend, events, confirmations)

## 4. Tests & docs

- [ ] 4.1 Reproducibility test: identical inputs → identical digest
- [ ] 4.2 Tamper test: modified artifact fails verification naming the subject
- [ ] 4.3 Docs: what an attested bundle claims and how to verify one
