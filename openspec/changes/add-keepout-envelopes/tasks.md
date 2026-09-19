# Tasks: Keepout envelopes

## 1. Declaration

- [x] 1.1 Spec IR keepout type: tag, generating rule, clearance margin, reason, owner — `keepouts`
      on the Design Spec (1.15.0), each anchored to a tag or datum it moves with
- [x] 1.2 Generating rules: prism, cylinder, cone/frustum, swept profile, imported body — declared
      and validated; generating their geometry is 2.x
- [x] 1.3 Schema validation, round-trip, and diff legibility

## 2. Generation

- [ ] 2.1 Keepout archetypes in the pattern library under the existing contribution
      contract
- [ ] 2.2 Semantic tagging at creation; tag survives downstream operations
- [ ] 2.3 Keepouts held separately from the part solid — never unioned into it

## 3. Checking

- [ ] 3.1 T0 intrusion check: intersection volume, worst penetration depth, intruding tag
- [ ] 3.2 Clearance-margin band: intrusion into the margin warns, into the core fails
- [x] 3.3 Not-evaluated when a declared keepout was not generated or not checked — every
      declared keepout until intrusion is measured, naming a lost anchor
- [ ] 3.4 Repair hint naming the intruding feature and the direction that resolves it

## 4. Export

- [ ] 4.1 Dedicated layer/body on STEP and DXF, labeled non-manufacturing
- [x] 4.2 Keepout identity and reason recorded in the evidence bundle — the exported bundle
      carries each in its spec and its not-evaluated card entry

## 5. Tests

- [ ] 5.1 A rib added to fix deflection intrudes on a keepout and the card fails
- [x] 5.2 A keepout declared and never generated reports not-evaluated, never a pass
- [ ] 5.3 Exported keepout body is present, labeled, and absent from the machinable solid
- [x] 5.4 Zero-volume and inverted keepouts are refused rather than passing vacuously

## 6. Docs & examples

- [ ] 6.1 Example: an enclosure with a connector mating envelope and a service-access
      corridor
