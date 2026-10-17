# Change: Material compliance and the materials engineers actually use

## Why

Anvilate's materials database holds about seventeen metals. Real products are half
plastic, rubber and composite: a molded housing, an EPDM seal, a carbon-fiber panel, a
silicone gasket in a medical device. Without those materials, an agent designing a
snap-fit enclosure or a seal has to invent properties, which this project refuses to do.

Each of those materials also carries obligations that have nothing to do with strength.
Engineers check these by hand, late, from supplier declarations:

- **Automotive.** Material composition goes into the industry's material data system as
  part of supplier approval. Substances on the EU REACH candidate list (253 entries as of
  2026-02-04) and the RoHS restricted list have to be declared or avoided. The EU
  end-of-life-vehicles regulation agreed in December 2025 sets recycled-plastic content
  targets.
- **Medical devices.** A material in contact with the body needs a biocompatibility
  basis (ISO 10993 by contact type and duration). It must also survive the chosen
  sterilization method.
- **Space.** A material in vacuum has to meet the outgassing screen (ASTM E595: total
  mass loss ≤ 1.0%, collected volatile condensable material ≤ 0.10%).
- **Every industry.** Dissimilar metals in contact corrode. A galvanic pair is a
  material decision, made long before anyone sees corrosion.

All of these are look-ups against a declared material on a BOM line. That is exactly
what Anvilate has once products have BOMs.

## What Changes

| Area | Change |
| --- | --- |
| Polymers and elastomers | Records for common engineering plastics and elastomers: modulus and strength at temperature, allowable strain for snap-fits, creep modulus at stated times, service temperature, with a source per value. |
| Composite lamina | Lamina records (stiffnesses, strengths, ply thickness), each with its basis, for laminate screening. User-supplied allowables carry their basis. |
| Substance screening | Declared material compositions are screened against public substance lists (REACH candidate list, REACH Annex XVII, RoHS Annex II) fetched with consent and pinned by hash. Hits are reported per BOM line with the list version. |
| Composition export | Per-part material composition with mass, exported in a shape suppliers can transcribe into automotive material-data submissions. |
| Recycled content | Declared recycled content rolled up by plastic mass across the product. |
| Material attributes | Biocompatibility basis, sterilization compatibility, outgassing values, flammability rating: declared with source, screened against the product's declared needs. |
| Galvanic pairs | Every connection between dissimilar metals is screened against a galvanic compatibility table from public-release data, with environment severity declared. |

## Impact

- New capability: `material-compliance`. Delta: `standards-data` (ADDED).
- Builds on `add-product-structure` and `add-interface-contracts`: BOM lines carry the
  materials, and connections identify the pairs in contact.
- Licensing:
  - Commercially restricted lists are fetched with the user's consent, never bundled.
    The automotive declarable-substance list is one, being free only for non-commercial
    use.
  - Vendor datasheet values are cited per value, never scraped in bulk.
  - No proprietary materials database is reproduced.
- Explicitly out:
  - Any claim of regulatory compliance. Anvilate reports hits against a named list
    version; the declaration is the user's.
  - Conflict-minerals reporting.
  - Submitting to any external material-data system.
