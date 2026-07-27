# Tasks: Member-force and section-property interop

## 1. Contracts

- [ ] 1.1 Typed member-force record (stations, components, units, load case, tool + version)
- [ ] 1.2 Typed external section-property record with source provenance
- [ ] 1.3 Axis-convention declaration and mapping validation rules

## 2. Implementation

- [ ] 2.1 Bind ingested demands to existing beam/column/beam-column/torsion screens
- [ ] 2.2 Optional sectionproperties adapter (import constants, tag provenance)
- [ ] 2.3 Report rendering: external-demand and external-property provenance lines

## 3. Tests

- [ ] 3.1 Round-trip against a published frame example: external forces + Anvilate checks
      reproduce the worked design check
- [ ] 3.2 Convention-mismatch rejection cases (undeclared, inconsistent, wrong units)
- [ ] 3.3 Optional-dependency absence behaves identically with manual entry

## 4. Docs & examples

- [ ] 4.1 Example: frame member forces (external) → cited AISC screens → scorecard
- [ ] 4.2 Example: custom section constants → beam check
