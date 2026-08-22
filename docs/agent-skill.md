# The agent skill: teaching coding agents to use Anvilate correctly

**An agent with tool access and no procedural guidance gets Anvilate wrong in four
predictable ways — and the artifact it produces still carries Anvilate's evidence bundle.**

The library already refuses the dangerous things. What it cannot do on its own is stop an
agent from *reporting* a screening result as a certified one, or from recalling a bolt
dimension after a database lookup refused. So Anvilate ships a first-party agent skill:
`src/anvilate/skills/anvilate/SKILL.md`, installed inside the package as
`anvilate/skills/anvilate/SKILL.md`, in the open SKILL.md convention, available offline.

```python
from anvilate.skills import SKILL_PATH, skill_text
```

The repository-convention half is the "Using Anvilate correctly" section of
[`AGENTS.md`](../AGENTS.md), which reaches agents that read the repo but never install the
package.

## The six rules

| Rule | What goes wrong without it |
| --- | --- |
| Retrieval, not recall | A remembered width-across-flats is a number with no provenance, and provenance is the whole product |
| Read the scorecard | "The calculation went fine" is not a verdict; `status` and `governing()` are |
| Not evaluated is not a pass | "Two of three checks pass" is a true sentence that reads as a passing part |
| Inverse-first repair | Guessing sizes when a design inverse solves for the exact margin in one call |
| Confirm before use | Reading draft values directly, or confirming them on the user's behalf |
| Screening, not certified | A green scorecard reported as a stamped analysis |

## It grants nothing

The skill is documentation. Loading it enables no capability, loosens no validation or
export gate, and changes no result — every rule in it is enforced by the library whether
or not it was read. That is why it can ship as plain text with no privilege attached.

## Why it cannot go stale

Documentation about a moving API rots silently, so the skill is bound to the library by
CI rather than by good intentions ([`tests/test_agent_skill.py`](../tests/test_agent_skill.py)):

- **Every `anvilate` symbol it names is imported.** A renamed function fails the build
  naming the stale reference, rather than shipping as advice.
- **Every worked example is executed**, each in a fresh namespace, and its stdout is
  compared byte for byte against the output the skill claims. An example whose output
  drifts is a failing test.
- **Every doctrine is anchored to an example.** Each rule carries an
  `<!-- doctrine: ... -->` marker, and the gate requires a runnable example inside that
  section. The examples' own assertions are what carry the claims — `assert card.passed is
  False` proves "not evaluated is not a pass" in a way no paragraph containing those words
  can.
- **Prohibited guidance fails the build.** Instructions to skip validation, bypass a gate,
  export past a failure, or present a result as certified are matched and refused. That
  gate is proved to fire, against a deliberately offending text, in the same file.

The doctrine gates are deliberately not keyword checks. A gate that greps for "not
evaluated" is satisfied by any paragraph containing the phrase, including one that states
the rule backwards — and a gate satisfiable by ordinary prose is worse than none, because
it reads as coverage.

The prohibition gate runs the other way and is sound as text matching: it can only fire,
never be satisfied. Two of its seven patterns are marked negatable, because the skill is
*required* to say it is not a certified analysis and not stamped by anybody; the other
five are instructions, and there is no sentence in which "skip the validation" is
acceptable guidance.

## What is not claimed

The skill targets the Python API, because that is the surface that exists today. When the
CLI and the MCP server land ([`headless-automation`](../openspec/specs/headless-automation/spec.md)),
the skill gains their workflows and the drift gate extends to their published schemas.
Measuring whether shipping the skill improves an agent-driven funnel needs the
benchmarking harness and has not been done.
