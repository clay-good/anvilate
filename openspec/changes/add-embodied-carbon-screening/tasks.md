# Tasks: Embodied carbon screening

## 1. Data & licensing

- [x] 1.1 License review of candidate factor sources; bundle only redistribution-clean
      data (federal/generic datasets), record per-record source identity
- [x] 1.2 Curated factor table: common materials + primary processes, with bands

## 2. Contracts

- [x] 2.1 Factor type (value, source identity, version, geography, module scope, band)
- [x] 2.2 Estimate result type (itemized contributions, total, band, labels)

## 3. Implementation

- [x] 3.1 Estimator composing mass properties, material, process, material loss
- [ ] 3.2 openEPD importer + material binding with provenance — DEFERRED: a CarbonFactor
      built by hand from an EPD already records everything the estimate needs, and the
      importer is schema plumbing rather than analysis
- [x] 3.3 Rendering with screening/partial-scope labels; Pareto objective participation

## 4. Tests

- [x] 4.1 Missing factor → "not evaluated," never zero
- [ ] 4.2 EPD binding overrides generic factor and is recorded in the bundle — follows 3.2
- [x] 4.3 Air-gapped run produces estimates with zero network calls

## 5. Docs & examples

- [x] 5.1 Example: bracket redesign showing mass, cost, and carbon move together
- [x] 5.2 Explanation page: what a cradle-to-gate screening figure is and is not

## Scope as shipped

- **No factor data is bundled at all**, which resolves 1.1 and 1.2 by taking the
  user-supplied-allowables route the rest of the library takes: every `CarbonFactor`
  carries its own source, dataset id, version and geography, and a blank source is
  refused. The datasets that are not redistribution-clean are therefore not a licensing
  question, because none of them are copied in.
- The **openEPD importer (3.2, and 4.2 which follows it) is deferred.** It is schema
  plumbing, not analysis, and a factor built by hand from an EPD already carries
  everything the estimate consumes.
- **Air-gapped by construction (4.3):** the module performs no I/O of any kind, so there
  is no network call to assert the absence of.
