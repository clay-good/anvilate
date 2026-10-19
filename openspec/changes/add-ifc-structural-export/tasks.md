# Tasks: IFC structural export

Builds on the export layer in `src/anvilate/export` and the release package.

## 1. Mapping

- [ ] 1.1 Archetype-to-IFC class map with predefined types; refusal for an archetype with no
      mapping
- [ ] 1.2 Standard profile definitions for rolled sections; B-rep for the rest
- [ ] 1.3 Property sets: standard common sets and the Anvilate set

## 2. Writer

- [ ] 2.1 IFC4 writer through the optional toolkit; units declared; header with the
      watermark when unvalidated
- [ ] 2.2 Products as aggregation with transforms and part numbers as tags
- [ ] 2.3 IFC 4.3 as a declared option; unsupported capabilities refused by name

## 3. Proof

- [ ] 3.1 Schema validation with an open checker in CI; re-read and compare volumes and
      centroids with the built solids
- [ ] 3.2 Import check in at least one open BIM viewer recorded under the export targets
- [ ] 3.3 A docs page section on IFC in the export targets docs
