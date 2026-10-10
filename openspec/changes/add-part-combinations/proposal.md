# Change: Part combinations — a bracket with its bolts, a shaft with its key and gear, seen together

## Why

Parts are designed to meet other parts. Once single parts draw (`expand-drawable-parts`),
the next thing an engineer asks their agent is "show me that bracket on the motor with the
bolts in" or "put the gear and bearings on that shaft". Most real mistakes live at those
meetings: a hole pattern that does not match, a bolt too short, a key that fouls a shoulder.

The `assembly-robotics` spec already requires typed joints, interference detection and
structured STEP assembly export. None of that is reachable from drawn parts today, and it
asks for more than a quick look needs. This change adds the small layer that makes
combinations useful first: place parts by the features they share, add standard hardware
as envelopes, check that the meeting works, and show one picture and one assembly STEP.

Single parts first, then combinations: every part in a combination is a catalog part that
already builds, screens and exports on its own.

## What Changes

| Area | Change |
| --- | --- |
| Placement by feature | A combination names two tagged features and a mate (face to face, hole pattern to hole pattern, shaft in bore, edge flush). Positions are computed, never typed in as coordinates. |
| Standard hardware | Bolts, nuts, washers, pins and keys from the bundled standards data, drawn as envelopes and placed in the holes they fill. |
| Mating checks | Hole patterns must match in count, pitch and size; a shaft and bore report their fit; bolt length must reach; parts must not interfere. Each mismatch is a named failure. |
| Ready-made combinations | Bolted bracket on a plate, flange pair with bolts, shaft with key, gear, bearings and collar, lug welded to a plate, frame of members. Each is a short document, not new geometry code. |
| One picture | The combination renders with each part in its own tone, numbered, with a parts list beside it. |
| One file | STEP assembly with named components and transforms, and a bill of materials. |

## Impact

- Affected specs: `assembly-robotics` (ADDED), `drawing-generation` (ADDED).
- Depends on: `expand-drawable-parts` (the parts and tagged features being placed).
- Affected code (when implemented): placement solver over tagged features, hardware
  envelopes from `anvilate.standards`, assembly render, STEP assembly writer, MCP tools.
- Explicitly out: motion, joint limits and kinematics; URDF/MJCF (already specified
  separately); weld bead geometry (a weld is a declared joint with a symbol, not a
  modelled bead); routing of cables and pipes; any constraint solving beyond mating two
  features at a time; editing an assembly interactively.
