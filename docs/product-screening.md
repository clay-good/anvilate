# Product screening

**Checks only a whole product has.** `product_screening(product, library=..., root=...)`
places a product and reports what no single part can: what it weighs and where, what it is
predicted to weigh, how far it can tilt, how close its items come, and how it can move.

```yaml
screening:
  mass_growth: {estimated: 0.15, calculated: 0.05, source: program mass-growth policy}
  max_mass: {value: {magnitude: 40, unit: kg}, source: two-person lift}
  min_tilt: {value: {magnitude: 8, unit: degree}, source: transport spec}
  min_clearance: {value: {magnitude: 2, unit: mm}, source: service access}
```

| Check | Method | Reads |
| --- | --- | --- |
| mass properties | per product node: mass, centre of mass, and inertia about it by the parallel-axis theorem, each body uniform over its own solid | each body's mass and solid |
| mass growth | basic mass by maturity, plus the declared allowance for each: predicted mass | `mass_growth` |
| product mass | predicted mass against the limit | `max_mass` |
| tip-over | the tilt at which the centre of mass leaves the footprint (the plan rectangle of the bodies resting lowest), atan(inside ÷ height), about its nearest edge | `min_tilt` |
| clearance | the least gap between every two items that share no mate or connection, and where it is | `min_clearance` |
| mobility | Grübler–Kutzbach, M = 6(n − 1 − j) + Σf, over bodies joined rigidly into links | declared joints |

Each body's mass states its basis and maturity:

| Body | Basis | Maturity |
| --- | --- | --- |
| a catalog part | computed from its geometry and density | calculated |
| a purchased component | declared by its record | measured |
| a placeholder | a placeholder's estimate | estimated |

A body with no mass leaves every node above it unweighed, naming it, and the mass check not
evaluated. Every figure resting on a placeholder names it as provisional.

The mobility count is never taken as proof a product cannot move. It is flagged when it is
zero or negative, and for any two joint axes that are parallel or coincident: a lid on three
coaxial hinges counts −9 and moves. Mates between two items that a declared joint joins are
read as part of that joint, not as welding them.

Not yet built: the load path to ground and part screens fed interface loads, cost roll-up,
cross-item tolerance chains, thermal mismatch, swept clearance over joint ranges, the
budget mechanism for mass and CG limits, and assembly economy.
