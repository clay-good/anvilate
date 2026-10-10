# Tasks: Part combinations

Depends on `expand-drawable-parts` groups 1 and 2 (registry, shared features, projector).

## 1. Document and placement

- [ ] 1.1 Combination document: parts by reference to their specs, mates between tagged
      features, optional offset and rotation step; schema published
- [ ] 1.2 Mate kinds: face to face, hole pattern to hole pattern, shaft in bore, edge flush
- [ ] 1.3 Deterministic placement from mates; refusals for under- and over-constraint

## 2. Hardware

- [ ] 2.1 Fastener, pin and key envelopes from the standards data, labelled as envelopes
- [ ] 2.2 Hardware stacks placed into mated holes from the clamped thickness

## 3. Checks

- [ ] 3.1 Hole-pattern agreement, clearance class, bolt engagement length
- [ ] 3.2 Shaft/bore fit class; key in keyway and seat
- [ ] 3.3 Interference between every pair, with overlap volume
- [ ] 3.4 Joint screens fed from mated geometry (bolted connection, shaft key, fit)

## 4. Output

- [ ] 4.1 Assembly views: per-part tone, balloons, parts list, optional exploded view
- [ ] 4.2 STEP AP242 assembly with named components and transforms; referee job reads it
- [ ] 4.3 Bill of materials (text, JSON, in the evidence bundle)
- [ ] 4.4 Export gated on the combination's card

## 5. Worked combinations and surfaces

- [ ] 5.1 Five worked combinations with example documents
- [ ] 5.2 CLI and MCP: build, render, check and export a combination with the same verbs
      as a single part
- [ ] 5.3 Docs: a combinations guide with one picture per worked example
