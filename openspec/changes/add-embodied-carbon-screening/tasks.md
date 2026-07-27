# Tasks: Embodied carbon screening

## 1. Data & licensing

- [ ] 1.1 License review of candidate factor sources; bundle only redistribution-clean
      data (federal/generic datasets), record per-record source identity
- [ ] 1.2 Curated factor table: common materials + primary processes, with bands

## 2. Contracts

- [ ] 2.1 Factor type (value, source identity, version, geography, module scope, band)
- [ ] 2.2 Estimate result type (itemized contributions, total, band, labels)

## 3. Implementation

- [ ] 3.1 Estimator composing mass properties, material, process, material loss
- [ ] 3.2 openEPD importer + material binding with provenance
- [ ] 3.3 Rendering with screening/partial-scope labels; Pareto objective participation

## 4. Tests

- [ ] 4.1 Missing factor → "not evaluated," never zero
- [ ] 4.2 EPD binding overrides generic factor and is recorded in the bundle
- [ ] 4.3 Air-gapped run produces estimates with zero network calls

## 5. Docs & examples

- [ ] 5.1 Example: bracket redesign showing mass, cost, and carbon move together
- [ ] 5.2 Explanation page: what a cradle-to-gate screening figure is and is not
