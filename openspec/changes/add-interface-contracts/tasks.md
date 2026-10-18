# Tasks: Interface contracts

Depends on `add-product-structure` (items, paths) and `add-part-combinations` (mates and
joint checks).

## 1. Declarations

- [ ] 1.1 Interface record: name, kind, frame, kind parameters; bound to a tagged feature
      on parts, declared on placeholders and components
- [x] 1.2 Closed kind vocabulary with required parameters and units, published in the
      schema and in the MCP `initialize` instructions
- [x] 1.3 Compatibility table (pairs, agreeing parameters, checks), published as data

## 2. Connections

- [x] 2.1 Connection by path and interface name; placement through existing mates
- [x] 2.2 Refusal of incompatible kinds before geometry
- [x] 2.3 Pairing checks routed to existing combination checks; new kind-specific checks
      only where none exists
- [ ] 2.4 Joints declared on connections; axis from interface frames

## 3. Product rule check

- [x] 3.1 Every interface connected or declared open with a reason
- [x] 3.2 Partner-count rule per kind

## 4. Output

- [ ] 4.1 Interface control table: CSV and report section
- [ ] 4.2 A docs page for interfaces: the vocabulary, the table, how a connection is checked
