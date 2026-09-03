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

## A skipped gate is a gate that did not run

Several tests skip when an optional package is absent — `jsonschema` for the published
contracts, `ezdxf` for the DXF export, `lxml` for the two interchange schemas. Locally
that is the point: the packages are optional. In CI they are not, because the dev extra
installs them, so a skip there means a check quietly stopped running while the build
stayed green.

`tests/conftest.py` fails a CI run (anything with `CI` set) that skips a test for a
missing import, unless the package is one only the *scheduled* jobs install. That
allow-list is held against the workflow itself by
`test_the_ci_skip_gate_allows_exactly_what_the_scheduled_jobs_install`, so an entry no
job backs — which would excuse a skip forever — fails the build instead.

## Finding the guards nothing has ever run

A line-trace of the suite says **around 52% of the roughly 4,800 `raise` sites in the imported modules
never execute**. Most are dimension and positivity checks whose absence a reader would
notice. The subset worth hunting is the one whose *condition carries a domain constant* —
a Poisson's ratio that cannot reach 0.5, an angle range a formula's geometry requires, a
correlation's validity floor. Those are the library's own statements about where a formula
stops applying, and an inverted comparison in one reads exactly like a correct one.

To run the instrument, measure once with `coverage` and then read the AST:

```bash
coverage run --source=src/anvilate -m pytest -q
```

Load the run with `coverage.Coverage(); cov.load(); cov.get_data().lines(path)` for the
reached set, then walk each module for `ast.Raise` nodes whose line is not in it, keeping
the ones whose nearest enclosing `if` compares against a numeric literal other than 0 or 1,
or against an UPPER_CASE name. That is the unpinned set. (An earlier version of this page
described rewriting every raise site through a `sys.settrace` recorder; the coverage run
gives the same answer in one command and without a scratch copy of the tree.)

Two things will otherwise fill the result with false positives, and both were learned by
getting them wrong. **Follow the call that validates.** Ten modules check a fraction
through a private `_fraction(value, name)`, so a scan that stops at the function body
reports every one of them as unguarded — 48 hits, 44 of them false, with the one real hole
buried in the middle. **And accept any bound, not just the one you expected**: a correct
`0 < accel_fraction <= 0.5` reads as a hole to a scan that only recognises a comparison
against 1.

That sweep found 38 on 2026-08-25; `tests/test_domain_guards.py` took it to 2, and both
survivors were recorded as safety nets no input can reach, asserted as such rather than
left as an unexplained gap. **One of the two was mis-declared, and re-measuring on
2026-08-29 is what found it.** `involute_angle`'s residual check was excused because it
"fires only if Newton fails to converge", and the solver is a *bracketed* Newton — it
cannot fail to converge. It converges onto whatever the bracket allows, and past a certain
argument that is the bracket's own top end: 89.9999999999427 degrees, the same answer for
every such argument. What actually stops it is the residual check, at a threshold the
arithmetic fixes rather than the author — one ulp of φ near the pole moves tan(φ) by sec²φ
times that, so the finest residual a double can express crosses the 1e-9 relative tolerance
around inv ≈ 5e6. A finite, non-negative argument reached the guard the whole time. **An unreachable-by-construction claim is a claim**, and the reason
it survived a year is that it reads as the conclusion of the analysis rather than as part
of it. One survivor is left. **Re-run the trace after writing the tests, not before.** Six of the
first twelve survivors turned out to be reached through a *different* guard than intended —
a bearing whose contact angle never got as far as its own check because the rotational
speed was refused first, one malformed fastener position caught by the "at least two"
rule. A guard reached through another guard is still unpinned, and only the second trace
says so.

One defect fell out of it: `eccentric_weld_group_peak_stress` checked that each segment was
a pair and then indexed each *point* without checking, so a malformed endpoint raised
`IndexError` — which a caller catching `ValueError` does not catch.

## The refusal a bare number gets

The library's whole premise is that it takes dimensioned quantities. So the single most
likely way to call it wrong is to pass a number — and until 2026-08-29, **1,524 of the
1,741 public analysis functions probed answered that with**

```text
AttributeError: 'float' object has no attribute 'has_dimension'
```

That is the guard calling a method on the thing it was checking. It names no parameter, no
expected dimension, and no library; it reads as an internal slip, which is what it was. The
function two lines down had a perfectly good sentence ready — `moment must be a
[force]*[length] quantity` — and no input could ever reach it.

**The instrument is three lines and needs no fixtures.** For every public function, bind
every required parameter to `1.0` and call it:

```python
kwargs = {p.name: 1.0 for p in signature.parameters.values()
          if p.default is inspect.Parameter.empty}
```

Returning is fine — a dimensionless correlation legitimately takes plain floats. Raising is
fine. What the sweep looks for is *which class*, and the answer partitioned into four
families, each one a different guard written a different way:

| Family | Count | What it looked like |
| --- | --- | --- |
| The dimension guard | 1,509 | `AttributeError: no attribute 'has_dimension'` |
| A sequence parameter given a scalar | 26 | `TypeError: object of type 'float' has no len()` |
| A model parameter given a scalar | 15 | `AttributeError: no attribute 'safety_factor'` |
| A `TypeError` where every sibling guard raises `ValueError` | 3 | `dead must be a Quantity load effect` |
| A count given a float | 1 | `'float' object cannot be interpreted as an integer` |
| A table lookup on a caller's key | 1 | `KeyError: 1.0` |

1,555 of the 1,741 functions probed. The other 186 were already right: 113 returned a
result (a dimensionless correlation legitimately takes plain floats) and 73 already refused
with a `ValueError` naming the parameter.

Two of those families were already known one layer down: `eccentric_weld_group_peak_stress`
was fixed in an earlier sweep for raising `IndexError` on a malformed endpoint, for exactly
this reason. What that fix could not see is that the same mistake was library-wide.

**Two things worth copying from the repair.** 212 of the guards were *textually identical*,
which is what made a mechanical pass safe — and measuring that before editing is what turned
"212 files" from a scary number into a boring one. And the pass has to know whose name to
put in the message: an early version wrote `{name}` inside scorecard functions, where `name`
is the *check's* name and not the parameter's, so `aluminum_compression_scorecard` refused
a bad stress in the name of the scorecard entry. The gate caught it, because it requires the
refusal to name a parameter the caller actually passed.

Three refusals that named the wrong thing fell out of the same requirement, all of them
predating the sweep: `_bend_geometry` hardcoded `"inner_radius"` and two of its callers spell
that parameter `initial_bend_radius`; a bimetal layer check said `alpha` where the parameter
is `alpha_1` or `alpha_2`; and `fiber_mode_count` refused in terms of `V`, the symbol its
formula uses, rather than `v_number`, the argument.

### Where it stands

`tests/test_contract.py::test_every_public_analysis_function_refuses_a_bare_number_by_name`
runs the sweep over the whole public surface on every CI run, and none of it raises anything
but a `ValueError` naming a parameter. The split on 2026-08-29 was 1,628 refusing and 113
returning a result; the gate deliberately does not pin those two counts — they move with
every function added — only the property and a *floor* on how many functions it probed,
because the third way a gate like this goes wrong is covering nothing and saying so in
green.

### The same probe, pointed the other way

Bind every required parameter to a `Quantity` with an absurd dimension instead of a bare
number, and the mirror mistake shows up: a caller told that everything here is a `Quantity`
wraps the parameters that are *not* quantities — a ratio, a count, an angle in degrees.
**213 functions answered with the interpreter's own sentence**, `'<' not supported between
instances of 'Quantity' and 'int'`.

Those were not 213 defects. `Quantity` defined no ordering, no arithmetic and no numeric
conversions at all, so the interpreter was answering for it every time — and the throwing
sites were a 170-way long tail with no dominant shape, so the mechanical pass that fixed the
bare-number families would not have worked here. Defining the operators to refuse, in one
file, fixed all 213 and could regress nothing: every one of them raised before.

The trade is real and is stated in the gate: an operator does not know the parameter it was
reached through, so it names the mistake and the number to pass instead rather than the
argument. Requiring a parameter name would have been requiring the 170 call sites.

**Measure the shapes before choosing the repair.** The same census that made 212 files a
boring number here said the opposite, and both answers came from the same five-line script.

## Finding a rendering nobody has looked at

A `__str__` is what a user sees when they print an object, and it is the easiest thing in
the package to write and never check. The instrument is the coverage run again, pointed at
a different node type:

```bash
coverage run --source=src/anvilate -m pytest -q
```

then walk each class for a `__str__`, `render` or `summary` and ask whether **any** line of
its body appears in the reached set. On 2026-08-29 that was **34 of 80 never executed** —
strings shipped to users that no test, example or doc block has ever printed.

Rendering them by hand found four defects in the twenty-five that were cheap to construct,
and they are one family: **the rendering drops the field that tells two different objects
apart.**

| Rendering | What it dropped | Why it mattered |
| --- | --- | --- |
| `AngularTolerance` | the shorter leg | ISO 2768-1 bands the tolerance *by* it, so two tolerances from different legs printed identically |
| `FieldOutcome` | `detail` | "the candidate did not parse" and "does not carry this field" both printed `expected X, got —` |
| `FADAssessment` | `toughness_is_estimate` | the scorecard downgrades a PASS to NOT_EVALUATED on that flag; printing the assessment showed the same margin either way |
| `Citation` | the separator it was parsed with | guessed from the edition's *length*, so `ASME B31.3-2022` rendered as `ASME B31.3 2022` |

**Two ways to narrow the search, and both need eyes at the end.** Grep for a `__str__` that
omits a boolean field the class declares — six hits, one real. The other five encode the
flag where the reader already sees it: an ISO 286 deviation renders its designation, whose
*case* is the hole/shaft flag; a datum renders the Ⓜ that `is_feature_of_size` gates; a
certificate reaches its flag through `signature_line()`, which a source scan cannot see.
And for a parse result, **make the round trip the assertion** — `str(parse(text)) == text`
over the library's own strings. That one found a defect nobody would have written a case
for: `29 CFR 1926` read as the year 1926.

### Where it stands

Twenty-five of the thirty-four were inspected and the four above fixed. The rest need
construction fixtures nobody has written — a flange-moment set, a lifter device, an
embodied-carbon estimate. If you build one for another reason, print it once and look.

## The bound a parameter's own name fixes

Re-measuring in August 2026 with a coverage run rather than a trace put 129 of the
still-unreached guards in a single family: a parameter whose *name* already fixes its
range — an efficiency, a mole fraction, a coefficient of utilization, a heat-capacity
ratio, a count of shear planes. They all exist for the same mistake, and it is one
keystroke: a percentage where a fraction belongs. `0.85` typed as `85`, the 0.6 weld
factor typed as `6`. The value is a well-formed float in the right units, so without the
guard it travels straight through the formula and comes back as a capacity a hundred
times too large.

So: **if a parameter is named for a bounded quantity, bound it.** Ten modules already
carry a private `_fraction(value, name)` for the (0, 1] case; use it, or write the
comparison inline. `tests/test_fraction_guards.py` trips 40 of these guards one at a time
and then passes a value just inside each bound, because a guard that refuses everything
passes a refusal test exactly as well as a correct one.

That file is also the ratchet. It re-derives the census from the source — following a
parameter into the helper it is validated by, which is the whole difference between a
census and a list of false positives — so a new function taking one of these parameters
without a guard fails there rather than shipping.

**The census is static, and that is a limit worth knowing.** It reads the source and asks
whether a guard is *written*; it cannot ask whether one is ever *evaluated*. A line-trace of
the suite is what answers that, and it found eight guards that existed and had never run —
five functions share the heat-exchanger `capacity_ratio` bound and only one of them was ever
called with a bad value, and the radiation case passed its slip as `emissivity_1`, so the
`emissivity_2` guard two lines down returned before it could refuse anything. All eight were
correct. They are cases now, because an unrun guard is an unevaluated comparison and an
inverted one reads exactly like a correct one. If you add a bounded parameter to a function
that already has a sibling guard, add the case too: the census will not tell you.

**And the message has to enforce what it says.** A refusal test cannot see the difference
between `(0, 1]` and `[0, 1]`: both refuse 85, and only one refuses a zero efficiency. So a
third gate reads every guard whose message names a closed interval — 240 of them — and
requires the comparison above it to accept exactly that set. It needs no fixture, it covers
the 32 interval guards no test reaches, and it is the check that catches an off-by-one bound
or an inverted chain, neither of which a call-and-refuse test can distinguish from a correct
guard. Two guards are compound rather than bare chains and are exempt with their reasons. **5 parameters are exempt**, each with
the reason its name lies about its range: a spectral efficiency is bits per second per
hertz, a molar absorptivity (in two functions) is tens of thousands, a heat pump's
seasonal efficiency is its COP of 3 to 4, and excess air routinely runs past 100%. An exemption that turns out to be
guarded after all fails as stale.

Writing it found one hole: the AISC J2.4 weld shear fraction guarded positivity and not
its upper bound, so `6` for `0.6` returned ten times the weld capacity with every other
check satisfied — the unsafe direction for a screen to be wrong in.

## Verifying the install, which no test can do

Every test in this suite runs against `src/`. So does every example. A dataset that stopped
being *packaged* would keep passing here and fail for the first person who `pip install`ed
it — the materials database raising on a lookup that works for every contributor.

`test_every_bundled_dataset_lives_where_the_wheel_will_carry_it` holds the mechanism: the
wheel target ships one whole package directory, every dataset is under it, and any key that
could narrow it (`exclude`, `only-include`, `artifacts`, `force-include`, `sources`) is a
failure rather than something to interpret. That is structural, and it is as far as an
offline suite can go: building a wheel fetches the backend, and this suite runs with the
socket layer closed.

The rest is a manual check, worth running before a release and after any change to
`pyproject.toml`:

```bash
python3.11 -m venv /tmp/fresh && /tmp/fresh/bin/pip install .
/tmp/fresh/bin/anvilate --version
/tmp/fresh/bin/anvilate check path/to/spec.yaml
/tmp/fresh/bin/python -c "
from anvilate.standards import default_materials_db
print(default_materials_db().get('ASTM-A36').name)"
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize"}' | /tmp/fresh/bin/anvilate-mcp
```

The material lookup is the line that matters: it reads a bundled YAML file, which is the
thing an editable install and a source-tree test run both hide. The last line covers the
*other* console script, which is a second delivery path with its own way to break. Run at
HEAD the lookup returns `ASTM A36 structural steel`, the twelve `standards/data` and five
`tolerance/data` files are present in `site-packages`, a pack screen runs on the installed
wheel, and the MCP server answers `initialize` with the 2026-07-28 revision.

**Two traps if you run it without a network.** `pip install .` fetches the build backend and
the runtime dependencies, so the offline substitute is to build the wheel once
(`python -m build --wheel`) and install it with `--no-index --no-deps`, copying `pint`,
`pydantic`, `pydantic_core`, `yaml`, `typing_extensions`, `typing_inspection`,
`annotated_types` and `platformdirs` into the fresh `site-packages` by hand.

Do **not** reach the dependencies by putting the repository's `site-packages` on
`PYTHONPATH` instead. The editable install lives there, and `importlib.metadata` will find
*its* `METADATA` rather than the wheel's — so `metadata("anvilate")["Summary"]` returns
whatever `pyproject.toml` said when the editable install was made, and the half of this
check that exists to catch stale packaging metadata silently verifies the artifact you were
not testing. It reported the old `Summary` and the old `Keywords` for a wheel that carried
the new ones. The unambiguous read is the zip itself:

```bash
python3 -c "
import zipfile; z = zipfile.ZipFile('dist/anvilate-0.0.1-py3-none-any.whl')
name = [n for n in z.namelist() if n.endswith('METADATA')][0]
print(z.read(name).decode())"
```

Both console-script *targets* are resolved in the suite —
`test_every_declared_console_script_resolves_to_a_callable` imports each module and requires
the attribute to be callable — so a renamed entry point fails here rather than at a user's
first run. What the manual pass adds is that the command is actually on `PATH` and that the
data it reaches for is actually in the wheel.

## Finding a capability nobody can discover

A capability that ships, is tested, and appears in no documentation fails no test — every
test passes. Only a contract gate over the *component list* finds it.

`tests/test_building_services_docs.py` holds the pack half permanently: every module under
`anvilate/packs` must have a documentation page and a test file, with the missing items
enumerated, which is what `discipline-packs` asks for in as many words. It found four —
`noise_exposure`, `lighting`, `ventilation` and `electrical` — all shipping and cited and
none of them mentioned anywhere a user would look.

The same question for top-level modules is a manual sweep, because the signal is weaker:

```bash
python - <<'PY'
import pathlib, pkgutil
import anvilate
docs = " ".join(p.read_text(errors="ignore") for p in pathlib.Path("docs").rglob("*.md"))
readme = pathlib.Path("README.md").read_text()
for info in pkgutil.iter_modules(anvilate.__path__):
    name = info.name
    if name.startswith("_"):
        continue
    if f"anvilate.{name}" in docs or f"anvilate.{name}" in readme or f"`{name}`" in readme:
        continue
    print(name)
PY
```

Run at HEAD it named six and five were false positives — `cli`, `derivation`, `evidence`,
`review` and `tolerance` are all documented, by pages that describe the capability without
importing the module by path. The sixth, `anvilate.specbench`, was real and is documented
now. **Read the output as a list to check by hand, not as a list of gaps**, which is why
this one is not a test.

## Three sweeps that came back clean

Both were run at HEAD and found nothing. Recorded so the next person spends the afternoon
somewhere else.

**Numbers narrated in `examples/` docstrings.** The ratchet in `test_examples.py` requires
every example quoting a figure to call `_assert_narrates`, which checks each narrated number
against a computed value **in both directions** — a quoted figure with nothing behind it
fails, and a computed value no figure uses fails too. Confirmed behaviourally rather than
read: a sampled docstring number perturbed in four examples failed the suite every time.

**Every example's printed output, not just its exit status.** `test_examples.py` runs all
490 and asserts they exit zero, and `_assert_narrates` checks the figures a docstring
quotes — but nothing looked at the rest of what they print. Run them all and grep the
output for `nan`, `inf`, `None`, and exponents past 1e15: ten lines matched and every one
is legitimate — a carrier density of 1e22 /m³, a photon flux of 2.5e15 /s, the
Prandtl-Meyer angle at infinite Mach, and prose containing the word "none". The one bare
`None` is `best('mass')` on a 20-point grid budget that finds nothing feasible, which is
the point that example is making.

**Numbers quoted in `src/` docstrings.** 720 distinctive figures in function docstrings; 39
are neither a numeric literal in their own module nor named anywhere in `tests/` or
`examples/`. Every one spot-checked is a derived coefficient the docstring states alongside
its exact form — `33/140 ≈ 0.236`, `72/56 = 1.286`, `ξ = 1 − 1/√3 ≈ 0.423`, the Rayleigh
ratio at the ν the sentence names — so the prose carries its own derivation and a gate would
be re-deriving what the sentence already shows.

A gate over the arithmetic those sentences state was written and thrown away: eleven claims
of the form `a/b ≈ c` across the whole package, seven of them real and all seven correct,
and the four "failures" were the regex reading `1/√3 ≈ 0.577` as `√3 ≈ 0.577`. At that
corpus size the pattern is likelier to be wrong than the prose is, which is the point at
which a gate stops paying.

## Finding a published constant nothing pins

The public-surface manifests say a symbol exists. They do not say anything exercises it.
Cross the manifests against every identifier appearing in `tests/` and `examples/`:

```bash
python - <<'PY'
import pathlib, re
symbols = [
    line.strip()
    for manifest in ("core", "analysis")
    for line in pathlib.Path(f"docs/api/{manifest}-public-surface.txt").read_text().splitlines()
    if line.strip() and not line.startswith("#")
]
named = set(
    re.findall(
        r"[A-Za-z_][A-Za-z0-9_]*",
        "\n".join(f.read_text() for d in ("tests", "examples")
                  for f in pathlib.Path(d).rglob("*.py")),
    )
)
for symbol in symbols:
    if symbol.split(".")[-1] not in named:
        print(symbol)
PY
```

At HEAD that is 54 of 2,019. **Most are not defects**: a result type like `HertzContact` is
returned by a tested function and reached by attribute access, never by name. The subset
worth reading is the **constants**, and the way to settle one is to change it and run the
tests — indirect coverage through a caller counts, and only a mutation tells you whether
there is any.

Doing that at HEAD found one: `BELLEVILLE_PLATEAU_RATIO`, √2, published and used nowhere
but its own module's prose. Changing it to √2.2 failed nothing.

**Pin a constant by its property, not its digits.** Its docstring already said what it is —
"dF/dy = 0 first acquires real roots there" — so the test samples the load-deflection curve
either side: rising everywhere below the ratio, touching zero at it, turning over above.
That reads as an argument rather than as a magic number, and it also catches a change to the
curve the constant describes, which asserting √2 never would.

### Where it stands

Every constant on the 54 was mutated at HEAD. **One was unpinned** —
`BELLEVILLE_PLATEAU_RATIO`, fixed above. The other nine are pinned through a caller and
need nothing: `BALL_BEARING_LIFE_EXPONENT`, `BEARING_WEIBULL_SLOPE`,
`NUT_FACTOR_AS_RECEIVED`, `DEFAULT_POISSON_RATIO`, `UNIFORM_WEAR`, `RELEASED_DIRECTORY`,
`DCC_NAMESPACE`, `SI_NAMESPACE`, and the three `*_CITATION` strings, which are rendered into
documents that tests read.

The remaining 44 are result types — `HertzContact`, `ThinWallStress`, `BeamBendingResult`
and their kin. They are exercised by every test of the function that returns them; being
named is not the same as being reached, and this sweep can only see the first.

## Renderings nobody has looked at

Point a coverage run at `__str__` / `render` / `summary` bodies rather than at raise sites:

```bash
.venv/bin/coverage run --source=src/anvilate -m pytest -q
.venv/bin/coverage json -o /tmp/cov.json -q
```

then walk each class and ask whether **any** line of the method body is in the executed
set. On 2026-08-30, **30 of 81 never ran**. The narrowing step is mechanical: parse the
class, list its declared fields, and report the ones the method body never names. Twenty
of the thirty drop at least one field, and most of those are legitimate — a summary is
allowed to summarise. What you are looking for is narrower:

> **the field that tells two different objects apart.**

Render two instances that differ *only* in the dropped field and compare the strings. That
is also the test to leave behind, and it fails for the right reason. Three came out of the
thirty:

| Class | What printed alike |
| --- | --- |
| `ThickWallStress` | A closed cylinder and an open one at the same pressure. The longitudinal stress is the entire meaning of `closed_ends`, and it is zero on one of them — `ThinWallStress` prints the same quantity. |
| `LifterDevice` | Two lifters rated alike and weighing differently. The self weight is what the upper attachment sees on top of the rated load, and BTH-1 screening turns on that difference — the documented example is a bail that passes rated and fails rated-plus-self-weight. |
| `VerificationItem` | An item standing behind one check and the same item standing behind three. `driving_checks` is what the class's own docstring calls the link the matrix exists to make. |

A rendering that never executes is not covered by "the suite is green": nothing asserted
the old strings, so nothing failed when they changed. That is the point of running the
coverage pass rather than reading the methods — each of the three reads like a reasonable
summary and is obvious the moment two instances print side by side.

## Finding a docs page whose numbers nothing checks

The existing ratchet asks whether a page's *filename* appears in a test. That is a
substring gate: a page can be named in a test that never reads a number off it. The
stronger question is behavioural — **change a number on the page; does anything fail?**

Re-runnable sweep, one page at a time:

```bash
python - <<'PY'
import re, subprocess, pathlib
DOCS, TESTS = pathlib.Path("docs"), pathlib.Path("tests")
DISTINCTIVE = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+\.\d{2,})(?![\w])")
text = {p: p.read_text() for p in sorted(TESTS.glob("*.py"))}
for page in sorted(DOCS.rglob("*.md")):
    files = [str(p) for p, t in text.items() if page.name in t]
    original = page.read_text()
    match = DISTINCTIVE.search(original)
    if not files or not match:
        continue
    old = match.group(0)
    new = old[:-1] + ("7" if old[-1] != "7" else "3")
    page.write_text(original[: match.start()] + new + original[match.end() :])
    try:
        run = subprocess.run([".venv/bin/python", "-m", "pytest", *files, "-q", "-x",
                              "-p", "no:randomly"], capture_output=True, timeout=600)
    finally:
        # `git checkout`, not the cached text. Restoring from a variable restores to
        # whatever the file said when this run started — and if a previous run was killed
        # mid-page, that is a mutation. The first version did exactly that, took a stale
        # mutation as the original, and left fifteen pages dirty.
        subprocess.run(["git", "checkout", "--", str(page)], check=True)
    print(f"{'CAUGHT' if run.returncode else 'MISSED'}  {page.name}: {old} -> {new}")
PY
```

It runs the suite once per page, so it is a sweep you run deliberately rather than a gate
in CI. Start from a clean tree and check it afterwards, because a killed run still leaves
one page mutated — the one it was on:

```bash
git status --short docs/
```

Run at HEAD it found two pages arguing from figures nothing checked. `typed-callouts.md`
quotes "a safety factor of 2.52 against 1.08" — the whole argument of the page, stated
twice — while the example asserted only its own Marin factors, so the two numbers a reader
takes away were joined to nothing. `analysis-interop.md` quotes "416,231 times larger
(25.4⁴)", which is not a fixture at all but a conversion the unit layer can do.

### Where it stands

Run at HEAD: **25 of 33 pages caught, 8 missed, and all eight are accounted for.** Before
re-running it in the hope of finding work, read this list:

| Missed | Why it is not a defect |
| --- | --- |
| `export-targets.md`, `valid-is-not-correct.md`, `research/*` (2) | External figures — package versions verified by hand, a paper's own results. On the allow-list in `test_contract.py`. |
| `agent-skill.md` | "governs over one at 99.99%" is rhetoric. Blocking outranks utilization at *every* utilization, so the figure carries no claim; the ordering is gated instead, and the test says why the number is not. |
| `evidence-attestation.md` | The prose quotes `pint 0.24.4` as the stale version a hand-written BOM once attested. A historical example, not a live claim. |
| `thermal-screening.md` | Was "the block states inputs with no computed result beside them". That was true of the block the sweep perturbed and false of the page: the isolator entry further down prints five computed figures, and they are gated now. |
| `timber-screening.md` | "§3.10" is a clause number. The number pattern cannot tell one from a value; two-decimal clause references are the sweep's standing false positive. |

Two limits to hold in mind when reading a CAUGHT: the sweep perturbs each page's **first**
distinctive number only, so a page it clears may still carry unguarded figures further down;
and it runs only the test files that name the page, so a gate living elsewhere is invisible
to it.

## Past the first figure, which is where most of them were

The first limit above is the whole finding. Running the same sweep over **every**
distinctive figure — 344 of them across 32 pages — came back **161 caught, 149 missed**,
and the missed ones were not the leftovers of the caught pages: they were the second half
of an argument whose first number happened to be gated.

Three shapes came back, and only the first is a defect in the usual sense:

1. **The coefficient inside a formula the page prints.** `0.41·B_c/D_c`, `0.25·f'm`,
   `S_u/(1.20·N_d)`, `ρ = (1 − 0.22/λ)/λ`, `F_cE = 0.822·E'_min/(l_e/d)²`. A page that
   prints the formula is claiming it is the one that runs, and the coefficient lives
   nowhere else on the page. The repair is not to compare it to a constant — it is to
   **evaluate the page's own text** and hold the result against the function, which
   catches a coefficient in the wrong row as well as one that moved.
2. **The other half of a rendered block.** Every one of these pages showed a scorecard
   block and a test read one line of it — a safety factor, an allowable — leaving the
   status word, the citation, `required minimum 1.00`, and the clause naming the governing
   limit state attached to nothing. Compare the block **record by record** against the card
   that produced it. That is one assertion loop and it covers every field at once.
3. **A tolerance one ulp too loose.** `approx(1.15, abs=0.02)` against a page stating two
   decimals admits the last digit changing. Match the tolerance to the precision the page
   prints, or the gate exists and does not hold.

And two shapes that are *not* defects, both of which the sweep will report forever:

- **A last-digit change to a large number is below the page's own rounding.** Perturbing
  `686,000 cycles` to `686,007` is a relative change of 1e-5, and a gate that allows the
  three significant figures the page states is right to ignore it. Read a MISSED on a
  6-or-more-digit figure by hand before treating it as work.
- **Narrated history.** `docs/calculation-reports.md` quotes the *wrong* output a fixed bug
  used to print. Nothing in the library should reproduce those, and a gate that pinned them
  would be pinning the bug.

### Where the all-figures run stands

Every gap it found is closed, and each gate was proved by mutating the claim it covers —
about 120 mutations, page side and library side. What is left, and why none of it is work:

| Left MISSED | Why |
| --- | --- |
| `1910.95`, `1926.251`, `§3.10` | Regulation and clause numbers. The pattern cannot tell one from a value; this is the standing false positive. |
| `686,000` / `2,850,000` / `34,700,000` cycles, and the moment and second moment in `calculation-reports.md`'s narrated example | Six or more digits, so the sweep's last-digit change is a relative 1e-5 — under the rounding the page states, and the gates allow exactly that rounding. The same substitution on `citations.md` *is* gated, because that page tells a reader to multiply it out. |
| Everything on `calculation-reports.md` after line 150 | Narrated history: the *wrong* output fixed bugs used to print. Pinning it would pin the bug. |
| `pint 0.24.4`, `pydantic 2.9.2`, the CLI's toolchain line | Version strings in worked output — external, and stale on purpose where the prose says so. |
| The `1234.56789` half of the record-precision sentence, `P(below 2.00)`, `util 0.94` | Illustrations with no case defined above them, so the figure feeds both sides of any comparison. Each gate's docstring says which figures it does not hold; see "an assertion that cannot fail" below. |

Running it over every figure costs ~380 test runs. Spread the pages over independent copies
of the tree (`git archive HEAD | tar -x -C worker/`) and run six at once — but **hold a
tree for the whole page**, since a thread pool hands out threads in completion order and
two pages mutating one copy is silent nonsense rather than an error. Group-testing the
page first (mutate every figure at once; only split if something fails) pays only on pages
where nothing is gated, and costs more than it saves on the rest.

Both are gated now, and both gates read the page rather than a copy of it. Where a page
states inputs *and* a result, rebuild the case from the page's inputs. Where the page's
block *is* the output, state the inputs in the test and compare — reading the values back
out of the rendered block makes the page its own fixture, and it will then agree with
itself however far it drifts.

## The same design, written in two unit systems

Every check here takes dimensioned quantities and converts internally, so the unit the
caller writes should not be able to change the answer. That is a property a sweep can
check, and nothing was checking it.

The sweep: wrap every function in `anvilate.analysis`, `anvilate.standards` and
`anvilate.tolerance`, record one real call each during an ordinary suite run — **1,542
functions** — then replay each recorded call with every argument converted to US customary
base units (`pint`'s `ureg.default_system = "US"`, so a metre becomes a yard and a newton a
pound·yard/s²) and compare the two results field by field. Same physical inputs, different
spelling, and the answers must agree.

One disagreement came back, and it opened a class:

    DIFFER  analysis.coupling.flange_coupling_bolt_count: 4.0  vs  5.0

**An integer count is the answer to a division, and the division is done in floating
point.** 2000 N·m over a 100 mm bolt circle on 5 kN bolts is exactly four bolts; write the
same radius in feet and the quotient is 4.000000000000001, and a bare `ceil` buys a fifth
bolt. Four functions had the shape, and the sweep only reached the first — the other three
take plain floats or fit exactly in metric, so no conversion moves them:

| Function | The exactly-fitting case | Was | Is |
| --- | --- | --- | --- |
| `broaching_teeth_in_cut` | a 6 in workpiece at a 0.5 in pitch | 11 | 12 |
| `flange_coupling_bolt_count` | 2000 N·m, a 100 mm circle in feet, 5 kN bolts | 5 | 4 |
| `minimum_teeth_to_avoid_undercut` | φ = 30°, k = 0.5 (2k/sin²φ = 4) | 5 | 4 |
| `minimum_sprocket_teeth_for_chordal_variation` | the target a 23-tooth sprocket meets | 24 | 23 |

The broaching one is the one that matters: teeth in cut sets the instantaneous cutting
force, so the undercount reported a load 8% below the one the broach actually carries. The
other three err upward, which is harmless in the part and still wrong in the answer.

So: **a whole count comes from `_counting.whole_count_ceil` or `whole_count_floor`, never
from `math.ceil` or `math.floor`.** They snap a ratio within a relative 1e-9 of an integer
onto it and round only what genuinely falls between two — a tolerance far below any
engineering resolution and far above what a conversion and a division accumulate. Pin the
new count on the exactly-fitting case, on a case that truly falls between two integers, and
where the inputs carry units, on the same design written two ways.

Two more results the sweep reported, and neither is a defect. `laminar_boundary_layer_
thickness` and `laminar_skin_friction_coefficient` refused the converted call: their test
input sits *exactly* on the Re = 5·10⁵ transition, so a conversion moves it across a guard
that is correctly there. And `half_sine_shock_amplification` takes `int((1+β)/(2β))` on a
bound that is an integer whenever ρ is a half-integer — ρ = 2.5 computes it as
2.9999999999999996 — but the dropped endpoint is `sin(2πρ)`, which is exactly zero at every
ρ that makes the bound whole, so the term it loses never governs the maximum. Reach the
survivor before writing the excuse; both of these were reached.

### The same harness, pointed at inert arguments

Once every function's real call is recorded, the cheap follow-up is to **nudge each argument
and require the answer to move**. A parameter that is accepted, validated and then never
read is a parameter a caller will believe went into the number.

Run it as written and it reports 143 arguments. Almost all are the fixture's fault, not the
code's, and two rules cut it to **11**:

- **Record four *different* calls per function, and report a parameter only if it is inert
  in every one.** One recorded call is often at a degenerate point — `slider_crank_
  displacement` at top dead centre is zero for any crank radius, `sunset_hour_angle` at the
  equinox is 90° at any latitude — and the parameter is read perfectly well a millimetre
  away.
- **Nudge by ±40%, not 1%.** A parameter that only matters in another branch (`web_thickness`
  in `aisc_plate_girder_flange_stress` reaches the answer through k_c, which a *compact*
  flange never consults) needs a nudge big enough to cross the branch. Take a refusal as a
  reaction: an argument that a guard rejects is an argument that is read.

Of the 11 survivors, ten are the same two shapes one layer down — a classification that a
40% move does not reclassify, or a load combination the recorded case is not governed by.
The one real finding: `bearing_fundamental_train_frequency` and `bearing_ball_spin_
frequency` require a `number_of_rolling_elements` that neither formula contains. The cage
turns at one rate and an element spins at one rate however many elements the bearing
carries; the count is taken so that all four defect frequencies share one set of inputs and
one validation. That is a good reason and it was written nowhere, so both docstrings now say
it and a test pins it — the two ignore the count exactly while BPFO and BPFI scale with it.

Note for the next run: `int` arguments need their own nudge. Scaling an `int` by 1.4 and
rounding is what crosses a band; adding one almost never does, and a threshold parameter
will report inert for that reason alone.

### And once more, for outcomes nothing can produce

Third question for the same recorded calls: **which declared outcomes can no input reach?**
Sweep every numeric argument over 10⁻³ to 10³ around its recorded value, collect the enum
members the functions actually return, and subtract from the members the enums declare.

Read the report with one distinction in hand, because it decides which lines are work:

- An enum that is an **input vocabulary** — `ModuleScope`, `ToleranceClass`, `ServiceClass`,
  `CurveSurvival` — is chosen by the caller, not computed, so a numeric sweep can never
  reach its members and reports them all. Not findings.
- An enum that is an **output classification** is a claim about what the screen can tell
  you, and a member nothing produces is a claim the library cannot honour.

One of those came back. `AluminumLimitState.LATERAL_TORSIONAL_BUCKLING` had **no producer,
no consumer, no test and no docs line** — `grep` over the whole tree found its declaration
and nothing else. `aluminum_compression_strength` computes three states and returns the
smallest, so no input could ever report it, and a caller matching on it wrote dead code. It
is gone, and `_CASES` in `test_aluminum_formulas.py` is now a totality gate: every member of
the enum must be the expected mode of a row, and every row is a case that runs. Beam
lateral-torsional buckling *is* screened — `aluminum_lateral_torsional_moment`, ADM §F.4.2 —
it simply answers with a moment rather than a compressive stress, which is why it never
belonged in this enum.

## The gate that stopped at the package boundary

Section 6 above says changing the public surface is a deliberate act with a diff, and the
gates that enforce it covered `anvilate.analysis` and the top-level modules. Eight
sub-packages had none — and asking the obvious question of each (does the package publish
what its modules declare?) found four that had drifted:

| Package | Withheld | Why it matters |
| --- | --- | --- |
| `units` | `AmbiguousRotationalSpeedError`, `AmbiguousCountRateError`, `OffsetTemperatureError`, and the five converters that close those traps, plus `build_registry` | The package published its unit-error family and not these. You cannot `except` what you cannot import, so telling an ambiguous rpm from any other unit error meant reaching into `anvilate.units.rotation` — a path under no contract at all. |
| `standards` | `WeldDetailCategory`, `WeldStressKind`, `EN1993_NORMAL_DETAIL_CATEGORIES` | The whole EN 1993-1-9 detail-category vocabulary, while the curve function that consumes it was published. |
| `spec` | `Interface` | The discriminated union a caller annotates with, next to both of its members. |
| `spec`, `units` | `Envelope`, `require_finite` | The other direction: published by the package while the module defining them called them private. |

Three gates now, and the shape of the third is the point. **Only the forward direction is
asserted** — every symbol a module declares must be published by its package — because a
package may legitimately re-export from outside its own modules, as `anvilate.report` does
with `Derivation`. The reverse half is covered by a separate gate that every `__all__` name
resolves, which is worth having on its own: `__all__` is checked by nothing at import time,
so a stale name breaks `import *` and nothing else.

`export` and `packs` are exempt, and the exemption is held to its story: 463 example imports
come from `anvilate.units` and none from `anvilate.packs` itself — a pack is addressed by
submodule. So a namespace package must publish **nothing**, which is what keeps the
exemption from becoming a half-aggregating package where some symbols are re-exported and
the rest are invisible.
