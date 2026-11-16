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
- [x] 2.2 Per-line substance screen with article concentration and list version
      (a list is a CSV you load, pinned by its version and SHA-256; an item is one
      material, so its article and homogeneous-material concentrations are one fraction;
      CAS check digits are checked everywhere a number is matched)

## 3. Exports

- [x] 3.1 Per-part composition export; product recycled-content roll-up

## 4. Material needs and pairs

- [x] 4.1 Needs declarations (body contact, sterilization, vacuum, flammability,
      temperature) and attribute screens
- [x] 4.2 Galvanic compatibility table from public-release data, with provenance;
      environment severity; isolation clearing
      (MIL-STD-889C Table II ships with its citation; the three clause rules a separation
      alone misses are checked; 889C's Table I is a scanned image and is not transcribed,
      and which items of a product touch is still the caller's)
- [x] 4.3 A docs page for material compliance: what is screened, against which list
      version, and what remains the user's declaration
