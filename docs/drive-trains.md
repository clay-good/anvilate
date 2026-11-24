# Drive trains

**One input, and every shaft's speed and torque follow from it.** A gearbox screened mesh by
mesh runs each on a torque somebody typed. Those torques are not free: the input power and
speed and the tooth counts decide all of them. A drive train declares the machine, and
`derive_flow` derives the rest.

```python
from anvilate.drivetrain import (DriveInput, DriveShaft, DriveTrain, Gear, Mesh,
                                 RequiredOutput, derive_flow, screen_output_speed)

train = DriveTrain(
    shafts=(DriveShaft(name="input", carries=("gear 2",)),
            DriveShaft(name="countershaft", carries=("gear 3", "gear 4")),
            DriveShaft(name="output", carries=("gear 5",))),
    gears=(Gear(item="gear 2", teeth=16, pitch_diameter=q("2.6667 in")), ...),
    meshes=(Mesh(name="2-3", driver="gear 2", driven="gear 3", efficiency=1.0,
                 source="lossless, as the case study"), ...),
    input=DriveInput(shaft="input", speed=q("1750 rpm"), power=q("20 hp")),
    output=RequiredOutput(shaft="output", speed_low=q("82 rpm"), speed_high=q("88 rpm"),
                          source="the reducer's specification"),
    reverted=True,
)
flow = derive_flow(train)          # every shaft's speed, torque and power; each mesh's loads
screen_output_speed(train, flow)          # the output speed against its band, as a card entry
```

| What is derived | How |
| --- | --- |
| a driven shaft's speed | the driver's speed times the driver's teeth over the driven gear's |
| its power | the driver's power times the mesh's declared efficiency, which cites its source; a lossless analysis declares 1.0 and says so |
| its torque | power over speed |
| a mesh's pitch-line velocity and tangential load | from the driver's speed and torque and its declared pitch diameter |
| its radial and total load | the tangential load times the tangent, and over the cosine, of the mesh's declared pressure angle; with no angle declared there is no split, since 14.5, 20 and 25 degrees all ship |

| Refused, naming what to correct | Why |
| --- | --- |
| a gear no shaft carries, or two shafts carrying one gear | a gear sits on exactly one shaft |
| a shaft two paths turn at different speeds | a shaft's speed is determined once |
| a shaft nothing drives from the input | an undriven shaft has no load to screen |
| a center distance that is not the sum of the pitch radii | the gears would not mesh where they are drawn |
| a reverted layout whose stages differ (175 mm and 180 mm) | a reverted layout shares one center distance |
| a torque typed on a mesh that the flow contradicts (`check_typed_torque`) | inside a declared train the torque is the flow's |

It is held to the power-transmission case study of Shigley's *Mechanical Engineering
Design*, 10th edition (Budynas and Nisbett), Chapter 18: 20 hp at 1,750 rpm through 16/72
and 16/72 at 6 teeth/in gives 388.9 and 86.42 rpm, torques of 60.0, 270 and 1,215 lbf·ft,
and tangential loads of 540.2 and 2,431 lbf. The chapter prints 540.0 for the first, from
the pitch diameter rounded to 2.67 in; the library takes the exact 16/6 in.

**And the whole chain, on the chapter's own layout.** Its Fig. 18-2 dimensions the
intermediate shaft, which puts bearing A at 0.75 in, gear 3 at 2.75, gear 4 at 8.50 and
bearing B at 10.75; Section 18-9 then prints what those two bearings carry. Flow, mesh
split, two-bearing statics and bearing demand together land on it:

| Section 18-9 prints | This library derives |
| --- | --- |
| RA = 375 lbf (RAz = 115.0, RAy = 356.7) | 374.4 lbf (114.8, 356.4) |
| RB = 1918 lbf (RBz = 1776.0, RBy = 725.3) | 1918.3 lbf (1776.0, 725.0) |
| LD = (12 000 h)(60 min/h)(389 rev/min) = 2.8e8 rev | 2.80e8 rev, from the declared life and the derived 388.9 rpm |
| "the bending moment is largest at gear 4" | the peak station is gear 4 |

Two parts in a thousand, and no tighter, because the chapter's own inputs are rounded: RAz
is the difference between 1,891 and 1,776 lbf, so the rounding in its printed 540.0 arrives
at A magnified about fifteen times. RB, which is not a difference of near-equals, lands
within two parts in a hundred thousand. The chapter's force analysis and deflection check
are in its Chapter 7 and are not quotable from the free chapter.

The two bearings differ by a factor of five because the two planes are not interchangeable:
the two radial loads act the same way and add, while the two tangential loads oppose and the
bearings carry only their difference. That is what the declared `line_of_centers` of 0 and
180 degrees means, and the test holds both plane equilibria rather than the resultants alone.

## A product declares its drive train

A product document carries the machine it is, over the items it already has, at schema
1.17.0:

```yaml
anvilate_product: 1.17.0
drive_train:
  shafts:
  - name: fast                 # an instance of this product
    carries: [pinion]          # so is every item a shaft carries
    supports: [{name: A, at: {magnitude: 0, unit: mm}}, ...]
    stations: [{item: pinion, at: {magnitude: 100, unit: mm}}]
    stiffness: {diameter: ..., elastic_modulus: ..., source: AISI 1045, Shigley Table A-5}
  gears: [{item: pinion, teeth: 18, pitch_diameter: ...}, ...]
  meshes: [{name: pinion-wheel, driver: pinion, driven: wheel, efficiency: 1.0, source: ...}]
  input: {shaft: fast, speed: {magnitude: 1500, unit: rpm}, power: ...}
  output: {shaft: slow, speed_low: ..., speed_high: ..., source: ...}
```

Every shaft and gear the train names is an instance of the product, by the same names its
stack-up chains and its material needs use. **The flow is derived at parse**, so a train no
input drives, whose shaft speeds two paths disagree on, or whose centre distances do not
close is refused before anything is built — the point of declaring the machine is that it
cannot be built wrong, and a refusal that waited for the first screen to read it would
arrive after the geometry.

`product_screening` then puts the train's own checks on the product's card: the output speed
against its band, and the bending at each point of every shaft that declares two bearings
and a stiffness. A shaft that declares neither is not read for bending and nothing is
reported for it — that is the document's statement, not a gap the card fills in.

**Nothing is typed twice.** A part the train names is refused if it states a load the train
derives and the two disagree: a shaft's `torque` against the flow's, its `bending_moment`
against its own two-bearing statics, a mesh's `pinion_torque` against the flow's driver
torque. The remedy is not "leave it out" — a `transmission_shaft` requires its torque and
its bending moment, so the element has no state without them — so the refusal names the
derived value to write and the other way out, which is to take the item out of the train. A
part the train does not name is screened on what its own document states, as it always was.

## The mesh loads reach the bearings

A shaft that declares where its bearings and its gears sit is solved by statics:
`solve_shaft_statics` applies each mesh load where its gear sits, and returns the two bearing
reactions and the bending moment along the shaft.

```python
from anvilate.drivetrain import DriveShaft, ShaftStation, ShaftSupport, solve_shaft_statics

DriveShaft(name="output", carries=("gear 5",),
           supports=(ShaftSupport(name="E", at=q("0 mm")),
                     ShaftSupport(name="F", at=q("300 mm"))),
           stations=(ShaftStation(item="gear 5", at=q("150 mm"))))

statics = solve_shaft_statics(train, flow, "output")
statics.reaction("E").magnitude          # 5,754 N
statics.peak                             # gear 5 at 150 mm: 863.1 N·m bending
```

Each mesh pulls its gear two ways: the tangential load across the line joining the gear
centres, and the radial load along it, pushing the two gears apart. Where a shaft carries two
meshing gears those two loads do not act in one plane, so each mesh declares its
`line_of_centers` — the angle, about the shaft axis, of that line. A shaft carrying one
meshing gear needs no angle, because its line of centres may be taken as the reference plane.
The input shaft is taken to turn counter-clockwise seen along +x; the other sense flips every
tangential load together, which leaves every reaction and bending magnitude where it was.

| | |
| --- | --- |
| two supports | solved by equilibrium: `determinate` is true, and the bending moment is given at every bearing and station |
| three or more | refused, named as statically indeterminate, unless every support declares the `share` it takes and the `source` that share rests on |
| a declared split | the reactions are those shares; `basis` carries their sources, and `moments` is empty, because a split equilibrium did not give cannot be integrated into a bending moment diagram without the shaft's stiffness |
| two supports with shares declared | refused: equilibrium already answers, so a declared split would be a second source of truth |
| fewer than two supports, both at one position, a gear with no station, a mesh with no pressure angle | refused, each naming what to declare |

The case study's own bearing reactions are not reproduced here: its shaft layout belongs to
Example 7-2, outside the free chapter. The spans above are the library's test's own, and the
reactions are hand-derived from them.

## The derived loads reach the existing screens

The rolling-bearing screen already reads an `equivalent_load`, a `speed` and a
`required_life`. Two of those three are not free, and `bearing_demands` is where they come
from: the load is the reaction the statics derived, the speed is the one the flow derived,
and each `Demand` is sourced to the derivation it came from, so the bearing's rating-life
entry says where its numbers are from instead of resting on a number somebody typed.

```python
from anvilate.components import _rating_entries
from anvilate.drivetrain import bearing_demands

demands = bearing_demands(train, flow, "output")   # keyed by support name: E, F
(entry,) = _rating_entries(bearing_6210, demands["E"])
entry.life.value          # the ISO 281 L10 rating life, in hours
```

`required_life` is the train's declared output life (`RequiredOutput.life`). Where the train
declares none, the demand is left out and the bearing entry reports as not evaluated naming
it — the honest answer, because nothing in the train knows how long the product must run.
The equivalent load is the radial reaction alone: a helical train also loads its bearings
axially, and an equivalent load combining the two with X and Y factors before those axial
loads are derived would understate the demand, so it is not offered.

The shaft and key screens need no wrapper. The torque is `flow.shaft(name).torque` and the
bending moment is `statics.peak.magnitude`, and both are quantities the existing analysis
functions already take.

## How far each shaft bends, where it matters

A shaft that declares its `stiffness` — one diameter and a modulus, with their source — gets
its elastic curve read **where each bearing and each gear sits**, not at whichever point of
the shaft happens to sag most. Each mesh load goes onto the simply-supported prismatic beam
between the two bearings in each of the two planes, and the two are combined at every point.

```python
from anvilate.drivetrain import ShaftStiffness, screen_shaft_curve, solve_shaft_curve

curve = solve_shaft_curve(train, flow, "output")
curve.point("gear 5")      # gear 5 at 150 mm: 0.1019 mm, 0°
curve.point("E").slope     # what the bearing is asked to take
screen_shaft_curve(train, flow, "output")   # each point against the limit declared on it
```

No limit is supplied from this library. A tapered roller bearing and a self-aligning one
differ by two orders of magnitude in the slope they take, so a `slope_limit` or a
`deflection_limit` is declared on the support or station it applies to, with the
`limit_source` it rests on. A point that declares none is not screened and not reported; a
shaft where *no* point declares one gets a single not-evaluated entry naming the
declaration, because a shaft screened on nothing looks exactly like a shaft that passed.

Refused, naming what to correct: a shaft with no declared stiffness; a shaft whose reactions
came from a declared split rather than from equilibrium, since a split equilibrium did not
give does not carry a shape either; and a load outside the bearing span, because an overhung
shaft is the overhanging-beam case and this is not it. A stepped shaft bends on a diameter
that changes along it, and averaging the steps would report a deflection nothing has, so
`ShaftStiffness` takes one diameter and a stepped shaft waits.

## The gear data block

**A drawing view can dimension a gear's bore and face width and nothing about its teeth.**
Everything a gear is actually made or bought by — the module, the tooth count, the rack the
form follows, the accuracy it is cut to, the dimension it is inspected over — lives in a data
block beside the views. `gear_data` writes it from the train:

```python
from anvilate.drivetrain import gear_data

block = gear_data(train)
block.to_csv()      # the eighteen columns, as the release package's gear-data.csv
block.lines()       # field and value down the page, as the assembly sheet prints it
```

| Column | Where it comes from |
| --- | --- |
| item, shaft | the gear's item path, and the shaft the train says carries it |
| teeth | declared on the gear |
| module | derived: the pitch diameter over the tooth count |
| pitch diameter | declared on the gear |
| pressure angle | the mesh the gear runs in |
| profile shift | declared on the gear; a design choice, so it cites no source |
| basic rack, accuracy class | declared on the gear as a value **and** the standard it is to: `ISO 53:1998 profile A`, not a bare `A` |
| span measurement, over-pins measurement | declared on the gear; which one a shop measures depends on the gear and its tooling, so neither is derived from the other |
| mesh, role | the mesh, and whether this gear is its driver or its driven gear |
| mates with, mating teeth | the gear at the other end of that mesh, and its teeth |
| ratio | derived: the driver's teeth to the driven gear's |
| center distance | the mesh's own when it declares one, and the sum of the two pitch radii when it does not |
| center distance basis | which of those two the centre distance on this row is |

Nothing here is supplied from this library, and a field the gear does not declare reads
`not declared` rather than a blank: a blank cell reads as a value of nothing, and a basic
rack nobody declared is a number a gear shop would cut to. The worked reducer's gears are
bought as stock gears not yet chosen, so its block carries their teeth, module, pitch
diameter and pressure angle and says the rest is not declared.

One row per gear **per mesh**. A gear in two meshes — an idler — has one set of teeth and two
mating gears, and the mating gear, the ratio and the centre distance are the mesh's and not
the gear's, so neither row has to be read against the other to be understood.

Three things a block cannot state while the declaration contradicts itself, so each is
refused by `derive_flow` before the block is written:

| Refused | Why |
| --- | --- |
| a mesh whose two gears are cut to different modules (4.233 mm and 6.35 mm) | two gears in mesh are cut to one module, and the centre-distance check cannot see this: the sum of the two pitch radii closes whatever the modules are. Held to 1%, so a pitch diameter written to three figures is not a mismatch and the closest two stock modules — 3 and 3.25, 8% apart — still are |
| a gear two meshes give two pressure angles (20° and 25°) | the angle is the tooth form the gear was cut with; a train may carry a 20° stage and a 14.5° one, but not one gear in both |
| a gear no mesh names | a gear that meshes with nothing is not in the train, and has no mating gear to state |

There is no helix angle and no hand. The loads this module derives are a spur train's: a
declared helix angle would make an axial load `solve_shaft_statics` does not carry, and a
helical gear screened as a spur one is a wrong answer rather than a missing one.

## What the machine sweeps while it runs

A clearance that holds with the machine stopped can close the moment it runs. A shaft that
declares the `axis` it turns about — `x`, `y` or `z`, in the product's own coordinates —
makes everything it carries sweep its **envelope of revolution**, and
`product_screening` gauges each envelope against the `min_clearance` the product declares:

| Gauged | Not gauged |
| --- | --- |
| a turning item against every item nothing turns | two items on one shaft, which turn together |
| a turning item against the envelopes on the *other* shafts | two gears **in mesh**, because touching is what a mesh does |
| | a pair a mate or a rigid connection already holds, which touches by design |

The envelope is the cylinder the item's **bounding box** sweeps about the axis. That is
conservative on purpose — a gap it reports is a gap the real body has at least — and it
means a round gear standing in as a box sweeps wider than the gear does. The detail line
says so, so a reader never reads a box's envelope as a gear's. An item whose footprint
overhangs its shaft sweeps a ring reaching well past its own body, which is the case the
check exists to catch: a 120 mm disc flush with one side of a 40 mm post reaches 102 mm from
the axis, not 60.

Nothing is inferred. A box's longest side is not an axis of rotation, so a shaft that
declares no axis sweeps nothing and the entry says which declaration is missing.

## Not yet

Helical gears and the axial loads they make, a stepped shaft's curve, a bundled table of
bearing and gear bending limits, mesh geometry and rating against the gear standards, and the
heat balance: the last two wait on a standard read rather than remembered.

The worked reducer declares no shaft axis: its gear placeholders are boxes placed beside
their shafts rather than turned about them, and sweeping a box that is not on the axis would
report a ring nothing has. It gets the axis when its gears are placed on their shafts.
