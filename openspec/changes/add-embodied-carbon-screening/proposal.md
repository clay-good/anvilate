# Change: Embodied carbon screening — cradle-to-gate kgCO2e beside the physics verdict

## Why

Anvilate already computes the two inputs a screening carbon estimate needs — material and
mass — and already reports screening-grade cost next to the physics verdict. Adding
cradle-to-gate kgCO2e makes mass reduction legible as a carbon decision at the moment the
design is still cheap to change. The proven precedent is Ansys Granta's Eco Audit
(material + mass + primary process → embodied energy and CO2e, explicitly framed for
comparison rather than certification); nothing open-source and local-first does this for
mechanical parts.

The regulatory pull is real but nearer-term than it looks only for materials: the EU
Digital Product Passport central registry went live 2026-07-19, but no product-specific
delegated act is in force yet, and iron & steel is the first product group targeted
(obligations expected ~2028-2030). That argues for building the honest screening estimate
now and the passport export never — until a delegated act actually specifies it.

Licensing is the trap and dictates the design. EC3's API forbids commercial use and
caching on the free tier and charges $5,000–$50,000/year otherwise; the ICE database
prohibits non-educational use after 2026-09-30. Both are therefore excluded as bundled
data. The clean path: the openEPD schema is Apache-2.0
(https://github.com/cchangelabs/openepd), and Ökobaudat's federal generic datasets are
free with a public API and citable dataset UUIDs
(https://www.oekobaudat.de/en/guidance/data-providers.html).

## What Changes

- New capability spec `sustainability-screening`: a per-part cradle-to-gate estimate from
  material mass × cited factor plus process and scrap contributions; every factor carries
  provenance and an uncertainty band; openEPD documents can be imported to replace a
  generic factor with a product-specific one; results are labeled a partial,
  cradle-to-gate screening figure in ISO 14067 language and never called a product
  footprint; and the estimate may participate as a Pareto objective alongside mass and
  cost.

## Impact

- Affected specs: new `sustainability-screening`. Interacts with `cost-estimation`
  (parallel screening-grade estimate, same rendering doctrine), `standards-data`
  (factor tables with provenance), and `add-uncertainty-margins` (bands) — none change.
- Affected code (when implemented): a small curated factor table with source UUIDs, an
  openEPD importer, and an estimator composing mass properties.
- Explicitly out: bundling EC3 or ICE data; full LCA beyond cradle-to-gate; use-phase and
  end-of-life modules; and any Digital Product Passport export until a delegated act
  defines one.
