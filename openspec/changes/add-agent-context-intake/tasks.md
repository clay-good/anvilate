# Tasks: Context intake

## 1. Sources on values

- [ ] 1.1 Source reference on a provenanced value: file, digest, locator, method, confirmation
- [ ] 1.2 Origins `measured_from_file` and `agent_read`; schema, round-trip, diff, bundle
- [ ] 1.3 Unconfirmed count on the scorecard; dependent checks say so
- [ ] 1.4 Export gate: unconfirmed readings export only watermarked
- [ ] 1.5 Confirmation as an explicit act naming a person; refused without one
- [ ] 1.6 Stale-source report when a cited file's digest no longer matches

## 2. Readers

- [x] 2.1 STEP: units as written and as read, solids, product names, size, volume
- [ ] 2.1b STEP: mass when a material is supplied; a name per solid
- [x] 2.2 STEP: planes, cylinders, holes (split faces merged), hole patterns, unclassified count
- [ ] 2.3 STEP: assembly tree with names and placements
- [x] 2.4 DXF: unit stated or refused, layers, closed profiles from chained entities, blocks
- [x] 2.5 DXF: dimension entities with override disagreement (existing requirement)
- [x] 2.6 STL and 3MF as meshes: size, volume, count, labelled
- [x] 2.7 Refusals for DWG, IGES, Parasolid and native formats, each with its export step
- [ ] 2.8 Reader test corpus: files written by SolidWorks, Fusion, Onshape and FreeCAD,
      in mm and inch, single part and assembly

## 3. Using what was read

- [x] 3.1 Folder inventory, bounded, with who reads what
- [ ] 3.2 Seed a catalog pattern from a measured profile or part; "no pattern matches" result
- [ ] 3.3 Measured-versus-read disagreement report

## 4. Surfaces

- [x] 4.1 `anvilate-mcp --context DIR` (repeatable, read-only); path confinement tests
- [x] 4.2 MCP tools and CLI commands for inventory and reading, within size and time limits
- [x] 4.3 Agent guide: "point your agent at a folder", with a worked session

## 5. Docs

- [x] 5.1 What Anvilate reads, what the agent reads, what nobody reads, in one table
