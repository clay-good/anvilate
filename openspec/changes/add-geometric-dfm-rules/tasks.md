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
      (the **single-side warning** ships: a face-to-face mate carrying one fillet weld is
      welded from one side and pulls towards it, and a mate carrying two is balanced, which
      is the one thing about weld distortion a combination's declaration decides on its
      own. It states no magnitude — the size of the pull depends on the process, the heat
      input and the restraint, none of which the document says — so it names the joints and
      stops. Groove and plug welds are excluded, with the reason. It declares the
      catalogued mode `a weldment that comes out of the fixture bent`, which applies to a
      welded connection whose build is also declared, cited to TWI's Job Knowledge page on
      distortion.
      **Torch access is not built**: a weld's location is its mate's, so the geometry is
      reachable, but the approach model — the angle a torch comes in at and the clearance
      its nozzle needs — is a shop convention this change would have to choose, and a
      chosen convention is not a practice DEFAULT of the kind `dfm._PRACTICE` labels. It
      needs a source or an owner's call)

## 3. Reporting

- [x] 3.1 Findings with tag, value, limit, lever; repair-loop hint form
- [x] 3.2 Manufacturability filter on the scorecard; physics verdicts unaffected

## 4. Cost

- [ ] 4.1 Sheet metal, injection molding (tooling and piece), die casting estimates
- [ ] 4.2 Cost delta shown when a DFM repair changes tooling
- [x] 4.3 A docs page for DFM rules: each rule, its source, how to load a shop profile
