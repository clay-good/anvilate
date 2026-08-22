<!-- BEGIN OPENLORE (managed — edits inside this block will be overwritten) -->
<!-- openlore-fingerprint: 25cdd746ebf39b56 -->
This project uses OpenLore for persistent architectural memory.

ALWAYS call `orient()` (via the openlore MCP server, or `npx openlore orient --json`)
before reading source files when starting a new task. This returns the relevant
functions, callers, spec sections, and insertion points for the task at hand —
one structural lookup instead of file-by-file rediscovery.

OpenLore prefixes tool responses with a brief, factual freshness note (the
Epistemic Lease) once your cached context has aged or the repo has moved since
your last `orient()`. It is informational — re-`orient()` if you are relying on
cached cross-module structure; otherwise carry on.

For the MCP setup, ensure `openlore mcp` is configured as an MCP server.
See https://github.com/clay-good/OpenLore for details.
<!-- END OPENLORE -->

## Using Anvilate correctly

Anvilate turns a described part into a **scorecard**: one typed result per check, each
citing the clause behind it. It is a T1 analytical screening library — closed-form,
unit-checked, fast — and it is not a certified analysis.

The full guidance, with a worked example for every rule, ships inside the package at
`src/anvilate/skills/anvilate/SKILL.md` (installed as `anvilate/skills/anvilate/SKILL.md`,
so it is available offline). Read it before driving the library. The six rules it expands
on, in short:

- **Retrieval, not recall.** Standard dimensions come from the bundled databases with
  their citations attached. A refusal names the near misses; do not answer it with a
  remembered number.
- **Read the scorecard.** Report `Scorecard.status` and `governing()`, not an impression
  of how the calculation went.
- **Not evaluated is not a pass.** A check that could not run is `NOT_EVALUATED`, a card
  containing one is never `passed`, and "two of three checks pass" is a true sentence that
  reads as a passing part.
- **Inverse first repair.** A failing check carries a repair hint; where a design inverse
  exists it solves for the value that lands exactly at the required margin. Use it before
  guessing sizes, and say out loud when you round to a stock size.
- **Confirm before use.** Values read from a requirements document or a calibration
  certificate are drafts. `release()` refuses until a named person confirms them — do not
  read the drafts directly, and never make the confirmation decision for the user.
- **Screening, not certified.** Say what a green scorecard is: the closed-form checks that
  ran were satisfied by the inputs given. Report what the evidence bundle says it does not
  cover.

The skill is documentation. It grants nothing, loosens no gate, and changes no result;
identical calls behave identically whether or not it was loaded.
