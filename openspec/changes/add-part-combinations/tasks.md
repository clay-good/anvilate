# Tasks: Part combinations

Depends on `expand-drawable-parts` groups 1 and 2 (registry, shared features, projector).

## 1. Document and placement

- [x] 1.1 Combination document: parts by reference to their specs, mates between tagged
      features, optional offset and rotation step; schema published
- [x] 1.2 Mate kinds: face to face, hole pattern to hole pattern, shaft in bore, edge flush
- [x] 1.3 Deterministic placement from mates; refusals for under- and over-constraint

## 2. Hardware

- [x] 2.1 Bolt, washer and nut envelopes from the standards data, labelled as envelopes
- [x] 2.1b Dowel pin envelopes: `pin` in a hardware entry, an ISO 2338 pin in every hole of
      the mate, checked for fit and length (a parallel key is the `shaft_key` part; seating
      it in a keyway is 3.2)
- [x] 2.2 Hardware stacks placed into mated holes from the clamped thickness

## 3. Checks

- [x] 3.1 Hole-pattern agreement, clearance class, bolt engagement length
- [x] 3.2a Shaft/bore fit: a `shaft_in_bore` mate holds bore and shaft to one nominal size,
      and a declared `fit` (ISO 286) is stated with what it leaves between them
- [ ] 3.2b Key in keyway and seat
- [x] 3.3 Interference between every pair, with overlap volume
- [ ] 3.4 Joint screens fed from mated geometry (bolted connection, shaft key, fit)

## 4. Output

- [x] 4.1 Assembly views: per-part tone, balloons, parts list
- [ ] 4.1b Exploded view; a failing mate marked on the picture; weld symbol
- [x] 4.2 STEP AP242 assembly with named components and transforms; referee job reads it
- [x] 4.3 Bill of materials (text, JSON, in the evidence bundle)
- [x] 4.4 Export gated on the combination's card

## 5. Worked combinations and surfaces

- [x] 5.1 Five worked combinations with example documents
- [x] 5.2 CLI and MCP: build, render, check and export a combination with the same verbs
      as a single part
- [x] 5.3 Docs: a combinations guide with one picture per worked example
