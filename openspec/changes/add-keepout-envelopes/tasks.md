# Tasks: Keepout envelopes

## 1. Declaration

- [x] 1.1 Spec IR keepout type: tag, generating rule, clearance margin, reason, owner — `keepouts`
      on the Design Spec (1.15.0), each anchored to a tag or datum it moves with
- [x] 1.2 Generating rules: prism, cylinder, cone/frustum, swept profile, imported body — declared
      and validated; generating their geometry is 2.x
- [x] 1.3 Schema validation, round-trip, and diff legibility

## 2. Generation

- [x] 2.1 Keepout archetypes in the pattern library under the existing contribution
      contract — `KEEPOUT_ARCHETYPES`, five golden volumes each, gated
- [x] 2.2 Semantic tagging at creation; tag survives downstream operations — each body is built
      from its keepout and carries it, anchored to a tagged face of the part
- [x] 2.3 Keepouts held separately from the part solid — never unioned into it

## 3. Checking

- [x] 3.1 T0 intrusion check: intersection volume, worst penetration depth, intruding tag —
      `anvilate.keepouts.check_keepouts`, with a summary of what was screened
- [ ] 3.2 Clearance-margin band: intrusion into the margin warns, into the core fails — the
      band is measured and named; it fails rather than warns, because the scorecard has no
      warning status yet
- [x] 3.3 Not-evaluated when a declared keepout was not generated or not checked — every
      declared keepout until intrusion is measured, naming a lost anchor
- [x] 3.4 Repair hint naming the intruding feature and the direction that resolves it — solved
      for the box patterns' dimension along the keepout axis

## 4. Export

- [x] 4.1 Dedicated layer/body on STEP and DXF, labeled non-manufacturing — a keepout STEP of
      its own, byte-identical per input, and a `KEEPOUT_NON_MANUFACTURING` DXF layer
- [x] 4.2 Keepout identity and reason recorded in the evidence bundle — the exported bundle
      carries each in its spec and its not-evaluated card entry

## 5. Tests

- [x] 5.1 A rib added to fix deflection intrudes on a keepout and the card fails — a plate
      thickened to fix deflection reaches into a beam path (the patterns carry no ribs)
- [x] 5.2 A keepout declared and never generated reports not-evaluated, never a pass
- [x] 5.3 Exported keepout body is present, labeled, and absent from the machinable solid
- [x] 5.4 Zero-volume and inverted keepouts are refused rather than passing vacuously

## 6. Docs & examples

- [x] 6.1 Example: an enclosure with a connector mating envelope and a service-access
      corridor — examples/enclosure_keepouts.py
