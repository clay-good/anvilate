# The export gate, and the watermark on the file

**A DXF is the file a fabricator cuts from. One that does not say it came out of a T1
screen is indistinguishable from a released drawing.** Until this landed, nothing in
Anvilate's export layer knew what a scorecard was: `export_plate_dxf` took a width, a
height and a list of holes, wrote the file, and returned the path.

The `artifact-export` requirement had said otherwise from the start — export is enabled only
when the acceptance checks pass; a caller *may* export an unvalidated part, and then the
file's metadata *and the evidence bundle* must be watermarked as unvalidated.
`anvilate.export.gate` is that sentence as code.

## What a caller does

```python
from anvilate.export.dxf import export_plate_dxf
from anvilate.export.gate import authorize_export

card = screen_lifting_lug(lug, required_safety_factor=1.5)
export_plate_dxf(..., authorization=authorize_export(card))
```

| The card | `authorize_export` | The file |
| --- | --- | --- |
| every check ran and passed | returns a validated authorization | header says `VALIDATED`, carries the screening notice |
| a check passed above its band | returns a validated authorization | same — over-margin is a warning, not a blocker |
| a check failed | raises `ExportRefused`, naming it | no file |
| a check could not run | raises `ExportRefused`, naming it | no file |
| no card at all | raises `ExportRefused` | no file |
| any refusal, with `override=True` | returns an overridden authorization | header says `UNVALIDATED` and names the blocking checks |

## Four decisions worth reading

**The authorization is a required argument.** Every entry point that emits an artifact takes
it as a mandatory keyword. An optional gate is one a caller can omit, and the calls that
omit it are exactly the ungated ones — the same reasoning the MCP tool contracts apply to an
optional subject.

**A check that could not run blocks as hard as one that failed.** The gate reads
`Scorecard.passed`, which is already false while a check is unevaluated. Counting only
`failures()` would have exported a part whose tear-out path nobody dimensioned.

**There is no unwatermarked authorization.** Both branches carry a notice. A clean pass is
still a screen, and saying so is the difference between evidence and a drawing somebody
builds from. The unvalidated line is the *additional* one.

**An override that overrides nothing is an error.** `override=True` on a passing card raises
rather than being ignored, because a no-op override means the caller expected a failing card
and did not get one — usually because they are holding a different card from the one they
handed in.

## Where the watermark lives

DXF gets `$CUSTOMPROPERTYTAG`/`$CUSTOMPROPERTY` pairs in the header — the format's own place
for application metadata, shown by CAD packages under drawing properties, and read back by
`ezdxf.readfile`. It goes in the header rather than on a `TEXT` layer because a layer can be
switched off. QIF gets the same lines at the front of the header `Scope`.

## The bundle half

The requirement watermarks two things: the exported file's own metadata *and* the evidence
bundle. `ExportRecord(artifact=..., authorization=...)` is the second half — a record of
what was emitted and the verdict it carries, collected on `BundleSections.exports`.

It changes the roll-up. Every check on a card can pass and the bundle still read
`NOT_EVALUATED`, because a drawing authorized from no card at all — a callout drawing, say —
is a file in the world with no verdict behind it. Nothing failed; something left unproven.
That disclosure rides into `to_json_dict`, which is the body of the content-addressed
attestation predicate, so it travels with the sealed bundle rather than with the terminal
that produced it. And an empty `exports` is not "nothing was exported": `missing()` names
`export` as a layer the bundle does not speak to, the same way it names an absent
verification plan.

Nothing consults these records before writing a file. They are a disclosure, not a second
permission — the permission is the `authorization` the exporter already required.

## What keeps it there

Four ratchets, each written so that a plausible way around the gate fails the build rather
than passing quietly:

- Every public export entry point whose body writes a file or serializes a document must
  take a mandatory `authorization`. The scan finds the members itself, so a new exporter is
  in scope the moment it is written; the exemption list is checked in the other direction
  too, so a name on it that starts emitting an artifact fails.
- Every `saveas` call anywhere in the export package — private helpers included — must sit
  in a function that takes an authorization, so the write cannot be moved one frame down out
  of the public scan's sight.
- The MCP tool that declares the validation and watermark gates is resolved through its
  `backing` symbol, which must require an authorization. "The MCP surface grants no bypass"
  stops being a sentence in a spec and becomes a claim that can fail.
- The sandbox gate, declared by `build_part`, is asserted to be **undischarged**: that tool
  executes caller-supplied code, names no backing symbol, and the export package contains no
  sandbox. The day an implementation lands, that test fails and somebody has to decide what
  discharges it, rather than the tool quietly acquiring code with no sandbox behind it.

Seventeen mutations were run against the gate in a scratch copy — dropping the unevaluated
checks from the blocking set, treating a missing card as a pass, making `_stamp` a no-op,
freezing the watermark at its clean form, making the authorization optional with a clean
default, removing QIF's cross-check, removing the `model_copy` override, and moving the file
write into a private helper, plus four on the bundle half — the unvalidated artifact no
longer degrading the roll-up, the export section turned informational, the records dropped
from the predicate body, and the absent layer no longer named as missing, and five on the screening
label — the disclaimer dropped from the rendering and from the predicate body, the empty
assumptions list vanishing again in the bundle and in the report, and a blank assumption
accepted. All seventeen were killed.

## What is not gated

The report renderer carries its own disclaimer and is not an artifact the export gate sees.
There is no STEP or 3MF writer yet; when one lands it comes through this gate, and the
ratchet above is what makes that a build failure rather than a review comment.
