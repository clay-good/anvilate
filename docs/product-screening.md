# Product screening

**Checks only a whole product has.** `product_screening(product, library=..., root=...)`
places a product and reports what no single part can: what it weighs and where, what it is
predicted to weigh, how far it can tilt, how close its items come, and how it can move.

```yaml
screening:
  mass_growth: {estimated: 0.15, calculated: 0.05, source: program mass-growth policy}
  max_mass: {value: {magnitude: 40, unit: kg}, source: two-person lift}
  max_cg_height: {value: {magnitude: 600, unit: mm}, source: transport spec}
  min_tilt: {value: {magnitude: 8, unit: degree}, source: transport spec}
  min_clearance: {value: {magnitude: 2, unit: mm}, source: service access}
```

| Check | Method | Reads | Cites |
| --- | --- | --- | --- |
| mass properties | per product node: mass, centre of mass, and inertia about it by the parallel-axis theorem, each body uniform over its own solid | each body's mass and solid | no limit; the parallel-axis theorem, each body's basis and maturity per contribution |
| mass growth | basic mass by maturity, plus the declared allowance for each: predicted mass | `mass_growth` | `mass_growth.source`, ledgered as growth |
| product mass | a [budget](performance-budgets.md) whose terms are the bodies, summed worst case, each grown by its maturity's allowance: predicted mass against the limit, naming the governing body | `max_mass` | `max_mass.source` |
| centre-of-mass height | the centre of mass's height above the product's lowest point against the limit | `max_cg_height` | `max_cg_height.source` |
| tip-over | the tilt at which the centre of mass leaves the footprint (the plan rectangle of the bodies resting lowest), atan(inside ÷ height), about its nearest edge | `min_tilt` | `min_tilt.source` |
| clearance | the least gap between every two items that share no mate or connection, and where it is; and over each joint's range, the least gap its moving item comes to ([interfaces](interfaces.md#joints)) | `min_clearance` | `min_clearance.source` |
| load path | each body's load (declared loads and its own weight) carried down to the bodies it rests on, and from the lowest to the floor, by ΣFz, ΣMx and ΣMy at each body | `loads`, `splits`, `vertical_acceleration` | no limit (a support that would have to pull fails); a declared split's `basis` and `vertical_acceleration.source` in the detail |
| caster load | each caster's rating against the load the path brings it, naming the load-path entry it reads | a `caster` component's `load_rating` | the caster record's rating `source`, and the load-path entry it reads |
| thermal mismatch | for each connection between two catalog parts of different materials, \|α₁ − α₂\| · ΔT · span, the span between the outermost mated holes or across where they meet, against the declared slip, citing both coefficients | `thermal` | `thermal.source` for the range and slip, and each coefficient's `source` in the detail |
| stack-up chains | a 1D chain through items and connections, worst-case and root-sum-square, and a seeded Monte Carlo run when declared; judged on the worst case, with each link's share and the governing link | `chains` | each link's `source`, and ISO 2768-1 for a link with no declared tolerance; the required band declares no source yet |
| material needs | each declared need against the attribute each item's material declares, citing both; see [material compliance](material-compliance.md) | `materials`, `needs` | each need's and each material attribute's source; see [material compliance](material-compliance.md) |
| mobility | Grübler–Kutzbach, M = 6(n − 1 − j) + Σf, over bodies joined rigidly into links | declared joints | no limit; the Grübler–Kutzbach count, with its caveats |

An entry held to a declared limit carries that limit's source as its reference, so the card
names what each verdict was held against. The methods are rigid-body statics and mass
properties, which cite no clause; the citation is the user's.

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

A declared `vertical_acceleration`, gravity included and acting down, is what the path is
carried at: each body's weight and each load given as a mass are m·a rather than m·g, and a
load given as a force is carried as stated. At `{magnitude: 2, unit: g0}` the cart's 63 kg
puts twice its at-rest load on each caster, and a 100 N hand on the plate adds
100 N, not 200.

```yaml
vertical_acceleration: {value: {magnitude: 2, unit: g0}, source: transport shock}
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

`report.costs` is a screening cost for each product node, rolled up from the unit prices of
the items under it: a made part's or placeholder's `price`, and a component record's. A
price is the user's, with its source and date:

```yaml
price: {amount: 8.5, currency: USD, source: quote Q-118, date: 2026-09-01}
```

A node is `complete` only when every item under it is priced in one currency. An item with
no price is named in `unpriced`, and the node's `priced_total` is then the sum of the priced
items, labeled incomplete, never the node's cost. Prices in more than one currency are not
summed, since nothing here converts them; the currencies are listed and there is no total.
A cart whose frame costs 120.00, whose plate costs 15.00, and whose three casters cost 8.50
each totals 160.50 over 5 items. Without the casters' price it is incomplete, at 135.00 for
the priced items, naming all three. A reference is not costed. `report.cost_lines` gives
each costed item's price, source and date.

Each body's mass states its basis and maturity:

| Body | Basis | Maturity |
| --- | --- | --- |
| a catalog part | computed from its geometry and density | calculated |
| a purchased component | declared by its record | measured |
| a placeholder | a placeholder's estimate | estimated |

`report.mass_budget` is that budget evaluated: each body's share and headroom (how much it
could grow, the rest held, before the limit is spent), and the growth allowances as
[margin-ledger](margin-ledger.md) entries rather than mass. The centre-of-mass height is a
weighted mean, not a sum, so it is a limit of its own and not a budget. A cart of a 2 kg
base and a 0.5 kg block against 3 kg leaves the base 2.5 kg of headroom and the block
1.0 kg; against 2.2 kg it fails, the base governing, and neither has headroom.

A body with no mass leaves every node above it unweighed, naming it, and the mass check not
evaluated. Every figure resting on a placeholder names it as provisional.

The mobility count is never taken as proof a product cannot move. It is flagged when it is
zero or negative, and for any two joint axes that are parallel or coincident: a lid on three
coaxial hinges counts −9 and moves. Mates between two items that a declared joint joins are
read as part of that joint, not as welding them.

Not yet built: lateral accelerations, loads on interfaces, side connections in the load path,
part screens other than a caster's fed their loads, and fastener and tool counts.
