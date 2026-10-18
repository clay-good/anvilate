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
| load path | each body's load (declared loads and its own weight) carried down to the bodies it rests on, and from the lowest to the floor, by ΣFz, ΣMx and ΣMy at each body | `loads`, `splits` |
| caster load | each caster's rating against the load the path brings it, naming the load-path entry it reads | a `caster` component's `load_rating` |
| thermal mismatch | for each connection between two catalog parts of different materials, \|α₁ − α₂\| · ΔT · span, the span between the outermost mated holes or across where they meet, against the declared slip, citing both coefficients | `thermal` |
| stack-up chains | a 1D chain through items and connections, worst-case and root-sum-square, and a seeded Monte Carlo run when declared; judged on the worst case, with each link's share and the governing link | `chains` |
| mobility | Grübler–Kutzbach, M = 6(n − 1 − j) + Σf, over bodies joined rigidly into links | declared joints |

A body rests on the bodies whose tops meet its bottom over a shared plan area, and the
lowest rest on the floor. One support, two with the load over the line between them, or
three not in a line determine the reactions. A support that would have to pull fails, as
lifting off. More than three supports leave the path indeterminate: the entry names them
and how many are redundant, nothing below is evaluated from a guessed share, and a declared
split, with its basis, divides it instead:

```yaml
splits:
  - {body: cart/frame, basis: measured at the four wheels, shares: {cart/caster1: 0.25, ...}}
```

Expansion coefficients are declared with their source, not looked up: the bundled
materials carry none. A dissimilar connection with no range, or a material with no declared
coefficient, is not evaluated, naming what is missing.

A chain link is a part's dimension, by item and tag, or a connection's ± allowance with its
source. A dimension the item declares no tolerance for takes the ISO 2768-1 general
tolerance of its process on the nominal the link states, and the entry says so.

`report.economy` is advisory and never changes the verdict: the part count, each bought
designation with how many are used, and merge candidates, pairs of made parts joined without
relative motion, of one material, neither listed in `serviced`.

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

Not yet built: accelerations and loads on interfaces, side connections in the load path,
part screens other than a caster's fed their loads, cost roll-up, swept clearance over joint
ranges, the budget mechanism for mass and CG limits, and
fastener and tool counts.
