# Tasks: Failure-mode coverage

## 1. Catalog

- [x] 1.1 Mode record: id, description, applicability keys, discovery stage, citation
- [x] 1.2 Applicability keyed on declared facts (element class, material pair, interface
      kind, environment), never on free text in the spec
- [x] 1.3 Provenance and version on every record; user- and module-extensible

## 2. Resolution

- [x] 2.1 Applicable-mode resolution from the compiled spec
- [x] 2.2 Bind modes to the checks that address them; a check declares which modes it
      addresses, so the mapping is data rather than inference
- [x] 2.3 Bind modes to verification test archetypes where analysis cannot reach
- [x] 2.4 Unaddressed set: applicable, no check, no test

## 3. Reporting

- [x] 3.1 Count, population size, and the enumerated unaddressed set — never a bare
      percentage
- [x] 3.2 Discovery-stage attribution, rendered as a stage and not as a severity
- [x] 3.3 Card-level completeness statement referencing the unaddressed set

## 4. Gates

- [x] 4.1 CI: every catalog entry resolves to a real check id, test archetype, or an
      explicit unaddressed marker with a stated reason — both directions
- [ ] 4.2 CI: every check declares the modes it addresses; a check addressing none fails
      or declares why
- [x] 4.3 CI floor on catalog population per shipped element class, so an empty catalog
      cannot report full coverage

## 5. Tests

- [x] 5.1 A part passing every check with an unaddressed applicable mode does not render
      as complete — the defect class this capability exists to expose
- [x] 5.2 Deleting a catalog entry changes the coverage report, proving the report reads
      the catalog rather than asserting a number
- [x] 5.3 Adding a module adds its modes and the coverage denominator moves

## 6. Docs & examples

- [x] 6.1 Worked example: a clean card beside its failure-mode report
- [x] 6.2 Page: what the catalog is, why it is a floor and never exhaustive
