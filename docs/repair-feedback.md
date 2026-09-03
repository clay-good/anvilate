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
the forward check lands at exactly the required margin. See
[`examples/sheave_repair_from_inverse.py`](../examples/sheave_repair_from_inverse.py).

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

The last row is the point. The infinite-slope factor divides by γ·z·sin(2β)/2, which
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
