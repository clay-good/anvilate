# Tasks: Product structure

Depends on `add-part-combinations` (mates, hardware, combination card).

## 1. Document

- [ ] 1.1 Product document schema (URN-identified): items, instances, patterns, mates,
      ground, layout, variants; references by relative path or embedded
- [x] 1.2 Item identity: part number, revision, description, make/buy/reference;
      provisional numbers derived from path and content, marked provisional
- [x] 1.3 Refusals: containment cycle, duplicate part number with different content,
      mirrored instance, unreadable sub-document

## 2. Tree

- [x] 2.1 Definitions and instances; linear and circular patterns
- [x] 2.2 Stable instance paths, unaffected by sibling order
- [x] 2.3 Placeholders: envelope, mass, center of mass, interfaces, reason
- [x] 2.4 Layout datums and driving parameters; unused-parameter report
- [x] 2.5 Variants resolved to complete products; interface check on substitution

## 3. Cards and builds

- [x] 3.1 Card per node with roll-up; finding stated once at its owner, referenced above
- [x] 3.2 Placeholder dependence carried on every affected entry
- [x] 3.3 Content-keyed rebuild; reuse count in the summary; equality with a cold build
      gated in CI

## 4. Agent surface

- [x] 4.1 Bounded summary tree from the existing build tool; node detail by path
- [x] 4.2 CLI parity for `check`, `combine`/`build` on product documents
- [x] 4.3 Worked products: linear stage, gear reducer, enclosure, frame on casters — each
      built, checked and exported in CI
- [x] 4.4 A docs page for products: the document, the tree, placeholders, what comes out
