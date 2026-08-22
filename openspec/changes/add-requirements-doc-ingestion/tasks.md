# Tasks: Requirements-document ingestion

## 1. Extraction

- [ ] 1.1 Requirements-oriented extraction pass over the local PDF stack (quantities with
      units, constraint phrases, environment statements)
- [x] 1.2 Draft-spec assembly with per-value source locations and document provenance

## 2. Confirmation flow

- [x] 2.1 Confirmation checklist integration (reuse datasheet flow)
- [x] 2.2 Draft-vs-confirmed spec state and pipeline refusal on unconfirmed load-bearing
      values
- [x] 2.3 Conflict surfacing for inconsistent duplicate quantities

## 3. Tests & docs

- [x] 3.1 Extraction fixtures: representative requirement sheets (license-clean,
      synthetic)
- [x] 3.2 Refusal behavior tests for unconfirmed values
- [x] 3.3 Documentation: what ingestion extracts, what it never does (no silent
      load-bearing values)

## Scope as shipped

`src/anvilate/ingest.py`, `tests/test_ingest.py`,
`examples/rfq_sheet_to_confirmed_inputs.py`, `docs/requirements-ingestion.md`.

**1.1 is the only task still open, and it is open for a dependency, not a decision.** The
extraction pass ships over plain text; the PDF half needs the local document stack
(Docling/pdfplumber) that the project does not yet carry. The state machine is the part
that matters and it does not change when that lands — `SourceLocation` already carries a
page number, and `extract_requirements` takes one.

**No confidence scores, deliberately.** A number between 0 and 1 on an extraction invites
a threshold and is not a measurement of anything — it is the extractor grading its own
homework. Every value carries the exact line and location instead, so "is this right?" is
answered by looking.

**A bare number is recorded as not-extracted rather than guessed at.** A requirements
sheet says "quantity: 4" as often as it says "design load: 50 kN". Every labelled line the
pass declines is listed with the reason, which makes the pass auditable by subtraction —
a reader can see what it did not take instead of assuming it took everything.

**A conflict blocks the release even when both sides are confirmed.** Two values for one
field is not a field, whatever anyone signed. Resolution means rejecting one, and a
rejection stays in the record: "somebody refused this" is different information from
"nobody has looked at this yet", which is why there are three states and not a boolean.

**Two defects the tests caught during the build, both worth recording.** A nested
conditional expression in `with_confirmation` parsed right-associatively as "confirm
EVERYTHING if the state is CONFIRMED", so confirming one field confirmed the whole draft —
the precise opposite of per-value confirmation. And the conflict detector collapsed an
incommensurable-unit conversion failure to a one-element set, which read as "the two
values agree"; the conversion failure *is* the disagreement.
