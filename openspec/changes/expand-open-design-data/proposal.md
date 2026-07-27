# Change: Expand open design data — allowables, fatigue, sections, published dataset

## Why

Research surfaced four concrete, license-clean data upgrades:

- **MIL-HDBK-5J** (public domain, distribution unlimited —
  https://archive.org/details/milhdbk-5-j) carries statistically based A/B-basis design
  allowables, fatigue, and joint bearing data for aerospace alloys: the single biggest
  data-quality jump available at zero licensing risk, upgrading Anvilate from
  typical-value properties to design-allowable-grade data with table citations.
- **Open fatigue data**: NIMS MatNavi's registration-gated but free S-N/creep sheets
  (https://mits.nims.go.jp/) fit the existing fetch-on-first-use rule; 2025 CC-licensed
  research datasets (welded-joint S-N, https://www.nature.com/articles/s41597-025-06067-5)
  give DOI-cited curves for the existing fatigue and weld modules.
- **Named steel sections**: the free AISC Shapes DB v16.0 xlsx (fetch-on-first-use, never
  bundled) and open Eurocode profile data (EN 10365 dimensions via eurocodepy-class
  sources) close the loop from "W12x26" to properties to the already-built AISC-cited
  checks.
- **The dataset as a product**: no community-governed "KiCad library for mechanical
  dimensions" exists; publishing Anvilate's citation-tagged tables as a standalone
  versioned dataset creates ecosystem gravity.

## What Changes

- `standards-data` gains four requirements: an allowables-basis distinction in the
  materials schema with a MIL-HDBK-5J-seeded design-allowables pack; fatigue-data
  ingestion (fetch-on-first-use NIMS importer, CC-licensed dataset packs with DOI
  provenance); named-section resolution via importers (AISC fetch-on-first-use, open EN
  profile data bundled); and publication of the bundled tables as a standalone versioned
  open dataset.

## Impact

- Affected specs: `standards-data` (4 added requirements).
- Affected code (when implemented): materials schema extension (basis field), importers,
  dataset publishing pipeline; existing fetch-on-first-use and provenance mechanisms are
  reused, not changed.
