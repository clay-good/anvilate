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

## Not yet

Declaring the train inside a product document, the mesh loads applied to the shafts and
their bearings (the case study's bearing reactions rest on positions in its Example 7-2,
which the free chapter does not carry),
mesh geometry and rating against the gear standards, heat, and swept clearance: each
waits on a standard read rather than remembered.
