# Process piping screening (ASME B31.3)

Anvilate screens a straight run and a miter bend for pressure design, on the wall you
can rely on rather than the wall stamped on the pipe. It does not do pipe stress
analysis, and it will not pick your allowable stress.

## Scope, and what it is not

**Screened:**

| Check | Clause | Function |
| --- | --- | --- |
| Straight-pipe wall for pressure | §304.1.2 | `asme_b313_pipe_wall_thickness` |
| The pressure a wall carries (the rating inverse) | §304.1.2 | `asme_b313_pipe_pressure` |
| The wall to *order*, allowances included | §304.1.1 | `asme_b313_minimum_ordered_wall` |
| A run's rating against its service, as a verdict | §304.1.2 | `asme_b313_pressure_scorecard` |
| Miter-bend pressure, single and multiple | §304.2.3 | `asme_b313_miter_bend_pressure` |
| Branch reinforcement area required | §304.3.3 | `asme_b313_branch_required_reinforcement_area` |
| Allowable displacement stress range | §302.3.5 | `asme_b313_allowable_displacement_stress_range` |
| Computed displacement stress range S_E | §319.4.4 | `asme_b313_displacement_stress` |
| Bend stress intensification factor | §319.4.4 (Appendix D) | `asme_b313_bend_stress_intensification` |

**Not screened, and needing a real pipe stress analysis:** support spans
and sustained-load stresses, occasional loads, nozzle and equipment allowables,
supports and anchors, thermal transients, and every code case beyond Chapter II. A
green scorecard here means the pressure design screens clean; it does not mean the
line is designed.

## The wall you can rely on

The pipe you install is not the wall you get to keep. A mill may ship up to 12.5%
under nominal, and a corrosion allowance is metal set aside to be eaten. Neither
carries pressure.

```python
from anvilate.standards import default_pipe_schedule_table

pipe = default_pipe_schedule_table().get("4", "40")
pipe.outside_diameter.quantity   # 114.3 mm — not 4 inches, and nothing about "4" says so
pipe.wall_thickness.quantity     # 6.02 mm nominal
pipe.available_wall(corrosion_allowance=Quantity.parse("1.5 mm"))   # 3.77 mm
```

The dimension table is ASME B36.10M, 108 rows over 18 nominal sizes and six schedules.
An untabled combination raises rather than interpolating — a wall between two rows is
not a pipe anybody can buy.

**STD and XS are carried as schedules, not as aliases for 40 and 80.** They agree only
so far: STD tracks Schedule 40 through NPS 10 and then holds at 9.53 mm while Schedule
40 keeps thickening to 17.48 mm at NPS 24. Treating them as synonyms is right for small
bore and wrong for large.

## The allowable stress is yours, and so is its temperature

The B31.3 allowable stress tables are copyrighted, so the value is always caller-supplied.
But a bare number cannot be reviewed, because **an allowable is only meaningful at a
temperature**: A106-B is 138 MPa at 200 °C and about 110 MPa at 400 °C. A screen handed
the first for a line running at the second is a quarter high with nothing to show for it.

```python
from anvilate.analysis import AllowableStress, asme_b313_pressure_scorecard

allowable = AllowableStress(
    value=Quantity.parse("138 MPa"), temperature=Quantity.parse("473.15 K"),
    material="ASTM A106-B", source="ASME B31.3 Table A-1",
)
asme_b313_pressure_scorecard(
    "process line", design_pressure=Quantity.parse("5 MPa"),
    design_temperature=Quantity.parse("673.15 K"),   # 400 °C, not the 200 °C row
    outside_diameter=pipe.outside_diameter.quantity, nominal_wall=pipe.wall_thickness.quantity,
    allowable=allowable, corrosion_allowance=Quantity.parse("1.5 mm"),
)
# [NOT EVALUATED] the allowable was read at 473.15 K but the design temperature is 673.15 K
```

`AllowableStress.is_valid_at` refuses in both directions. An allowable read *cooler* than
the service is unconservative. One read far *hotter* is safe but is not the row the code
wants, and answering `False` is better than interpolating between table rows Anvilate
does not have.

Three ways the screen returns `NOT_EVALUATED` instead of a number, and each is the point:
no allowable supplied, an allowable read at the wrong temperature, and a wall wholly
consumed by its allowances — which is not the same as a rating of zero.

**Where to get allowables legally:** the ASME B31.3 Appendix A tables (a licensed copy),
the material supplier's certified datasheet, or your client's piping specification. Read
the row at your design temperature; do not scale a room-temperature value.

## Miter bends rate below the pipe they are made from

A miter turns a line by welding straight segments at an angle instead of using a formed
elbow. It is cheaper and it is weaker — the cut leaves the wall carrying a bending
moment the hoop formula knows nothing about. For the NPS 4 Schedule 40 line above,
rating 15.18 MPa straight:

| Cut angle θ | Rating | |
| --- | --- | --- |
| 10° | 11.45 MPa | 75% of the straight pipe |
| 22.5° | 8.53 MPa | 56% |
| 30° | 4.85 MPa | 32% — §304.2.3 changes formula past 22.5°, and it is a step down |
| 45° | 3.23 MPa | 21% |

`miter_angle` is the **cut** angle, half the change of direction the joint makes, so a
90° elbow built from two cuts has θ = 22.5°. Supply `effective_bend_radius` for a
multiple miter and the rating is the lesser of the cut-angle limit and the bend-radius
limit — a tight bend governs over a shallow cut. Past 22.5° the code gives no
multiple-miter rating at all, and the function refuses rather than quoting the
single-miter number as though it were one.

## Example

[`examples/process_pipe_schedule.py`](../examples/process_pipe_schedule.py) — a 5 MPa
service where Schedule 10 looks like plenty at 3.05 mm and rates below the service once
the mill tolerance and corrosion allowance come off, while Schedule 40 clears it with
margin. Rate the wall you can rely on, not the wall stamped on the pipe.
