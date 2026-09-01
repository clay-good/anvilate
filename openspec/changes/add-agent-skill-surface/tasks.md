# Tasks: Agent skill surface

## 1. Content

- [x] 1.1 Skill covering: compile + confirm, retrieval-not-recall, run gauntlet, read
      scorecard, "not evaluated" != pass, inverse-first repair, export gate + disclaimer —
      six doctrine sections, each anchored by a marker and carried by a runnable example.
      The gauntlet/export half is scoped to the surface that exists: there is no CLI or MCP
      server yet, so the skill teaches the Python API and the evidence bundle's own gate
      (a plan with nothing performed is NOT_EVALUATED; `verified` is false) rather than
      describing an `anvilate export` that nobody can call
- [x] 1.2 Repository-convention instruction file for coding agents — the "Using Anvilate
      correctly" section of AGENTS.md, below the OpenLore managed block, with a CI gate
      that fails if it is written inside the block that gets overwritten
- [x] 1.3 Version + targeted tool-surface version stamped in both — frontmatter `version`
      must equal `anvilate.__version__`, and `tool-surface` must name the manifests the
      drift gate checks against

## 2. Packaging

- [x] 2.1 Ship in the distribution; verify offline availability — the skill lives inside
      the package (`anvilate/skills/anvilate/SKILL.md`), reached through
      `importlib.resources`, and a built wheel was confirmed to carry it
- [x] 2.2 Ensure no capability, gate, or default changes when loaded — the skill is a text
      file with no import side effects and nothing reads it at runtime; `anvilate.skills`
      exposes only a path and a reader

## 3. CI

- [x] 3.1 Validate every referenced tool/argument against published schemas — every
      backticked `anvilate.*` symbol is imported and resolved; a renamed function fails the
      build naming the stale reference
- [x] 3.2 Execute skill examples under the documentation-examples harness — each example
      runs in a fresh namespace and its stdout is compared byte for byte to the output the
      skill claims
- [x] 3.3 Prohibited-guidance check (no gate bypass, no certified-analysis claims) — seven
      patterns, proved to fire against a deliberately offending text. Two are negatable
      because the skill is required to deny them; the five instruction patterns are not,
      since a blanket negation allowance let a stray "not" excuse the very instructions
      they forbid

## 4. Evaluation

- [ ] 4.1 Measure the agent-driving funnel with and without the skill loaded; publish the
      delta. Three of the four pieces are now in place: the scoring
      (`anvilate.agenteval`, from `extend-benchmarking-agent-evals` 2.1-2.3), the server
      (every tool names its subject and the loop runs end to end), and the corpus —
      `agenteval.default_task_set`, eight tasks over the eight published operations,
      including the three that are refused, because a set that avoided them would report a
      model can drive Anvilate on the strength of a surface it never touched.

      **What is missing is the measurement, and no code here can supply it**: running the
      funnel needs an agent, and this package initiates no sampling and ships no model. The
      corpus and the scoring are what a harness outside it consumes. An unmeasured delta is
      still not published as one.
