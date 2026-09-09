# Typed repair feedback

A scorecard says whether each check passed. Typed repair feedback says what to do
about the ones that did not — and flags the ones that passed by too much. All of
it is computed deterministically from the analysis library, never guessed.

Three pieces, all opt-in and backward compatible:

## Repair hints on a failing check

A failing check can carry a `RepairHint`: the governing parameter (by its stable
name), the direction that improves the margin, and — when the check has a paired
design inverse — the exact value that lands it at the required margin.

```python
from anvilate.scorecard import Direction, RepairHint, ScorecardEntry

# A design inverse solved for the sheave diameter that meets the allowable at SF 1.5.
hint = RepairHint.solved(
    "sheave_diameter", direction=Direction.INCREASE, value=509.3, unit="mm",
    provenance="minimum_sheave_diameter_for_bending_stress",
)
entry = ScorecardEntry.from_safety_factor(
    "wire bending over the sheave", computed=0.74, required=1.5, repair_hint=hint,
)
print(entry.repair_hint)   # increase sheave_diameter to 509.3 mm
```

When no inverse exists but the check is monotonic in a known parameter, use
`RepairHint.directional(...)`: it names the parameter and direction and omits the
value rather than inventing one. A hint only rides on a `FAIL` entry — it is
dropped from a passing check even if you pass one.

Repair turns from a search into a single solve: apply `hint.corrective_value` and
the forward check lands at the required margin — and passes. `RepairHint.solved`
places the value one part in 10^12 into the passing side rather than exactly on the
boundary, because a check passes on `computed >= required` and a screen re-run at a
corrective value recomputes its safety factor down a different arithmetic path than
the solve came up. Landing on the boundary leaves the verdict to float noise, and
that is not hypothetical: the base-plate hint solves t·√(required/SF), and the square
root left the repaired plate at a safety factor of 1.9999999999999996 against a
required 2.0 — the fix this library named was itself a `FAIL`. See
[`examples/sheave_repair_from_inverse.py`](../examples/sheave_repair_from_inverse.py).

### A hint has to be one you can act on

The inventory says *which* parameter each screen names. What it cannot say is whether the
hint a caller receives is usable, so every repair hint the suite builds is swept at session
end: it rides a `FAIL` and nothing else, its corrective value is a finite number, it says
where the value came from, and — the one that was wrong — **its unit is one this library can
parse**. A tooth count was labelled `teeth`, which is a word and not a unit, so a consumer
converting the value raised on a number that was otherwise correct. A dimensionless
value — a count, a ratio — carries no unit at all, which is what the luminaire count and the
isolator frequency ratio already did.

### Every screen records whether it has a lever

`docs/api/repair-levers.txt` holds the decision for all 59 public screens.
There are 50 levers across 29 of them, and 30 recorded as having none yet — each
figure gated against the file it describes. A screen without a lever is a gap someone
wrote down, not one nobody noticed: the same contract `design-inverses.txt` holds
over the inverses.

The 30 with none are classified in that file's header rather than left as a flat list:
a demand and an allowable both computed upstream (a stress is not a knob, and the geometry
that produced it is what the screen never saw), an aggregator whose card carries its
elements' hints, or a geometry whose knob is not a number — a section is a discrete choice
from a table, and a corrective value is a float.

That classification was wrong in five of its six hardest cases when it was first written,
because it was written from the screens' names. The concrete bearing, the bolted
connection and the column member were all filed as "no single knob" and all three turned
out to have one; three pressure-vessel screens were filed there when they take a
already-computed value. The file says so.

A third kind, `aggregated`, marks a screen that FORWARDS a lever rather than computing
one: `screen_structure` dispatches each member and concatenates their entries, so its ten
rows are its members', arriving unchanged. The label exempts those rows from the
wrong-value sweep below — the value belongs to the screen that computed it — and is itself
gated, because an `aggregated` row that names a parameter no other screen offers would be
a way of ducking that sweep.

**And every solved lever's value is swept.** These gates check that a lever is recorded and
that the screen builds it; they cannot check that anyone would notice if the number were
wrong, which is a solved hint's whole claim. So `RepairHint.solved` is made to return a
value 5% off — and 5% the other way, since a test asserting only "larger than before" would
survive one direction — and some test naming both the screen and the parameter has to fail.
It found two gaps the moment it was written: a screen wired with no test at all, and an
aggregator whose pass-through nothing checked.

The gate reads it both directions. A recorded lever must actually be constructed by
that screen (resolved through the module's own call graph, because the hint is usually
built in a helper the screen calls), every lever a screen constructs must be recorded,
the `solved`/`directional` kind must match the classmethod used, and the parameter must
be a keyword argument of the screen or a field of a model it takes — walked through
lists and unions, so `screen_structure`'s levers resolve to the member models a caller
actually sets.

### Declaring a lever, and when not to

A direction is a claim about the check's behavior, so it is declared only where it
holds. The geotechnical pack is the worked case:

| Screen | Check | Lever | Kind |
| --- | --- | --- | --- |
| `screen_retaining_wall` | overturning, sliding | `vertical_load` ↑ | solved — both factors are linear in V |
| `screen_driven_pile` | pile capacity | `length` ↑ | solved — shaft friction is linear in L, end bearing fixed |
| `screen_shallow_footing` | bearing capacity | `width` ↑ | directional — B also enters q_ult, so no closed form |
| `screen_infinite_slope` | slope stability | `pore_pressure` ↓ | solved — FS is linear in u (drainage) |
| `screen_infinite_slope` | slope stability | `slope_angle` ↓ | directional, **below 45° only** |

The pressure-vessel check is the other worked case, and it shows what a solved hint
owes the reader:

| Screen | Check | Lever | Kind |
| --- | --- | --- | --- |
| `asme_b313_pressure_scorecard` | straight-pipe pressure | `nominal_wall` ↑ | solved — the B31.3 wall inverse, grossed back up |
| `isolation_scorecard` | isolator transmissibility | `frequency_ratio` ↑ | solved — the DAMPED transmissibility inverse |
| `junction_temperature_scorecard` | junction temperature rise | `thermal_resistance` ↓ | solved — `heatsink_thermal_resistance_required` |
| `screen_ventilation` | outdoor air, air changes | `provided_outdoor_airflow` ↑ | solved — both, and they ask different amounts |
| `screen_shear_plate` | shear yielding / shear rupture | `gross_shear_area` ↑ / `net_shear_area` ↑ | solved — a different area per limit state |
| `screen_tension_member` | gross yielding / net rupture | `gross_area` ↑ / `net_area` ↑ | solved — a different area per limit state |
| `screen_welded_connection` | throat shear | `leg_size` ↑ | solved — `fillet_weld_leg_for_load` |
| `screen_gusset_plate` | block shear | `net_shear_area` ↑ | solved — holding the tension area the bolt gauge fixes |
| `screen_feeder` | voltage drop | `conductor_area` ↑ | solved — the resistive half only, **and sometimes not at all** |
| `screen_feeder` | conductor ampacity | `conductor_ampacity` ↑ | solved — the line current at the margin |
| `screen_pipe_run` | head budget | `available_head` ↑ | solved — the loss the pipe consumes |
| `screen_masonry_wall` | axial, combined | `axial_stress` ↓ | solved — two answers, and the unity one can run out |
| `screen_lighting` | task illuminance | `luminaire_count` ↑ | solved — the least WHOLE count that reaches it |
| `screen_lighting` | lighting power density | `input_watts_per_luminaire` ↓ | solved — the lever the other check does not fight |
| `screen_pump_duty` | motor rating, NPSH | `motor_rating` ↑, `npsh_available` ↑ | solved — the duty's shaft power, the pump's required NPSH |
| `screen_noise_exposure` | noise dose | `exposure_duration` ↓ | solved — the permissible time at the combined level |
| `screen_cover_plate` | plate bending, flatness | `thickness` ↑ | solved — **twice**, at two different powers |
| `screen_concrete_bearing` | ACI confined bearing | `bearing_area` ↑ | solved — in whichever confinement branch the answer lands in |
| `screen_bolted_connection` | bolt shear / bearing / tear-out | `bolt_diameter` ↑ / `plate_thickness` ↑ / `edge_distance` ↑ | solved — three knobs, and the bolt fights the edge |
| `screen_column_member` | AISC §E3 buckling | `length` ↓ | **directional** — no closed inverse across the inelastic branch |
| `screen_shaft` | strength / fatigue / twist | `diameter` ↑ | solved — **three times**, at d³, d³ and d⁴, and they disagree |
| `screen_shaft_key` | key shear / side bearing | `key_length` ↑ | solved — a different length per limit state |
| `screen_rolling_bearing` | rating life / static capacity | `dynamic_load_rating` ↑ / `static_load_rating` ↑ | solved — the catalogue rating, because a bearing is selected and not machined |
| `screen_gear_mesh` | bending / pitting / contact ratio / undercut | `module` ↑ / `pressure_angle` ↓ / `pinion_teeth` ↑ | solved twice at two different powers, **directional** on the angle, and a whole count |

The check rates the wall a pipe can be *relied* on to have: the ordered wall less the
mill under-tolerance and the corrosion allowance. So the inverse's answer is not the
hint. `asme_b313_pipe_wall_thickness` gives the pressure-design wall the service
demands; the wall to *order* is that plus the corrosion allowance, all divided by
(1 − mill tolerance) — the same two deductions the check made, undone in the same
order. Naming the pressure-design wall would name a pipe that still fails, and a test
asserts exactly that.

The two plate rows are the case where the levers differ *between entries on one card*:
shear yielding is checked on the gross section and rupture through the holes, so a hint
that named one area for both would tell a detailer to grow the wrong thing — a wrong
answer, not a vague one.

The cover plate is the case where **one lever solves to two different numbers**. A plate's
peak stress goes as 1/t² and its centre deflection as 1/t³, so the bending check asks for
t·√(required/SF) and the flatness check for t·(δ/limit)^(1/3) — and the flatness one has no
safety factor to scale from at all, because a deflection check is a length against a
length. The cover needs the larger; a card publishing one would leave the other failing.

The two lighting rows are the case where the checks **pull in opposite directions on the
same knob**. Illuminance rises with the luminaire count and so does the power density, so a
card that answered both with the count would tell a designer to add fittings and remove
them. Each names the lever that is actually its own: a dim room needs more fittings, and an
over-budget install needs fittings that draw less for the same lumens. The count is also
the library's only **whole-number** lever — its inverse rounds up to the least count that
meets the margin, and `RepairHint.solved(..., whole=True)` skips the boundary nudge for it,
because 19.000000000019 luminaires is not an answer.

The feeder's drop row is the one where the lever can be **out of reach**. Only the
resistive half of ΔV = √3·I·(R·cosφ + X·sinφ) shrinks with the conductor; the reactance is
the run's geometry. On a reactive run the √3·I·X·sinφ term alone can exceed the whole
allowance, and then no conductor size fixes it — the answer is a different route,
power-factor correction, or a higher distribution voltage. The check keeps its `FAIL` and
offers **nothing**, because a lever that cannot reach is worse than silence. A test asserts
the ampacity hint on the same card is still there, so the silence reads as being about the
drop rather than about the card giving up.

The gusset row is the one where the solve is **not** a scaling. Block shear adds two
areas, `R_n = F_u·(0.6·A_nv + A_nt)`, so neither is the lever on its own and the tension
term does not scale with the shortfall: the answer is `A_nv = (SF·P/F_u − A_nt)/0.6`,
holding the tension plane's width, which the bolt gauge fixes. `A_nv·required/computed`
would be wrong, and by a lot.

The junction row is the only lever in the library that points **down**, and the
ventilation row is the only screen whose two checks share one knob: outdoor air and air
changes are both levered by the air delivered, and they ask for different amounts of it.
The card publishes both numbers rather than the governing one, because a designer sizing
a fan needs to see how far apart the two demands are.

The last row of the geotechnical table is the other point. The infinite-slope factor divides by γ·z·sin(2β)/2, which
peaks at β = 45°: below it, steepening costs margin, and above it the trend reverses.
"Flatten the slope" is false for a slope steeper than that, so past 45° the screen
offers no hint at all. Silence is a legitimate answer; a direction that is wrong is
worse than none. Every declaration above is pinned by a round-trip or a sweep in
`tests/test_geotechnical_pack.py`, including one test whose only job is to prove the
reversal the slope hint refuses to cross.

## Two-sided acceptance bands

`from_safety_factor` takes an optional `upper` bound. A check above it is
`OVER_MARGIN` — a pass, never a failure, never blocking export — with the excess
quantified so an over-engineered candidate is as visible as a failing one:

```python
entry = ScorecardEntry.from_safety_factor("bracket", computed=8.7, required=2.0, upper=3.0)
entry.status        # CheckStatus.OVER_MARGIN
entry.passed        # True — it met the minimum
entry.over_margin   # True — it ran past the band
```

Omit `upper` and high margins pass silently, exactly as before — the band is
strictly opt-in. [`examples/over_margin_target_band.py`](../examples/over_margin_target_band.py)
walks one padeye through all three verdicts against a 2.00–4.00 band, by pack argument and by
document. A scorecard whose only blemish is over-margin checks rolls up to
`OVER_MARGIN` and stays `passed`; a single failure still dominates.

The discipline packs expose the band the same way. `screen_lifting_lug(lug,
required_safety_factor=1.4, target_safety_factor=2.5)` flags an over-plated lug as
`OVER_MARGIN` on both limit states; omit `target_safety_factor` and it screens
one-sided as before. The helper `strength_scorecard(..., upper=...)` carries the
band into any pack check.

## Governing check and governing change

`Scorecard.governing()` returns the tightest check — the largest utilization
(required ÷ computed), the one a reviewer reads first.

**It ranks by status before utilization, and the rungs are the card's own**: FAIL >
NOT_EVALUATED > OVER_MARGIN > PASS. Over-margin used to sit on the passing rung, and it was
the one rung that mattered, because an over-margin check has a *low* utilization by
definition — that is what over-engineered means — so it lost the tie-break to every
ordinary passing check. A card reading `OVER_MARGIN` named a `pass` check as governing:

```text
padeye: OVER_MARGIN
  over_margin    padeye net tension ... exceeds target band 2.00–4.00 by 2.67
  pass           padeye pin bearing
  governing:     padeye pin bearing (pass)     # <- the one check that is not why
```

Inside the over-margin rung the tie-break inverts. The limit being passed there is the
*top* of the band, so furthest past it is the lowest utilization: the most over-engineered
check governs, not the least.

Across a revalidation, `governing_shift(previous)` reports when the reference point moved:

```python
shift = after.governing_shift(before)
if shift is not None:
    print(shift)   # governing check changed: 'bending' (util 0.94) → 'bolt bearing' (util 0.88)
```

It returns `None` when the same check still governs or when neither card carries a
safety-factor check — a quiet no-news, not a false alarm.

## In a report

`CalculationReport` renders all three: an over-margin check shows its band and
excess, a failing check prints its repair line, and the margin summary names the
governing check. See [calculation reports](calculation-reports.md).
