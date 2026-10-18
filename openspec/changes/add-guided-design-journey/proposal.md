# Change: The design journey — from a sentence to a review-ready package, with the next step always named

## Why

Today's happy path is three steps and five journeys (check, draw, export, context,
combination), each two to four calls. They work, and they stop at a single part or one
combination. The question an engineer actually brings is bigger: *"design me a two-stage
reducer, 1.5 kW in, 60 rpm out, check it, simulate the housing, make it lighter, and give
me something I can put in front of the lead."* The pieces for that are specified or
built, but nothing connects them, so the agent has to discover the order itself:

- **It cannot tell what is left.** A scorecard says what passed and failed. It does not
  say that the FEA tier was never asked for, that a placeholder still stands in for the
  motor, or that a failed check has an inverse the agent could apply in one call. An
  agent that reads `PASS` on a T1 card and stops has done exactly what the result told it.
- **It has no finish line.** "Done" is wherever the agent decides to stop. There is no
  state that means *ready for an engineer to review*, so a session ends on a passing part
  with half its claims never screened, or loops on repairs nobody asked for.
- **The first run is a part, never a product.** Every sample in the gallery is a single
  part. The capability that is hardest to believe (a product built, screened, simulated
  and improved without a human touching it) is the one a new user never sees.
- **The optional pieces fail silently.** The FEA solver is the clearest case:
  `anvilate doctor` fails on every install because of it, and the remedy is not one a
  user can act on from the message.

The user's request for this change was explicit: *can Anvilate take a product from a
description to an optimized, simulated design before a human engineer ever clicks a
button?* The answer this change gives is **yes, up to the review**: the agent can drive
everything to a review-ready package with no human step, and the one deliberate human
action that remains is the review itself, which `responsible-charge-review` already
makes explicit, recorded and scoped. That boundary is the product, not a limitation:
it is the thing that makes the automated part trustworthy.

## What Changes

| Area | Change |
| --- | --- |
| The next step, typed | Every workflow tool result carries `next`: an ordered list of typed steps (`tool`, the argument to pass, and a one-line reason), derived deterministically from the card. A failing check with an inverse yields "apply this repair"; a demanded tier that did not run yields the tool that runs it; an all-pass card yields "export the review package". Never prose the agent must parse, never a model's suggestion. |
| Journey state | A product or part result states which stage of the journey it has reached: `described`, `screened`, `simulated`, `optimized`, `review_ready`, each with the gaps that hold it back. `review_ready` means every claim the document makes has a verdict, no `NOT_EVALUATED` entry stands without a declared reason, and the review package is written. |
| The design journey | A sixth measured journey, *design a product*, walked in a test and by real agents: describe a product, screen it, apply inverses, run FEA where the spec demands it, optimize under a stated budget, export the review package. Its call count and wall-clock are budgeted like the others. |
| Review package | One export (`export_artifact` with format `review_package`) writes the evidence bundle, the reviewer dossier, the release-package files and the study record into the output folder, and returns their paths. It is the finish line of the journey and the input to the human review. |
| A first product | The gallery gains a worked product: the two-stage gear reducer from `add-product-structure`, set up so one request takes it through the whole journey offline (with FEA marked not evaluated when no solver is installed, and saying how to add one). |
| Optional pieces say how | Every optional capability (FEA solver, mesher, PDF reader, DXF writer) is reported by `doctor` and by the tool that needs it as *optional, not installed*, with the one command for the user's platform. A missing optional capability never fails `doctor`. |

## Impact

- Affected specs: `onboarding` (ADDED), `headless-automation` (ADDED).
- Builds on: `add-product-structure` (the worked reducer), `add-local-fea` (the simulate
  stage), `add-design-optimization` (the optimize stage), `add-drive-trains` (the
  reducer's own checks), `add-release-package` and `responsible-charge-review` (the
  package and the review it feeds), `trim-agent-tool-set` (this change adds no tool:
  `next` and journey state ride on existing results, and the review package is a format
  of the existing export tool).
- Compatible with `simplify-visual-output`, which modifies the same onboarding
  requirements for the agent-only surface; this change only adds requirements.
- Explicitly out:
  - An agent loop inside Anvilate. The user's agent drives; Anvilate only names the next
    step (D2).
  - Any automatic sign-off, approval or release. `review_ready` is a state of the
    evidence, not a decision about the design.
  - A chat or wizard interface (D5).
