# Tasks: Material compliance

Depends on `add-product-structure` (BOM lines) and `add-interface-contracts`
(connections in contact).

## 1. Materials data

- [ ] 1.1 Polymer and elastomer records with property temperatures and creep durations,
      each value sourced
- [ ] 1.2 Composite lamina records with strength basis
- [x] 1.3 Composition (CAS and fraction) and recycled fraction on material records

## 2. Substance lists

- [ ] 2.1 Consent-gated, digest-pinned fetchers for the REACH candidate list, REACH
      Annex XVII, RoHS Annex II, and the automotive declarable-substance list (terms
      recorded; nothing bundled)
- [ ] 2.2 Per-line substance screen with article concentration and list version

## 3. Exports

- [x] 3.1 Per-part composition export; product recycled-content roll-up

## 4. Material needs and pairs

- [x] 4.1 Needs declarations (body contact, sterilization, vacuum, flammability,
      temperature) and attribute screens
- [ ] 4.2 Galvanic compatibility table from public-release data, with provenance;
      environment severity; isolation clearing
- [x] 4.3 A docs page for material compliance: what is screened, against which list
      version, and what remains the user's declaration
