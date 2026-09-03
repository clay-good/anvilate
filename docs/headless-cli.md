# `anvilate` on the command line

Three of the four commands `headless-automation` names are backed, and a fifth that
`evidence-attestation` names is backed too. The one that is not is refused by name, with
what it is waiting on.

| Command | Takes | Flags | 0 means |
| --- | --- | --- | --- |
| `check` | one or more specs, or a directory | `--format`, `--show-work` | every check passed, or passed with margin to spare |
| `export` | one or more specs, or a directory | `--artifact`, `--format` | the bundle rolled up clean |
| `verify` | a DSSE envelope | `--artifact`, `--hmac-key-file`, `--format` | signature, digests and predicate all checked clean |
| `diff` | two specs | — | nothing got worse |
| `build` | a spec | — | nothing: it is specified and unbuilt, and exits 4 |

Each command's `--help` states its own exit rule, because what counts as failure differs
between them — `diff` returns 0 on a run where every check fails, as long as none of them
got worse.

```bash
anvilate check part.yaml
anvilate check parts/            # every spec under a directory, recursively
anvilate check a.yaml b.yaml
```

```text
deck_plate: NOT_EVALUATED
  not_evaluated  T1 analytical
                 the Design Spec declares no structural element type, so no discipline-pack screen can be selected from it; build the pack's element and screen that
  governing:     T1 analytical (not_evaluated)
```

**Each check prints the clause it cites**, in brackets under its detail. It is the thing
that separates a scorecard from a spreadsheet, and a check with no clause — a material
resolving, a tier gap — grows no line.

**A failing check prints its repair hint under it**, marked with `→`. Where a design
inverse exists the hint is the value that lands exactly on the required margin — `→ increase
thickness to 12 mm` — so the shell answers "what do I change?" as well as "what failed?". A
check that carries no hint grows no line.

**The governing check is named last because it is what a reviewer reads first.** It is the
check closest to — or furthest past — its limit, and blocking status outranks utilization,
so a check that could not run governs over one at 99% and the card says which. A card with
nothing to govern says *that*: `governing()` is None when nothing blocks and no check
carries a margin, which is an ordinary card of passing deflection checks rather than an
error, and a missing line and a card with nothing to govern must not look the same.

**A directory is searched; a file you name is taken at your word.** The difference
matters. A document *found* by searching that is not a Design Spec is some other YAML file —
a CI config, a lockfile — and is skipped, with a line saying so rather than silently. One you
*named* is an error: you said it was a spec and it is not. An empty search is a bad request
rather than a pass, because "nothing found, nothing failed, exit 0" is the silent green this
command exists to avoid.

**The sweep asks the loader what a spec is**, and it used to ask the `anvilate_spec` key
instead. That key is optional on purpose — see [`anvilate_spec` is a record, not an
assertion](spec-screening.md#anvilate_spec-is-a-record-not-an-assertion) — so a spec written
without one screened when you named it and came back `not a Design Spec, skipped` when the
sweep found it. `examples/padeye.spec.yaml`, the document the README tells you to run, is one.
Over a directory of a passing, a failing and an unevaluated spec all written that way, the
sweep found one of the three and exited 2: a merge gate blocking on exit 1 would have let the
failed part through, and the failure was nowhere in the output.

Declaring `anvilate_spec` is still worth doing, and it is what makes a sweep's refusal
unconditional: a document that *claims* to be a spec is treated as one whatever state it is
in, while a **broken** spec that declares no version is indistinguishable from a stray file
and is skipped like one.

**`check` and `export` search a directory; `diff` and `verify` take a file**, and handing one
of the latter a directory used to answer `[Errno 21] Is a directory: 'specs'`. True, names the
path, and useless — least of all does it say the thing that explains the mistake, which is that
two of the commands *do* take a directory. The refusal names them:

```text
anvilate diff: specs is a directory, and diff takes a file. `anvilate check` and
`anvilate export` are the commands that search a directory for the specs in it.
```

**A file or directory the sweep cannot open is a bad request, not a stray file.** `skipped`
says "this is some other YAML file", and the sweep cannot know that about a file it never
read — so a `*.yaml` it has no permission to open, or a symlink whose target was deleted,
stops the run and names the reason:

```text
anvilate check: specs/bracket.spec.yaml: could not be read (Permission denied), so it was
not screened
anvilate check: specs/private: could not be searched (Permission denied), so the parts in it
were not screened
```

Both used to go green. The file read as a stray one and was reported as such, even when it
declared `anvilate_spec` — the raw-bytes probe cannot read a file it cannot open. The
directory was worse: the search swallowed the error, so a subdirectory of parts produced no
candidates and *no line anywhere in the output*, and from the outside a directory that is
empty and one that cannot be opened look the same. A `latest -> .` symlink is still fine: the
search does not follow directory symlinks, so one part reached twice is counted once.

**A file that will not parse is the third case, and it used to fall into the second.** A
document cannot be recognised by its keys if it cannot be read at all — parsing is what
reveals them — so a broken spec in a searched directory was reported as `not a Design Spec,
skipped` and the sweep carried on to exit 0, over a part nobody screened. The raw text still
tells them apart: one that *says* `anvilate_spec` and will not parse is somebody's broken
spec, and it is a bad request naming the file. A malformed YAML file that claims nothing is
still just a stray file and is still skipped.

A file you **name** that will not parse is a bad request with the position in it —
`line 8, column 1: the document is not valid YAML — found character '\t' that cannot start
any token`. It used to be a stack trace through PyYAML and exit 1, the code that means a
part failed.

**A file that will not *decode* is the same case one layer earlier.** Every document these
commands read is UTF-8, and a file that is not gets a bad request naming what wrote it:

```text
anvilate check: bracket.spec.yaml: is UTF-16 (little-endian), not UTF-8 — every document
this tool reads is UTF-8. Re-save it as UTF-8 (in Notepad, 'UTF-8' rather than 'Unicode').
```

That is the ordinary way to arrive at one — Notepad's "Unicode" save writes UTF-16 with a
byte-order mark — so the refusal names the encoding and the remedy. Without a mark there is
nothing to name and it reports the offending byte and its offset instead, which is what a
binary file named by mistake gets. This too used to be a stack trace, through
`<frozen codecs>`, and exit 1: `UnicodeDecodeError` is raised on the way from bytes to text,
before any parser sees a character, and it descends from `ValueError` rather than from
`OSError` — so it fell through both the guard around the open and the guard around the parse.

In a searched directory the decision is the same as for a broken one, and it is taken on the
raw bytes: a file whose bytes say `anvilate_spec` in UTF-8 or UTF-16 is somebody's spec and
stops the run by name, and anything else is a stray file and is skipped. A thumbnail that
landed in a specs directory is not a part; a spec somebody saved from Notepad is.

**The last line says how much of the run was affected**, not just the worst verdict:
`60 specs: FAIL — 2 failed, 58 passed`. The `N specs: WORST` prefix is unchanged, because a
log filter greps for it, and the counts come after — `60 specs: FAIL` over a run where 58
passed reads as sixty parts that failed, and a reviewer scanning a CI log could not tell two
broken parts from sixty. Blocking counts appear only when non-zero, so an all-passing run
stays `4 specs: PASS — 4 passed` rather than three zeroes to read past. It is the same
argument `Scorecard.__str__` makes one level down about `scorecard FAIL (2 checks)`.

Over many specs each block carries its path as well as its name — two parts in a repository can share one, and a run that printed the name alone gave two identical blocks and no way to tell which was which. A single named spec keeps the bare name, since the caller supplied the path. Over many specs the exit code is the worst verdict found, so one failing part fails the
run — what a merge gate needs.

**Every blocking check goes to stderr**, with the spec it came from, which is what a CI log
shows:

```text
anvilate check: parts/deck.yaml: not_evaluated: T1 analytical — the Design Spec declares no structural element type...
```

A check that could not run is listed too and labelled as such. It blocks exactly as hard,
and calling it a failure would be a different claim. A passing card writes nothing to
stderr at all.

`--format json` prints `{"specs": [...]}` — one object per spec with its path, its name and
its whole scorecard. A list whatever the count, because a shape that changes with the number
of arguments is a shape every caller has to branch on, and the branch is wrong the first time
a directory happens to hold exactly one spec.

`anvilate --version` reports what is **installed**, not `anvilate.__version__`. A script
asking a tool its version is asking what it is running, and a module constant answers what
somebody last typed — the same defect as a hand-written bill of materials, one file over.
The two are kept equal by a gate over all three places the version is written:
`pyproject.toml`, the module constant, and the installed distribution.

### `--show-work` prints the formula behind the number

The text rendering shows a safety factor; `--show-work` shows where it came from — the
governing formula, the values put into it, the result, and a line per symbol:

```text
  pass           padeye net tension
                 safety factor 6.67 vs required minimum 2.00
                 [ASME BTH-1 §3-3]
                   σ_t = P / ((W − d) · t)
                   σ_t = 60.0 kN / ((120.00 mm − 40.00 mm) · 20.00 mm)
                   σ_t = 37.5 MPa
                 where:
                   P = 60.0 kN  (lifted load)
                   W = 120.00 mm  (lug width across the hole)
                   d = 40.00 mm  (pin hole diameter)
                   t = 20.00 mm  (lug plate thickness)
                   σ_t = 37.5 MPa  (net-section tensile stress)
```

It is the same block [the calculation report](calculation-reports.md) prints, through the
same renderer, so the two cannot drift — **and in the units the spec declares.** A document
saying `units: US` prints its work in kip, inches and ksi; one saying `SI` prints mm and
MPa. That line of the document says what its reader works in, and `check` used to read past
it. `--format json` has always carried the derivation;
this is the half a person reads. A check with no derivation prints
`[derivation not rendered]` rather than being left out — a check missing from the listing
reads as one whose formula was not worth showing, and those are different things. Where the
check states *why* it has none, the reason prints on the same line:
`[derivation not rendered — Service Class 0 is the standard's own exemption from fatigue
analysis…]`. Nothing is owed there, and the label alone could not say so.

## The exit code is the interface

A CI job reads the code, not the text, so the code follows the scorecard's own rule rather
than collapsing to pass/fail:

| Code | Meaning |
| --- | --- |
| 0 | every check passed (or passed with margin to spare) |
| 1 | a check failed |
| 2 | the card could not be fully evaluated — **not a pass**, and not a failure |
| 3 | the request was wrong: a usage error, a missing file, a document that is not a spec |
| 4 | the operation is specified but unbuilt |

### The JSON says what the text says

`--format json` used to carry the checks and nothing else — not the card's verdict, and not
the governing check. The verdict is recoverable from the exit code. **`governing` is not
recoverable at all**: it is the worst check by a specific ordering, and a consumer left to
work it out from `entries` is reimplementing `Scorecard.governing()` at every call site that
reads this output. Both are carried now, per spec and for the run:

```json
{"status": "fail",
 "specs": [{"name": "deck_plate", "path": "a.yaml", "status": "not_evaluated",
            "governing": {"name": "T0 geometry", "status": "not_evaluated"},
            "scorecard": {"entries": ["..."]}}]}
```

`verify --format json` was missing three of the report's conclusions for the same reason —
`status`, `attested`, and the toolchain the envelope records are computed rather than
stored, so a plain model dump left all three out. **`attested` is the consequential one.** A
consumer reading `signature_state: symmetric_verified` and nothing else concludes the
envelope is attested, which is exactly what the text headline exists to correct: a shared
secret proves the envelope was not altered and says nothing about who made it. All three are
carried, and one reader supplies the toolchain to both renderings.

`export` carries the same roll-up: `status` at the top of the payload, a
`N bundles: WORST` line at the end of the text, and the exit code — all three from one
computation, because three renderings of one run that can disagree eventually will.

`governing` is `null` rather than absent on a card with nothing to govern — an ordinary card
of passing checks that carry no safety factor — because a missing key and a card with
nothing to govern must not look the same. That is the rule the text line already followed.

### An unbuilt operation is refused however it is invoked

`anvilate build` said what it was waiting on and exited 4. `anvilate build part.yaml` — the
thing a reader of that help actually types — answered `unrecognized arguments: part.yaml`
and exited 3, which this table defines as *the request was wrong*. The request was not
wrong; the operation is unbuilt.

There is no invocation of an unbuilt operation that would be correct, so everything after
the command name is now accepted and ignored, and the answer is the same reason and the same
code every time. `--help` still exits 0: asking what a command is waiting on is not invoking
it. The built commands are untouched — a missing spec is still a bad request.

### A code 3 has to say what to write

The likeliest way to get one is a hand-written document, and the likeliest mistake in one is
writing a provenanced value bare:

```yaml
units: SI                 # what you would naturally write
units:                    # what the IR asks for
  value: SI
  origin: user_stated
```

Every value in a compiled spec carries where it came from, so `units` is a wrapper rather
than a scalar. The first form used to be refused with `Input should be a valid dictionary or
instance of Provenanced[UnitSystem]` — pydantic's own message, naming a Python generic to
somebody holding a YAML file, on this command and on the MCP `compile_spec` surface alike.
It now names the shape to write, the three legal origins, and the one that also needs a
rationale.

A bare value is **not** taken as `user_stated`. Where a number came from is what the wrapper
records, and inventing an origin for one that states none is the same silent green the
scorecard refuses to give.

**Code 2 is the one that matters and No-silent-green settles it.** A screen that could not
run is not a screen that passed, so a merge gate on `anvilate check` must not go green on
it. Keeping it distinct from 1 lets a caller that genuinely wants "nothing failed" say so
deliberately, in one place, rather than getting it by accident everywhere:

```bash
anvilate check part.yaml || [ $? -eq 2 ]   # accept a not-evaluated card, on purpose
```

**What counts as failure differs per command, and each `--help` says so.** The program's
own description used to state `check`'s rule — "exit 0 only when every check passed" — as
though it were the program's, and it is false for `diff`, whose 0 means nothing got worse
and which returns it on a run where every check fails. The first thing a user reads was
contradicted by a command in the same help output.

**A usage error is a bad request, not a verdict.** `ArgumentParser.error` exits 2,
hardcoded — so for one commit `anvilate frobnicate`, `anvilate` with no command, and
`anvilate check` with no file all came back with the code the line above tells a CI job it
may accept, and a typo read as a screen that ran and could not conclude. Every usage error
is 3 now. `--help` still exits 0, because asking for help is not a failure.

The mapping is a total map over the four scorecard statuses, so a fifth status is a
decision somebody has to make rather than a silent zero.

## `anvilate export`

```bash
anvilate export part.yaml              # the evidence bundle, rendered
anvilate export parts/ --format json   # one bundle per spec in the tree
```

`export` takes the same paths `check` does — a file, several files, or a directory searched recursively — because CI publishing bundles for a repository should not be a shell loop in a script nothing type-checks. The evidence bundle is assembled from a scorecard, so it needs no geometry — and the exit
code is the bundle's own roll-up, which is never better than its worst section.

**What comes out is the document, not the roll-up.** For a long time this command printed
`BundleSections.render()` — the layer summary, whose checks line says `3 run, 1 failing`
and names none of them. A reviewer holding that output could not tell which check failed,
at what margin, or against which clause. It prints `render_document()` now: the same
roll-up, then every check with its detail and its citation, then the spec those verdicts
were computed from, then the disclaimer. The spec block is the YAML you can paste back into
`anvilate check`: a reviewer holding only this output can re-run the analysis and get the
same card, which is the scenario `artifact-export` asks for and a test now performs. See
[the evidence bundle](evidence-bundle.md) for why the roll-up still exists. A DXF or a
QIF results file does need a built part, and each is refused by name:

```text
anvilate export --artifact dxf: a DXF is drawn from built geometry, and there is no built
part to draw. See openspec/specs/geometry-generation.
```

The three artifact names are the same three `export_artifact`'s published MCP schema
declares, held equal by a test — a CLI offering a fourth, or silently dropping one, is a
surface saying something different from the contract. The two surfaces now agree on more
than the names: `export_artifact` returns the same bundle document for the same spec, the
two are compared by value in `tests/test_surface_parity.py`, and the MCP handler reads the
refusal reasons above out of this module rather than restating them. The difference that
remains is where the document goes — the CLI prints it, and the tool returns it and writes
nothing at all, because a path an MCP client names is a capability the server does not
grant. Dropping one is how this went wrong
the first time: `export` was refused whole on the reasoning that it "writes a downstream
artifact from a built part", which is true of a DXF and false of the bundle. A refusal wide
enough to cover something that works is as misleading as a missing one.

**The bundle goes to stdout, and that is deliberate.** Every artifact-emitting entry point
in the package takes a mandatory `ExportAuthorization` ([export gating](export-gating.md)),
and there is no bundle *writer* behind that gate. Printing is not emitting — a caller
redirecting the output is doing their own act — and a file-writing path here would be the
first one outside `anvilate.export`, which is exactly the bypass the gate exists to prevent.
A test asserts the command creates no file anywhere.

## `anvilate verify`

`evidence-attestation` requires "a verification command that checks signature, subject
digests, and predicate schema". The library has done all three since the attestation layer
shipped; nothing at the shell called it.

```bash
anvilate verify attestation.json \
  --hmac-key-file key.bin \
  --artifact scorecard.json=out/scorecard.json \
  --artifact lug.dxf=out/lug.dxf
```

```text
PASS  attested=False
  signature   symmetric_verified
  bundle      46802dedaa2fe2a7ac0e3628221fb482b08da7f5d7b996a0ccfd8de975f3cf63
  predicate   https://anvilate.dev/attestation/screening/v1
  checked     scorecard.json, lug.dxf
  unchecked   none
  produced by anvilate 0.0.1
  toolchain   anvilate_materials 2026.03, ezdxf 1.4.4, pint 0.25.3, pydantic 2.13.5, pyyaml 6.0.3
  note        a symmetric key proves the envelope was not altered, not who made it — anyone holding the key could have, so this is not attestation
```

**A malformed envelope is refused, never a traceback.** An envelope arrives from somewhere
else, so it is untrusted input: a file that is not JSON, an object with none of the DSSE
fields, a payload that is not base64, and a payload that is valid base64 over bytes that are
not JSON all come back as a refusal with the reason. The last of those used to produce the
right report — "the envelope payload is not readable JSON" — and then raise on the way to
printing it, because both renderings re-parse the payload to read the attested toolchain.

**The toolchain is read out of the envelope, not out of the machine.** The requirement's
own scenario says an engineer running this "confirms the signature, that artifact digests
match, and reports the toolchain versions attested" — and a verifier on a different machine
with different versions installed must still be told what *produced* the artifact. An
envelope attesting no toolchain reads `none attested`, for the same reason the report's
headings never vanish.

Three things this command will not do, and they are the reasons it exists:

- **A signature nobody could check is not a pass.** Without `--hmac-key-file` the state is
  `not_checked` and the exit code is 2. Reporting that as success is the single worst thing
  this command could do.
- **A subject with no file is reported unchecked, never assumed to match.** The `checked`
  and `unchecked` lists both always render, because a run that checked nothing and one
  whose subjects all matched must not look the same.
- **A symmetric signature is not attestation.** `attested` is True only for an
  authorship-establishing signature. A shared secret proves the envelope was not altered by
  anyone without the key and proves nothing about who made it, so a fully checked symmetric
  envelope reads PASS with `attested=False` — and the reason is printed, because that pair
  without it invites exactly the wrong conclusion.

Only local symmetric keys are supported: `LocalHmacSigner` is what this package ships.
Keyless and asymmetric verification are unimplemented, and the command says `not_checked`
rather than pretending otherwise.

## `anvilate diff`

```bash
anvilate diff before.yaml after.yaml
```

```text
deck_plate → deck_plate

SPEC
  -description: A mezzanine deck plate.
  +description: A mezzanine deck plate, revised.

VERDICT  pass → fail

CHECKS
  ! bending: pass → fail
      the moment exceeds the section
  (2 unchanged)

GEOMETRY
  not compared: mass, volume and centre-of-gravity deltas need two built parts. See openspec/specs/geometry-generation.
```

The requirement asks `diff` to compare "two builds of a part **(or a spec change)**", and
the parenthesis is the whole of what is possible without a geometry kernel — and the half a
merge gate reads, since the scenario is a commit that changes a shared pattern and makes a
downstream part fail.

**The diff is of the spec, not of the file.** Two documents that differ textually and
compile to the same IR are *no change* — a reordered mapping, a comment, a requoted string
are edits to a file and not to a design, and a review comment that reports them buries the
change that matters. `git diff` is the tool for the other question.

**The exit code is about what got worse, not about the new card.** A part that was already
failing and still fails has not regressed, and a diff that failed the build for it would
fail every build until somebody fixed an unrelated part. So the code is the worst *new*
status among checks that moved for the worse, and 0 when none did — with a regression to
`not_evaluated` counting, because a check that used to run and now cannot has got worse.

A check present in only one card is reported as added or removed. A different set of checks
is not a worse set, and calling it either would be a guess.

**The card's own verdict is compared too, and that is not a guess.** A revision that renames
the element deletes every check by name and adds a not-evaluated gap in their place: nothing
"moved for the worse" under a name-by-name rule, and the part went from screened to
unscreened while `diff` exited 0. `VERDICT before → after` is on the card and counts toward
the exit code, because a different *verdict* is a worse verdict and `Scorecard.status` is
defined for exactly that comparison.

**And "worse" is not the order the card blocks in.** That comparison first used
`_BLOCKING_ORDER`, which sorts `fail` above `not_evaluated` because a failure is the thing to
look at first — so `fail → not_evaluated` read as an *improvement*, and `diff` exited 0 over a
change that deleted two failing checks. Delete the spec's `element_type`, or the `constraints`
the checks are judged against, and the failing part came back "nothing regressed" while the
rendering three lines above said `- padeye net tension: removed (was fail)`. Deleting the
thing being checked is how a failing gate gets silenced, so it is the one change a gate must
never call an improvement.

So **`fail` and `not_evaluated` are incomparable**, and moving either way is reported. One
loses the check, the other reveals a failure; neither is an improvement, and no single ranking
of the four statuses can say that. A genuine repair still exits 0: `fail → pass` is an
improvement and reads as one.

**The geometry half is named rather than omitted**, for the same reason the unbuilt command
is named rather than left unknown: a reader who sees no mass delta should be told there is
none to be had, not left wondering whether the mass was equal.

## The one that is refused

`build` needs a built part, and the geometry kernel is not in this package. It is a named
subcommand that exits 4 and says what it is waiting on:

```text
anvilate build: build runs the part's generating program, which needs a geometry kernel
this package does not ship. See openspec/specs/geometry-generation.
```

The alternative — leaving it out — makes the shell report `unknown command: build`, which
tells a script author they typed it wrong. They did not; the operation is specified and
unbuilt, and that is a different thing to be told. It is the same rule the
[MCP surface](mcp-tool-contracts.md) follows for the operations it cannot serve.

## Running it in CI

`.github/actions/check` is a composite action that installs Anvilate and screens a whole
repository:

```yaml
- uses: anvilate/anvilate/.github/actions/check@main
  with:
    path: parts/
    report: anvilate-report.json
    bundles: anvilate-bundles.json
```

| Input | Default | What it does |
| --- | --- | --- |
| `path` | `.` | The file or directory to screen. A directory is searched recursively. |
| `python-version` | `3.11` | The Python to install Anvilate under. |
| `allow-not-evaluated` | `false` | Accept exit code 2 as a pass. |
| `report` | (none) | Where to write the JSON scorecard report. |
| `bundles` | (none) | Where to write the JSON evidence bundles. |

**`allow-not-evaluated` is off by default and that is the whole point.** A screen that
could not run is not a screen that passed, and a merge gate treating the two alike is the
silent green this tool exists to avoid. Turn it on only while a known gap is being closed,
and the action prints a warning annotation when it fires.

The report and the bundles are written *before* the verdict is decided, so a failing run
still leaves both — a CI job that fails and produces no artifact is a job somebody has to
re-run to understand. `headless-automation` asks CI to publish evidence bundles as outputs,
and the bundle roll-up is never better than its worst section, so it is the artifact a
reviewer reads when the run fails rather than a nicety.

The action's script is the least-tested code in most repositories: nothing imports it,
nothing type-checks it, and it runs for the first time on somebody else's pull request. So
`tests/test_ci_action.py` resolves it against the CLI — every flag it passes must exist,
every environment variable it reads must be bound, and the exit codes its comment documents
must be the ones `EXIT_CODES` can actually produce.

**The container image the requirement also names is not shipped.** Building one is not
something this repository can test: the suite runs with the socket layer closed, and a
`docker build` is a network operation whose result no offline gate can check. An image
published without a gate on what it contains is the kind of claim the rest of this project
refuses to make. Installing the package is what the action does, and it is what the
documentation recommends until an image can be held to something.

**And the install line had the same problem from the other side.** The action ran
`pip install anvilate`, which is what a published tool's action does — and there is no
`anvilate` on PyPI. The index answers 404 for it. Every flag the action passes was resolved
against the CLI and every exit code against `EXIT_CODES`, and the one line that runs before
any of them would have failed for every user of the action. Asking whether each part of an
instruction is right is not the same as asking whether the instruction is true.

So the action installs the repository — `anvilate @ git+https://github.com/clay-good/anvilate@<ref>`
— and takes a `ref` input so a caller can pin a tag instead of tracking `main`. It works
today, which is the whole of the argument for it. The scheduled `pypi-availability` job is
what will say when to change it back: it asks the index whether the distribution exists and
fails **either way round** — if `anvilate` is published while the action still installs from
git, and if the action names PyPI while the index has nothing. A gate that fired in only one
direction would leave this exact state sitting unnoticed a second time.

