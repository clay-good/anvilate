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
| CNC turning | `slenderness_max` | The length along the spindle over the largest diameter across it, for a part held at one end; the spindle lies along x, y or z | 4 |
| Sheet metal | `bend_radius_ratio_min` | Inside bend radius over thickness | 1 |
| Sheet metal | `hole_to_bend_min` | A hole's edge to the nearest bend line less the inside radius, in thicknesses: the edge needs that many thicknesses plus the radius | 2.5 |
| Sheet metal | `hole_to_edge_min` | A hole's edge to the blank's edge, in thicknesses | 2 |
| Sheet metal | `flange_length_min` | Each flange's length over thickness | 4 |
| Injection molding | `draft_min` | Each face's angle to the pull: planar faces, and cylinders about the pull | 1° |
| Injection molding | `wall_ratio_max` | The thickest wall over the thinnest: the declared walls, or, where fewer than two are declared, the walls measured on the solid | 2 |
| Injection molding | `rib_ratio_max` | The declared rib over the declared wall it stands on, so it does not sink | 0.6 |
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

A card holding both kinds is read apart with `card.manufacturability()` and
`card.physics()`. A manufacturability finding is an entry that addresses a failure mode the
[catalogue](failure-mode-coverage.md) says is normally found in production: a feature the
shop cannot make as drawn, a fastener no tool reaches, an adjustment sealed away, a
tolerance nobody can measure. Every other entry is physics, and keeps its verdict.

A rule that cannot read its property off the part is not evaluated, naming what is missing,
rather than passed: a wall ratio on a part that declares fewer than two walls and has no
planar face to measure one under, or a rib with no wall for it to stand on. A part with nothing of the kind to judge, such as no holes, passes
and says there was nothing to judge.

The wall ratio reads the walls the part declares, and where it declares fewer than two, the
walls measured on the solid. Under each planar face, a ray inward gives the depth of
material, and twice the distance from the ray's midpoint to the nearest face bounds it from
the side, so a rim measures its width and not its height. A 40 × 40 × 10 tray with 2 mm
walls on one axis, 5 mm on the other and a 4 mm floor measures 5 over 2, a ratio of 2.5.
Curved faces are not sampled.

Not built yet: a turned part's sections judged on their own, weldments, undercuts, boss
proportions, curved down-facing faces, and cost estimates.
