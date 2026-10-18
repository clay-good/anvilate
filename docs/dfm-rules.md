# DFM rules

**The built solid read the way a shop quoting it would.** Each rule measures the part and
compares the measurement with a threshold in a process profile. No solver is involved.

```python
from anvilate.dfm import DfmProcess, default_profile, screen_dfm

profile = default_profile(DfmProcess.CNC_MILLING).override(
    "internal_radius_min", 4.0, source="shop standard MS-12: smallest pocket tool Ø8"
)
for entry in screen_dfm(built, profile, tool_direction=(0, 0, 1)):
    print(entry)
```

## The rules

| Process | Rule | Measured on the solid | Practice default |
| --- | --- | --- | --- |
| CNC milling | `internal_radius_min` | Every concave fillet about the tool axis, and every sharp concave edge along it (radius 0) | 1 mm |
| CNC milling | `hole_depth_ratio_max` | Each drilled feature's depth over its diameter | 10 |
| Sheet metal | `bend_radius_ratio_min` | Inside bend radius over thickness | 1 |
| Sheet metal | `hole_to_bend_min` | A hole's edge to the nearest bend line, in thicknesses | 2.5 |
| Sheet metal | `hole_to_edge_min` | A hole's edge to the blank's edge, in thicknesses | 2 |
| Sheet metal | `flange_length_min` | Each flange's length over thickness | 4 |
| Injection molding | `draft_min` | Each face's angle to the pull: planar faces, and cylinders about the pull | 1° |
| Injection molding | `wall_ratio_max` | The thickest declared wall over the thinnest | 2 |
| Die casting | `draft_min` | As for molding | 1° |
| Die casting | `wall_ratio_max` | As for molding | 2 |
| Additive | `overhang_min` | Each down-facing planar face's angle above horizontal, off the build plate | 45° |

The corner rule judges only corners along the tool axis. Where a wall meets the floor that
a flat end mill cuts, the corner is sharp by design and needs no cutter radius. A sharp
inside edge is found by probing beside it: for an edge between faces with outward normals
n₁ and n₂, the point m + ε(n₁ − n₂) lies inside the material only when the edge is concave.

## Where the thresholds come from

Every bundled threshold is a **practice default**: a common shop figure, not a clause of a
standard. Every finding says so. A shop loads its own figures with
`profile.override(rule, value, source=...)`, and each finding then names that source.
Thresholds from licensed handbooks are never bundled. You enter them yourself, with their
citation.

## What a finding carries

Each rule gives one scorecard entry for the part. It names the faces, edges or features
beyond the limit, and compares the worst measurement with the limit. A bend radius that is
too tight also says the `inside_radius` that meets the limit. The screen reads a built
solid, so it does not yet emit a typed repair hint into the part's spec. These findings are manufacturability
findings. They sit beside the physics verdicts and change none of them.

The wall ratio reads the walls the part declares. A wall-thickness map measured on the solid
is not built yet, and neither are turning, weldments, undercuts, rib and boss proportions,
curved down-facing faces, or cost estimates.
