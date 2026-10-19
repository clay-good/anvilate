# Tasks: Geometric DFM rules

## 1. Measurement

- [x] 1.1 Measurements over the tagged B-Rep: internal radius, hole depth ratio, wall
      thickness map, draft per face against a pull direction, overhang per face against a
      build direction, feature-to-bend and feature-to-edge distance
- [x] 1.2 Process profile schema: thresholds with source or practice-default label;
      user overrides with source

## 2. Rule packs

- [x] 2.1 CNC milling and turning
      (milling: internal corner radius, hole depth ratio; turning: slenderness)
- [x] 2.2 Sheet metal
      (bend radius, hole-to-bend with the inside radius, hole-to-edge, flange length)
- [x] 2.3 Injection molding
      (draft, wall ratio, rib ratio; undercuts are not detected yet)
- [x] 2.4 Die casting
      (draft and wall ratio)
- [x] 2.5 Additive: material extrusion, powder bed fusion
      (extrusion: overhang and wall; powder bed fusion: wall)
- [ ] 2.6 Weldments: torch access, single-side distortion warning

## 3. Reporting

- [x] 3.1 Findings with tag, value, limit, lever; repair-loop hint form
- [x] 3.2 Manufacturability filter on the scorecard; physics verdicts unaffected

## 4. Cost

- [ ] 4.1 Sheet metal, injection molding (tooling and piece), die casting estimates
- [ ] 4.2 Cost delta shown when a DFM repair changes tooling
- [x] 4.3 A docs page for DFM rules: each rule, its source, how to load a shop profile
