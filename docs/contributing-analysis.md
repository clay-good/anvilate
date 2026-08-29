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

A line-trace of the suite says **around 56% of the roughly 4,300 `raise` sites in the imported modules
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
comparison inline. `tests/test_fraction_guards.py` trips 32 of these guards one at a time
and then passes a value just inside each bound, because a guard that refuses everything
passes a refusal test exactly as well as a correct one.

That file is also the ratchet. It re-derives the census from the source — following a
parameter into the helper it is validated by, which is the whole difference between a
census and a list of false positives — so a new function taking one of these parameters
without a guard fails there rather than shipping. **5 parameters are exempt**, each with
the reason its name lies about its range: a spectral efficiency is bits per second per
hertz, a molar absorptivity (in two functions) is tens of thousands, a heat pump's
seasonal efficiency is its COP of 3 to 4, and excess air routinely runs past 100%. An exemption that turns out to be
guarded after all fails as stale.

Writing it found one hole: the AISC J2.4 weld shear fraction guarded positivity and not
its upper bound, so `6` for `0.6` returned ten times the weld capacity with every other
check satisfied — the unsafe direction for a screen to be wrong in.

## Two sweeps that came back clean

Both were run at HEAD and found nothing. Recorded so the next person spends the afternoon
somewhere else.

**Numbers narrated in `examples/` docstrings.** The ratchet in `test_examples.py` requires
every example quoting a figure to call `_assert_narrates`, which checks each narrated number
against a computed value **in both directions** — a quoted figure with nothing behind it
fails, and a computed value no figure uses fails too. Confirmed behaviourally rather than
read: a sampled docstring number perturbed in four examples failed the suite every time.

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
| `thermal-screening.md` | The block states inputs with no computed result beside them, so there is nothing on the page to disagree with the library about. |
| `timber-screening.md` | "§3.10" is a clause number. The number pattern cannot tell one from a value; two-decimal clause references are the sweep's standing false positive. |

Two limits to hold in mind when reading a CAUGHT: the sweep perturbs each page's **first**
distinctive number only, so a page it clears may still carry unguarded figures further down;
and it runs only the test files that name the page, so a gate living elsewhere is invisible
to it.

Both are gated now, and both gates read the page rather than a copy of it. Where a page
states inputs *and* a result, rebuild the case from the page's inputs. Where the page's
block *is* the output, state the inputs in the test and compare — reading the values back
out of the rendered block makes the page its own fixture, and it will then agree with
itself however far it drifts.
