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

### Every screen records whether it has a lever

`docs/api/repair-levers.txt` holds the decision for all 51 public screens.
There are 21 levers across 13 of them, and 38 recorded as having none yet — each
figure gated against the file it describes. A screen without a lever is a gap someone
wrote down, not one nobody noticed: the same contract `design-inverses.txt` holds
over the inverses.

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
