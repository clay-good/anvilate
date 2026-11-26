# Tasks: IFC structural export

Builds on the export layer in `src/anvilate/export` and the release package.

## 1. Mapping

- [x] 1.1 Archetype-to-IFC class map with predefined types; refusal for an archetype with no
      mapping — `IFC_ELEMENT_CLASSES`; a 4.3-only type is `USERDEFINED` + `ObjectType` in IFC4
- [x] 1.2 Standard profile definitions for rolled sections; B-rep for the rest — I shapes,
      BOX/TUBE/pipe and AISC HSS as profile + `IfcExtrudedAreaSolid`, bounds-checked
- [x] 1.3 Property sets: standard common sets and the Anvilate set — `Pset_<Class>Common`
      (`Reference`, `LoadBearing`) and `Anvilate_Screening`

## 2. Writer

- [x] 2.1 IFC4 writer through the optional toolkit; units declared; header with the
      watermark when unvalidated
- [x] 2.2 Products as aggregation with transforms and part numbers as tags — combinations
      (`combination_ifc_parts`, `IfcElementAssembly`, fasteners) and now products:
      `product_ifc_parts` carries each item's `assembly_path` and `render_ifc` writes one
      nested `IfcElementAssembly` per sub-product, so a tree arrives as a tree. The path is
      in the content digest the GlobalIds are seeded from, so a flattened tree is not the
      same file. An item with no mapped archetype — a placeholder above all — is refused
      naming it rather than written as a proxy; a reference item is skipped
- [x] 2.3 IFC 4.3 as a declared option; unsupported capabilities refused by name
      — `--ifc-schema IFC4X3_ADD2` on `export` and `combine`, `ifc_schema` on MCP; a schema
      named for a non-IFC output is refused. Every mapped element writes and validates in
      4.3, so the one capability it lacks (`Pset_MechanicalFastenerCommon`) is omitted for
      fasteners in both schemas rather than refused

## 3. Proof

- [x] 3.1 Schema validation with an open checker in CI; re-read and compare volumes and
      centroids with the built solids
- [ ] 3.2 Import check in at least one open BIM viewer recorded under the export targets
- [x] 3.3 A docs page section on IFC in the export targets docs
