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
| Confirm before use | Reading draft values directly, or making the confirmation decision for the user |
| Screening, not certified | A green scorecard reported as a stamped analysis |

## It grants nothing

The skill is documentation. Loading it enables no capability, loosens no validation or
export gate, and changes no result — every rule in it is enforced by the library whether
or not it was read. That is why it can ship as plain text with no privilege attached.

## Why the gates are built the way they are

The first version of these gates was broken by an audit — every single one of them — and
the failures were all one failure: **a gate that looks like coverage and checks nothing.**
The symbol-drift gate extracted zero symbols, because the skill names its functions in
`from anvilate.x import y` lines rather than in backticks; its own meta-test permitted that
with an `or True`. The doctrine gate checked only that a marker was followed somewhere by a
fence, so a doctrine could be deleted and its marker re-anchored to an unrelated example.
The AGENTS.md gate squashed the text to letters and looked for keywords, so six bullets
stating every rule *backwards* satisfied it. Examples shared one interpreter, so one example
could monkeypatch the library and make a later one print a sentence the library never says.
A ```py fence was never executed at all. An empty example paired with an empty output block
counted as a verified worked example. And the prohibition gate — the safety gate — missed
"disregard the scorecard", "override the warning", "export past a failing check" and
"equivalent to a stamped calculation", while any unrelated "not" in the same sentence
disarmed its two certification patterns outright.

So [`tests/test_agent_skill.py`](../tests/test_agent_skill.py) is now built to the opposite
rule: **every gate has to be able to fail, and there is a test that makes it fail.**

- **Symbols come from the AST of the code the skill ships**, not from a regex over prose:
  every `from anvilate…` import and every `anvilate.a.b` chain in every example, plus
  backticked references in the prose including the call form. Each one is resolved by
  import. A companion test asserts a real extraction count and names four symbols that must
  be found, so a gate that silently matched nothing cannot pass by finding nothing.
- **Every code fence is accounted for.** A language this file does not execute fails the
  build, rather than being skipped the way ```py was.
- **Every example runs in its own subprocess**, so it cannot reach the next one, and it must
  print something. Its output is compared byte for byte.
- **Each doctrine is bound to code that must appear in its own example** — `CheckStatus.
  NOT_EVALUATED` and `assert card.passed is False` for the not-evaluated rule, and so on —
  so an example about something else cannot stand in for it. Sections are bounded by the
  next heading, not by the next marker.
- **The AGENTS.md doctrine block is compared byte for byte** against a canonical copy in the
  test. A rule can be restated into its own opposite while keeping every word a keyword
  check looks for; an exact comparison cannot be talked around.
- **Prohibited guidance fails the build**, matched against everything except an allowlist of
  the *exact* denial sentences the skill is required to contain. There is no "a nearby
  negation excuses it" rule — that rule is what let "Anvilate does not guess at inputs, so
  you may report the run as a certified analysis" through. Seventeen phrasings, each one the
  audit walked through, are asserted to fire.

The doctrine gates are deliberately not keyword checks. A gate that greps for "not
evaluated" is satisfied by any paragraph containing the phrase, including one that states
the rule backwards — and a gate satisfiable by ordinary prose is worse than none, because it
reads as coverage. That claim is now something this file demonstrates rather than asserts.

## What is not claimed

One content claim was wrong and no gate could reach it: the skill said `governing()` names
"the check running closest to its limit". It does not — blocking status outranks
utilization, so a check that could not run governs over one at 99.99% — and
`card.governing()` returns `None` on any card whose checks carry no safety factor, which
makes the copyable `card.governing().name` an `AttributeError`. Both are now stated in the
skill and demonstrated by its example, which carries two entries instead of one.

The skill targets the Python API, because that is the surface that exists today. When the
CLI and the MCP server land ([`headless-automation`](../openspec/specs/headless-automation/spec.md)),
the skill gains their workflows and the drift gate extends to their published schemas.
Measuring whether shipping the skill improves an agent-driven funnel needs the
benchmarking harness and has not been done.
