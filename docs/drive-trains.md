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

## Not yet

Declaring the train inside a product document, axial loads from helical gears, a stepped
shaft's curve, a bundled table of bearing and gear bending limits, mesh geometry and rating
against the gear standards, heat, and swept clearance: each of the last three waits on a
standard read rather than remembered.
