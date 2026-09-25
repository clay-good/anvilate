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
- [x] 3.2 openEPD importer + material binding with provenance — `carbon_factor_from_openepd`
      reads a declaration's A1A2A3 GWP over the mass of one declared unit into a
      `CarbonFactor` whose source, dataset id and version name the declaration, with the
      declaration's own rsd as its band. Every guess is refused (several impact methods, no
      A1A2A3, a non-kgCO2e unit, a non-mass declared unit with no kg_per_declared_unit, and
      an expired declaration against a stated date). Shape from the Apache-2.0 reference
      models (cchangelabs/openepd); no declaration is committed (tests/test_openepd.py)
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
- The **openEPD importer (3.2) is built**; it takes the declaration's text from the caller
  and performs no I/O itself, so 4.3 still holds. **4.2 is open:** carbon has no place in
  the Design Spec or the evidence bundle yet, so a binding has nowhere to be recorded.
- **Air-gapped by construction (4.3):** the module performs no I/O of any kind, so there
  is no network call to assert the absence of.
