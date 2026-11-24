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
| caster load, guide load | each caster's and each linear guide's rating against the load the path brings it, normal to the face it rests on, naming the load-path entry it reads; a bearing is not fed, since radial or axial depends on an axis its record does not state | a `caster`'s `load_rating`, a `linear_guide`'s `dynamic_load_rating` | the record's rating `source`, and the load-path entry it reads |
| thermal mismatch | for each connection between two catalog parts of different materials, \|α₁ − α₂\| · ΔT · span, the span between the outermost mated holes or across where they meet, against the declared slip, citing both coefficients | `thermal` | `thermal.source` for the range and slip, and each coefficient's `source` in the detail |
| stack-up chains | a 1D chain through items and connections, worst-case and root-sum-square, and a seeded Monte Carlo run when declared; judged on the worst case, with each link's share and the governing link | `chains` | the band's `source`, each link's `source`, and ISO 2768-1 for a link with no declared tolerance; a band with no source says so |
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

**A split can be a solve rather than a guess.** Four legs under a skid is four supports,
and four is more than three, so the refusal above is where the work stops for every real
frame. Declare a frame over the product's connections (see
[frame analysis](frame-analysis.md)), solve it, and `frame_split` turns its reactions into
the split:

```python
from anvilate.frame import solve_frame
from anvilate.product_screening import frame_split

split = frame_split(
    body="skid/deck",
    solution=solve_frame(frame),
    supports={"skid/leg_a": "fa", "skid/leg_b": "fb", "skid/leg_c": "fc", "skid/leg_d": "fd"},
    placeholders=("leg_d",),      # members whose stiffness is an assumption
)
```

The shares are the vertical reactions, normalised. A load biased to one corner of a
four-legged skid puts **39.8%** into that leg and about a fifth into each of the others —
the figure statics on four supports cannot give, and the one the leg is sized on. Three
things are refused rather than returned: a node the frame does not support, a leg the
solve puts into **uplift** (a share of a load it does not carry would read as a load path
it is not on), and a split naming fewer than two supports, which the load path works out
for itself.

The `basis` names the frame, the analysis it was, how well the solve closed, and any
member resting on a placeholder's assumed stiffness. **That basis is printed on every
entry below the split**, not only on the body it divided: a reader following a number
down to a caster meets the assumption at each step rather than once at the top, where it
is easy to read as applying only there.

### Where a load arrives

A load names **one item** or **one interface**, and they are not the same place:

```yaml
loads:
- {item: frame, mass: {magnitude: 50, unit: kg}, source: payload spec}   # at the middle
- {at: frame.pad, mass: {magnitude: 50, unit: kg}, source: payload spec} # where the pad is
```

A load on an item acts at the middle of the item, which is the honest reading when all the
declaration says is which item carries it. A load `at` an `item.interface` acts where that
interface is — at the centre of the face it is on, which is off to one side of the item —
and an axis-located interface puts it on that axis. That offset is not cosmetic: the load
path is a moment calculation, so the same 50 kg at a 600 mm frame's left face and at its
right face put different shares on the casters underneath, and one of the two can be the
difference between a caster inside its rating and one over it.

The interface is resolved when the document is parsed, so a load at an interface nothing
offers is refused by name before any path is solved. Each body's entry then says what
arrived on it directly and where from — `of which 490.3 N as the load at frame.pad
(payload spec)` — so a reader following a number down meets the declaration that put it
there rather than only a total.

A declared `vertical_acceleration`, gravity included and acting down, is what the path is
carried at: each body's weight and each load given as a mass are m·a rather than m·g, and a
load given as a force is carried as stated. At `{magnitude: 2, unit: g0}` the cart's 63 kg
puts twice its at-rest load on each caster, and a 100 N hand on the plate adds
100 N, not 200.

```yaml
vertical_acceleration: {value: {magnitude: 2, unit: g0}, source: transport shock}
```

**A lateral acceleration is a different thing, and it is the one that tips the product
over.** It does not scale weights; it makes a horizontal force at each body's centre of
mass, and the moment of that force **moves the point each body's vertical load acts at**.
The existing check — a load acting outside what the body rests on fails, as lifting off —
then does the rest.

```yaml
lateral_acceleration: {value: {magnitude: 0.3, unit: g0}, direction: [1, 0], source: transport shock}
```

The direction is declared, because nothing else says which way the product goes. A load
given as a **mass** is accelerated sideways; one given as a **force** is a force, and no
direction is invented for it. Each entry names the sideways force, its source, and how
far it moved the point.

**The slender part goes first, by an order of magnitude.** On the worked cart — a 600 x
400 frame on three casters, carrying a 50 kg payload — a caster is 60 mm across and
100 mm tall, so the sideways force arriving at its top has the whole of that height as a
lever and walks its own load outside its own footprint at **0.30 g**. The cart on its
three casters does not tip until **2.99 g**. A check on the product as a whole would have
reported it standing up through ten times the acceleration that lays a wheel over.

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

## Where these checks come out

`anvilate check <product>.yaml` prints the item tree first and then **the product as a
whole** — every check on this page — and its exit code is the worse of the two. Over MCP,
`build_combination` given a product returns the tree as `product`, these checks as
`whole_product`, and the `next` steps and `journey` stage read from both together. In
Python it is `product_screening(product)`, beside `place_product` for the item tree.

Both halves are needed, and reading one alone says the wrong thing. An item whose own
checks pass can sit under a product whose mass budget does not. And the other way round: an
item is screened when the product is **placed**, before any load path exists, so a caster
whose rating reads a load reports that the product states no load for it — while the load
path, run afterwards, derives that load and can fail the same caster on it. Where the two
meet, the whole-product verdict wins, because it is the one computed with the load;
`load_path_supersedes(placed, screening)` names those checks, the command line says how
many it dropped and which, and the JSON carries them as `superseded`.

### A bearing's load is radial or axial by how it is mounted

A caster and a linear guide take the path's load in the direction they are rated for: the
load goes down through the contact they rest on. A rolling bearing does not. The same
vertical force is ordinary radial duty on a horizontal shaft and a **thrust** on a vertical
one, and a bearing is often not built for the second. Nothing infers which: an envelope is
a box, and a box has no axis.

```yaml
mountings:
- {item: bearing, axis: x, source: the assembly drawing, sheet 2}
```

| What the product says | What the bearing's rating gets |
| --- | --- |
| nothing | not evaluated, naming `screening.mountings` — the force could be either duty |
| `axis: x` or `axis: y` | the path's load as its **equivalent load**, sourced to the path entry and the mounting |
| `axis: z` | not evaluated: the load arrives along the bearing's own axis, and an equivalent load combining a thrust with this bearing's X and Y factors is not derived here |

Being fed the load is not the same as having a verdict. A rating life also needs the speed
the bearing turns at and the life it must reach, and where the product has not said so the
entry asks for those — which is the difference from before, when it said only that the
product stated no load. A bearing on a declared drive train gets all three already, from
the flow and the required output's life.

Not yet built: side connections in the load path, catalog parts' own screens fed their
loads, and fastener and tool counts.
