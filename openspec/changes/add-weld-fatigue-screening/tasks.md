# Tasks: Weld fatigue screening

## 1. Contracts

- [ ] 1.1 Detail-category input type (value, standard, edition, detail description,
      provenance)
- [ ] 1.2 Correction declaration types (thickness, mean stress)

## 2. Implementation

- [ ] 2.1 Standardized S-N curve construction from a declared category, cited
- [ ] 2.2 Thickness and mean-stress corrections with visible factors
- [ ] 2.3 Spectrum damage via existing Miner summation
- [ ] 2.4 Allowable-cycles / allowable-range design inverse

## 3. Tests

- [ ] 3.1 Worked-example anchoring against published detail-category examples
      (re-derived, never redistributed)
- [ ] 3.2 Forward/inverse round-trip per the library contract
- [ ] 3.3 Missing category → "not evaluated"; corrections appear in results
- [ ] 3.4 Optional: validation sampling against the open welded-joint S-N dataset,
      license verified before ingestion

## 4. Docs & examples

- [ ] 4.1 Example: fillet-welded attachment screened over a load spectrum
- [ ] 4.2 Explanation page: why Anvilate makes you choose the detail category
