# Change: Context intake — the agent reads the folder, Anvilate reads the CAD files and keeps the receipts

## Why

The common setup is now an engineer pointing their agent at a folder: last year's STEP
models, DXF profiles, a datasheet PDF, photos of a whiteboard sketch, a scanned drawing.
The agent reads all of it and proposes a part. Anvilate still works in that setup, because
the agent writes the spec and Anvilate checks and builds it. But two things are missing.

- **The agent cannot read CAD files reliably.** A STEP or DXF file is thousands of lines
  of coordinates. An agent that "reads" one is guessing. Anvilate has the kernel to
  measure them exactly, and today exposes it only for mating interfaces, from the CLI.
- **A number the agent read off a picture looks the same as one the engineer stated.**
  The spec records where each value came from, but has no way to say "the agent read
  80 mm off `sketch.png`, and nobody has confirmed it".

The division of labour is the design. The agent reads prose, pictures and PDFs, which it
is good at and which Anvilate will not do. Anvilate reads CAD files deterministically,
records the source of every value, and holds a value read from a picture as a draft until
a person confirms it. The existing rule that no general vision model may be the sole
extractor of a dimension was written before the agent was the reader; it is replaced by a
rule that fits: the agent may propose, the file is cited, a person confirms.

## What Changes

| Area | Change |
| --- | --- |
| Folder inventory | One call lists a folder's engineering files with what Anvilate can read from each and what is the agent's to read. |
| Read a STEP part | Solids, names, units as written and as read, overall size, volume and mass, planar faces, cylinders and hole patterns, and assembly structure, as typed facts. |
| Read a DXF | The declared unit or a refusal to guess one, layers, closed profiles with their size, holes, and dimension entities with any text override flagged. |
| Read meshes | STL and 3MF give size and volume only, labelled as a mesh, never as design geometry. |
| Formats it will not read | DWG, IGES, Parasolid and native CAD files are refused with the one step that fixes it: export STEP or DXF from the CAD. |
| Values carry their source | A spec value can record the file it came from, where in the file, who read it (Anvilate measured, or the agent read), and whether a person has confirmed it. |
| Drafts are not load-bearing | An unconfirmed agent-read value is used to draw and screen, and the result is marked as resting on it and cannot export as validated. |
| Start a part from a file | A measured profile or part can seed a catalog pattern's parameters ("a mounting plate like this DXF"). |
| Confined | The server reads only inside folders named when it starts. Nothing read leaves the machine by Anvilate's doing. |

## Impact

- Affected specs: `input-ingestion` (ADDED, MODIFIED), `spec-ir` (ADDED),
  `headless-automation` (ADDED).
- Affected code (when implemented): STEP reader over the extended (XDE) data, DXF reader
  on ezdxf, provenance kinds, export gate, MCP tools and `--context` roots.
- Complements `expand-drawable-parts` (a read profile seeds a pattern) and
  `add-part-combinations` (a read part can be a mating part).
- Explicitly out: Anvilate parsing images, scans or prose; OCR; PMI and GD&T read from
  STEP; converting DWG (a user-installed converter is the user's step); reverse-engineering
  a mesh into a solid; feature recognition beyond planes, cylinders and hole patterns.
