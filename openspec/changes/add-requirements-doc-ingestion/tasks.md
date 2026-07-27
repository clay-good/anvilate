# Tasks: Requirements-document ingestion

## 1. Extraction

- [ ] 1.1 Requirements-oriented extraction pass over the local PDF stack (quantities with
      units, constraint phrases, environment statements)
- [ ] 1.2 Draft-spec assembly with per-value source locations and document provenance

## 2. Confirmation flow

- [ ] 2.1 Confirmation checklist integration (reuse datasheet flow)
- [ ] 2.2 Draft-vs-confirmed spec state and pipeline refusal on unconfirmed load-bearing
      values
- [ ] 2.3 Conflict surfacing for inconsistent duplicate quantities

## 3. Tests & docs

- [ ] 3.1 Extraction fixtures: representative requirement sheets (license-clean,
      synthetic)
- [ ] 3.2 Refusal behavior tests for unconfirmed values
- [ ] 3.3 Documentation: what ingestion extracts, what it never does (no silent
      load-bearing values)
