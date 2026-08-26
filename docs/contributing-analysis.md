# Adding a check to the analysis library

Seven rules. Each one exists because breaking it produces a number a reader would
believe. Where a rule has a gate, the gate is named — and where it does not, that is
said plainly rather than implied.

## 1. Say where the formula came from

Every public check names its source, in its own docstring or its module's. A source is
a token from [`docs/api/citation-authorities.txt`](api/citation-authorities.txt): a
standards body and clause (`AISC 360-22 §F2`), a handbook (`Roark`), or the eponym of
the relation itself (`von Mises`, `Paris-Erdogan`, `Terzaghi`). Naming the method *is*
a citation here, because it tells a reader exactly which relation was implemented.

```python
# Yes — the reader can go and check it.
"""The NDS §3.7.1 column stability factor C_P (the Ylinen column equation)."""

# No — beautifully explained, and unverifiable.
"""The stress in the member, which is the load over the area."""
```

**Gate:** `test_every_new_public_check_names_its_source`. It is a ratchet in both
directions: a new uncited symbol fails, and a symbol on
[`uncited-symbols.txt`](api/uncited-symbols.txt) that has since been cited fails too, so
the recorded debt cannot go stale. Do not add yourself to that list — it is a record of
work owed, not an opt-out. About 23% of the surface is still on it.

## 2. Take and return dimensioned quantities

Inputs are `Quantity`, dimension-checked at the top of the function; outputs are
`Quantity` in a stated unit. A bare float crossing this boundary is how a millimetre
becomes a metre.

```python
_require(shear_force, "[force]", "shear_force")
b = width.to("m").magnitude          # convert once, at the edge
...
return Quantity(magnitude=stress / 1e6, unit="MPa")
```

Two traps this library has actually been bitten by, both worth knowing before you write
your first conversion:

- **`.to("K")` on a temperature *difference*** carries the 273.15 offset into a delta.
  In a cubic correlation that was a factor of 22,701. Use the delta helpers.
- **`.to("Hz")` on an angular rate** silently drops the 2π. Rotational speeds go through
  `angular_speed_rad_per_s` / `count_rate_per_second`; no `.to("Hz")` survives outside
  `units/rotation.py`.

**Gate:** none, beyond review. This is the rule with the least automated cover.

## 3. Anchor the number to something worked outside the code

A test that re-derives the formula from the code pins nothing. Anchor to a hand
calculation, a published worked example, or an independent numerical method, and state
the intermediates so a reviewer can follow.

The half-sine shock spectrum is the pattern: it is a derivation, not a transcription, so
its test integrates the ODE it claims to solve and compares, at seven values of τ/T. The
NDS anchors state the whole hand solution in the docstring and assert its numbers.

**Also assert what the number is not.** A verdict is not a value: a check tested only on
its PASS/FAIL is unpinned, and mutation testing here has repeatedly found safety
coefficients that could be doubled with a green suite.

## 4. Pair a design inverse with its forward check

If you ship a solver for "what thickness do I need", it must land the forward check at
exactly the required margin when you feed its answer back in. Test the round trip.

```python
hint = entry.repair_hint                      # solved by the inverse
repaired = screen(part.model_copy(update={"thickness": hint.corrective_value}))
assert repaired.safety_factor == pytest.approx(required)   # exactly, not "better"
```

A repair hint without a closed-form inverse may name a direction instead — but a
direction is a claim about the function's shape over its whole domain, so **sweep it
before you declare it.** "Flatten the slope" is false above 45°, where the infinite-slope
driving term peaks and the factor of safety turns back upward. Scope the claim to where
it holds and emit nothing outside it. Silence is a legitimate answer.

## 5. Ship a runnable example

Every analysis module is named by at least one script under `examples/`, and every
script under `examples/` is executed by `tests/test_examples.py`. An example nobody runs
is an example nobody notices breaking.

An example earns its place by teaching something the API reference cannot: the mount
chosen for vibration that makes a transport shock *worse*, the joist that passes dry and
fails wet, the post whose "reassuringly firm" pad sits at resonance.

**Gates:** `test_every_module_has_a_runnable_example` and
`test_every_example_is_executed_by_this_file`.

## 6. Change the public surface deliberately

The public API is enumerated in
[`docs/api/analysis-public-surface.txt`](api/analysis-public-surface.txt) and every
module declares `__all__`. Adding a symbol means adding a manifest line in the same
commit; removing one is a breaking change.

The cross-cutting layers that sit on top of the scorecard — `derivation`, `evidence`,
`explore`, `gdt`, `interop`, `loads`, `review`, `uncertainty`, `verification` — keep the
same contract against their own manifest,
[`docs/api/core-public-surface.txt`](api/core-public-surface.txt), and each needs a
`- :mod:` bullet in the `anvilate` package docstring the way an analysis module needs one
in `anvilate.analysis`'s.

**Gates:** `test_public_surface_matches_manifest`,
`test_package_aggregate_matches_module_alls`, `test_every_module_declares_its_public_surface`,
`test_no_exported_symbol_shadows_its_own_module` (a function named after its own module
shadows it, and the other gates structurally cannot see that), and the five `*_core_*`
gates that hold the same line for the top-level modules.

## 7. Never bundle someone else's allowables

Copyrighted table values — code allowable stresses, species design values, detail
categories — are always the caller's to supply. Anvilate composes, cites, and screens;
it does not redistribute the table.

The consequence is a rule, not a disclaimer: **a check with no allowable reports
`NOT_EVALUATED`, never `PASS`.** Same for a zero demand, a NaN, a missing rating.

```python
if adjusted_bending_value is None:
    return ScorecardEntry(name=name, status=CheckStatus.NOT_EVALUATED,
                          detail="not evaluated — no NDS reference design value supplied")
```

Where the allowable depends on a condition, carry the condition with it. `AllowableStress`
holds the temperature its value was read at and refuses in both directions, because a
200 °C allowable used on a 400 °C line is a quarter too high and the arithmetic cannot
tell.

Dimension tables that are *not* copyrighted (ISO 2338 pins, ASME B36.10M pipe schedules)
are bundled with a provenance record, and retrieved rather than recalled.

---

## The rule behind the rules

Every one of these is the same rule wearing different clothes: **a check must not be able
to report a green it did not earn.** When you are unsure whether something needs a guard,
ask what a reader would conclude if the code silently did the wrong thing — if the answer
is "they would believe it", it needs the guard.

Two corollaries worth internalizing:

- **When you guard one operand, guard the others in the same commit.** Four separate
  findings in this codebase have been a NaN or zero check applied to one side of a
  comparison and not the other.
- **A sweep's own claim of completeness is the thing to re-verify.** "These five were the
  only sites" has been wrong more than once. Re-grep.

## Finding a constant nothing pins

A module-level constant can be correct, exported, documented, and still have nothing
holding it to its value. The sweep that finds them: in a scratch copy, replace every
`NAME = <number>` in `analysis/` with a `float` subclass that records its own reads, run
the suite once, and list the constants no test ever read. Then mutate those individually
and confirm the suite still passes.

Run at 230 module-level constants, that sweep returned **one**:
`impact.SUDDENLY_APPLIED_FACTOR`. The formula it summarizes was well covered — `h = 0`
gives `K = 2` — but nothing tied the *public name* to the function, so the library could
have exported a wrong constant with every function correct. It is pinned by the property
now: the constant must equal what `impact_factor` returns at zero drop height, for any
static deflection.

**Check that the scratch copy is green before believing any of it.** The first run of this
sweep used a copy holding only `src/` and `tests/`, so 525 tests failed on the missing
`examples/` and `docs/` regardless of any mutation — every batch was "killed" and the sweep
reported perfect coverage while measuring nothing. Copy the repo with `git archive HEAD`
and run the suite once before mutating anything.

## Finding the guards nothing has ever run

A line-trace of the suite says **around 56% of the roughly 4,300 `raise` sites in the imported modules
never execute**. Most are dimension and positivity checks whose absence a reader would
notice. The subset worth hunting is the one whose *condition carries a domain constant* —
a Poisson's ratio that cannot reach 0.5, an angle range a formula's geometry requires, a
correlation's validity floor. Those are the library's own statements about where a formula
stops applying, and an inverted comparison in one reads exactly like a correct one.

To run the instrument, append a `sys.settrace` line recorder to `tests/conftest.py`, run
the suite once, then walk each module's AST for `ast.If` nodes whose body raises and whose
test mentions a numeric literal other than 0 or 1, or an UPPER_CASE name. Anything whose
`raise` line is not in the trace is unpinned.

That sweep found 38 on 2026-08-25; `tests/test_domain_guards.py` took it to 2, and both
survivors are safety nets that no input can reach (asserted as such rather than left as an
unexplained gap). **Re-run the trace after writing the tests, not before.** Six of the
first twelve survivors turned out to be reached through a *different* guard than intended —
a bearing whose contact angle never got as far as its own check because the rotational
speed was refused first, one malformed fastener position caught by the "at least two"
rule. A guard reached through another guard is still unpinned, and only the second trace
says so.

One defect fell out of it: `eccentric_weld_group_peak_stress` checked that each segment was
a pair and then indexed each *point* without checking, so a malformed endpoint raised
`IndexError` — which a caller catching `ValueError` does not catch.
