# Tasks: Fitness-for-service fracture screening

## 1. Contracts

- [ ] 1.1 Flaw geometry types (through-wall, surface, embedded; plate/cylinder) with
      validity-range metadata
- [ ] 1.2 Toughness input with provenance + estimate-labeled Charpy correlation path

## 2. Implementation

- [ ] 2.1 Newman–Raju-class SIF solutions with range enforcement (extends fracture.py)
- [ ] 2.2 Reference-stress plastic-collapse solutions per geometry
- [ ] 2.3 FAD curve, assessment-point placement, load-line margin, Lr cutoff
- [ ] 2.4 Screening/assessor framing in scorecard rendering

## 3. Tests

- [ ] 3.1 Worked-example anchoring against NASA/open-literature SIF tabulations
- [ ] 3.2 FAD margin agreement with published R6-class worked examples (re-derived)
- [ ] 3.3 Out-of-range flaw → "not evaluated"; estimate labeling round-trips to evidence

## 4. Docs & examples

- [ ] 4.1 Example: surface flaw in a pressure-vessel shell from detection to FAD verdict
- [ ] 4.2 Explanation page: what FAD screening is, and why disposition needs a qualified
      assessor
